"""Fictional responder coordination; distances are geodesic, not road routes."""
from contextlib import closing
from datetime import datetime, timezone
from math import radians, sin, cos, atan2, sqrt, isfinite
from flask import jsonify, request, g
from psycopg2.extras import RealDictCursor
from database import get_connection
from geocoding import search_address, resolve_address, GeocodeError, AddressChoice

SEVERITIES = {'Low':1, 'Moderate':2, 'High':3, 'Critical':4}
SERVICES = ('Ambulance','Fire','Police')
SERVICE_FOR = {'Medical':'Ambulance','Fire':'Fire','Police':'Police'}


def coordinates(data, required=True):
    a,b=data.get('latitude'),data.get('longitude')
    if not required and a in (None,'') and b in (None,''):
        return None,None
    try:
        if isinstance(a,bool) or isinstance(b,bool): raise ValueError()
        a,b=float(a),float(b)
        if not isfinite(a) or not isfinite(b) or not -90<=a<=90 or not -180<=b<=180: raise ValueError()
    except (ValueError,TypeError):
        raise ValueError('Enter both latitude (-90 to 90) and longitude (-180 to 180).')
    return a,b


def distance(a,b,c,d):
    a,b,c,d=map(radians,(a,b,c,d))
    h=sin((c-a)/2)**2+cos(a)*cos(c)*sin((d-b)/2)**2
    return round(6371*2*atan2(sqrt(min(1,h)),sqrt(max(0,1-h))),2)


def fresh(unit):
    return unit['location_updated_at'] is not None and (datetime.now(timezone.utc)-unit['location_updated_at']).total_seconds() <= 900


