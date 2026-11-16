import json
from io import BytesIO
from unittest.mock import patch
from contextlib import closing
from test_integration import Integration
from database import get_connection
from geocoding import GeocodeError,search_address

class AddressIntegration(Integration):
    def test_address_lookup_and_assignment_guard(self):
        self.login()
        r=self.client.post('/api/reports',json=dict(caller_name='Address test',caller_phone='555-0100',address='123 Public Square',city='Test City',emergency_type='Other',description='Address integration test'))
        n=r.json['incident_id'];self.ids.append(n);root=f'/api/incidents/{n}'
        p={'place_id':'10','display_name':'123 Public Square, Test City','latitude':41.88,'longitude':-87.63}
        with patch('geocoding.search_address',return_value=[p]):
            self.assertEqual(self.client.post(root+'/locate',json={}).status_code,200)
        row=next(x for x in self.client.get('/api/incidents').json if x['incident_id']==n)
        self.assertEqual(row['latitude'],p['latitude']);self.assertEqual(row['geocoded_query'],'123 Public Square, Test City')
        self.assertEqual(row['resolved_address'],p['display_name'])
        self.assertEqual(self.client.patch(root+'/triage',json={'severity':'Critical'}).status_code,200)
        with patch('dispatch.resolve_address',side_effect=AssertionError('Should use stored match')):
            self.assertEqual(self.client.post(root+'/locate',json={}).status_code,200)
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute('UPDATE Location SET geocoded_query=NULL WHERE location_id=(SELECT location_id FROM Incident JOIN EmergencyCall USING(call_id) WHERE incident_id=%s)',(n,))
        p2={**p,'place_id':'20','display_name':'Other Public Square','latitude':42}
        with patch('geocoding.search_address',return_value=[p,p2]):
            result=self.client.post(root+'/locate',json={});self.assertEqual(result.status_code,409);self.assertEqual(len(result.json['candidates']),2)
            self.assertEqual(self.client.post(root+'/locate',json={'place_id':'bad'}).status_code,422)
            self.assertEqual(self.client.post(root+'/locate',json={'place_id':'20'}).status_code,200)
        with patch('geocoding.search_address',return_value=[p]):
            result=self.client.post('/api/units',json=dict(unit_name='Address test unit',dispatcher_name='Crew',unit_type='Fire',capability=4,location_address='123 Public Square, Test City'))
            self.assertEqual(result.status_code,201);unit=result.json['unit_id']
            try:
                units=self.client.get('/api/units').json
                saved=next(x for x in units if x['unit_id']==unit)
                self.assertEqual(saved['location_address'],p['display_name']);self.assertEqual(saved['latitude'],p['latitude'])
                with patch('geocoding.search_address',return_value=[]):
                    self.assertEqual(self.client.patch(f'/api/units/{unit}',json={'location_address':'Unknown place','status':'Available'}).status_code,422)
                self.assertEqual(self.client.get('/api/units').json,units)
            finally:
                with closing(get_connection()) as c,c,c.cursor() as q:q.execute('DELETE FROM ResponseUnit WHERE unit_id=%s',(unit,))
    def test_cache_and_failure(self):
        query=self.username+' public address'
        payload=[{'place_id':1,'display_name':'Public address','lat':'41','lon':'-87','addresstype':'house'}]
        try:
            with patch('geocoding.urlopen',return_value=BytesIO(json.dumps(payload).encode())) as mocked,patch('geocoding.time.sleep'):
                first=search_address(query);second=search_address(query)
                self.assertEqual(first,second);self.assertEqual(mocked.call_count,1)
            with patch('geocoding.urlopen',side_effect=OSError('offline')),patch('geocoding.time.sleep'):
                with self.assertRaises(GeocodeError):search_address(query+' unknown')
        finally:
            with closing(get_connection()) as c,c,c.cursor() as q:
                q.execute('DELETE FROM GeocodeCache WHERE query=%s',(query.casefold(),))
