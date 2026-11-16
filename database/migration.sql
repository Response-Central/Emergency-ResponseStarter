-- Safe to rerun on the original starter database.
ALTER TABLE Incident ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE Incident ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE TABLE IF NOT EXISTS AdminUser (
 username VARCHAR(100) PRIMARY KEY,
 password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS AdminSession (
 token_hash TEXT PRIMARY KEY,
 username VARCHAR(100) NOT NULL REFERENCES AdminUser(username),
 expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS incident_status_idx ON Incident(status);
ALTER TABLE Location ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION CHECK (latitude BETWEEN -90 AND 90);
ALTER TABLE Location ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180);
ALTER TABLE Incident ADD COLUMN IF NOT EXISTS severity VARCHAR(20) NOT NULL DEFAULT 'Moderate' CHECK (severity IN ('Low','Moderate','High','Critical'));
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION CHECK (latitude BETWEEN -90 AND 90);
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180);
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS location_updated_at TIMESTAMPTZ;
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS dispatcher_name VARCHAR(100);
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS capability INTEGER NOT NULL DEFAULT 4 CHECK (capability BETWEEN 1 AND 4);
CREATE TABLE IF NOT EXISTS IncidentAssignment (
 assignment_id SERIAL PRIMARY KEY,
 incident_id INTEGER NOT NULL REFERENCES Incident(incident_id),
 unit_id INTEGER NOT NULL REFERENCES ResponseUnit(unit_id),
 assigned_by VARCHAR(100) NOT NULL,
 assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 released_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_assignment_per_unit ON IncidentAssignment(unit_id) WHERE released_at IS NULL;
CREATE INDEX IF NOT EXISTS assignment_incident_idx ON IncidentAssignment(incident_id);
ALTER TABLE Location ADD COLUMN IF NOT EXISTS geocoded_query TEXT;
ALTER TABLE Location ADD COLUMN IF NOT EXISTS resolved_address TEXT;
ALTER TABLE ResponseUnit ADD COLUMN IF NOT EXISTS location_address TEXT;
CREATE TABLE IF NOT EXISTS GeocodeCache (
 query TEXT PRIMARY KEY,
 results JSONB NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- Rename only bundled example records; reported user records are retained.
UPDATE ResponseUnit SET unit_name=REPLACE(unit_name,'DEMO ',''),dispatcher_name=REPLACE(dispatcher_name,'Demo ','')
WHERE unit_name IN ('DEMO Ambulance 01','DEMO Ambulance 02','DEMO Fire Engine 01','DEMO Fire Engine 02','DEMO Police 01','DEMO Police 02');
UPDATE Location SET address='600 Charlotte Avenue',city='Nashville, TN',latitude=NULL,longitude=NULL,geocoded_query=NULL,resolved_address=NULL
WHERE location_id IN (SELECT location_id FROM EmergencyCall WHERE caller_name IN ('DEMO Dispatch Scenario','Demo Reporter'));
UPDATE EmergencyCall SET caller_name='Campus reception',description='Medical assistance requested at the campus entrance.' WHERE caller_name='DEMO Dispatch Scenario';
UPDATE EmergencyCall SET caller_name='Community reporter',description='Broken outdoor light near the north entrance.' WHERE caller_name='Demo Reporter';

-- Keep historical resolved incidents from occupying a response unit.
UPDATE IncidentAssignment a SET released_at=NOW() FROM Incident i
WHERE i.incident_id=a.incident_id AND i.status='Resolved' AND a.released_at IS NULL;
