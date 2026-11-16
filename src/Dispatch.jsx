import React, { useEffect, useState } from "react";
const levels = ["Low", "Moderate", "High", "Critical"];
const stamp = (t) =>
  t
    ? new Date(t).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "No location";
function UnitAddress({ unit, choices }) {
  return (
    <>
      <label>
        Current address
        <input
          name="location_address"
          required
          maxLength={500}
          defaultValue={unit?.location_address || ""}
          placeholder="Street address, city, region, postal code"
        />
      </label>
      {choices?.length > 0 && (
        <label>
          Matching location
          <select name="place_id" required defaultValue="">
            <option value="" disabled>
              Select the correct address
            </option>
            {choices.map((p) => (
              <option value={p.place_id} key={p.place_id}>
                {p.display_name}
              </option>
            ))}
          </select>
        </label>
      )}
    </>
  );
}
export function Fleet({ api, refreshKey }) {
  const [units, setUnits] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [choices, setChoices] = useState({});
  async function load() {
    try {
      setUnits(await api("/units"));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [refreshKey]);
  async function save(e, unit) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    if (!unit) data.capability = Number(data.capability);
    setBusy(true);
    setError("");
    try {
      await api(
        unit ? `/units/${unit.unit_id}` : "/units",
        unit ? "PATCH" : "POST",
        data,
      );
      setChoices((old) => ({ ...old, [unit?.unit_id || "new"]: null }));
      setMessage(
        unit ? "Unit location updated from address." : "Response unit created.",
      );
      if (!unit) form.reset();
      await load();
    } catch (e) {
      setError(e.message);
      if (e.candidates)
        setChoices((old) => ({
          ...old,
          [unit?.unit_id || "new"]: e.candidates,
        }));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel fleet">
      <div className="list-heading">
        <div>
          <p className="eyebrow">RESPONSE NETWORK</p>
          <h2>Units & availability</h2>
          <p>
            Updates every 10 seconds. Save a unit’s current address to update
            its location.
          </p>
        </div>
        <button onClick={load}>Refresh units</button>
      </div>
      {error && (
        <p role="alert" className="dispatch-error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <div className="unit-grid">
        {units.map((u) => (
          <article className="unit-card" key={u.unit_id}>
            <div className="list-heading">
              <h3>{u.unit_name}</h3>
              <span className="badge">
                {u.incident_id ? "Assigned" : u.status}
              </span>
            </div>
            <p>
              {u.unit_type} · {u.dispatcher_name || "Unspecified crew"}
            </p>
            <small>
              Handles up to {levels[u.capability - 1]} severity ·{" "}
              {u.incident_id
                ? `Incident #${u.incident_id}`
                : "No active assignment"}
            </small>
            <p className="helper">
              Location {stamp(u.location_updated_at)}{" "}
              {u.latitude != null && u.longitude != null
                ? "· saved location"
                : "· location missing"}
            </p>
            <details>
              <summary>Update location / availability</summary>
              <form onSubmit={(e) => save(e, u)} key={u.location_updated_at}>
                <UnitAddress unit={u} choices={choices[u.unit_id]} />
                <label>
                  Availability
                  <select
                    name="status"
                    defaultValue={
                      u.status === "Offline" ? "Offline" : "Available"
                    }
                  >
                    <option>Available</option>
                    <option>Offline</option>
                  </select>
                </label>
                <button disabled={busy}>Save unit location</button>
              </form>
            </details>
          </article>
        ))}
      </div>
      {!units.length && <p>No units yet. Add a response unit below.</p>}
      <details className="add-unit">
        <summary>+ Add response unit</summary>
        <form onSubmit={(e) => save(e)}>
          <div className="form-grid">
            <label>
              Unit name
              <input
                name="unit_name"
                maxLength={100}
                required
                placeholder="Ambulance 01"
              />
            </label>
            <label>
              Crew / dispatcher
              <input
                name="dispatcher_name"
                maxLength={100}
                required
                placeholder="Crew name"
              />
            </label>
            <label>
              Service
              <select name="unit_type">
                <option>Ambulance</option>
                <option>Fire</option>
                <option>Police</option>
              </select>
            </label>
            <label>
              Maximum severity capability
              <select name="capability" defaultValue="4">
                {levels.map((s, i) => (
                  <option key={s} value={i + 1}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <UnitAddress choices={choices.new} />
          <button className="primary" disabled={busy}>
            Create response unit
          </button>
        </form>
      </details>
    </section>
  );
}
export default function DispatchPanel({ incident, api, onChange }) {
  const [places, setPlaces] = useState([]),
    [locating, setLocating] = useState(false),
    [locationError, setLocationError] = useState(""),
    [located, setLocated] = useState(false);
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function load() {
    try {
      setData(await api(`/incidents/${incident.incident_id}/dispatch`));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    setData(null);
    setMessage("");
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [
    incident.incident_id,
    incident.severity,
    incident.latitude,
    incident.longitude,
    incident.status,
  ]);
  async function action(path, method, body, success) {
    setBusy(true);
    setError("");
    try {
      const result = await api(path, method, body);
      setMessage(
        success +
          (result.hospital
            ? ` Destination: ${result.hospital.hospital_name} · receiving bed reserved.`
            : ""),
      );
      await onChange();
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const root = `/incidents/${incident.incident_id}`;
  async function locate(placeId) {
    setLocating(true);
    setLocationError("");
    setLocated(false);
    try {
      await api(root + "/locate", "POST", placeId ? { place_id: placeId } : {});
      setPlaces([]);
      setLocated(true);
      await onChange();
      await load();
    } catch (e) {
      if (e.candidates) setPlaces(e.candidates);
      setLocationError(e.message);
    } finally {
      setLocating(false);
    }
  }
  useEffect(() => {
    setPlaces([]);
    setLocated(false);
    locate();
  }, [incident.incident_id, incident.address, incident.city]);

  return (
    <section className="dispatch-panel">
      <div className="list-heading">
        <div>
          <p className="eyebrow">DISPATCH COORDINATION</p>
          <h2>Assign the right response.</h2>
          <p>
            Review severity and the reported address, then assign a suitable
            unit.
          </p>
        </div>
        <span className={"badge severity-" + incident.severity.toLowerCase()}>
          {incident.severity}
        </span>
      </div>
      <p className="helper">
        Category determines service; severity sets minimum unit capability.
        Admin confirms every assignment. Distance is straight-line km, not a
        driving route or ETA. Distance uses the unit’s last saved location;
        update its address when it moves.
      </p>
      {error && (
        <p className="dispatch-error" role="alert">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <form
        className="triage-form"
        key={incident.incident_id}
        onSubmit={(e) => {
          e.preventDefault();
          action(
            root + "/triage",
            "PATCH",
            Object.fromEntries(new FormData(e.currentTarget)),
            "Incident severity saved.",
          );
        }}
      >
        <label>
          Severity
          <select name="severity" defaultValue={incident.severity}>
            {levels.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>

        <button disabled={busy}>Save severity</button>
      </form>
      <div className="address-match">
        <div className="list-heading">
          <div>
            <h3>Reported address</h3>
            <p>
              {incident.address}, {incident.city}
            </p>
          </div>
          <button disabled={locating || busy} onClick={() => locate()}>
            Locate address
          </button>
        </div>
        {locating && <p role="status">Looking up the reported address…</p>}
        {locationError && (
          <p role="alert" className="dispatch-error">
            {locationError}
          </p>
        )}
        {places.length > 0 && (
          <div className="address-choices">
            <p>Choose the location that matches the report:</p>
            {places.map((p) => (
              <button
                key={p.place_id}
                disabled={locating}
                onClick={() => locate(p.place_id)}
              >
                {p.display_name}
              </button>
            ))}
          </div>
        )}
        {located && incident.resolved_address && (
          <p className="matched-location">
            <b>Located:</b> {incident.resolved_address}
          </p>
        )}
        <p className="helper">
          Address lookup by{" "}
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noreferrer"
          >
            © OpenStreetMap contributors
          </a>
          . Only the address is sent for lookup. Distances update after a
          location is matched.
        </p>
      </div>
      {data?.hospital && (
        <section
          className="hospital-destination"
          aria-label="Ambulance hospital destination"
        >
          <p className="eyebrow">AMBULANCE DESTINATION</p>
          <h3>{data.hospital.hospital_name}</h3>
          <p>
            {data.hospital.area} · {data.hospital.distance_km.toFixed(2)} km
            from the incident
          </p>
          <span className="badge">
            {data.hospital.released_at
              ? "Bed released"
              : "1 receiving bed reserved"}
          </span>
          <p className="helper">
            Nearest hospital with a free receiving bed at assignment time.
            Distance is straight-line, not a driving route or ETA.
          </p>
        </section>
      )}
      <div className="list-heading">
        <h3>
          Nearby response units{" "}
          {data?.recommended_service && `· ${data.recommended_service}`}
        </h3>
        <button disabled={busy} onClick={load}>
          Refresh distances
        </button>
      </div>
      {!data ? (
        <p>Loading recommendations…</p>
      ) : (
        <>
          <div className="dispatch-candidates">
            {data.units.map((u, index) => (
              <article
                className={"candidate " + (u.eligible ? "eligible" : "")}
                key={u.unit_id}
              >
                <div>
                  <strong>{u.unit_name}</strong>
                  {u.eligible && index === 0 && (
                    <span className="badge">Nearest suitable</span>
                  )}
                  <p>
                    {u.unit_type} · {u.dispatcher_name || "Unspecified crew"} ·
                    Up to {levels[u.capability - 1]}
                  </p>
                  <small>
                    Location updated {stamp(u.location_updated_at)}
                    {u.reason && ` · ${u.reason}`}
                  </small>
                </div>
                <div className="candidate-action">
                  <b>
                    {u.distance_km == null
                      ? "Unknown distance"
                      : `${u.distance_km.toFixed(2)} km`}
                  </b>
                  <button
                    disabled={busy || locating || !located || !u.eligible}
                    onClick={() =>
                      action(
                        root + "/assignments",
                        "POST",
                        { unit_id: u.unit_id },
                        `${u.unit_name} assigned.`,
                      )
                    }
                  >
                    Assign unit
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!data.units.length && <p>Add a unit in Units & availability.</p>}
          <h3>Assignment history</h3>
          {!data.assignments.length ? (
            <p>No units assigned yet.</p>
          ) : (
            data.assignments.map((a) => (
              <article className="assignment" key={a.assignment_id}>
                <div>
                  <strong>{a.unit_name}</strong>
                  <p>
                    {a.unit_type} · {a.dispatcher_name} · Assigned by{" "}
                    {a.assigned_by}
                  </p>
                  <small>
                    {new Date(a.assigned_at).toLocaleString()} ·{" "}
                    {a.released_at
                      ? `Released ${new Date(a.released_at).toLocaleString()}`
                      : "Active assignment"}
                  </small>
                </div>
                {!a.released_at && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      action(
                        `${root}/assignments/${a.assignment_id}/release`,
                        "POST",
                        {},
                        "Unit released. The incident remains open until resolved.",
                      )
                    }
                  >
                    Release unit
                  </button>
                )}
              </article>
            ))
          )}
        </>
      )}
    </section>
  );
}
