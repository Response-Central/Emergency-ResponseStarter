import React, { useEffect, useState } from "react";
export default function CapacityOverview({
  api,
  refreshKey,
  view = "summary",
}) {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    let cancelled = false;
    const read = async () => {
      try {
        const result = await api("/capacity");
        if (!cancelled) {
          setData(result);
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    read();
    const timer = setInterval(read, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [refreshKey]);
  async function save(e, hospital) {
    e.preventDefault();
    setSaving(true);
    setError("");
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api("/hospitals/" + hospital.hospital_id, "PATCH", {
        total_beds: Number(values.total_beds),
        occupied_beds: Number(values.occupied_beds),
      });
      setData(await api("/capacity"));
      setMessage(hospital.hospital_name + " capacity updated.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <section
      className="capacity-overview"
      aria-label={
        view === "hospitals"
          ? "Hospital capacity"
          : view === "units"
            ? "Unit availability"
            : "Unit availability and hospital capacity"
      }
    >
      <div
        className={"capacity-summary " + (view !== "summary" ? "single" : "")}
      >
        {view !== "hospitals" && (
          <article className="capacity-total">
            <p className="eyebrow">RESPONSE AVAILABILITY</p>
            <div className="capacity-value">
              <strong>{data ? data.available_units : "—"}</strong>
              <span>
                units available
                {data && <small>of {data.total_units} total units</small>}
              </span>
            </div>
            <div className="service-counts">
              {data?.services.map((s) => (
                <span key={s.unit_type}>
                  <b>
                    {s.available}/{s.total}
                  </b>{" "}
                  {s.unit_type === "Ambulance"
                    ? "Ambulances"
                    : s.unit_type === "Fire"
                      ? "Fire engines"
                      : "Police units"}
                </span>
              ))}
            </div>
          </article>
        )}
        {view !== "units" && (
          <article className="capacity-total">
            <p className="eyebrow">HOSPITAL RECEIVING CAPACITY</p>
            <div className="capacity-value">
              <strong>{data ? data.available_beds : "—"}</strong>
              <span>
                beds available
                {data && (
                  <small>
                    of {data.total_beds} configured receiving beds ·{" "}
                    {data.reserved_beds} reserved
                  </small>
                )}
              </span>
            </div>
            <p className="helper">
              Ambulances reserve the nearest available hospital bed. One bed per
              incident; resolving the case releases it.
            </p>
          </article>
        )}
      </div>
      {error && (
        <p role="alert" className="dispatch-error">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="helper">
          {message}
        </p>
      )}
      {view === "hospitals" && (
        <>
          <div className="hospital-grid">
            {data?.hospitals.map((h) => (
              <article
                className={
                  "hospital-card " +
                  (h.available_beds === 0 ? "hospital-full" : "")
                }
                key={h.hospital_id}
              >
                <div className="list-heading">
                  <h3>{h.hospital_name}</h3>
                  <span className="hospital-symbol">✚</span>
                </div>
                <p>{h.area}</p>
                <div className="bed-count">
                  <strong>{h.available_beds}</strong>
                  <span>
                    beds available<small>{h.total_beds} total</small>
                  </span>
                </div>
                <div
                  className="bed-meter"
                  role="img"
                  aria-label={`${h.occupied_beds} occupied, ${h.reserved_beds} reserved, ${h.available_beds} available`}
                >
                  <span
                    className="occupied"
                    style={{
                      width: `${(h.occupied_beds / h.total_beds) * 100}%`,
                    }}
                  />
                  <span
                    className="reserved"
                    style={{
                      width: `${(h.reserved_beds / h.total_beds) * 100}%`,
                    }}
                  />
                </div>
                <p className="bed-legend">
                  {h.occupied_beds} occupied · {h.reserved_beds} reserved
                </p>
                <details>
                  <summary>Manage beds</summary>
                  <form onSubmit={(e) => save(e, h)}>
                    <label>
                      Total receiving beds
                      <input
                        type="number"
                        min="1"
                        max="5000"
                        step="1"
                        name="total_beds"
                        defaultValue={h.total_beds}
                        required
                      />
                    </label>
                    <label>
                      Occupied beds (excluding reservations)
                      <input
                        type="number"
                        min="0"
                        max={5000}
                        step="1"
                        name="occupied_beds"
                        defaultValue={h.occupied_beds}
                        required
                      />
                    </label>
                    <button disabled={saving}>Save beds</button>
                  </form>
                </details>
              </article>
            ))}
          </div>
          <p className="helper">
            Available beds = total − occupied − active reservations. Counts
            update with assignments and saved capacity changes; hospital
            distances use the incident location.
          </p>
        </>
      )}
    </section>
  );
}
