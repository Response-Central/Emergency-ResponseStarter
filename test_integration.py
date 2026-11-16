"""Integration tests against the configured PostgreSQL database (creates/cleans test rows)."""
import hashlib
import secrets
import unittest
from contextlib import closing
from werkzeug.security import generate_password_hash
from app import app, attempts
from database import get_connection

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.username='test_'+secrets.token_hex(6)
        cls.password=secrets.token_urlsafe(24)
        cls.ids=[]
        with closing(get_connection()) as c, c, c.cursor() as q:
            q.execute('INSERT INTO AdminUser VALUES (%s,%s)',(cls.username,generate_password_hash(cls.password)))
    @classmethod
    def tearDownClass(cls):
        with closing(get_connection()) as c, c, c.cursor() as q:
            for incident in cls.ids:
                q.execute('DELETE FROM HospitalReservation WHERE incident_id=%s',(incident,))
                q.execute('DELETE FROM Incident WHERE incident_id=%s RETURNING call_id',(incident,))
                call=q.fetchone()[0]
                q.execute('DELETE FROM EmergencyCall WHERE call_id=%s RETURNING location_id',(call,))
                q.execute('DELETE FROM Location WHERE location_id=%s',(q.fetchone()[0],))
            q.execute('DELETE FROM AdminSession WHERE username=%s',(cls.username,))
            q.execute('DELETE FROM AdminUser WHERE username=%s',(cls.username,))
    def setUp(self):
        self.client=app.test_client()
        attempts.clear()
    def login(self):
        return self.client.post('/api/auth/login',json={'username':self.username,'password':self.password})
    def test_report_lifecycle(self):
        self.assertEqual(self.client.get('/api/incidents').status_code,401)
        self.assertEqual(self.client.patch('/api/incidents/1',json={'status':'Resolved'}).status_code,401)
        data=dict(caller_name='Test Reporter',caller_phone='555-0100',address='Test campus',city='Test city',emergency_type='Other',description='Integration test, no real incident.')
        res=self.client.post('/api/reports',json=data)
        self.assertEqual(res.status_code,201)
        n=res.json['incident_id']; self.ids.append(n)
        login=self.login();self.assertEqual(login.status_code,200)
        self.assertIn('HttpOnly',login.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',login.headers['Set-Cookie'])
        self.assertTrue(any(r['incident_id']==n for r in self.client.get('/api/incidents').json))
        for status in ['In Progress','Resolved']:
            self.assertEqual(self.client.patch(f'/api/incidents/{n}',json={'status':status}).status_code,200)
        other=app.test_client();other.set_cookie('cer_session',self.client.get_cookie('cer_session').value)
        row=next(r for r in other.get('/api/incidents').json if r['incident_id']==n)
        self.assertEqual(row['status'],'Resolved')
        self.assertEqual(row['description'],data['description'])
        self.assertEqual(self.client.patch(f'/api/incidents/{n}',json={'status':'bogus'}).status_code,400)
        self.assertEqual(self.client.patch('/api/incidents/2147483647',json={'status':'Resolved'}).status_code,404)
        self.assertEqual(self.client.post('/api/auth/logout',json={}).status_code,200)
        self.assertEqual(other.get('/api/incidents').status_code,401)
    def test_validation_and_csrf(self):
        for data in [None,[],{}, {'caller_name':' '*5}]:
            self.assertEqual(self.client.post('/api/reports',json=data,content_type='application/json').status_code,400)
        self.assertEqual(self.client.post('/api/reports',data='bad').status_code,415)
        self.assertEqual(self.client.post('/api/reports',json={},headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)
        self.assertEqual(self.client.post('/api/auth/login',json={'username':self.username,'password':'wrong'}).status_code,401)
    def test_expired_session(self):
        self.login()
        with closing(get_connection()) as c,c,c.cursor() as q:
            q.execute("UPDATE AdminSession SET expires_at=NOW()-INTERVAL '1 hour' WHERE username=%s",(self.username,))
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
    def test_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.client.post('/api/auth/login',json={'username':'invalid','password':'invalid'}).status_code,401)
        self.assertEqual(self.client.post('/api/auth/login',json={}).status_code,429)

if __name__=='__main__': unittest.main(verbosity=2)
