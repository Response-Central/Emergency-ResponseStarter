import React, { useEffect, useState } from "react";
import DispatchPanel, { Fleet } from "./Dispatch.jsx";

async function api(path, method = "GET", body) {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Cannot connect. Make sure the Python API is running.");
  }
  if (!response.ok) {
    const error = new Error(
      data.error || "Something went wrong. Please try again.",
    );
    error.status = response.status;
    error.candidates = data.candidates;
    throw error;
  }
  return data;
}
const types = ["Medical", "Fire", "Police", "Other"];
const marks = { Medical: "✚", Fire: "♨", Police: "◇", Other: "⚑" };
const date = (value) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
const id = (n) => `CER-${String(n).padStart(5, "0")}`;

const registerFor = (status) =>
  status === "Reported" ? "new" : status === "Resolved" ? "resolved" : "active";
const registers = {
  new: {
    label: "New reports",
    description:
      "Newly submitted reports awaiting review. Start a response to move a report to Active incidents.",
    empty: "No new reports.",
    hint: "New submissions appear here until work begins.",
  },
  active: {
    label: "Active incidents",
    description:
      "Cases with a response underway. Resolve a case to move it to Resolved cases.",
    empty: "No active incidents.",
    hint: "Reports move here when marked In Progress or assigned a unit.",
  },
  resolved: {
    label: "Resolved cases",
    description:
      "Completed cases are kept here. Reopen a case to return it to the appropriate register.",
    empty: "No resolved cases yet.",
    hint: "Cases move here when marked Resolved.",
  },
};
export default function App() {
  const [page, setPage] = useState("home"),
    [user, setUser] = useState(null),
    [rows, setRows] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [receipt, setReceipt] = useState(null),
    [incidentView, setIncidentView] = useState("new"),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState(null),
    [notice, setNotice] = useState(""),
    [loaded, setLoaded] = useState(false);
  const [theme, setTheme] = useState(() => {
    try {
      return (
        localStorage.getItem("cer-theme") ||
        (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
      );
    } catch {
      return "light";
    }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("cer-theme", theme);
    } catch {}
  }, [theme]);
  useEffect(() => {
    api("/auth/me")
      .then(setUser)
      .catch(() => {});
  }, []);
  function go(next) {
    setError("");
    setNotice("");
    setPage(next);
    window.scrollTo(0, 0);
  }
  async function refresh() {
    setBusy(true);
    setError("");
    try {
      const fresh = await api("/incidents");
      setRows(fresh);
      setSelected((previous) =>
        previous
          ? fresh.find((r) => r.incident_id === previous.incident_id) || null
          : null,
      );
      setLoaded(true);
    } catch (e) {
      setError(e.message);
      if (e.status === 401) {
        setUser(null);
        setPage("login");
      }
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (page === "dashboard" && user) refresh();
  }, [page, user]);
  useEffect(() => {
    if (page !== "dashboard" || !user) return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const fresh = await api("/incidents");
        if (cancelled) return;
        setRows(fresh);
        setSelected((previous) =>
          previous
            ? fresh.find((r) => r.incident_id === previous.incident_id) || null
            : null,
        );
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }, 10000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [page, user]);
  async function login(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setUser(
        await api(
          "/auth/login",
          "POST",
          Object.fromEntries(new FormData(e.currentTarget)),
        ),
      );
      go("dashboard");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function report(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api(
        "/reports",
        "POST",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      setReceipt(data.incident_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function update(item, status) {
    setBusy(true);
    setError("");
    try {
      await api("/incidents/" + item.incident_id, "PATCH", { status });
      setIncidentView(registerFor(status));
      setSearch("");
      setSelected({ ...item, status });
      setNotice(`${id(item.incident_id)} marked ${status.toLowerCase()}.`);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (selected) setIncidentView(registerFor(selected.status));
  }, [selected?.incident_id, selected?.status]);
  const registerRows = rows.filter(
    (r) => registerFor(r.status) === incidentView,
  );
  const shown = registerRows.filter((r) =>
    `${id(r.incident_id)} ${r.emergency_type} ${r.address} ${r.city}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const field = (label, name, props = {}) => (
    <label>
      {label}
      <input name={name} required {...props} />
    </label>
  );
  function switchRegister(view) {
    setIncidentView(view);
    setSelected(null);
    setSearch("");
    setNotice("");
  }
  return (
    <>
      <header>
        <button className="brand" onClick={() => go("home")}>
          <span className="brand-icon">✚</span>
          <span>
            Response<span className="brand-light">Central</span>
            <small>CENTRALIZED EMERGENCY RESPONSE</small>
          </span>
        </button>
        <nav>
          <span className="portal-label">
            <i /> OPERATIONS PORTAL
          </span>
          <button
            className="theme"
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
          >
            {theme === "light" ? "☾" : "☀"}
            <span>{theme === "light" ? "Dark" : "Light"} mode</span>
          </button>
          {user && <button onClick={() => go("dashboard")}>Dashboard</button>}
        </nav>
      </header>
      <div className="safety">
        <b>For immediate danger, call your local emergency number.</b>
        <span>This portal does not contact emergency services.</span>
      </div>
      <main>
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        {notice && (
          <div className="success" role="status">
            {notice}
          </div>
        )}
        {page === "home" && (
          <>
            <section className="hero">
              <div>
                <p className="eyebrow">
                  ONE COMMUNITY. ONE COORDINATED RESPONSE.
                </p>
                <h1>
                  A clearer path
                  <br />
                  from <em>report</em>
                  <br />
                  to response.
                </h1>
                <p className="hero-copy">
                  Bring every incident into focus. A central place to report
                  concerns, coordinate action, and keep your community moving
                  forward.
                </p>
                <div className="hero-meta">
                  <span>
                    01 <b>Report</b>
                  </span>
                  <span>
                    02 <b>Review</b>
                  </span>
                  <span>
                    03 <b>Resolve</b>
                  </span>
                </div>
              </div>
              <div className="access-panel">
                <div className="section-label">
                  GET STARTED <span>↗</span>
                </div>
                <h2>How can we help?</h2>
                <p>Choose where you’d like to begin.</p>
                <button
                  className="access report-access"
                  onClick={() => {
                    setReceipt(null);
                    go("report");
                  }}
                >
                  <span className="access-icon">⚑</span>
                  <span>
                    <strong>Report a problem</strong>
                    <small>Submit an emergency or community concern</small>
                  </span>
                  <b>→</b>
                </button>
                <button
                  className="access"
                  onClick={() => go(user ? "dashboard" : "login")}
                >
                  <span className="access-icon blue">◇</span>
                  <span>
                    <strong>Admin sign in</strong>
                    <small>Review incidents and coordinate next steps</small>
                  </span>
                  <b>→</b>
                </button>
                <p className="private-note">
                  ◈ Reports are visible only to signed-in administrators.
                </p>
              </div>
            </section>
            <section className="features">
              <article>
                <span>01 / CONNECT</span>
                <h3>One place to report.</h3>
                <p>
                  Capture the details that matter: what happened, where, and how
                  to reach you.
                </p>
              </article>
              <article>
                <span>02 / COORDINATE</span>
                <h3>Clarity for every incident.</h3>
                <p>
                  Give administrators a shared overview of new reports and
                  ongoing work.
                </p>
              </article>
              <article>
                <span>03 / FOLLOW THROUGH</span>
                <h3>Progress you can manage.</h3>
                <p>
                  Move incidents from reported to in progress, then through to
                  resolution.
                </p>
              </article>
            </section>
          </>
        )}
        {page === "login" && (
          <section className="form-layout">
            <aside>
              <p className="eyebrow">ADMINISTRATOR ACCESS</p>
              <h1>
                Stay informed.
                <br />
                <em>Take action.</em>
              </h1>
              <p>
                Sign in to your incident workspace to review reports and manage
                their progress.
              </p>
              <div className="aside-note">
                ◇{" "}
                <span>
                  Restricted workspace
                  <br />
                  <small>Authorized project administrators only</small>
                </span>
              </div>
            </aside>
            <div className="panel">
              <button className="text-button" onClick={() => go("home")}>
                ← Back to home
              </button>
              <h2>Welcome back</h2>
              <p>Enter your administrator credentials.</p>
              <form onSubmit={login}>
                {field("Username", "username", {
                  autoComplete: "username",
                  maxLength: 100,
                })}
                {field("Password", "password", {
                  type: "password",
                  autoComplete: "current-password",
                  maxLength: 500,
                })}
                <button className="primary" disabled={busy}>
                  {busy ? "Signing in…" : "Sign in to dashboard →"}
                </button>
              </form>
              <p className="helper">
                Need access? Ask your project administrator to create an
                account.
              </p>
            </div>
          </section>
        )}
        {page === "report" &&
          (receipt ? (
            <section className="receipt panel">
              <span className="receipt-check">✓</span>
              <p className="eyebrow">REPORT RECEIVED</p>
              <h1>
                Thank you for
                <br />
                speaking up.
              </h1>
              <p>Your report has been saved for administrator review.</p>
              <div className="reference">
                <small>YOUR REFERENCE NUMBER</small>
                <strong>{id(receipt)}</strong>
                <span>Status: Reported</span>
              </div>
              <p className="helper">
                Save this reference for your records. This submission does not
                contact or dispatch emergency services.
              </p>
              <button
                className="primary"
                onClick={() => {
                  setReceipt(null);
                  setError("");
                }}
              >
                Submit another report
              </button>
              <button onClick={() => go("home")}>Return home</button>
            </section>
          ) : (
            <section className="form-layout report-layout">
              <aside>
                <p className="eyebrow">PUBLIC REPORTING</p>
                <h1>
                  See a problem?
                  <br />
                  <em>Let us know.</em>
                </h1>
                <p>
                  Share clear, accurate details so an administrator can
                  understand the situation.
                </p>
                <ol className="steps">
                  <li>
                    <b>01</b>
                    <span>
                      Your details<small>How to contact you</small>
                    </span>
                  </li>
                  <li>
                    <b>02</b>
                    <span>
                      The location<small>Where the incident happened</small>
                    </span>
                  </li>
                  <li>
                    <b>03</b>
                    <span>
                      The situation
                      <small>What an administrator should know</small>
                    </span>
                  </li>
                </ol>
              </aside>
              <div className="panel">
                <button className="text-button" onClick={() => go("home")}>
                  ← Back to home
                </button>
                <h2>Report a problem / emergency</h2>
                <p>
                  All fields are required. Please avoid unnecessary sensitive
                  details.
                </p>
                <form onSubmit={report}>
                  <h3>
                    <span>01</span> Contact details
                  </h3>
                  <div className="form-grid">
                    {field("Full name", "caller_name", {
                      maxLength: 100,
                      autoComplete: "name",
                    })}
                    {field("Phone number", "caller_phone", {
                      type: "tel",
                      maxLength: 30,
                      autoComplete: "tel",
                    })}
                  </div>
                  <h3>
                    <span>02</span> Incident location
                  </h3>
                  {field("Street address or specific location", "address", {
                    maxLength: 255,
                    autoComplete: "street-address",
                  })}
                  {field("City", "city", {
                    maxLength: 100,
                    autoComplete: "address-level2",
                  })}
                  <h3>
                    <span>03</span> What happened?
                  </h3>
                  <label>
                    Incident type
                    <select name="emergency_type" required defaultValue="">
                      <option value="" disabled>
                        Select a category
                      </option>
                      {types.map((t) => (
                        <option key={t}>{t}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Description
                    <textarea
                      name="description"
                      required
                      maxLength={2000}
                      rows={5}
                      placeholder="Describe what happened and any details that may help…"
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    {busy ? "Submitting report…" : "Submit report →"}
                  </button>
                  <p className="helper">
                    Your report will be stored in the project database for admin
                    review.
                  </p>
                </form>
              </div>
            </section>
          ))}
        {page === "dashboard" && user && (
          <section className="dashboard">
            <div className="dashboard-heading">
              <div>
                <p className="eyebrow">OPERATIONS WORKSPACE</p>
                <h1>
                  Incident overview<span>.</span>
                </h1>
                <p>
                  Welcome, {user.username}. Keep every report moving toward
                  resolution.
                </p>
              </div>
              <div className="actions">
                <button disabled={busy} onClick={refresh}>
                  ↻ Refresh
                </button>
                <button
                  onClick={async () => {
                    setError("");
                    try {
                      await api("/auth/logout", "POST", {});
                      setUser(null);
                      setRows([]);
                      setSelected(null);
                      go("home");
                    } catch (e) {
                      setError(e.message);
                    }
                  }}
                >
                  Sign out
                </button>
              </div>
            </div>
            <div className="stats">
              {[
                ["Total reports", rows.length, "All recorded incidents"],
                [
                  "Awaiting review",
                  rows.filter((r) => r.status === "Reported").length,
                  "Newly reported",
                ],
                [
                  "In progress",
                  rows.filter((r) => r.status === "In Progress").length,
                  "Work underway",
                ],
                [
                  "Resolved",
                  rows.filter((r) => r.status === "Resolved").length,
                  "Closed incidents",
                ],
              ].map(([label, n, sub], i) => (
                <article key={label}>
                  <span className={"stat-dot dot-" + i} />
                  <p>{label}</p>
                  <strong>{loaded ? n : "—"}</strong>
                  <small>{sub}</small>
                </article>
              ))}
            </div>
            <div
              className="register-tabs"
              role="group"
              aria-label="Incident registers"
            >
              {Object.entries(registers).map(([key, register]) => (
                <button
                  key={key}
                  className={incidentView === key ? "current" : ""}
                  aria-pressed={incidentView === key}
                  onClick={() => switchRegister(key)}
                >
                  {register.label}
                  <span>
                    {rows.filter((r) => registerFor(r.status) === key).length}
                  </span>
                </button>
              ))}
            </div>
            <div className="panel incident-panel">
              <div className="list-heading">
                <div>
                  <h2>{registers[incidentView].label}</h2>
                  <p>{registers[incidentView].description}</p>
                </div>
                <span className="count">{shown.length} reports</span>
              </div>
              <div className="filters">
                <label className="search">
                  Search incidents
                  <input
                    aria-label="Search incidents"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search reference, location, or type…"
                  />
                </label>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>REFERENCE / RECEIVED</th>
                      <th>INCIDENT</th>
                      <th>LOCATION</th>
                      <th>STATUS</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
                      <tr key={r.incident_id}>
                        <td>
                          <strong>{id(r.incident_id)}</strong>
                          <small>{date(r.created_at)}</small>
                        </td>
                        <td>
                          <span
                            className={
                              "type-icon " + r.emergency_type.toLowerCase()
                            }
                          >
                            {marks[r.emergency_type]}
                          </span>
                          {r.emergency_type}
                          <small
                            className={"severity-" + r.severity.toLowerCase()}
                          >
                            {r.severity} severity
                          </small>
                        </td>
                        <td>
                          {r.address}
                          <small>{r.city}</small>
                        </td>
                        <td>
                          <span
                            className={
                              "badge " + r.status.replace(" ", "").toLowerCase()
                            }
                          >
                            {r.status}
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              setSelected(r);
                              setNotice("");
                            }}
                          >
                            Review ↗
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!shown.length && (
                <div className="empty">
                  <h3>
                    {busy
                      ? "Loading incidents…"
                      : registerRows.length
                        ? "No matching incidents"
                        : registers[incidentView].empty}
                  </h3>
                  <p>
                    {registerRows.length
                      ? "Try another search."
                      : registers[incidentView].hint}
                  </p>
                </div>
              )}
            </div>
            {selected && registerFor(selected.status) === incidentView && (
              <section className="panel detail" aria-label="Incident details">
                <div className="list-heading">
                  <div>
                    <p className="eyebrow">INCIDENT DETAILS</p>
                    <h2>
                      {id(selected.incident_id)} · {selected.emergency_type}
                    </h2>
                  </div>
                  <button onClick={() => setSelected(null)}>
                    Close details ×
                  </button>
                </div>
                <div className="detail-grid">
                  <div>
                    <h3>Situation</h3>
                    <p className="description">{selected.description}</p>
                    <h3>Location</h3>
                    <p>
                      {selected.address}, {selected.city}
                    </p>
                  </div>
                  <div>
                    <h3>Reported by</h3>
                    <p>
                      {selected.caller_name}
                      <br />
                      {selected.caller_phone}
                    </p>
                    <p className="helper">
                      Received {date(selected.created_at)}
                      <br />
                      Updated {date(selected.updated_at)}
                    </p>
                    <label>
                      Manage status
                      <select
                        disabled={busy}
                        value={selected.status}
                        onChange={(e) => update(selected, e.target.value)}
                      >
                        {["Reported", "In Progress", "Resolved"].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                </div>
                <DispatchPanel
                  key={selected.incident_id}
                  incident={selected}
                  api={api}
                  onChange={refresh}
                />
              </section>
            )}
            <Fleet api={api} />
          </section>
        )}
      </main>
      <footer>
        <span>
          <b>ResponseCentral</b> / Community coordination, made clear.
        </span>
        <span>Response coordination · No emergency-service connection</span>
      </footer>
    </>
  );
}
