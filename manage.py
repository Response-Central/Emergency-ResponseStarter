"""Database setup and interactive admin creation. Never puts passwords in source."""
import argparse
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
            samples=[('Ambulance 01', 'Ambulance', 'Medic Alex', 4, 36.1361216, -86.8225064, 'West End Avenue, Cherokee Park, Nashville, Davidson County, Middle Tennessee, Tennessee, 37205, United States'), ('Ambulance 02', 'Ambulance', 'Medic Jordan', 2, 36.147089, -86.77598, '800, Fort Negley Boulevard, Wedgewood-Houston, Nashville, Davidson County, Middle Tennessee, Tennessee, 37203, United States'), ('Fire Engine 01', 'Fire', 'Fire crew Taylor', 4, 36.160254, -86.7768171, '121, 4th Avenue South, Downtown Nashville, East Nashville, Nashville, Davidson County, Middle Tennessee, Tennessee, 37201, United States'), ('Fire Engine 02', 'Fire', 'Fire crew Casey', 3, 36.1581728, -86.7760929, 'Country Music Hall of Fame and Museum, 222, Rep. John Lewis Way South, Downtown Nashville, East Nashville, Nashville, Davidson County, Middle Tennessee, Tennessee, 37203, United States'), ('Police 01', 'Police', 'Patrol Morgan', 4, 36.165328, -86.783331, '600, Dr. Martin L. King, Jr. Boulevard, Downtown Nashville, Nashville, Davidson County, Middle Tennessee, Tennessee, 37209, United States'), ('Police 02', 'Police', 'Patrol Riley', 2, 36.1621868, -86.7778534, '150, 4th Avenue North, Downtown Nashville, East Nashville, Nashville, Davidson County, Middle Tennessee, Tennessee, 37219, United States')]
            for name,service,crew,cap,lat,lon,address in samples:
                cur.execute('SELECT 1 FROM ResponseUnit WHERE unit_name=%s',(name,))
                if not cur.fetchone():
                    cur.execute('INSERT INTO ResponseUnit (unit_name,unit_type,dispatcher_name,capability,latitude,longitude,location_updated_at,location_address) VALUES (%s,%s,%s,%s,%s,%s,NOW(),%s)',(name,service,crew,cap,lat,lon,address))
            cur.execute("SELECT 1 FROM EmergencyCall WHERE caller_name='Campus reception'")
            if not cur.fetchone():
                cur.execute("INSERT INTO Location (address,city,latitude,longitude) VALUES ('600 Charlotte Avenue','Nashville, TN',NULL,NULL) RETURNING location_id")
                loc=cur.fetchone()[0]
                cur.execute("INSERT INTO EmergencyCall (caller_name,caller_phone,emergency_type,description,location_id) VALUES ('Campus reception','555-0100','Medical','Medical assistance requested at the campus entrance.',%s) RETURNING call_id",(loc,))
                cur.execute("INSERT INTO Incident (call_id,severity) VALUES (%s,'High')",(cur.fetchone()[0],))
            print('Response units and one example incident ready. Existing locations are not refreshed automatically.')
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
