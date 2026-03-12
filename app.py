"""
MediCare Clinic System — Flask Web App
Run locally:  python app.py
Deploy free:  Railway / Render / PythonAnywhere
Default login: Dr. Admin / admin123
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3, hashlib, uuid, os, re, json, collections
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "medicare-secret-2024-change-in-prod")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clinic.db")

# ══════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════
def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with get_db() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS doctors (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT UNIQUE NOT NULL,
                role       TEXT NOT NULL DEFAULT 'Doctor',
                password   TEXT NOT NULL,
                qr_id      TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS patients (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                age             TEXT NOT NULL DEFAULT '',
                contact         TEXT NOT NULL DEFAULT '',
                date_of_appointment TEXT NOT NULL,
                appointment_time    TEXT NOT NULL,
                queue_no        INTEGER NOT NULL DEFAULT 1,
                symptoms        TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'Pending',
                diagnosis       TEXT NOT NULL DEFAULT '',
                prescription    TEXT NOT NULL DEFAULT '',
                notes           TEXT NOT NULL DEFAULT '',
                examined_by     TEXT NOT NULL DEFAULT '',
                examined_at     TEXT NOT NULL DEFAULT '',
                submitted_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # migrations for older schemas
        for col, defn in [
            ("role",         "TEXT NOT NULL DEFAULT 'Doctor'"),
            ("age",          "TEXT NOT NULL DEFAULT ''"),
            ("contact",      "TEXT NOT NULL DEFAULT ''"),
            ("queue_no",     "INTEGER NOT NULL DEFAULT 1"),
            ("prescription", "TEXT NOT NULL DEFAULT ''"),
            ("examined_by",  "TEXT NOT NULL DEFAULT ''"),
            ("examined_at",  "TEXT NOT NULL DEFAULT ''"),
        ]:
            try:
                c.execute(f"ALTER TABLE doctors ADD COLUMN {col} {defn}")
                c.commit()
            except Exception:
                pass
            try:
                c.execute(f"ALTER TABLE patients ADD COLUMN {col} {defn}")
                c.commit()
            except Exception:
                pass

        if c.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] == 0:
            c.execute("INSERT INTO doctors(name,role,password,qr_id) VALUES(?,?,?,?)",
                ("Dr. Admin","Doctor",hashlib.sha256(b"admin123").hexdigest(),str(uuid.uuid4())))
            c.commit()

def next_queue(date):
    with get_db() as c:
        r = c.execute("SELECT MAX(queue_no) FROM patients WHERE date_of_appointment=?",(date,)).fetchone()
        return (r[0] or 0) + 1

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "doctor_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════
#  BASE STYLE
# ══════════════════════════════════════════════════════
STYLE = """
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0a1628;--navy2:#0f1f38;--card:#111f33;--card2:#162540;
  --border:#1e3254;--border2:#243d60;
  --teal:#0d9488;--teal2:#14b8a6;--teal3:#5eead4;
  --gold:#d4a853;--gold2:#f0c060;
  --red:#ef4444;--red2:#fca5a5;
  --green:#22c55e;--green2:#86efac;
  --text:#e8f0fe;--text2:#7a9cc0;--text3:#3d5a7a;
  --font:'Segoe UI',system-ui,sans-serif;
  --mono:'Courier New',monospace;
}
body{font-family:var(--font);background:var(--navy);color:var(--text);min-height:100vh;line-height:1.6}
body::before{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(ellipse 80% 50% at 10% 20%,rgba(13,148,136,.12) 0%,transparent 60%),
             radial-gradient(ellipse 60% 40% at 90% 80%,rgba(212,168,83,.07) 0%,transparent 55%)}
body::after{content:'';position:fixed;inset:0;z-index:0;pointer-events:none;
  background-image:linear-gradient(rgba(255,255,255,.015) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,255,255,.015) 1px,transparent 1px);
  background-size:48px 48px}
nav{position:sticky;top:0;z-index:100;padding:.85rem 2rem;
  display:flex;align-items:center;gap:.75rem;
  background:rgba(10,22,40,.92);backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border)}
.logo{font-weight:800;font-size:1.1rem}
.nav-actions{margin-left:auto;display:flex;gap:.6rem;align-items:center}
.nav-user{font-size:.78rem;color:var(--text2);background:var(--card);
  border:1px solid var(--border);padding:.3rem .75rem;border-radius:100px}
.nav-user span{color:var(--teal2);font-weight:600}
.page{position:relative;z-index:1;min-height:calc(100vh - 57px);
  display:flex;align-items:center;justify-content:center;padding:2.5rem 1.25rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:20px;
  padding:2.2rem 2rem;width:100%;max-width:460px;
  animation:slideUp .4s cubic-bezier(.16,1,.3,1)}
.card-wide{max-width:560px}
@keyframes slideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
.field{margin-bottom:1.1rem}
.field label{display:block;font-size:.72rem;font-weight:600;color:var(--text2);
  letter-spacing:.08em;text-transform:uppercase;margin-bottom:.42rem}
.field input,.field textarea,.field select{width:100%;padding:.72rem 1rem;
  background:var(--card2);border:1px solid var(--border);border-radius:10px;
  color:var(--text);font-size:.9rem;font-family:var(--font);outline:none;
  transition:border-color .2s;resize:vertical}
.field input:focus,.field textarea:focus,.field select:focus{border-color:var(--teal)}
.field input::placeholder,.field textarea::placeholder{color:var(--text3)}
.field select option{background:var(--card2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:.9rem}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.45rem;
  padding:.75rem 1.5rem;border:none;border-radius:11px;font-size:.88rem;font-weight:700;
  font-family:var(--font);cursor:pointer;transition:all .2s;text-decoration:none}
.btn-block{display:flex;width:100%}
.btn-teal{background:var(--teal);color:#fff}
.btn-teal:hover{background:var(--teal2);transform:translateY(-1px)}
.btn-gold{background:var(--gold);color:#0a0f1a}
.btn-gold:hover{background:var(--gold2);transform:translateY(-1px)}
.btn-ghost{background:var(--card2);border:1px solid var(--border);color:var(--text2)}
.btn-ghost:hover{border-color:var(--teal);color:var(--teal2)}
.btn-red{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:var(--red2)}
.btn-green{background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.3);color:var(--green2)}
.btn-sm{padding:.42rem .85rem;font-size:.78rem;border-radius:8px}
.alert{padding:.75rem 1rem;border-radius:10px;font-size:.84rem;margin-bottom:1rem;display:none}
.alert.show{display:block}
.alert-err{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.28);color:var(--red2)}
.alert-ok{background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.28);color:var(--teal3)}
.alert-info{background:rgba(212,168,83,.1);border:1px solid rgba(212,168,83,.25);color:var(--gold2)}
.tabs{display:flex;gap:3px;padding:3px;background:var(--card2);
  border:1px solid var(--border);border-radius:12px;margin-bottom:1.4rem}
