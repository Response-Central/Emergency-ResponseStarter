from contextlib import closing
from test_integration import Integration
from database import get_connection
from dispatch import distance

class DispatchIntegration(Integration):
    unit_ids=[]
    @classmethod
    def tearDownClass(cls):
        with closing(get_connection()) as c,c,c.cursor() as q:
            for n in cls.unit_ids:
                q.execute('DELETE FROM IncidentAssignment WHERE unit_id=%s',(n,))
                q.execute('DELETE FROM ResponseUnit WHERE unit_id=%s',(n,))
        super().tearDownClass()
    def create_report(self):
        r=self.client.post('/api/reports',json=dict(caller_name='Dispatch test',caller_phone='555-0100',address='Fictional test site',city='Test',emergency_type='Medical',description='Test only'))
        self.assertEqual(r.status_code,201)
        n=r.json['incident_id'];self.ids.append(n);return n
    def create_unit(self,service='Ambulance',cap=4):
        r=self.client.post('/api/units',json=dict(unit_name='TEST-'+self.username,unit_type=service,dispatcher_name='Test crew',capability=cap,latitude=41.886,longitude=-87.624))
        self.assertEqual(r.status_code,201)
        n=r.json['unit_id'];self.unit_ids.append(n);return n
    def test_dispatch_lifecycle(self):
        self.assertEqual(self.client.get('/api/units').status_code,401)
        self.login()
        incident=self.create_report();other=self.create_report();root=f'/api/incidents/{incident}'
        u=self.create_unit();wrong=self.create_unit('Fire');low=self.create_unit(cap=1)
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,409)
        self.assertEqual(self.client.patch(root+'/triage',json={'severity':'Critical','latitude':91,'longitude':0}).status_code,400)
        for coord in ['nan','inf',True]:
            self.assertEqual(self.client.patch(root+'/triage',json={'severity':'Critical','latitude':coord,'longitude':0}).status_code,400)
        self.assertEqual(self.client.patch(root+'/triage',json={'severity':'Critical','latitude':41.881,'longitude':-87.630}).status_code,200)
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute("UPDATE Location SET geocoded_query=address||', '||city WHERE location_id=(SELECT location_id FROM EmergencyCall JOIN Incident USING(call_id) WHERE incident_id=%s)",(incident,))
        units=self.client.get(root+'/dispatch').json['units'];mine=next(x for x in units if x['unit_id']==u)
        self.assertTrue(mine['eligible']);self.assertGreater(mine['distance_km'],0)
        for unit in [wrong,low]:
            self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':unit}).status_code,409)
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute("UPDATE ResponseUnit SET location_updated_at=NOW()-INTERVAL '16 minutes' WHERE unit_id=%s",(u,))
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,409)
        self.assertEqual(self.client.patch(f'/api/units/{u}',json={'latitude':41.886,'longitude':-87.624,'status':'Offline'}).status_code,200)
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,409)
        self.client.patch(f'/api/units/{u}',json={'latitude':41.886,'longitude':-87.624,'status':'Available'})
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,201)
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,409)
        self.client.patch(f'/api/incidents/{other}/triage',json={'severity':'High','latitude':41.88,'longitude':-87.63})
        self.assertEqual(self.client.post(f'/api/incidents/{other}/assignments',json={'unit_id':u}).status_code,409)
        assignments=self.client.get(root+'/dispatch').json['assignments'];a=assignments[0]['assignment_id']
        self.assertEqual(self.client.post(f'{root}/assignments/{a}/release',json={}).status_code,200)
        self.assertEqual(self.client.post(f'{root}/assignments/{a}/release',json={}).status_code,404)
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,201)
        self.assertEqual(self.client.patch(root,json={'status':'Resolved'}).status_code,200)
        self.assertTrue(all(a['released_at'] for a in self.client.get(root+'/dispatch').json['assignments']))
        self.assertEqual(self.client.post(root+'/assignments',json={'unit_id':u}).status_code,409)
        self.assertAlmostEqual(distance(0,0,0,1),111.19,places=2)
