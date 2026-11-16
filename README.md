# ResponseCentral

A polished centralized emergency response **class project**, built on rohanbasnet8/Emergency-ResponseStarter. React 19 + Vite 8 frontend, Flask API, and PostgreSQL. This does not contact or dispatch real emergency services.

## Requirements

- Node.js 22.12+ (Node 24 LTS recommended), including npm; or pnpm
- Python 3.11+ and pip
- PostgreSQL 17 (other recent PostgreSQL versions should also work)

No Docker or cloud services are required. Run all commands from the extracted project folder.

## 1. Install

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

macOS/Linux: use `python3 -m venv .venv`, then `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`, and `cp .env.example .env`.

Edit `.env` with your own PostgreSQL host, port, database, username, and password. Never commit `.env`. No admin password is bundled in the source or frontend.

## 2. Initialize PostgreSQL

Start your local PostgreSQL service. In pgAdmin, create an empty database named `emergency_response_starter`; or run (if PostgreSQL bin is on PATH):

```powershell
createdb -h 127.0.0.1 -U postgres emergency_response_starter
.\.venv\Scripts\python.exe manage.py init-db
.\.venv\Scripts\python.exe manage.py create-admin
```

The admin command prompts for a username and a password (10+ characters, entered twice without echo). Passwords are stored as Werkzeug scrypt hashes. Running it again for the same username resets that password and revokes existing sessions.

`init-db` creates the original tables for an empty database, then applies the rerunnable migration. For an existing starter database, point `.env` to it and run the same command; it retains Location, EmergencyCall, Incident, and ResponseUnit and adds timestamps and auth tables. Back up important databases before migrating. Existing incidents receive the migration time as their initial timestamp because the starter did not record one. Existing unusual status values are retained; the dashboard allows changing them to the supported statuses.

Optional sample records: run `database/sample_data.sql` in pgAdmin once, after initialization. It assumes the original example IDs in a fresh database; do not run it on an existing populated database. The app works with an empty register.

## 3. Run

Terminal 1:

```powershell
.\.venv\Scripts\python.exe app.py
```

Terminal 2:

```powershell
npm run dev
```

Open http://127.0.0.1:5173 (use this hostname consistently for cookies). API runs on http://127.0.0.1:5001. Vite proxies `/api` to Flask; no CORS configuration is necessary. Keep both terminals open; Ctrl+C stops them. The included `start-backend.cmd` and `start.cmd` run these commands after setup.

If using pnpm instead, run `pnpm install --frozen-lockfile`, `pnpm dev`, and `pnpm build`. A pnpm lockfile from the source project is retained. Node and package managers must be on PATH.

## Use the app

1. Landing page: choose **Report a problem** or **Admin sign in**.
2. Public report: enter contact information, location, category, and description. Submission atomically saves a location, emergency call, and incident to PostgreSQL; keep the confirmation reference.
3. Sign in with the admin you created. The dashboard shows totals, awaiting review, in-progress, and resolved counts.
4. Search by reference, type, or location; filter by status. Click **Review** to view description and contact information, then choose **Reported**, **In Progress**, or **Resolved**.
5. Reports, units, and recommendations refresh every ten seconds while the admin dashboard is open. Use Refresh for an immediate update. Theme preference persists in localStorage and initially follows the OS theme. Admin sessions survive reload for up to eight hours; sign out revokes the database session.

There is no public incident list or public contact-information endpoint. Reporting does not require an account. Counts represent all stored reports, not live dispatch metrics. Status/triage edits use last-write-wins, suitable for a small classroom demo. Assignments use database row locks and a unique active-assignment index to prevent double-booking. Assignment history is retained. There is no actual agency integration, GPS feed, road-routing service, or production monitoring.

## Build and verify

```powershell
npm run build
.\.venv\Scripts\python.exe -m unittest test_integration -v
```

Tests require the configured PostgreSQL database and initialized schema, but no running Flask server. They create a uniquely named test admin and temporary report, then remove those rows. PostgreSQL sequence numbers can have gaps. Prefer a separate test database by setting `DB_NAME` in the terminal (environment variables override `.env`). Tests cover report lifecycle and persistence, protected routes, invalid payloads, JSON/cross-site write checks, cookie flags, invalid login, throttling, expiry, and logout revocation.

`dist/` contains the production frontend build. `vite preview` alone does not proxy the API; the supported classroom run is the two-server development setup above. A production deployment needs a real WSGI server, HTTPS, and a reverse proxy routing `/api` to Flask and static requests to `dist/`.

## Security and scope

- Server-generated opaque tokens; only SHA-256 token hashes are stored in PostgreSQL.
- HttpOnly, SameSite=Strict session cookies expire after eight hours. Set `COOKIE_SECURE=true` behind HTTPS; leave false for local HTTP.
- JSON-only write requests, no permissive CORS, cross-site Fetch Metadata rejection, parameterized SQL, input bounds, and ten login attempts per IP per five minutes.
- Login throttling is in memory per process and resets on restart; this is an academic starter, not a hardened public emergency platform. Public report abuse prevention, distributed throttling, retention policies, and comprehensive auditing would be needed for public use.
- The CSS optionally loads Google Fonts; system fonts work offline. No maps, external APIs, or real service credentials are required.

## Files

- `src/App.jsx`, `src/style.css`: responsive landing, report, sign-in, and admin views.
- `app.py`: validated reports, admin authentication, protected register and status updates.
- `database.py`: original psycopg2 connection pattern and `.env` loading.
- `database/schema.sql`: preserved original schema.
- `database/migration.sql`: additive timestamp and auth tables.
- `manage.py`: non-destructive initialization and interactive admin setup.
- `test_integration.py`: PostgreSQL integration checks.

