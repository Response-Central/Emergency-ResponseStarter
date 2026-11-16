from contextlib import closing
from functools import wraps
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
import time
from werkzeug.security import check_password_hash

import psycopg2
from flask import Flask, jsonify, request, g
from psycopg2.extras import RealDictCursor

from database import get_connection

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
attempts = {}


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def require_admin(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with closing(get_connection()) as conn, conn.cursor() as cur:
            cur.execute("SELECT username FROM AdminSession WHERE token_hash=%s AND expires_at>NOW()", (digest(request.cookies.get('cer_session', '')),))
            row = cur.fetchone()
        if not row:
            return jsonify(error='Please sign in to continue.'), 401
        g.username = row[0]
        return fn(*args, **kwargs)
    return wrapped


@app.before_request
def protect_writes():
    # JSON-only writes prevent cross-site form submissions; no permissive CORS.
    if request.method in ('POST', 'PATCH', 'DELETE') and not request.is_json:
        return jsonify(error='Send application/json.'), 415
    if request.method in ('POST', 'PATCH', 'DELETE') and request.headers.get('Sec-Fetch-Site') == 'cross-site':
        return jsonify(error='Cross-site requests are not allowed.'), 403


@app.post('/api/auth/login')
def login():
    key = request.remote_addr
    now = time.monotonic()
    recent = [t for t in attempts.get(key, []) if now-t < 300]
    attempts[key] = recent
    if len(recent) >= 10:
        return jsonify(error='Too many attempts. Try again in five minutes.'), 429
    recent.append(now)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Send a JSON object.'), 400
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not isinstance(password, str) or len(username)>100 or len(password)>500:
        return jsonify(error='Enter your username and password.'), 400
    with closing(get_connection()) as conn, conn:
        with conn.cursor() as cur:
            cur.execute('SELECT password_hash FROM AdminUser WHERE username=%s', (username,))
            row = cur.fetchone()
            if not row or not check_password_hash(row[0], password):
                return jsonify(error='Incorrect username or password.'), 401
            token = secrets.token_urlsafe(32)
            cur.execute('DELETE FROM AdminSession WHERE expires_at<NOW()')
            cur.execute('INSERT INTO AdminSession VALUES (%s,%s,%s)', (digest(token), username, datetime.now(timezone.utc)+timedelta(hours=8)))
    attempts.pop(key, None)
    response = jsonify(username=username)
    response.set_cookie('cer_session', token, httponly=True, samesite='Strict', secure=os.getenv('COOKIE_SECURE', 'false').lower()=='true', max_age=28800)
    return response


@app.get('/api/auth/me')
@require_admin
def me():
    return jsonify(username=g.username)


@app.post('/api/auth/logout')
def logout():
    with closing(get_connection()) as conn, conn, conn.cursor() as cur:
        cur.execute('DELETE FROM AdminSession WHERE token_hash=%s', (digest(request.cookies.get('cer_session', '')),))
    response = jsonify(message='Signed out.')
    response.delete_cookie('cer_session')
    return response


@app.patch('/api/incidents/<int:incident_id>')
@require_admin
def update_incident(incident_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get('status') not in ('Reported', 'In Progress', 'Resolved'):
        return jsonify(error='Choose Reported, In Progress, or Resolved.'), 400
    released_units = 0
    with closing(get_connection()) as conn, conn, conn.cursor() as cur:
        cur.execute('SELECT 1 FROM Incident WHERE incident_id=%s FOR UPDATE', (incident_id,))
        if not cur.fetchone():
            return jsonify(error='Incident not found.'), 404
        if data['status'] == 'Resolved':
            cur.execute('UPDATE IncidentAssignment SET released_at=NOW() WHERE incident_id=%s AND released_at IS NULL', (incident_id,))
            released_units = cur.rowcount
            cur.execute('UPDATE HospitalReservation SET released_at=NOW() WHERE incident_id=%s AND released_at IS NULL', (incident_id,))
        cur.execute('UPDATE Incident SET status=%s, updated_at=NOW() WHERE incident_id=%s RETURNING incident_id', (data['status'], incident_id))
        if not cur.fetchone():
            return jsonify(error='Incident not found.'), 404
    return jsonify(message='Status updated.', released_units=released_units)



@app.get("/api/health")
def health():
    return jsonify(message="Python API is running")


@app.get("/api/incidents")
@require_admin
def incidents():
    with closing(get_connection()) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT i.incident_id, e.emergency_type, l.address, l.city, e.caller_name, e.caller_phone, e.description, i.status, i.created_at, i.updated_at, i.severity, l.latitude, l.longitude, l.geocoded_query, l.resolved_address
                FROM Incident i
                JOIN EmergencyCall e ON e.call_id = i.call_id
                JOIN Location l ON l.location_id = e.location_id
                ORDER BY i.incident_id DESC
            """)
            return jsonify(cursor.fetchall())


@app.post("/api/reports")
def report():
    data = request.get_json(silent=True)
    fields = {"caller_name": 100, "caller_phone": 30, "address": 255,
              "city": 100, "emergency_type": 30, "description": 2000}
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object."), 400
    for field, limit in fields.items():
        value = data.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            return jsonify(error=f"Complete {field.replace('_', ' ')} (maximum {limit} characters)."), 400
    if data["emergency_type"] not in ("Medical", "Fire", "Police", "Other"):
        return jsonify(error="Choose a valid emergency type."), 400

    # One transaction saves the location, call, and incident together.
    with closing(get_connection()) as connection:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO Location (address, city) VALUES (%s, %s) RETURNING location_id",
                    (data["address"].strip(), data["city"].strip()),
                )
                location_id = cursor.fetchone()[0]
                cursor.execute("""
                    INSERT INTO EmergencyCall
                    (caller_name, caller_phone, emergency_type, description, location_id)
                    VALUES (%s, %s, %s, %s, %s) RETURNING call_id
                """, (data["caller_name"].strip(), data["caller_phone"].strip(),
                       data["emergency_type"], data["description"].strip(), location_id))
                call_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO Incident (call_id) VALUES (%s) RETURNING incident_id", (call_id,)
                )
                incident_id = cursor.fetchone()[0]
    return jsonify(message="Report saved to the project database.", incident_id=incident_id), 201


@app.errorhandler(psycopg2.Error)
def database_error(error):
    app.logger.error("Database request failed: %s", type(error).__name__)
    return jsonify(error="Database is not ready. Follow the database steps in README.md."), 503


from dispatch import register_dispatch
register_dispatch(app, require_admin)
from hospitals import register_hospitals
register_hospitals(app, require_admin)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