.tab{flex:1;padding:.55rem;border-radius:9px;border:none;background:transparent;
  color:var(--text2);font-size:.82rem;font-weight:600;font-family:var(--font);cursor:pointer;transition:all .2s}
.tab.active{background:var(--teal);color:#fff}
.badge{display:inline-block;padding:.22rem .65rem;border-radius:100px;font-size:.72rem;font-weight:700}
.badge-pend{background:rgba(212,168,83,.15);border:1px solid rgba(212,168,83,.3);color:var(--gold2)}
.badge-prog{background:rgba(13,148,136,.15);border:1px solid rgba(13,148,136,.3);color:var(--teal3)}
.badge-exam{background:rgba(34,197,94,.13);border:1px solid rgba(34,197,94,.3);color:var(--green2)}
.badge-canc{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.28);color:var(--red2)}
.dash-wrap{display:flex;min-height:calc(100vh - 57px);position:relative;z-index:1}
.sidebar{width:230px;flex-shrink:0;background:var(--navy2);border-right:1px solid var(--border);
  display:flex;flex-direction:column;position:sticky;top:57px;height:calc(100vh - 57px);overflow-y:auto}
.sb-head{padding:1.3rem 1.1rem;border-bottom:1px solid var(--border)}
.sb-role{font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--teal2);margin-bottom:.2rem}
.sb-name{font-weight:700;font-size:.95rem}
.sb-nav{flex:1;padding:.75rem .6rem;display:flex;flex-direction:column;gap:2px}
.sb-link{display:flex;align-items:center;gap:.6rem;padding:.6rem .85rem;border-radius:9px;
  color:var(--text2);font-size:.83rem;font-weight:500;text-decoration:none;transition:all .18s;
  cursor:pointer;border:none;background:transparent;width:100%;text-align:left;font-family:var(--font)}
.sb-link:hover{background:rgba(13,148,136,.1);color:var(--teal2)}
.sb-link.active{background:rgba(13,148,136,.16);color:var(--teal2);font-weight:700}
.sb-count{margin-left:auto;font-size:.68rem;font-weight:700;padding:.1rem .45rem;
  border-radius:100px;background:var(--teal);color:#fff}
.sb-count.gold{background:rgba(212,168,83,.25);color:var(--gold2)}
.sb-foot{padding:.85rem 1rem;border-top:1px solid var(--border)}
.main-content{flex:1;padding:1.5rem;overflow-x:auto}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.85rem;margin-bottom:1.5rem}
.stat{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:1.1rem 1rem}
.stat.teal{border-color:rgba(13,148,136,.3);background:rgba(13,148,136,.08)}
.stat.gold{border-color:rgba(212,168,83,.3);background:rgba(212,168,83,.07)}
.stat.green{border-color:rgba(34,197,94,.3);background:rgba(34,197,94,.07)}
.stat.red{border-color:rgba(239,68,68,.3);background:rgba(239,68,68,.07)}
.stat-val{font-size:1.9rem;font-weight:800;line-height:1;margin-bottom:.25rem;font-family:var(--mono)}
.stat.teal .stat-val{color:var(--teal2)}.stat.gold .stat-val{color:var(--gold2)}
.stat.green .stat-val{color:var(--green2)}.stat.red .stat-val{color:var(--red2)}
.stat-lbl{font-size:.7rem;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.07em}
.table-wrap{background:var(--card);border:1px solid var(--border);border-radius:16px;overflow:hidden}
.table-top{padding:1rem 1.2rem;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.6rem}
.fbtn{padding:.35rem .75rem;border-radius:7px;font-size:.74rem;font-weight:600;
  font-family:var(--font);cursor:pointer;border:1px solid var(--border);
  background:var(--card2);color:var(--text2);transition:all .18s}
.fbtn:hover,.fbtn.active{background:rgba(13,148,136,.15);border-color:var(--teal);color:var(--teal2)}
.srch{padding:.42rem .85rem;border-radius:8px;font-size:.82rem;background:var(--card2);
  border:1px solid var(--border);color:var(--text);font-family:var(--font);
  outline:none;width:200px;transition:border-color .2s}
.srch:focus{border-color:var(--teal)}
.srch::placeholder{color:var(--text3)}
table{width:100%;border-collapse:collapse}
thead th{padding:.65rem 1rem;text-align:left;font-size:.67rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;color:var(--text2);
  border-bottom:1px solid var(--border);background:var(--card2)}
tbody tr{transition:background .12s;cursor:pointer}
tbody tr:hover{background:rgba(13,148,136,.05)}
tbody td{padding:.85rem 1rem;font-size:.85rem;border-bottom:1px solid rgba(255,255,255,.04)}
tbody tr:last-child td{border-bottom:none}
.stag{display:inline-block;background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.22);
  color:var(--teal3);font-size:.7rem;padding:.14rem .5rem;border-radius:100px;margin:.1rem}
.info-row{display:flex;justify-content:space-between;align-items:flex-start;
  padding:.5rem 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:.85rem}
.info-row:last-child{border:none}
.info-lbl{color:var(--text2);flex-shrink:0;min-width:100px}
.info-val{font-weight:600;text-align:right;word-break:break-word}
.queue-display{background:linear-gradient(135deg,var(--teal),var(--teal2));
  border-radius:16px;padding:1.5rem;text-align:center;margin:1.2rem 0}
.queue-number{font-size:4rem;font-weight:800;font-family:var(--mono);line-height:1}
.queue-label{font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;opacity:.75;margin-bottom:.3rem}
.chip{padding:.28rem .75rem;border-radius:100px;font-size:.74rem;font-weight:600;
  border:1px solid var(--border);color:var(--text2);background:var(--card2);
  cursor:pointer;transition:all .18s;user-select:none;display:inline-block;margin:.15rem}