If the database is unavailable, confirm service, `.env`, port, database name and initialization. If sign-in expires, sign in again. If port 5173 or 5001 is occupied, stop the old instance before launching. The UI shows errors and does not claim a report succeeded until PostgreSQL commits it.


## Dispatch and automatic address lookup

Upgrade an existing checkout without losing reports:

```powershell
.\.venv\Scripts\python.exe manage.py init-db
.\.venv\Scripts\python.exe manage.py seed-units
```

Restart Flask after upgrading. Vite reloads frontend changes automatically. `seed-units` adds six response units around Nashville, Tennessee, and one example incident if absent; the older `seed-dispatch-demo` command remains an alias. Existing bundled names are cleaned by the migration; submitted user records are retained. The units are for this academic project; the system has no actual emergency-service connection.

### Assign from the reported address

1. Open **Review** on an incident. The assignment panel automatically searches the street address and city supplied in the report. There is no latitude/longitude entry in the website.
2. One precise result is saved automatically. If the lookup returns several matches, select the correct address. The matched address is displayed in the panel. A missing, ambiguous, or unavailable lookup blocks assignment and does not substitute random coordinates. Correct incomplete addresses with the reporter before proceeding.
3. Set severity to Low, Moderate, High, or Critical and click **Save severity**. This preserves the matched location.
4. The app matches Medical → Ambulance, Fire → Fire, Police → Police; Other permits manual selection across services. Unit capability must meet severity. Suitable available units with locations less than 15 minutes old are ranked by Haversine straight-line distance, not road distance or ETA. The nearest eligible unit is labeled.
5. Click **Assign unit**. The incident becomes In Progress. Database row locks and a unique active-assignment index prevent double-booking. Several units can serve one incident; each unit has at most one active assignment.
6. **Release unit** retains history and leaves the incident open. **Resolved** releases all its units. Offline units remain offline after release. Reopen resolved incidents before making a new assignment.
7. Under **Units & availability**, update a unit using its **Current address**, not coordinates. Choose a matching location if needed and save again. Saving updates its location and timestamp. New units use the same address-based flow. An assigned unit remains occupied even if its availability is set to Available.

The dashboard polls every ten seconds. Unit locations represent saved addresses; there is no GPS tracking or automatic vehicle movement. Last-known coordinates in the initial unit dataset remain available until stale; save each unit's current address when refreshing its location.

### Geocoding service and privacy

The backend uses OpenStreetMap Nominatim: https://nominatim.org/release-docs/latest/api/Search/

Only the address and city are sent to this third-party lookup service; names, phone numbers, severity, and incident descriptions are not sent. Do not use this academic starter to submit confidential addresses to the public service. See the service policy: https://operations.osmfoundation.org/policies/nominatim/ . Results are attributed in the website, cached in PostgreSQL for 30 days, and requests are serialized with a PostgreSQL advisory lock and spaced at least a second apart. No autocomplete or bulk background geocoding is used. Successful incident matches are retained and reused. Area-only matches such as a city or postal code are excluded.

Internet access is required for uncached addresses. Provider failures or no precise matches show an error; report submission and other admin functions still work. No API key is required for the default small local configuration. Set `GEOCODER_URL` to an equivalent Nominatim-compatible endpoint and `GEOCODER_USER_AGENT` to your application's identifying user agent when changing providers. For production or confidential data, use an appropriate authorized geocoding service instead.

### Verification

```powershell
npm run build
.\.venv\Scripts\python.exe -m unittest test_dispatch.DispatchIntegration test_geocoding.AddressIntegration -v
```

The tests create and remove temporary units/reports. Coverage includes service/capability matching, stale/offline units, assignment conflicts, release, auto-release on resolution, address matching, ambiguity selection, invalid selection, severity-only updates, unit address saves, lookup failure, and caching. Provider responses are mocked in automated tests; the default provider was also checked manually with public landmark addresses.

`dispatch.py` implements dispatch routes, `geocoding.py` handles the provider and cache, and `src/Dispatch.jsx` contains the assignment and fleet views. `database/migration.sql` extends the original tables additively. The API retains validated coordinate support for existing integrations, while website users work with addresses. Incident assignments require a location matched to the current reported address.

The built-in unit locations are now around Nashville, Tennessee (West End, Fort Negley, downtown, and Charlotte Avenue). Fresh installations should run `manage.py seed-units`. Admin credentials are created locally with `manage.py create-admin`; no account password is embedded in the source.


## New, active, and resolved registers

The admin dashboard opens **New reports** for Reported cases. **Active incidents** contains In Progress cases (and any legacy open status). **Resolved cases** contains only Resolved cases. The three registers have separate counts and search within the selected register. Starting a response or assigning a unit moves a report to Active incidents; resolving it moves it to Resolved cases. Reopening as Reported returns it to New reports; reopening as In Progress returns it to Active incidents. PostgreSQL records are preserved.

## Run from GitHub

Clone the repository, then follow the Install, PostgreSQL, and Run steps above. The repository includes the React/Vite source, Python API, dependency manifests and pnpm lockfile, database schema and additive migrations, admin/setup utilities, launch scripts, tests, and `.env.example`. Create your own local `.env`, initialize PostgreSQL with `manage.py init-db`, load Nashville units with `manage.py seed-units`, and create your admin using `manage.py create-admin`. Local passwords, database contents, virtual environments, and node_modules are intentionally excluded; they are created during setup.
