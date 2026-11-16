from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from test_integration import Integration
from app import app
from database import get_connection
import hospitals

class HospitalIntegration(Integration):
    @classmethod
    def setUpClass(cls):
        super().setUpClass();cls.hospital_ids=[];cls.unit_ids=[]
    @classmethod
    def tearDownClass(cls):
        with closing(get_connection()) as c,c,c.cursor() as q:
            for n in cls.hospital_ids:
                q.execute('DELETE FROM HospitalReservation WHERE hospital_id=%s',(n,))
                q.execute('DELETE FROM Hospital WHERE hospital_id=%s',(n,))
            for n in cls.unit_ids:
                q.execute('DELETE FROM IncidentAssignment WHERE unit_id=%s',(n,))
                q.execute('DELETE FROM ResponseUnit WHERE unit_id=%s',(n,))
        super().tearDownClass()
    def prepare_hospitals(self,second_full=False):
        ids=[]
        with closing(get_connection()) as c,c,c.cursor() as q:
            for lat,occupied in [(36.16,0),(36.17,int(second_full))]:
                q.execute('INSERT INTO Hospital(hospital_name,area,latitude,longitude,total_beds,occupied_beds) VALUES (%s,%s,%s,%s,1,%s) RETURNING hospital_id',(self.username+str(len(self.hospital_ids)),'Test area',lat,-86.78,occupied))
                n=q.fetchone()[0];ids.append(n);self.hospital_ids.append(n)
        original=hospitals.hospital_rows
        return ids,patch('hospitals.hospital_rows',side_effect=lambda cursor:[h for h in original(cursor) if h['hospital_id'] in ids])
    def report_and_unit(self,service='Ambulance'):
        r=self.client.post('/api/reports',json=dict(caller_name='Hospital test',caller_phone='555-0100',address='Test location',city='Test city',emergency_type='Medical' if service=='Ambulance' else 'Police',description='Hospital integration test'))
        n=r.json['incident_id'];self.ids.append(n)
        self.client.patch(f'/api/incidents/{n}/triage',json={'severity':'High','latitude':36.16,'longitude':-86.78})
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute("UPDATE Location SET geocoded_query=address||', '||city WHERE location_id=(SELECT location_id FROM Incident JOIN EmergencyCall USING(call_id) WHERE incident_id=%s)",(n,))
        r=self.client.post('/api/units',json=dict(unit_name='Hospital test unit',unit_type=service,dispatcher_name='Test crew',capability=4,latitude=36.16,longitude=-86.78))
        u=r.json['unit_id'];self.unit_ids.append(u)
        return n,u
    def test_closest_full_fallback_and_release(self):
        self.login();ids,mock=self.prepare_hospitals()
        with mock:
            n,u=self.report_and_unit();other,u2=self.report_and_unit();third,u3=self.report_and_unit()
            r=self.client.post(f'/api/incidents/{n}/assignments',json={'unit_id':u})
            self.assertEqual(r.status_code,201);self.assertEqual(r.json['hospital']['hospital_id'],ids[0])
            # A second ambulance on this incident shares its existing one-bed reservation.
            extra=self.client.post('/api/units',json=dict(unit_name='Second ambulance',unit_type='Ambulance',dispatcher_name='Test crew',capability=4,latitude=36.16,longitude=-86.78)).json['unit_id'];self.unit_ids.append(extra)
            self.assertEqual(self.client.post(f'/api/incidents/{n}/assignments',json={'unit_id':extra}).status_code,201)
            self.assertEqual(self.client.get('/api/capacity').json['reserved_beds'],1)
            r=self.client.post(f'/api/incidents/{other}/assignments',json={'unit_id':u2})
            self.assertEqual(r.status_code,201);self.assertEqual(r.json['hospital']['hospital_id'],ids[1])
            self.assertEqual(self.client.get('/api/capacity').json['available_beds'],0)
            self.assertEqual(self.client.post(f'/api/incidents/{third}/assignments',json={'unit_id':u3}).status_code,409)
            self.assertIsNone(next(u for u in self.client.get('/api/units').json if u['unit_id']==u3)['incident_id'])
            self.assertEqual(self.client.patch(f'/api/hospitals/{ids[0]}',json={'total_beds':1,'occupied_beds':1}).status_code,409)
            self.assertEqual(self.client.patch(f'/api/hospitals/{ids[0]}',json={'total_beds':0,'occupied_beds':0}).status_code,400)
            self.assertEqual(self.client.patch(f'/api/incidents/{n}',json={'status':'Resolved'}).json['released_units'],2)
            self.assertEqual(self.client.get('/api/capacity').json['available_beds'],1)
            self.assertEqual(self.client.post(f'/api/incidents/{third}/assignments',json={'unit_id':u3}).json['hospital']['hospital_id'],ids[0])
    def test_concurrent_assignments_cannot_take_last_bed_twice(self):
        self.login();ids,mock=self.prepare_hospitals(second_full=True)
        cases=[self.report_and_unit(),self.report_and_unit()];barrier=Barrier(2)
        def assign(case):
            client=app.test_client();self.assertEqual(client.post('/api/auth/login',json={'username':self.username,'password':self.password}).status_code,200)
            barrier.wait(timeout=10)
            return client.post(f'/api/incidents/{case[0]}/assignments',json={'unit_id':case[1]}).status_code
        with mock,ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(assign,case) for case in cases]
            statuses=[f.result(timeout=20) for f in futures]
            self.assertEqual(sorted(statuses),[201,409])
            capacity=self.client.get('/api/capacity').json
            self.assertEqual(capacity['available_beds'],0);self.assertEqual(capacity['reserved_beds'],1)
    def test_non_ambulance_does_not_reserve_bed(self):
        self.assertEqual(self.client.get('/api/capacity').status_code,401)
        self.login();n,u=self.report_and_unit(service='Police')
        with patch('dispatch.reserve_nearest_hospital',side_effect=AssertionError('Police must not reserve a receiving bed')):
            self.assertEqual(self.client.post(f'/api/incidents/{n}/assignments',json={'unit_id':u}).status_code,201)
        with closing(get_connection()) as c,c.cursor() as q:
            q.execute('SELECT COUNT(*) FROM HospitalReservation WHERE incident_id=%s',(n,));self.assertEqual(q.fetchone()[0],0)