.chip.sel{background:rgba(212,168,83,.15);border-color:rgba(212,168,83,.4);color:var(--gold2)}
.exam-grid{display:grid;grid-template-columns:320px 1fr;gap:1.2rem}
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:1.2rem}
.chart-title{font-size:.85rem;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:.07em;margin-bottom:.85rem}
@media(max-width:780px){.exam-grid{grid-template-columns:1fr}}
@media(max-width:700px){.sidebar{display:none}.grid2{grid-template-columns:1fr}.card{padding:1.5rem 1.2rem}}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--navy)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}
@media print{
  .no-print{display:none!important}
  body{background:#fff!important;color:#000!important}
  body::before,body::after{display:none!important}
  .receipt-card{background:#fff!important;border:1px solid #ccc!important;color:#000!important}
  .receipt-card *{color:#000!important;background:transparent!important;border-color:#ccc!important}
}
</style>
"""

def base_page(title, body, extra_nav=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · MediCare</title>
{STYLE}
</head>
<body>
<nav>
  <span style="font-size:1.2rem">🏥</span>
  <span class="logo">MediCare</span>
  {extra_nav}
</nav>
{body}
</body>
</html>"""

def badge(status):
    m = {"Pending":"badge-pend","In Progress":"badge-prog","Examined":"badge-exam","Cancelled":"badge-canc"}
    return m.get(status, "badge-pend")

def sym_tags(s):
    parts = [x.strip() for x in re.split(r'[\n,]+',s) if x.strip()]
    return "".join(f'<span class="stag">{p}</span>' for p in parts)

def sym_short(s, n=3):
    parts = [x.strip() for x in re.split(r'[\n,]+',s) if x.strip()]
    out = "".join(f'<span class="stag">{p}</span>' for p in parts[:n])
    if len(parts) > n: out += f'<span class="stag" style="opacity:.5">+{len(parts)-n}</span>'
    return out

# ══════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════

@app.route("/")
def landing():
    nav = ""
    if session.get("doctor_name"):
        nav = f'<div class="nav-actions"><div class="nav-user">{session["doctor_role"]} · <span>{session["doctor_name"]}</span></div><a href="/logout" class="btn btn-ghost btn-sm">Sign Out</a></div>'
    else:
        nav = '<div class="nav-actions"><a href="/login" class="btn btn-ghost btn-sm">Staff Login</a></div>'

    body = f"""
<div class="page" style="align-items:flex-start;padding-top:4rem">
<div style="position:relative;z-index:1;max-width:900px;width:100%">
  <div style="display:inline-flex;align-items:center;gap:.5rem;
    background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.25);
    border-radius:100px;padding:.32rem 1rem;font-size:.72rem;font-weight:700;
    color:var(--teal2);letter-spacing:.1em;text-transform:uppercase;margin-bottom:1.4rem">
    ● Clinic Management System
  </div>
  <h1 style="font-size:clamp(2rem,5vw,3.5rem);font-weight:800;line-height:1.1;
    letter-spacing:-.03em;margin-bottom:.75rem">
    Healthcare Made <span style="color:var(--teal2)">Simple</span>
  </h1>
  <p style="color:var(--text2);font-size:1.05rem;max-width:440px;line-height:1.7;margin-bottom:2.5rem">
    Manage patient appointments, doctor examinations, and clinic workflows — accessible from any device, anywhere.
  </p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.1rem">
    <div style="background:var(--card);border:1px solid var(--border);border-radius:18px;padding:1.8rem">
      <div style="font-size:2.4rem;margin-bottom:.85rem">👨‍⚕️</div>
      <div style="font-size:1.1rem;font-weight:800;margin-bottom:.35rem">Doctor / Staff Portal</div>
      <p style="color:var(--text2);font-size:.83rem;line-height:1.65;margin-bottom:1.2rem">
        View patient queue, examine patients, write prescriptions, generate receipts &amp; view statistics.
      </p>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        <a href="/login"    class="btn btn-teal btn-sm">Sign In</a>
        <a href="/register" class="btn btn-ghost btn-sm">Register</a>
      </div>
    </div>
    <div style="background:var(--card);border:1px solid rgba(212,168,83,.25);border-radius:18px;padding:1.8rem">
      <div style="font-size:2.4rem;margin-bottom:.85rem">🩺</div>
      <div style="font-size:1.1rem;font-weight:800;margin-bottom:.35rem">Patient Admission</div>
      <p style="color:var(--text2);font-size:.83rem;line-height:1.65;margin-bottom:1.2rem">
        Book your appointment. Choose a date and time — you'll get a queue number instantly.
      </p>
      <a href="/admission" class="btn btn-gold btn-sm">Book Appointment</a>
    </div>
  </div>
</div>
</div>"""
    return base_page("Home", body, nav)


@app.route("/register", methods=["GET","POST"])
def register():
    error = ""; qr_id = ""; dname = ""; drole = ""
    if request.method == "POST":
        name = request.form.get("name","").strip()
        role = request.form.get("role","Doctor")
        pw   = request.form.get("password","").strip()
        pw2  = request.form.get("password2","").strip()
        if not name:       error = "Full name is required."
        elif len(pw) < 6:  error = "Password must be at least 6 characters."
        elif pw != pw2:    error = "Passwords do not match."
        else:
            qr = str(uuid.uuid4())
            try:
                with get_db() as c:
                    c.execute("INSERT INTO doctors(name,role,password,qr_id) VALUES(?,?,?,?)",
                              (name, role, hashlib.sha256(pw.encode()).hexdigest(), qr))
                    c.commit()
                qr_id = qr; dname = name; drole = role
            except Exception as e:
                error = "That name is already registered." if "UNIQUE" in str(e) else str(e)

    if qr_id:
        body = f"""
<div class="page"><div class="card card-wide" style="position:relative;z-index:1;text-align:center">
  <div style="font-size:3rem;margin-bottom:.5rem">✅</div>
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.3rem">Account Created!</h2>
  <p style="color:var(--text2);font-size:.85rem;margin-bottom:1.2rem">{drole}: {dname}</p>
  <div class="alert alert-info show" style="text-align:left">
    ⚠️ <strong>Save your QR ID below</strong> — use it to log in via QR. Shown only once!
  </div>
  <div style="font-family:var(--mono);font-size:.72rem;color:var(--text2);
    background:var(--card2);border:1px solid var(--border);border-radius:8px;
    padding:.6rem .9rem;word-break:break-all;line-height:1.7;margin:.75rem 0">{qr_id}</div>
  <p style="font-size:.78rem;color:var(--text3);margin-bottom:1.2rem">Copy and save this ID somewhere safe</p>
  <a href="/login" class="btn btn-teal btn-block">Go to Login →</a>
</div></div>"""
    else:
        err = f'<div class="alert alert-err show">{error}</div>' if error else ""
        body = f"""
<div class="page"><div class="card card-wide" style="position:relative;z-index:1">
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">Create Staff Account</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.5rem">For Doctors and Nurses only</p>
  {err}
  <form method="POST">
    <div class="field"><label>Role</label>
      <div style="display:flex;gap:.75rem">
        <label style="display:flex;align-items:center;gap:.45rem;cursor:pointer;
          text-transform:none;font-size:.88rem;font-weight:500;color:var(--text)">
          <input type="radio" name="role" value="Doctor" checked style="accent-color:var(--teal)"> Doctor
        </label>
        <label style="display:flex;align-items:center;gap:.45rem;cursor:pointer;
          text-transform:none;font-size:.88rem;font-weight:500;color:var(--text)">
          <input type="radio" name="role" value="Nurse" style="accent-color:var(--teal)"> Nurse
        </label>
      </div>
    </div>
    <div class="field"><label>Full Name</label>
      <input name="name" type="text" placeholder="e.g. Dr. Maria Santos" required autocomplete="off"></div>
    <div class="field"><label>Password</label>
      <input name="password" type="password" placeholder="Minimum 6 characters" required></div>
    <div class="field"><label>Confirm Password</label>
      <input name="password2" type="password" placeholder="Re-enter password" required></div>
    <button class="btn btn-teal btn-block" type="submit">Create Account &amp; Get QR ID</button>
  </form>
  <p style="text-align:center;margin-top:1rem;font-size:.82rem;color:var(--text3)">
    Already registered? <a href="/login" style="color:var(--teal2)">Sign in</a>
    &nbsp;·&nbsp;<a href="/" style="color:var(--text3)">← Home</a>
  </p>
</div></div>"""
    return base_page("Register", body)


@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        mode = request.form.get("mode","pw")
        if mode == "pw":
            name = request.form.get("name","").strip()
            pw   = request.form.get("password","").strip()
            with get_db() as c:
                row = c.execute("SELECT * FROM doctors WHERE name=? AND password=?",
                                (name, hashlib.sha256(pw.encode()).hexdigest())).fetchone()
            if row:
                session["doctor_id"]   = row["id"]
                session["doctor_name"] = row["name"]
                session["doctor_role"] = row["role"]
                return redirect(url_for("dashboard"))
            error = "Incorrect name or password."
        else:
            qr = request.form.get("qr_id","").strip()
            with get_db() as c:
                row = c.execute("SELECT * FROM doctors WHERE qr_id=?",(qr,)).fetchone()
            if row:
                session["doctor_id"]   = row["id"]
                session["doctor_name"] = row["name"]
                session["doctor_role"] = row["role"]
                return redirect(url_for("dashboard"))
            error = "Invalid QR ID."

    err = f'<div class="alert alert-err show">{error}</div>' if error else ""
    body = f"""
<div class="page"><div class="card" style="position:relative;z-index:1">
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">Staff Sign In</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.4rem">Doctors &amp; Nurses only</p>
  <div class="tabs">
    <button class="tab active" id="tab-pw-btn" onclick="switchTab('pw')">🔑 Password</button>
    <button class="tab"        id="tab-qr-btn" onclick="switchTab('qr')">📷 QR Scan</button>
  </div>
  {err}
  <div id="panel-pw">
    <form method="POST">
      <input type="hidden" name="mode" value="pw">
      <div class="field"><label>Full Name</label>
        <input name="name" type="text" placeholder="e.g. Dr. Admin" required autocomplete="off"></div>
      <div class="field"><label>Password</label>
        <input name="password" type="password" placeholder="Enter your password" required></div>
      <button class="btn btn-teal btn-block" type="submit">Sign In →</button>
    </form>
  </div>
  <div id="panel-qr" style="display:none">
    <div id="qr-reader" style="width:100%;border-radius:12px;overflow:hidden;margin-bottom:.75rem"></div>
    <div id="qr-status" class="alert" style="margin-bottom:.75rem"></div>
    <form method="POST" id="qr-form">
      <input type="hidden" name="mode" value="qr">
      <input type="hidden" name="qr_id" id="qr-id-input">
    </form>
    <div class="alert alert-info show" style="font-size:.79rem">
      📷 Point your camera at the QR code — or paste QR ID below
    </div>
    <form method="POST" style="margin-top:.75rem">
      <input type="hidden" name="mode" value="qr">
      <div class="field"><label>Or Paste QR ID</label>
        <input name="qr_id" type="text" placeholder="Paste your QR ID here"></div>
      <button class="btn btn-teal btn-block" type="submit">Verify &amp; Sign In →</button>
    </form>
  </div>
  <p style="text-align:center;margin-top:1.1rem;font-size:.82rem;color:var(--text3)">
    No account? <a href="/register" style="color:var(--teal2)">Register here</a>
    &nbsp;·&nbsp;<a href="/" style="color:var(--text3)">← Home</a>
  </p>
</div></div>
<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
<script>
var scanner=null;
function switchTab(t){{
  document.getElementById('panel-pw').style.display=t==='pw'?'block':'none';
  document.getElementById('panel-qr').style.display=t==='qr'?'block':'none';
  document.getElementById('tab-pw-btn').className='tab'+(t==='pw'?' active':'');
  document.getElementById('tab-qr-btn').className='tab'+(t==='qr'?' active':'');
  if(t==='qr')startQR(); else stopQR();
}}
function startQR(){{
  if(scanner)return;
  scanner=new Html5Qrcode("qr-reader");
  scanner.start({{facingMode:"environment"}},{{fps:10,qrbox:{{width:240,height:240}}}},
    function(text){{
      stopQR();
      document.getElementById('qr-id-input').value=text;
      document.getElementById('qr-form').submit();
    }},function(){{}}).catch(function(){{
      var s=document.getElementById('qr-status');
      s.className='alert alert-err show';
      s.textContent='Camera unavailable — please paste QR ID below.';
    }});
}}
function stopQR(){{if(scanner){{scanner.stop().catch(function(){{}});scanner=null;}}}}
</script>"""
    return base_page("Login", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/admission", methods=["GET","POST"])
def admission():
    error = ""; success_data = None
    if request.method == "POST":
        name = request.form.get("name","").strip()
        age  = request.form.get("age","").strip()
        cont = request.form.get("contact","").strip()
        date = request.form.get("appt_date","").strip()
        time = request.form.get("appt_time","").strip()
        syms = request.form.get("symptoms","").strip()
        if not name:  error = "Full name is required."
        elif not date: error = "Please choose a date."
        elif not time: error = "Please choose a time."
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
                qno = next_queue(date)
                with get_db() as c:
                    c.execute("""INSERT INTO patients
                        (name,age,contact,date_of_appointment,appointment_time,queue_no,symptoms)
                        VALUES(?,?,?,?,?,?,?)""",
                        (name,age,cont,date,time,qno,syms))
                    c.commit()
                success_data = {"name":name,"date":date,"time":time,"queue":qno}
            except ValueError:
                error = "Invalid date format."

    today = datetime.now().strftime("%Y-%m-%d")
    chips = ["Fever","Cough","Headache","Sore Throat","Stomach Pain",
             "Dizziness","Fatigue","Rashes","Chest Pain","Shortness of Breath"]

    if success_data:
        body = f"""
<div class="page" style="align-items:flex-start;padding-top:2.5rem">
<div class="card card-wide" style="position:relative;z-index:1;margin:0 auto;text-align:center;padding:.5rem 0">
  <div style="font-size:3.5rem;margin-bottom:.6rem">✅</div>
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.3rem">Appointment Booked!</h2>
  <p style="color:var(--text2);font-size:.85rem;margin-bottom:1rem">The doctor will see you when your number is called.</p>
  <div class="queue-display">
    <div class="queue-label">Your Queue Number</div>
    <div class="queue-number">{success_data['queue']}</div>
  </div>
  <div style="background:var(--card2);border:1px solid var(--border);border-radius:14px;padding:1rem;margin:.75rem 0;text-align:left">
    <div class="info-row"><span class="info-lbl">Patient</span><span class="info-val">{success_data['name']}</span></div>
    <div class="info-row"><span class="info-lbl">Date</span><span class="info-val">{success_data['date']}</span></div>
    <div class="info-row"><span class="info-lbl">Time</span><span class="info-val">{success_data['time']}</span></div>
  </div>
  <a href="/admission" class="btn btn-ghost btn-block" style="margin-top:.8rem">Book Another</a>
  <a href="/"          class="btn btn-teal  btn-block" style="margin-top:.5rem">← Back to Home</a>
</div></div>"""
    else:
        chip_html = "".join(f'<span class="chip" onclick="toggleChip(this,\'{c}\')">{c}</span>' for c in chips)
        time_opts = ""
        for h in range(8,18):
            for m in ["00","30"]:
                ampm = "AM" if h < 12 else "PM"
                h12  = h if h <= 12 else h - 12
                time_opts += f'<option value="{h:02d}:{m} {ampm}">{h12:02d}:{m} {ampm}</option>'
        err = f'<div class="alert alert-err show">{error}</div>' if error else ""
        body = f"""
<div class="page" style="align-items:flex-start;padding-top:2.5rem">
<div class="card card-wide" style="position:relative;z-index:1;margin:0 auto">
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">🩺 Admission Form</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.5rem">
    Choose your preferred date &amp; time — a queue number is assigned automatically</p>
  {err}
  <form method="POST">
    <div class="field"><label>Full Name *</label>
      <input name="name" type="text" placeholder="Your full name" required></div>
    <div class="grid2">
      <div class="field"><label>Age</label>
        <input name="age" type="number" placeholder="e.g. 25" min="0" max="120"></div>
      <div class="field"><label>Contact No.</label>
        <input name="contact" type="text" placeholder="09XXXXXXXXX"></div>
    </div>
    <div class="grid2">
      <div class="field"><label>Preferred Date *</label>
        <input name="appt_date" type="date" min="{today}" value="{today}" required></div>
      <div class="field"><label>Preferred Time *</label>
        <select name="appt_time" required>{time_opts}</select></div>
    </div>
    <div class="field"><label>Symptoms / Reason</label>
      <div style="margin-bottom:.5rem">{chip_html}</div>
      <textarea name="symptoms" id="syms" rows="3" placeholder="Describe your symptoms..."></textarea>
    </div>
    <button class="btn btn-gold btn-block" type="submit">Submit Appointment Request</button>
  </form>
  <p style="text-align:center;margin-top:1rem;font-size:.82rem;color:var(--text3)">
    <a href="/" style="color:var(--text3)">← Back to Home</a></p>
</div></div>
<script>
var picked=new Set();
function toggleChip(el,val){{
  if(picked.has(val)){{picked.delete(val);el.classList.remove('sel');}}
  else{{picked.add(val);el.classList.add('sel');}}
  var ta=document.getElementById('syms');
  var manual=ta.value.split('\\n').filter(function(l){{return !Array.from(picked).includes(l.trim())&&l.trim();}});
  ta.value=Array.from(picked).concat(manual).join('\\n');
}}
</script>"""
    return base_page("Admission", body)


@app.route("/dashboard")
@login_required
def dashboard():
    flt = request.args.get("f","All")
    with get_db() as c:
        all_p = [dict(r) for r in c.execute(
            "SELECT * FROM patients ORDER BY date_of_appointment ASC, queue_no ASC").fetchall()]
    counts = {"Pending":0,"In Progress":0,"Examined":0,"Cancelled":0}
    for p in all_p:
        if p["status"] in counts: counts[p["status"]] += 1

    rows = ""
    for p in all_p:
        if flt != "All" and p["status"] != flt: continue
        rows += f"""
        <tr onclick="location.href='/examine/{p['id']}'"
          data-status="{p['status']}" data-name="{p['name']}" data-queue="{p['queue_no']}">
          <td style="font-family:var(--mono);font-weight:700;color:var(--teal2)">#{p['queue_no']}</td>
          <td style="font-weight:600">{p['name']}<br>
            <span style="font-size:.74rem;color:var(--text2);font-weight:400">{p.get('age','')}{"&nbsp;·&nbsp;" if p.get('age') and p.get('contact') else ""}{p.get('contact','')}</span>
          </td>
          <td style="font-size:.82rem;color:var(--text2)">{p['date_of_appointment']}</td>
          <td style="font-size:.82rem;color:var(--text2)">{p['appointment_time']}</td>
          <td>{sym_short(p['symptoms'])}</td>
          <td><span class="badge {badge(p['status'])}">{p['status']}</span></td>
          <td onclick="event.stopPropagation()">
            <a href="/examine/{p['id']}" class="btn btn-teal btn-sm">Examine</a>
          </td>
        </tr>"""
    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;padding:3rem;color:var(--text3)">No patients found.</td></tr>'

    def af(f): return "active" if flt == f else ""

    body = f"""
<div class="dash-wrap">
  <aside class="sidebar">
    <div class="sb-head">
      <div class="sb-role">{session['doctor_role']}</div>
      <div class="sb-name">{session['doctor_name']}</div>
    </div>
    <nav class="sb-nav">
      <a class="sb-link {'active' if flt=='All' else ''}" href="/dashboard?f=All">
        📋 All Patients <span class="sb-count">{len(all_p)}</span></a>
      <a class="sb-link {'active' if flt=='Pending' else ''}" href="/dashboard?f=Pending">
        🟡 Pending <span class="sb-count gold">{counts['Pending']}</span></a>
      <a class="sb-link {'active' if flt=='In Progress' else ''}" href="/dashboard?f=In Progress">
        🔵 In Progress</a>
      <a class="sb-link {'active' if flt=='Examined' else ''}" href="/dashboard?f=Examined">
        ✅ Examined <span class="sb-count" style="background:rgba(34,197,94,.3);color:var(--green2)">{counts['Examined']}</span></a>
      <a class="sb-link {'active' if flt=='Cancelled' else ''}" href="/dashboard?f=Cancelled">
        ❌ Cancelled</a>
      <a class="sb-link" href="/statistics" style="margin-top:.5rem;border-top:1px solid var(--border);padding-top:.75rem">
        📊 Statistics</a>
    </nav>
    <div class="sb-foot">
      <a href="/logout" class="btn btn-ghost btn-sm btn-block">🚪 Sign Out</a>
    </div>
  </aside>
  <main class="main-content">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem;flex-wrap:wrap;gap:.6rem">
      <h1 style="font-size:1.4rem;font-weight:800">Patient Queue</h1>
      <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
        <input class="srch" id="srch" type="text" placeholder="Search patient..." oninput="doSearch()">
        <a href="/dashboard" class="btn btn-ghost btn-sm">↻ Refresh</a>
      </div>
    </div>
    <div class="stats">
      <div class="stat teal"><div class="stat-val">{len(all_p)}</div><div class="stat-lbl">Total</div></div>
      <div class="stat gold"><div class="stat-val">{counts['Pending']}</div><div class="stat-lbl">Pending</div></div>
      <div class="stat teal"><div class="stat-val">{counts['In Progress']}</div><div class="stat-lbl">In Progress</div></div>
      <div class="stat green"><div class="stat-val">{counts['Examined']}</div><div class="stat-lbl">Examined</div></div>
      <div class="stat red"><div class="stat-val">{counts['Cancelled']}</div><div class="stat-lbl">Cancelled</div></div>
    </div>
    <div class="table-wrap">
      <div class="table-top">
        <span style="font-weight:700;font-size:.95rem">Appointments</span>
        <div style="display:flex;gap:.35rem;flex-wrap:wrap">
          <button class="fbtn {af('All')}"         data-filter=""            onclick="filterTable('',this)">All</button>
          <button class="fbtn {af('Pending')}"     data-filter="Pending"     onclick="filterTable('Pending',this)">Pending</button>
          <button class="fbtn {af('In Progress')}" data-filter="In Progress" onclick="filterTable('In Progress',this)">In Progress</button>
          <button class="fbtn {af('Examined')}"    data-filter="Examined"    onclick="filterTable('Examined',this)">Examined</button>
          <button class="fbtn {af('Cancelled')}"   data-filter="Cancelled"   onclick="filterTable('Cancelled',this)">Cancelled</button>
        </div>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th>Queue</th><th>Patient</th><th>Date</th><th>Time</th>
            <th>Symptoms</th><th>Status</th><th>Action</th>
          </tr></thead>
          <tbody id="tbody">{rows}</tbody>
        </table>
      </div>
    </div>
  </main>
</div>
<script>
function filterTable(status,btn){{
  document.querySelectorAll('.fbtn').forEach(function(b){{b.classList.remove('active');}});
  if(btn)btn.classList.add('active');
  var srch=(document.getElementById('srch')||{{value:''}}).value.toLowerCase();
  document.querySelectorAll('tbody tr[data-status]').forEach(function(r){{
    var ms=!status||r.dataset.status===status;
    var mq=!srch||r.dataset.name.toLowerCase().includes(srch)||r.dataset.queue.includes(srch);
    r.style.display=(ms&&mq)?'':'none';
  }});
}}
function doSearch(){{
  var active=document.querySelector('.fbtn.active');
  filterTable(active?active.dataset.filter:'',active);
}}
</script>"""
    return base_page("Dashboard", body)


@app.route("/examine/<int:pid>", methods=["GET","POST"])
@login_required
def examine(pid):
    error = ""; saved = ""; show_receipt = False
    with get_db() as c:
        patient = dict(c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone())

    if request.method == "POST":
        action = request.form.get("action","save")
        diag   = request.form.get("diagnosis","").strip()
        presc  = request.form.get("prescription","").strip()
        notes  = request.form.get("notes","").strip()

        if action in ("done","save") and not diag:
            error = "Diagnosis is required."
        else:
            status = "Examined" if action == "done" else \
                     "Cancelled" if action == "cancel" else "In Progress"
            examined_at = datetime.now().strftime("%B %d, %Y %I:%M %p") if action == "done" else patient.get("examined_at","")
            with get_db() as c:
                c.execute("""UPDATE patients SET diagnosis=?,prescription=?,notes=?,
                             status=?,examined_by=?,examined_at=? WHERE id=?""",
                          (diag, presc, notes, status, session["doctor_name"], examined_at, pid))
                c.commit()
                patient = dict(c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone())
            if action == "cancel":
                return redirect(url_for("dashboard"))
            if action == "done":
                show_receipt = True
            else:
                saved = "Saved — marked as In Progress."

    is_examined = patient["status"] == "Examined"
    ro = 'readonly' if is_examined else ''
    fs = 'opacity:.65;pointer-events:none' if is_examined else ''

    receipt_html = ""
    if show_receipt or (is_examined and patient.get("diagnosis")):
        syms_receipt = "".join(
            f'<span style="display:inline-block;background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.2);color:var(--teal2);font-size:.75rem;padding:.22rem .65rem;border-radius:100px;margin:.15rem">{s}</span>'
            for s in re.split(r'[\n,]+', patient['symptoms']) if s.strip())
        notes_block = f"""<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:.9rem">
          <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Doctor Notes</div>
          <div style="font-size:.83rem;white-space:pre-line">{patient.get('notes','')}</div>
        </div>""" if patient.get('notes') else ""
        receipt_html = f"""
<div style="margin-top:2rem" class="no-print">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
    <div style="font-size:1rem;font-weight:700;color:var(--teal2)">🧾 Medical Receipt</div>
    <button onclick="window.print()" class="btn btn-ghost btn-sm no-print">🖨 Print Receipt</button>
  </div>
  <div class="receipt-card" style="background:var(--card2);border:1px solid var(--border);
    border-radius:14px;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
    <div style="text-align:center;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:1rem">
      <div style="font-size:1.3rem;font-weight:700">🏥 MediCare Clinic</div>
      <div style="font-size:.75rem;color:rgba(255,255,255,.35);margin-top:.2rem">Official Medical Receipt</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.25);margin-top:.2rem">Examined: {patient.get('examined_at','')}</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;font-size:.84rem">
      <div><span style="color:rgba(255,255,255,.4)">Patient:</span> <strong>{patient['name']}</strong></div>
      <div><span style="color:rgba(255,255,255,.4)">Date:</span> {patient['date_of_appointment']}</div>
      <div><span style="color:rgba(255,255,255,.4)">Time:</span> {patient['appointment_time']}</div>
      <div><span style="color:rgba(255,255,255,.4)">Doctor:</span> {patient.get('examined_by','')}</div>
    </div>
    <div style="background:rgba(212,168,83,.07);border:1px solid rgba(212,168,83,.15);border-radius:10px;padding:.9rem">
      <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.4rem">Symptoms Reported</div>
      {syms_receipt}
    </div>
    <div style="background:rgba(13,148,136,.07);border:1px solid rgba(13,148,136,.15);border-radius:10px;padding:.9rem">
      <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Diagnosis</div>
      <div style="font-size:.88rem;font-weight:500">{patient['diagnosis']}</div>
    </div>
    <div style="background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.15);border-radius:10px;padding:.9rem">
      <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Prescription</div>
      <div style="font-size:.83rem;white-space:pre-line">{patient.get('prescription','')}</div>
    </div>
    {notes_block}
    <div style="text-align:center;padding-top:.75rem;border-top:1px solid rgba(255,255,255,.07);
      font-size:.72rem;color:rgba(255,255,255,.2)">
      Thank you for trusting MediCare Clinic · Keep this receipt for your records
    </div>
  </div>
</div>"""

    save_btn = """
    <div style="text-align:center;padding:.75rem;background:rgba(34,197,94,.07);
      border:1px solid rgba(34,197,94,.2);border-radius:10px;color:var(--green2);font-size:.85rem">
      ✅ Examination already completed
    </div>""" if is_examined else """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.6rem">
      <button class="btn btn-teal" type="submit" name="action" value="save">💾 Save Progress</button>
      <button class="btn btn-green" type="submit" name="action" value="done"
        onclick="return confirm('Mark as Examined and generate receipt?')">✅ Done Examining</button>
    </div>
    <button class="btn btn-red btn-block" type="submit" name="action" value="cancel"
      onclick="return confirm('Cancel this appointment?')">✖ Cancel Appointment</button>"""

    err_html  = f'<div class="alert alert-err show">{error}</div>' if error else ""
    save_html = f'<div class="alert alert-ok show">{saved}</div>' if saved else ""

    body = f"""
<div style="position:relative;z-index:1;padding:1.5rem;max-width:1100px;margin:0 auto">
  <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap" class="no-print">
    <a href="/dashboard" class="btn btn-ghost btn-sm">← Dashboard</a>
    <h1 style="font-size:1.3rem;font-weight:800">Patient Examination</h1>
    <span class="badge {badge(patient['status'])}">{patient['status']}</span>
  </div>
  <div class="exam-grid">
    <div>
      <div class="card" style="margin-bottom:1rem">
        <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:1rem">Patient Information</h3>
        <div class="info-row"><span class="info-lbl">Name</span><span class="info-val">{patient['name']}</span></div>
        <div class="info-row"><span class="info-lbl">Age</span><span class="info-val">{patient.get('age','') or '—'}</span></div>
        <div class="info-row"><span class="info-lbl">Contact</span><span class="info-val">{patient.get('contact','') or '—'}</span></div>
        <div class="info-row"><span class="info-lbl">Queue #</span>
          <span class="info-val" style="font-family:var(--mono);font-size:1.1rem;color:var(--teal2)">#{patient['queue_no']}</span></div>
        <div class="info-row"><span class="info-lbl">Date</span><span class="info-val">{patient['date_of_appointment']}</span></div>
        <div class="info-row"><span class="info-lbl">Time</span><span class="info-val">{patient['appointment_time']}</span></div>
        <div class="info-row"><span class="info-lbl">Status</span>
          <span class="badge {badge(patient['status'])}">{patient['status']}</span></div>
        {"<div class='info-row'><span class='info-lbl'>Seen by</span><span class='info-val' style='color:var(--teal2)'>"+patient['examined_by']+"</span></div>" if patient.get('examined_by') else ""}
      </div>
      <div class="card">
        <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:.75rem">Symptoms</h3>
        {sym_tags(patient['symptoms']) or '<p style="color:var(--text3);font-size:.83rem">None reported</p>'}
      </div>
    </div>
    <div>
      <div class="card">
        <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:1.2rem">📝 Doctor's Examination</h3>
        {err_html}{save_html}
        <form method="POST" style="{fs}">
          <div class="field"><label>Diagnosis *</label>
            <input name="diagnosis" type="text" placeholder="Enter diagnosis"
              value="{patient.get('diagnosis','')}" required {ro}></div>
          <div class="field"><label>Prescription</label>
            <textarea name="prescription" rows="4"
              placeholder="e.g. Paracetamol 500mg — 1 tablet every 6 hours&#10;Rest for 3 days" {ro}>{patient.get('prescription','')}</textarea></div>
          <div class="field"><label>Notes <span style="font-size:.7rem;color:var(--text3)">(optional)</span></label>
            <textarea name="notes" rows="3"
              placeholder="Follow-up instructions, warnings..." {ro}>{patient.get('notes','')}</textarea></div>
          {save_btn}
        </form>
      </div>
      {receipt_html}
    </div>
  </div>
</div>"""

    nav = f'<div class="nav-actions"><div class="nav-user">{session["doctor_role"]} · <span>{session["doctor_name"]}</span></div><a href="/dashboard" class="btn btn-ghost btn-sm no-print">← Dashboard</a></div>'
    return base_page(f"Examine — {patient['name']}", body, nav)


@app.route("/statistics")
@login_required
def statistics():
    with get_db() as c:
        all_p = [dict(r) for r in c.execute("SELECT * FROM patients").fetchall()]

    total    = len(all_p)
    examined = sum(1 for p in all_p if p["status"] == "Examined")
    pending  = sum(1 for p in all_p if p["status"] == "Pending")
    inprog   = sum(1 for p in all_p if p["status"] == "In Progress")
    cancelled= sum(1 for p in all_p if p["status"] == "Cancelled")
    exam_rate= round(examined/total*100,1) if total else 0

    months_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly = collections.Counter()
    ex_m    = collections.Counter()
    pend_m  = collections.Counter()
    for p in all_p:
        try:
            m = datetime.strptime(p["submitted_at"][:10],"%Y-%m-%d").strftime("%b")
            monthly[m] += 1
            if p["status"] == "Examined": ex_m[m] += 1
            elif p["status"] == "Pending": pend_m[m] += 1
        except Exception:
            pass

    sym_counter  = collections.Counter()
    diag_counter = collections.Counter()
    for p in all_p:
        for s in re.split(r'[\n,]+', p["symptoms"]):
            if s.strip(): sym_counter[s.strip()] += 1
        if p.get("diagnosis","").strip():
            diag_counter[p["diagnosis"].strip()] += 1

    top_syms  = sym_counter.most_common(8)
    top_diags = diag_counter.most_common(6)
    dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    dow_c     = collections.Counter()
    for p in all_p:
        try:
            dow_c[dow_names[datetime.strptime(p["date_of_appointment"],"%Y-%m-%d").weekday()]] += 1
        except Exception:
            pass

    monthly_vals = json.dumps([monthly.get(m,0) for m in months_order])
    ex_vals      = json.dumps([ex_m.get(m,0)    for m in months_order])
    pend_vals    = json.dumps([pend_m.get(m,0)  for m in months_order])
    sym_labels   = json.dumps([x[0] for x in top_syms])
    sym_vals     = json.dumps([x[1] for x in top_syms])
    diag_labels  = json.dumps([x[0] for x in top_diags])
    diag_vals    = json.dumps([x[1] for x in top_diags])
    dow_vals     = json.dumps([dow_c.get(d,0) for d in dow_names])

    body = f"""
<div class="dash-wrap">
  <aside class="sidebar">
    <div class="sb-head">
      <div class="sb-role">{session['doctor_role']}</div>
      <div class="sb-name">{session['doctor_name']}</div>
    </div>
    <nav class="sb-nav">
      <a class="sb-link" href="/dashboard">📋 All Patients</a>
      <a class="sb-link" href="/dashboard?f=Pending">🟡 Pending <span class="sb-count gold">{pending}</span></a>
      <a class="sb-link active" href="/statistics">📊 Statistics</a>
    </nav>
    <div class="sb-foot">
      <a href="/logout" class="btn btn-ghost btn-sm btn-block">🚪 Sign Out</a>
    </div>
  </aside>
  <main class="main-content">
    <h1 style="font-size:1.4rem;font-weight:800;margin-bottom:1.2rem">📊 Statistics &amp; Analytics</h1>
    <div class="stats" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
      <div class="stat teal"><div class="stat-val">{total}</div><div class="stat-lbl">Total Patients</div></div>
      <div class="stat green"><div class="stat-val">{examined}</div><div class="stat-lbl">Examined</div></div>
      <div class="stat gold"><div class="stat-val">{pending}</div><div class="stat-lbl">Pending</div></div>
      <div class="stat teal"><div class="stat-val">{inprog}</div><div class="stat-lbl">In Progress</div></div>
      <div class="stat red"><div class="stat-val">{cancelled}</div><div class="stat-lbl">Cancelled</div></div>
      <div class="stat green"><div class="stat-val">{exam_rate}%</div><div class="stat-lbl">Exam Rate</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
      <div class="chart-card">
        <div class="chart-title">Monthly Admissions</div>
        <canvas id="c1" height="140"></canvas>
      </div>
      <div class="chart-card">
        <div class="chart-title">Examined vs Pending</div>
        <canvas id="c2" height="140"></canvas>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
      <div class="chart-card">
        <div class="chart-title">Top Symptoms</div>
        <canvas id="c3" height="160"></canvas>
      </div>
      <div class="chart-card">
        <div class="chart-title">Top Diagnoses</div>
        <canvas id="c4" height="160"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Appointments by Day of Week</div>
      <canvas id="c5" height="100"></canvas>
    </div>
  </main>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
Chart.defaults.color='rgba(255,255,255,0.5)';
Chart.defaults.borderColor='rgba(255,255,255,0.07)';
var MONTHS={json.dumps(months_order)};
function line(id,labels,datasets){{
  new Chart(document.getElementById(id),{{type:'line',data:{{labels,datasets}},
    options:{{responsive:true,plugins:{{legend:{{display:datasets.length>1,
      labels:{{color:'rgba(255,255,255,.6)',font:{{size:11}}}}}}}},
      scales:{{x:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'rgba(255,255,255,.45)',font:{{size:10}}}}}},
               y:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'rgba(255,255,255,.45)',font:{{size:10}}}},beginAtZero:true}}}}}}}});
}}
function ds(label,data,color){{
  return {{label,data,borderColor:color,backgroundColor:color+'22',
    borderWidth:2.5,pointBackgroundColor:color,pointRadius:4,tension:.35,fill:true}};
}}
line('c1',MONTHS,[ds('Admissions',{monthly_vals},'#14b8a6')]);
line('c2',MONTHS,[ds('Examined',{ex_vals},'#22c55e'),ds('Pending',{pend_vals},'#fbbf24')]);
line('c3',{sym_labels},[ds('Cases',{sym_vals},'#f472b6')]);
line('c4',{diag_labels},[ds('Cases',{diag_vals},'#818cf8')]);
line('c5',{json.dumps(dow_names)},[ds('Appointments',{dow_vals},'#f97316')]);
</script>"""
    return base_page("Statistics", body)


@app.route("/api/status/<int:pid>", methods=["POST"])
@login_required
def api_status(pid):
    status = request.json.get("status","")
    if status not in ("Pending","In Progress","Examined","Cancelled"):
        return jsonify({"ok":False})
    with get_db() as c:
        c.execute("UPDATE patients SET status=? WHERE id=?",(status,pid))
        c.commit()
    return jsonify({"ok":True})


# ══════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n{'='*50}\n  MediCare Web App — http://localhost:{port}\n  Default: Dr. Admin / admin123\n{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_ENV")=="development")
