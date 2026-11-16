"""Database setup and interactive admin creation. Never puts passwords in source."""
import argparse
import json
from contextlib import closing
from getpass import getpass
from pathlib import Path
from werkzeug.security import generate_password_hash
from database import get_connection

parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['init-db', 'create-admin', 'seed-dispatch-demo', 'seed-units'])
args = parser.parse_args()
with closing(get_connection()) as conn, conn:
    with conn.cursor() as cur:
        if args.command == 'init-db':
            cur.execute("SELECT to_regclass('public.incident')")
            if cur.fetchone()[0] is None:
                cur.execute(Path('database/schema.sql').read_text())
            cur.execute(Path('database/migration.sql').read_text())
            print('Database ready; existing reports preserved.')
        elif args.command in ('seed-dispatch-demo','seed-units'):
            units=json.loads(Path(__file__).with_name('database').joinpath('response_units.json').read_text(encoding='utf-8'))
            created=0
            for unit in units:
                cur.execute('SELECT 1 FROM ResponseUnit WHERE unit_name=%s',(unit['unit_name'],))
                if not cur.fetchone():
                    cur.execute('INSERT INTO ResponseUnit (unit_name,unit_type,dispatcher_name,capability,latitude,longitude,location_updated_at,location_address) VALUES (%s,%s,%s,%s,%s,%s,NOW(),%s)',tuple(unit[key] for key in ('unit_name','unit_type','dispatcher_name','capability','latitude','longitude','location_address')))
                    created+=1
            cur.execute("SELECT 1 FROM EmergencyCall WHERE caller_name='Campus reception'")
            if not cur.fetchone():
                cur.execute("INSERT INTO Location (address,city,latitude,longitude) VALUES ('600 Charlotte Avenue','Nashville, TN',NULL,NULL) RETURNING location_id")
                loc=cur.fetchone()[0]
                cur.execute("INSERT INTO EmergencyCall (caller_name,caller_phone,emergency_type,description,location_id) VALUES ('Campus reception','555-0100','Medical','Medical assistance requested at the campus entrance.',%s) RETURNING call_id",(loc,))
                cur.execute("INSERT INTO Incident (call_id,severity) VALUES (%s,'High')",(cur.fetchone()[0],))
            print(f'{created} units added; {len(units)} Nashville units configured. Existing assignments and locations preserved.')
        else:
            username = input('Admin username: ').strip()
            password = getpass('Password (at least 10 characters): ')
            if not username or len(username) > 100 or len(password) < 10:
                raise SystemExit('Use a username of 1–100 characters and password of 10+ characters.')
            if password != getpass('Confirm password: '):
                raise SystemExit('Passwords do not match.')
            cur.execute('INSERT INTO AdminUser VALUES (%s,%s) ON CONFLICT (username) DO UPDATE SET password_hash=EXCLUDED.password_hash', (username, generate_password_hash(password)))
            cur.execute('DELETE FROM AdminSession WHERE username=%s', (username,))
            print('Admin saved. Existing sessions revoked.')