def register_dispatch(app, require_admin):
    @app.errorhandler(AddressChoice)
    def address_choice(error):
        return jsonify(error=str(error),candidates=error.candidates),409

    @app.errorhandler(GeocodeError)
    def geocoding_error(error):
        return jsonify(error=str(error)),422

    @app.post('/api/incidents/<int:incident_id>/locate')
    @require_admin
    def locate_incident(incident_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Send a JSON object.'),400
        with closing(get_connection()) as c,c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('SELECT l.* FROM Incident i JOIN EmergencyCall e USING(call_id) JOIN Location l USING(location_id) WHERE incident_id=%s',(incident_id,))
            loc=q.fetchone()
        if not loc:return jsonify(error='Incident not found.'),404
        query=f"{loc['address']}, {loc['city']}"
        if loc['geocoded_query']==query and loc['latitude'] is not None and loc['longitude'] is not None and not data.get('place_id'):
            return jsonify(resolved=True,address=loc['resolved_address'])
        place=resolve_address(query,data.get('place_id'))
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('UPDATE Location SET latitude=%s,longitude=%s,geocoded_query=%s,resolved_address=%s WHERE location_id=%s AND address=%s AND city=%s RETURNING location_id',
                (place['latitude'],place['longitude'],query,place['display_name'],loc['location_id'],loc['address'],loc['city']))
            if not q.fetchone():return jsonify(error='Reported address changed. Refresh and retry.'),409
            q.execute('UPDATE Incident SET updated_at=NOW() WHERE incident_id=%s',(incident_id,))
        return jsonify(resolved=True,address=place['display_name'])

    @app.get('/api/units')
    @require_admin
    def units():
        with closing(get_connection()) as c,c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('''SELECT u.*, a.incident_id FROM ResponseUnit u LEFT JOIN IncidentAssignment a
                         ON a.unit_id=u.unit_id AND a.released_at IS NULL ORDER BY u.unit_name''')
            rows=q.fetchall()
        for u in rows: u['location_fresh']=fresh(u)
        return jsonify(rows)

    @app.post('/api/units')
    @require_admin
    def create_unit():
        data=request.get_json(silent=True)
        if not isinstance(data,dict): return jsonify(error='Send a JSON object.'),400
        name,crew=data.get('unit_name'),data.get('dispatcher_name')
        if not isinstance(name,str) or not 1<=len(name.strip())<=100 or not isinstance(crew,str) or not 1<=len(crew.strip())<=100:
            return jsonify(error='Enter a unit name and crew/dispatcher name (maximum 100 characters).'),400
        if data.get('unit_type') not in SERVICES or type(data.get('capability')) is not int or data['capability'] not in range(1,5):
            return jsonify(error='Choose a service and capability level.'),400
        location_address=None
        if 'location_address' in data:
            place=resolve_address(data['location_address'],data.get('place_id'))
            lat,lon=place['latitude'],place['longitude']
            location_address=place['display_name']
        else:
            try: lat,lon=coordinates(data)
            except ValueError as e: return jsonify(error=str(e)),400
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('''INSERT INTO ResponseUnit (unit_name,unit_type,dispatcher_name,capability,latitude,longitude,location_updated_at,location_address)
                         VALUES (%s,%s,%s,%s,%s,%s,NOW(),%s) RETURNING unit_id''',(name.strip(),data['unit_type'],crew.strip(),data['capability'],lat,lon,location_address))
            n=q.fetchone()[0]
        return jsonify(unit_id=n),201

    @app.patch('/api/units/<int:unit_id>')
    @require_admin
    def update_unit(unit_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or data.get('status') not in ('Available','Offline'):
            return jsonify(error='Choose Available or Offline.'),400
        location_address=None
        if 'location_address' in data:
            place=resolve_address(data['location_address'],data.get('place_id'))
            lat,lon=place['latitude'],place['longitude']
            location_address=place['display_name']
        else:
            try: lat,lon=coordinates(data)
            except ValueError as e: return jsonify(error=str(e)),400
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('''UPDATE ResponseUnit SET latitude=%s,longitude=%s,location_updated_at=NOW(),status=%s,location_address=%s
                         WHERE unit_id=%s RETURNING unit_id''',(lat,lon,data['status'],location_address,unit_id))
            if not q.fetchone(): return jsonify(error='Unit not found.'),404
        return jsonify(message='Unit location and availability updated.')

    @app.patch('/api/incidents/<int:incident_id>/triage')
    @require_admin
    def triage(incident_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or data.get('severity') not in SEVERITIES:
            return jsonify(error='Choose Low, Moderate, High, or Critical severity.'),400
        try: lat,lon=coordinates(data,required=False)
        except ValueError as e: return jsonify(error=str(e)),400
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('SELECT call_id FROM Incident WHERE incident_id=%s FOR UPDATE',(incident_id,))
            row=q.fetchone()
            if not row: return jsonify(error='Incident not found.'),404
            q.execute('UPDATE Incident SET severity=%s,updated_at=NOW() WHERE incident_id=%s',(data['severity'],incident_id))
            if lat is not None:
                q.execute('UPDATE Location SET latitude=%s,longitude=%s,geocoded_query=NULL,resolved_address=NULL WHERE location_id=(SELECT location_id FROM EmergencyCall WHERE call_id=%s)',(lat,lon,row[0]))
        return jsonify(message='Incident severity saved.')

    @app.get('/api/incidents/<int:incident_id>/dispatch')
    @require_admin
    def recommendations(incident_id):
        with closing(get_connection()) as c,c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('''SELECT i.*, e.emergency_type,l.latitude,l.longitude,l.address,l.city,l.geocoded_query FROM Incident i
                         JOIN EmergencyCall e USING(call_id) JOIN Location l USING(location_id) WHERE incident_id=%s''',(incident_id,))
            incident=q.fetchone()
            if not incident: return jsonify(error='Incident not found.'),404
            q.execute('''SELECT u.*,a.incident_id FROM ResponseUnit u LEFT JOIN IncidentAssignment a
                         ON a.unit_id=u.unit_id AND a.released_at IS NULL''')
            units=q.fetchall()
            q.execute('''SELECT a.*,u.unit_name,u.unit_type,u.dispatcher_name FROM IncidentAssignment a
                         JOIN ResponseUnit u USING(unit_id) WHERE a.incident_id=%s ORDER BY a.assigned_at DESC''',(incident_id,))
            assignments=q.fetchall()
        address_matched=incident['geocoded_query']==f"{incident['address']}, {incident['city']}"
        service=SERVICE_FOR.get(incident['emergency_type'])
        for u in units:
            u['distance_km']=distance(incident['latitude'],incident['longitude'],u['latitude'],u['longitude']) if address_matched and all(x is not None for x in [incident['latitude'],incident['longitude'],u['latitude'],u['longitude']]) else None
            reasons=[]
            if incident['status']=='Resolved': reasons.append('Incident resolved')
            if service and u['unit_type']!=service: reasons.append('Different service')
            if u['unit_type'] not in SERVICES: reasons.append('Unsupported service')
            if u['status']!='Available': reasons.append('Offline')
            if u['incident_id'] is not None: reasons.append('Already assigned')
            if u['capability']<SEVERITIES[incident['severity']]: reasons.append('Capability below severity')
            if not fresh(u): reasons.append('Location older than 15 minutes or missing')
            if u['distance_km'] is None: reasons.append('Reported address must be located')
            u['eligible']=not reasons
            u['reason']=' · '.join(reasons)
        units.sort(key=lambda u:(not u['eligible'],u['distance_km'] is None,u['distance_km'] or 0,u['unit_name']))
        return jsonify(units=units,assignments=assignments,recommended_service=service)

    @app.post('/api/incidents/<int:incident_id>/assignments')
    @require_admin
    def assign(incident_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('unit_id')) is not int:
            return jsonify(error='Choose a unit.'),400
        with closing(get_connection()) as c,c,c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('''SELECT i.*,e.emergency_type,l.latitude,l.longitude,l.address,l.city,l.geocoded_query FROM Incident i JOIN EmergencyCall e USING(call_id)
                         JOIN Location l USING(location_id) WHERE incident_id=%s FOR UPDATE OF i''',(incident_id,))
            inc=q.fetchone()
            if not inc: return jsonify(error='Incident not found.'),404
            if inc['status']=='Resolved': return jsonify(error='Reopen the incident before assigning.'),409
            q.execute('SELECT * FROM ResponseUnit WHERE unit_id=%s FOR UPDATE',(data['unit_id'],))
            u=q.fetchone()
            if not u: return jsonify(error='Unit not found.'),404
            q.execute('SELECT 1 FROM IncidentAssignment WHERE unit_id=%s AND released_at IS NULL',(u['unit_id'],))
            if q.fetchone() or u['status']!='Available': return jsonify(error='Unit is no longer available. Refresh and choose another.'),409
            if u['unit_type'] not in SERVICES or (SERVICE_FOR.get(inc['emergency_type']) and SERVICE_FOR[inc['emergency_type']]!=u['unit_type']) or u['capability']<SEVERITIES[inc['severity']]:
                return jsonify(error='Unit service or capability does not match this incident.'),409
            if inc['geocoded_query']!=f"{inc['address']}, {inc['city']}":
                return jsonify(error='Locate the reported address before assigning a unit.'),409
            if not fresh(u) or any(v is None for v in [inc['latitude'],inc['longitude'],u['latitude'],u['longitude']]):
                return jsonify(error='Locate the reported address and update the unit location within 15 minutes.'),409
            q.execute('INSERT INTO IncidentAssignment (incident_id,unit_id,assigned_by) VALUES (%s,%s,%s)',(incident_id,u['unit_id'],g.username))
            q.execute("UPDATE Incident SET status='In Progress',updated_at=NOW() WHERE incident_id=%s",(incident_id,))
        return jsonify(message='Unit assigned.'),201

    @app.post('/api/incidents/<int:incident_id>/assignments/<int:assignment_id>/release')
    @require_admin
    def release(incident_id,assignment_id):
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('SELECT 1 FROM Incident WHERE incident_id=%s FOR UPDATE',(incident_id,))
            q.execute('''UPDATE IncidentAssignment SET released_at=NOW() WHERE incident_id=%s AND assignment_id=%s
                         AND released_at IS NULL RETURNING unit_id''',(incident_id,assignment_id))
            if not q.fetchone(): return jsonify(error='Active assignment not found.'),404
            q.execute('UPDATE Incident SET updated_at=NOW() WHERE incident_id=%s',(incident_id,))
        return jsonify(message='Unit released; assignment history retained.')
