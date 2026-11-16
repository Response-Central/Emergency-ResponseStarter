"""Configured receiving-bed capacity and transactional ambulance destinations."""
import json
from pathlib import Path
from contextlib import closing
from flask import jsonify, request
from psycopg2.extras import RealDictCursor
from database import get_connection

class NoHospitalCapacity(Exception): pass


def seed_hospitals(cursor):
    rows=json.loads(Path(__file__).with_name('database').joinpath('hospitals.json').read_text(encoding='utf-8-sig'))
    for h in rows:
        cursor.execute('''INSERT INTO Hospital(hospital_name,area,latitude,longitude,total_beds,occupied_beds)
                         VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(hospital_name) DO NOTHING''',
                       tuple(h[k] for k in ('hospital_name','area','latitude','longitude','total_beds','occupied_beds')))


def hospital_rows(cursor):
    cursor.execute('''SELECT h.*,COUNT(r.reservation_id)::int AS reserved_beds,
                     h.total_beds-h.occupied_beds-COUNT(r.reservation_id)::int AS available_beds
                     FROM Hospital h LEFT JOIN HospitalReservation r ON r.hospital_id=h.hospital_id AND r.released_at IS NULL
                     GROUP BY h.hospital_id ORDER BY h.hospital_name''')
    return cursor.fetchall()


def reserve_nearest_hospital(cursor,incident,username,distance):
    # Every reservation/capacity mutation takes the same hospital locks in ID order.
    # Counts are read after acquiring the locks, so concurrent assignments cannot overfill.
    cursor.execute('SELECT hospital_id FROM Hospital ORDER BY hospital_id FOR UPDATE')
    cursor.fetchall()
    cursor.execute('''SELECT h.*,r.reservation_id FROM HospitalReservation r JOIN Hospital h USING(hospital_id)
                      WHERE r.incident_id=%s AND r.released_at IS NULL''',(incident['incident_id'],))
    existing=cursor.fetchone()
    if existing:
        existing['distance_km']=distance(incident['latitude'],incident['longitude'],existing['latitude'],existing['longitude'])
        return existing
    hospitals=hospital_rows(cursor)
    candidates=[h for h in hospitals if h['available_beds']>0]
    if not candidates:raise NoHospitalCapacity('No receiving beds are available. Free a bed or update hospital capacity, then assign the ambulance again.')
    for h in candidates:h['distance_km']=distance(incident['latitude'],incident['longitude'],h['latitude'],h['longitude'])
    chosen=min(candidates,key=lambda h:(h['distance_km'],h['hospital_id']))
    cursor.execute('''INSERT INTO HospitalReservation(hospital_id,incident_id,reserved_by) VALUES (%s,%s,%s) RETURNING reservation_id''',
                   (chosen['hospital_id'],incident['incident_id'],username))
    chosen['reservation_id']=cursor.fetchone()['reservation_id']
    return chosen


def register_hospitals(app,require_admin):
    @app.errorhandler(NoHospitalCapacity)
    def no_capacity(error):return jsonify(error=str(error)),409

    @app.get('/api/capacity')
    @require_admin
    def capacity():
        with closing(get_connection()) as c,c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('''SELECT u.unit_type,COUNT(*)::int AS total,
                        COUNT(*) FILTER(WHERE a.assignment_id IS NULL AND u.status='Available')::int AS available,
                        COUNT(*) FILTER(WHERE a.assignment_id IS NOT NULL)::int AS assigned,
                        COUNT(*) FILTER(WHERE a.assignment_id IS NULL AND u.status!='Available')::int AS offline
                        FROM ResponseUnit u LEFT JOIN IncidentAssignment a ON a.unit_id=u.unit_id AND a.released_at IS NULL
                        GROUP BY u.unit_type ORDER BY u.unit_type''')
            services=q.fetchall()
            hospitals=hospital_rows(q)
        return jsonify(services=services,hospitals=hospitals,available_units=sum(s['available'] for s in services),
                       total_units=sum(s['total'] for s in services),available_beds=sum(h['available_beds'] for h in hospitals),
                       total_beds=sum(h['total_beds'] for h in hospitals),reserved_beds=sum(h['reserved_beds'] for h in hospitals))

    @app.patch('/api/hospitals/<int:hospital_id>')
    @require_admin
    def update_beds(hospital_id):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('total_beds')) is not int or type(data.get('occupied_beds')) is not int:
            return jsonify(error='Enter whole numbers for total and occupied beds.'),400
        total,occupied=data['total_beds'],data['occupied_beds']
        if not 1<=total<=5000 or not 0<=occupied<=total:return jsonify(error='Total beds must be 1–5000; occupied beds must be between zero and total.'),400
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('SELECT 1 FROM Hospital WHERE hospital_id=%s FOR UPDATE',(hospital_id,))
            if not q.fetchone():return jsonify(error='Hospital not found.'),404
            q.execute('SELECT COUNT(*) FROM HospitalReservation WHERE hospital_id=%s AND released_at IS NULL',(hospital_id,))
            reserved=q.fetchone()[0]
            if occupied+reserved>total:return jsonify(error=f'Keep room for {reserved} active bed reservation(s).'),409
            q.execute('UPDATE Hospital SET total_beds=%s,occupied_beds=%s WHERE hospital_id=%s',(total,occupied,hospital_id))
        return jsonify(message='Hospital capacity updated.')
