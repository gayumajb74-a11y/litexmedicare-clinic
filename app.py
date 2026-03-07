"""
MediCare Clinic System — Flask Web App
Run locally:  python app.py
Deploy free:  Railway / Render / PythonAnywhere
"""

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import sqlite3, hashlib, uuid, os, re
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
            CREATE TABLE IF NOT EXISTS staff (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT UNIQUE NOT NULL,
                role       TEXT NOT NULL DEFAULT 'Doctor',
                password   TEXT NOT NULL,
                qr_id      TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS patients (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                age          TEXT NOT NULL DEFAULT '',
                contact      TEXT NOT NULL DEFAULT '',
                appt_date    TEXT NOT NULL,
                appt_time    TEXT NOT NULL,
                queue_no     INTEGER NOT NULL DEFAULT 1,
                symptoms     TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'Waiting',
                diagnosis    TEXT NOT NULL DEFAULT '',
                notes        TEXT NOT NULL DEFAULT '',
                examined_by  TEXT NOT NULL DEFAULT '',
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        if c.execute("SELECT COUNT(*) FROM staff").fetchone()[0] == 0:
            c.execute("INSERT INTO staff(name,role,password,qr_id) VALUES(?,?,?,?)",
                ("Dr. Admin","Doctor",hashlib.sha256(b"admin123").hexdigest(),str(uuid.uuid4())))
            c.commit()

def next_queue(date):
    with get_db() as c:
        r = c.execute("SELECT MAX(queue_no) FROM patients WHERE appt_date=?",(date,)).fetchone()
        return (r[0] or 0) + 1

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "staff_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════
#  HTML TEMPLATE  (single-file, all pages)
# ══════════════════════════════════════════════════════
BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} · MediCare</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:      #080f1a;
  --bg2:     #0d1829;
  --card:    #111f33;
  --card2:   #162540;
  --border:  #1e3254;
  --border2: #243d60;
  --teal:    #0d9488;
  --teal2:   #14b8a6;
  --teal3:   #5eead4;
  --gold:    #d4a853;
  --gold2:   #f0c060;
  --red:     #ef4444;
  --red2:    #fca5a5;
  --green:   #22c55e;
  --green2:  #86efac;
  --text:    #e8f0fe;
  --text2:   #7a9cc0;
  --text3:   #3d5a7a;
  --white:   #ffffff;
  --font:    'Plus Jakarta Sans', sans-serif;
  --mono:    'JetBrains Mono', monospace;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.6;
}

/* ── NOISE + GLOW ── */
body::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 80% 50% at 10% 20%, rgba(13,148,136,.12) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 90% 80%, rgba(212,168,83,.07) 0%, transparent 55%),
    radial-gradient(ellipse 40% 60% at 50% 50%, rgba(14,24,42,.8) 0%, transparent 70%);
}
body::after {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,.015) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.015) 1px, transparent 1px);
  background-size: 48px 48px;
}

/* ── NAV ── */
.nav {
  position: sticky; top: 0; z-index: 100;
  padding: .85rem 2rem;
  display: flex; align-items: center; gap: .75rem;
  background: rgba(8,15,26,.92);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
.nav-logo { display: flex; align-items: center; gap: .6rem; }
.nav-logo-icon {
  width: 32px; height: 32px; border-radius: 9px;
  background: linear-gradient(135deg, var(--teal), var(--teal2));
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
}
.nav-logo-text { font-weight: 800; font-size: 1.1rem; letter-spacing: -.02em; }
.nav-actions { margin-left: auto; display: flex; gap: .6rem; align-items: center; }
.nav-user {
  font-size: .78rem; color: var(--text2);
  background: var(--card); border: 1px solid var(--border);
  padding: .3rem .75rem; border-radius: 100px;
}
.nav-user span { color: var(--teal2); font-weight: 600; }

/* ── PAGE WRAPPER ── */
.page {
  position: relative; z-index: 1;
  min-height: calc(100vh - 57px);
  display: flex; align-items: center; justify-content: center;
  padding: 2.5rem 1.25rem;
}
.page-wide { align-items: flex-start; padding-top: 2rem; }

/* ── CARD ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.2rem 2rem;
  width: 100%; max-width: 460px;
  animation: slideUp .4s cubic-bezier(.16,1,.3,1);
}
.card-wide  { max-width: 560px; }
.card-full  { max-width: 100%; }

@keyframes slideUp {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── FORM ELEMENTS ── */
.field { margin-bottom: 1.1rem; }
.field label {
  display: block; font-size: .72rem; font-weight: 600;
  color: var(--text2); letter-spacing: .08em; text-transform: uppercase;
  margin-bottom: .42rem;
}
.field input, .field textarea, .field select {
  width: 100%; padding: .72rem 1rem;
  background: var(--card2); border: 1px solid var(--border);
  border-radius: 10px; color: var(--text);
  font-size: .9rem; font-family: var(--font);
  outline: none; transition: border-color .2s, box-shadow .2s;
  resize: vertical;
}
.field input:focus, .field textarea:focus, .field select:focus {
  border-color: var(--teal);
  box-shadow: 0 0 0 3px rgba(13,148,136,.12);
}
.field input::placeholder, .field textarea::placeholder { color: var(--text3); }
.field select option { background: var(--card2); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: .9rem; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: .9rem; }

/* ── BUTTONS ── */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: .45rem;
  padding: .75rem 1.5rem; border: none; border-radius: 11px;
  font-size: .88rem; font-weight: 700; font-family: var(--font);
  cursor: pointer; transition: all .2s; text-decoration: none;
  letter-spacing: -.01em;
}
.btn-block { display: flex; width: 100%; }
.btn-teal  { background: var(--teal);  color: #fff; }
.btn-teal:hover  { background: var(--teal2); transform: translateY(-1px); box-shadow: 0 8px 24px rgba(13,148,136,.3); }
.btn-gold  { background: var(--gold);  color: #0a0f1a; }
.btn-gold:hover  { background: var(--gold2); transform: translateY(-1px); box-shadow: 0 8px 24px rgba(212,168,83,.3); }
.btn-ghost { background: var(--card2); border: 1px solid var(--border); color: var(--text2); }
.btn-ghost:hover { border-color: var(--teal); color: var(--teal2); }
.btn-red   { background: rgba(239,68,68,.15); border: 1px solid rgba(239,68,68,.3); color: var(--red2); }
.btn-red:hover   { background: rgba(239,68,68,.25); }
.btn-green { background: rgba(34,197,94,.15); border: 1px solid rgba(34,197,94,.3); color: var(--green2); }
.btn-green:hover { background: rgba(34,197,94,.25); }
.btn-sm { padding: .42rem .85rem; font-size: .78rem; border-radius: 8px; }

/* ── ALERTS ── */
.alert {
  padding: .75rem 1rem; border-radius: 10px;
  font-size: .84rem; margin-bottom: 1rem; display: none;
}
.alert.show { display: block; }
.alert-err { background: rgba(239,68,68,.12); border: 1px solid rgba(239,68,68,.28); color: var(--red2); }
.alert-ok  { background: rgba(13,148,136,.12); border: 1px solid rgba(13,148,136,.28); color: var(--teal3); }
.alert-info{ background: rgba(212,168,83,.1);  border: 1px solid rgba(212,168,83,.25); color: var(--gold2); }

/* ── TABS ── */
.tabs {
  display: flex; gap: 3px; padding: 3px;
  background: var(--card2); border: 1px solid var(--border);
  border-radius: 12px; margin-bottom: 1.4rem;
}
.tab {
  flex: 1; padding: .55rem; border-radius: 9px; border: none;
  background: transparent; color: var(--text2);
  font-size: .82rem; font-weight: 600; font-family: var(--font);
  cursor: pointer; transition: all .2s;
}
.tab.active {
  background: var(--teal); color: #fff;
  box-shadow: 0 2px 12px rgba(13,148,136,.3);
}

/* ── BADGE ── */
.badge {
  display: inline-block; padding: .22rem .65rem;
  border-radius: 100px; font-size: .72rem; font-weight: 700;
  letter-spacing: .04em;
}
.badge-wait { background: rgba(212,168,83,.15); border: 1px solid rgba(212,168,83,.3); color: var(--gold2); }
.badge-prog { background: rgba(13,148,136,.15); border: 1px solid rgba(13,148,136,.3); color: var(--teal3); }
.badge-done { background: rgba(34,197,94,.13);  border: 1px solid rgba(34,197,94,.3);  color: var(--green2); }
.badge-canc { background: rgba(239,68,68,.12);  border: 1px solid rgba(239,68,68,.28); color: var(--red2); }

/* ── DASHBOARD LAYOUT ── */
.dash-wrap { display: flex; min-height: calc(100vh - 57px); position: relative; z-index: 1; }
.sidebar {
  width: 230px; flex-shrink: 0;
  background: var(--bg2); border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  position: sticky; top: 57px; height: calc(100vh - 57px); overflow-y: auto;
}
.sb-head { padding: 1.3rem 1.1rem; border-bottom: 1px solid var(--border); }
.sb-role {
  font-size: .68rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--teal2); margin-bottom: .2rem;
}
.sb-name { font-weight: 700; font-size: .95rem; }
.sb-nav { flex: 1; padding: .75rem .6rem; display: flex; flex-direction: column; gap: 2px; }
.sb-link {
  display: flex; align-items: center; gap: .6rem;
  padding: .6rem .85rem; border-radius: 9px;
  color: var(--text2); font-size: .83rem; font-weight: 500;
  text-decoration: none; transition: all .18s; cursor: pointer;
  border: none; background: transparent; width: 100%; text-align: left;
  font-family: var(--font);
}
.sb-link:hover { background: rgba(13,148,136,.1); color: var(--teal2); }
.sb-link.active { background: rgba(13,148,136,.16); color: var(--teal2); font-weight: 700; }
.sb-count {
  margin-left: auto; font-size: .68rem; font-weight: 700;
  padding: .1rem .45rem; border-radius: 100px;
  background: var(--teal); color: #fff;
}
.sb-count.gold { background: rgba(212,168,83,.25); color: var(--gold2); }
.sb-foot { padding: .85rem 1rem; border-top: 1px solid var(--border); }
.main-content { flex: 1; padding: 1.5rem; overflow-x: auto; }

/* ── STATS GRID ── */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: .85rem; margin-bottom: 1.5rem; }
.stat {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 14px; padding: 1.1rem 1rem;
}
.stat.teal  { border-color: rgba(13,148,136,.3); background: rgba(13,148,136,.08); }
.stat.gold  { border-color: rgba(212,168,83,.3); background: rgba(212,168,83,.07); }
.stat.green { border-color: rgba(34,197,94,.3);  background: rgba(34,197,94,.07); }
.stat.red   { border-color: rgba(239,68,68,.3);  background: rgba(239,68,68,.07); }
.stat-val { font-size: 1.9rem; font-weight: 800; line-height: 1; margin-bottom: .25rem; font-family: var(--mono); }
.stat.teal  .stat-val { color: var(--teal2); }
.stat.gold  .stat-val { color: var(--gold2); }
.stat.green .stat-val { color: var(--green2); }
.stat.red   .stat-val { color: var(--red2); }
.stat-lbl { font-size: .7rem; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: .07em; }

/* ── TABLE ── */
.table-wrap {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; overflow: hidden;
}
.table-top {
  padding: 1rem 1.2rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: .6rem;
}
.table-title { font-weight: 700; font-size: .95rem; }
.filter-row { display: flex; gap: .35rem; flex-wrap: wrap; }
.fbtn {
  padding: .35rem .75rem; border-radius: 7px; font-size: .74rem;
  font-weight: 600; font-family: var(--font); cursor: pointer;
  border: 1px solid var(--border); background: var(--card2); color: var(--text2);
  transition: all .18s;
}
.fbtn:hover, .fbtn.active { background: rgba(13,148,136,.15); border-color: var(--teal); color: var(--teal2); }
.search-input {
  padding: .42rem .85rem; border-radius: 8px; font-size: .82rem;
  background: var(--card2); border: 1px solid var(--border); color: var(--text);
  font-family: var(--font); outline: none; width: 200px; transition: border-color .2s;
}
.search-input:focus { border-color: var(--teal); }
.search-input::placeholder { color: var(--text3); }
table { width: 100%; border-collapse: collapse; }
thead th {
  padding: .65rem 1rem; text-align: left;
  font-size: .67rem; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--text2);
  border-bottom: 1px solid var(--border); background: var(--card2);
}
tbody tr { transition: background .12s; }
tbody tr:hover { background: rgba(255,255,255,.02); }
tbody td {
  padding: .85rem 1rem; font-size: .85rem;
  border-bottom: 1px solid rgba(255,255,255,.04);
}
tbody tr:last-child td { border-bottom: none; }
.td-name { font-weight: 600; }
.td-queue {
  font-family: var(--mono); font-size: .9rem; font-weight: 700;
  color: var(--teal2);
}
.action-btns { display: flex; gap: .35rem; }

/* ── MODAL ── */
.modal-overlay {
  display: none; position: fixed; inset: 0; z-index: 500;
  background: rgba(0,0,0,.7); backdrop-filter: blur(6px);
  align-items: center; justify-content: center; padding: 1rem;
}
.modal-overlay.open { display: flex; }
.modal {
  background: var(--card); border: 1px solid var(--border2);
  border-radius: 20px; padding: 1.8rem; width: 100%; max-width: 560px;
  max-height: 90vh; overflow-y: auto;
  animation: slideUp .3s cubic-bezier(.16,1,.3,1);
}
.modal h3 { font-size: 1.1rem; font-weight: 800; margin-bottom: 1.2rem; }
.modal-btns { display: flex; gap: .6rem; margin-top: 1.2rem; }
.modal-btns .btn { flex: 1; }

/* ── INFO ROWS ── */
.info-row {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: .5rem 0; border-bottom: 1px solid rgba(255,255,255,.05);
  font-size: .85rem;
}
.info-row:last-child { border: none; }
.info-lbl { color: var(--text2); flex-shrink: 0; min-width: 100px; }
.info-val { font-weight: 600; text-align: right; word-break: break-word; }

/* ── QR BOX ── */
.qr-box {
  background: #fff; border-radius: 14px; padding: 1.2rem;
  display: inline-flex; margin: 1rem auto; display: block; width: fit-content;
}
.qr-id {
  font-family: var(--mono); font-size: .72rem; color: var(--text2);
  background: var(--card2); border: 1px solid var(--border);
  border-radius: 8px; padding: .6rem .9rem; word-break: break-all;
  line-height: 1.7; margin: .75rem 0;
}

/* ── QUEUE NUMBER ── */
.queue-display {
  background: linear-gradient(135deg, var(--teal), var(--teal2));
  border-radius: 16px; padding: 1.5rem; text-align: center; margin: 1.2rem 0;
}
.queue-number { font-size: 4rem; font-weight: 800; font-family: var(--mono); line-height: 1; }
.queue-label  { font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; opacity: .75; margin-bottom: .3rem; }

/* ── LANDING ── */
.landing-hero { max-width: 900px; width: 100%; }
.landing-title {
  font-size: clamp(2rem,5vw,3.5rem); font-weight: 800;
  line-height: 1.1; letter-spacing: -.03em; margin-bottom: .75rem;
}
.landing-title .hl { color: var(--teal2); }
.landing-sub { color: var(--text2); font-size: 1.05rem; max-width: 440px; line-height: 1.7; margin-bottom: 2.5rem; }
.portal-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px,1fr)); gap: 1.1rem; }
.portal-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 18px; padding: 1.8rem; transition: border-color .2s, transform .2s;
}
.portal-card:hover { border-color: var(--teal); transform: translateY(-2px); }
.portal-icon { font-size: 2.4rem; margin-bottom: .85rem; }
.portal-title { font-size: 1.1rem; font-weight: 800; margin-bottom: .35rem; }
.portal-desc { color: var(--text2); font-size: .83rem; line-height: 1.65; margin-bottom: 1.2rem; }
.portal-btns { display: flex; gap: .5rem; flex-wrap: wrap; }

/* ── EXAM LAYOUT ── */
.exam-grid { display: grid; grid-template-columns: 320px 1fr; gap: 1.2rem; }
@media(max-width:780px) { .exam-grid { grid-template-columns: 1fr; } }

/* ── RESPONSIVE ── */
@media(max-width:700px) {
  .sidebar { display: none; }
  .grid2, .grid3 { grid-template-columns: 1fr; }
  .card { padding: 1.5rem 1.2rem; }
  .exam-grid { grid-template-columns: 1fr; }
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }

/* ── CHIP SYMPTOMS ── */
.chip-row { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .6rem; }
.chip {
  padding: .28rem .75rem; border-radius: 100px; font-size: .74rem; font-weight: 600;
  border: 1px solid var(--border); color: var(--text2); background: var(--card2);
  cursor: pointer; transition: all .18s; user-select: none;
}
.chip.selected { background: rgba(212,168,83,.15); border-color: rgba(212,168,83,.4); color: var(--gold2); }

/* ── STAG ── */
.stag {
  display: inline-block; background: rgba(13,148,136,.1); border: 1px solid rgba(13,148,136,.22);
  color: var(--teal3); font-size: .7rem; padding: .14rem .5rem;
  border-radius: 100px; margin: .1rem;
}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav">
  <div class="nav-logo">
    <div class="nav-logo-icon">🏥</div>
    <span class="nav-logo-text">MediCare</span>
  </div>
  <div class="nav-actions">
    {% if session.staff_name %}
      <div class="nav-user">{{ session.staff_role }} · <span>{{ session.staff_name }}</span></div>
      <a href="/logout" class="btn btn-ghost btn-sm">Sign Out</a>
    {% else %}
      <a href="/login" class="btn btn-ghost btn-sm">Staff Login</a>
    {% endif %}
  </div>
</nav>

{% block content %}{% endblock %}

<script>
// ── Tab switcher ──
function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelector('.tab[data-tab="'+tab+'"]').classList.add('active');
  document.getElementById('panel-'+tab).style.display = 'block';
}

// ── Filter table ──
function filterTable(status, btn) {
  document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  var rows = document.querySelectorAll('tbody tr[data-status]');
  var srch = (document.getElementById('srch') || {value:''}).value.toLowerCase();
  rows.forEach(function(r) {
    var match_status = !status || r.dataset.status === status;
    var match_srch   = !srch   || r.dataset.name.toLowerCase().includes(srch) || r.dataset.queue.includes(srch);
    r.style.display  = (match_status && match_srch) ? '' : 'none';
  });
}

// ── Search ──
function doSearch() {
  var active = document.querySelector('.fbtn.active');
  var status = active ? active.dataset.filter : '';
  filterTable(status, active);
}

// ── Modal ──
function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open');
});
</script>
</body>
</html>"""

# ══════════════════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════════════════

LANDING = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page" style="align-items:flex-start;padding-top:4rem">
  <div class="landing-hero" style="position:relative;z-index:1">

    <div style="display:inline-flex;align-items:center;gap:.5rem;
      background:rgba(13,148,136,.1);border:1px solid rgba(13,148,136,.25);
      border-radius:100px;padding:.32rem 1rem;font-size:.72rem;font-weight:700;
      color:var(--teal2);letter-spacing:.1em;text-transform:uppercase;margin-bottom:1.4rem">
      ● Clinic Management System
    </div>

    <h1 class="landing-title">Healthcare<br>Made <span class="hl">Simple</span></h1>
    <p class="landing-sub">Manage patient appointments, doctor examinations, and clinic workflows — accessible from any device, anywhere.</p>

    <div class="portal-grid">
      <!-- Staff Portal -->
      <div class="portal-card">
        <div class="portal-icon">👨‍⚕️</div>
        <div class="portal-title">Staff Portal</div>
        <p class="portal-desc">For Doctors & Nurses. View the patient queue, examine patients, update diagnosis and notes.</p>
        <div class="portal-btns">
          <a href="/login"    class="btn btn-teal btn-sm">Sign In</a>
          <a href="/register" class="btn btn-ghost btn-sm">Register</a>
        </div>
      </div>
      <!-- Patient Portal -->
      <div class="portal-card" style="border-color:rgba(212,168,83,.25)">
        <div class="portal-icon">🩺</div>
        <div class="portal-title">Patient Admission</div>
        <p class="portal-desc">Book your appointment. Choose a date and time — you'll get a queue number instantly.</p>
        <div class="portal-btns">
          <a href="/admission" class="btn btn-gold btn-sm">Book Appointment</a>
        </div>
      </div>
    </div>

  </div>
</div>
{% endblock %}""")

# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template_string(LANDING, title="Home")


@app.route("/register", methods=["GET","POST"])
def register():
    error = ""; qr_id = ""; staff_name = ""; staff_role = ""
    if request.method == "POST":
        name = request.form.get("name","").strip()
        role = request.form.get("role","Doctor").strip()
        pw   = request.form.get("password","").strip()
        pw2  = request.form.get("password2","").strip()
        if not name:        error = "Full name is required."
        elif len(pw) < 6:   error = "Password must be at least 6 characters."
        elif pw != pw2:     error = "Passwords do not match."
        else:
            qr = str(uuid.uuid4())
            try:
                with get_db() as c:
                    c.execute("INSERT INTO staff(name,role,password,qr_id) VALUES(?,?,?,?)",
                              (name, role, hashlib.sha256(pw.encode()).hexdigest(), qr))
                    c.commit()
                qr_id = qr; staff_name = name; staff_role = role
            except Exception as e:
                error = "That name is already registered." if "UNIQUE" in str(e) else str(e)

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
<div class="card card-wide" style="position:relative;z-index:1">

{% if qr_id %}
  <div style="text-align:center">
    <div style="font-size:3rem;margin-bottom:.5rem">✅</div>
    <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.3rem">Account Created!</h2>
    <p style="color:var(--text2);font-size:.85rem;margin-bottom:1.2rem">{{ staff_role }}: {{ staff_name }}</p>
    <div class="alert alert-info show" style="text-align:left">
      ⚠️ <strong>Save your QR ID below</strong> — use it to log in via QR instead of password. This is shown only once!
    </div>
    <div class="qr-id">{{ qr_id }}</div>
    <p style="font-size:.78rem;color:var(--text3);margin-bottom:1.2rem">Copy and save this ID somewhere safe (Notes, screenshot, etc.)</p>
    <a href="/login" class="btn btn-teal btn-block">Go to Login →</a>
  </div>

{% else %}
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">Create Staff Account</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.5rem">For Doctors and Nurses only — patients use the Admission form</p>

  {% if error %}
  <div class="alert alert-err show">{{ error }}</div>
  {% endif %}

  <form method="POST">
    <div class="field">
      <label>Role</label>
      <div style="display:flex;gap:.75rem">
        <label style="display:flex;align-items:center;gap:.45rem;cursor:pointer;text-transform:none;font-size:.88rem;font-weight:500;color:var(--text)">
          <input type="radio" name="role" value="Doctor" checked style="accent-color:var(--teal);width:16px;height:16px"> Doctor
        </label>
        <label style="display:flex;align-items:center;gap:.45rem;cursor:pointer;text-transform:none;font-size:.88rem;font-weight:500;color:var(--text)">
          <input type="radio" name="role" value="Nurse"  style="accent-color:var(--teal);width:16px;height:16px"> Nurse
        </label>
      </div>
    </div>
    <div class="field">
      <label>Full Name</label>
      <input name="name" type="text" placeholder="e.g. Dr. Maria Santos" required autocomplete="off">
    </div>
    <div class="field">
      <label>Password</label>
      <input name="password" type="password" placeholder="Minimum 6 characters" required>
    </div>
    <div class="field">
      <label>Confirm Password</label>
      <input name="password2" type="password" placeholder="Re-enter password" required>
    </div>
    <button class="btn btn-teal btn-block" type="submit">Create Account &amp; Get QR ID</button>
  </form>
  <p style="text-align:center;margin-top:1rem;font-size:.82rem;color:var(--text3)">
    Already registered? <a href="/login" style="color:var(--teal2)">Sign in</a>
  </p>
{% endif %}

</div>
</div>
{% endblock %}""")
    return render_template_string(tmpl, title="Register",
                                  error=error, qr_id=qr_id,
                                  staff_name=staff_name, staff_role=staff_role)


@app.route("/login", methods=["GET","POST"])
def login():
    error = ""
    if request.method == "POST":
        mode = request.form.get("mode","pw")
        if mode == "pw":
            name = request.form.get("name","").strip()
            pw   = request.form.get("password","").strip()
            with get_db() as c:
                row = c.execute("SELECT * FROM staff WHERE name=? AND password=?",
                                (name, hashlib.sha256(pw.encode()).hexdigest())).fetchone()
            if row:
                session["staff_id"]   = row["id"]
                session["staff_name"] = row["name"]
                session["staff_role"] = row["role"]
                return redirect(url_for("dashboard"))
            error = "Incorrect name or password."
        else:
            qr = request.form.get("qr_id","").strip()
            with get_db() as c:
                row = c.execute("SELECT * FROM staff WHERE qr_id=?",(qr,)).fetchone()
            if row:
                session["staff_id"]   = row["id"]
                session["staff_name"] = row["name"]
                session["staff_role"] = row["role"]
                return redirect(url_for("dashboard"))
            error = "Invalid QR ID."

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page">
<div class="card" style="position:relative;z-index:1">
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">Staff Sign In</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.4rem">Doctors &amp; Nurses only</p>

  <div class="tabs">
    <button class="tab active" data-tab="pw" onclick="switchTab('pw')">🔑 Password</button>
    <button class="tab"        data-tab="qr" onclick="switchTab('qr')">📋 QR Code ID</button>
  </div>

  {% if error %}
  <div class="alert alert-err show">{{ error }}</div>
  {% endif %}

  <!-- Password tab -->
  <div class="tab-panel" id="panel-pw">
    <form method="POST">
      <input type="hidden" name="mode" value="pw">
      <div class="field"><label>Full Name</label>
        <input name="name" type="text" placeholder="e.g. Dr. Admin" required autocomplete="off"></div>
      <div class="field"><label>Password</label>
        <input name="password" type="password" placeholder="Enter your password" required></div>
      <button class="btn btn-teal btn-block" type="submit">Sign In →</button>
    </form>
  </div>

  <!-- QR tab -->
  <div class="tab-panel" id="panel-qr" style="display:none">
    <form method="POST">
      <input type="hidden" name="mode" value="qr">
      <div class="field"><label>QR Code ID</label>
        <input name="qr_id" type="text" placeholder="Paste your QR ID here" required autocomplete="off"></div>
      <div class="alert alert-info show" style="font-size:.79rem">
        📋 Copy the QR ID that was shown when you registered and paste it above.
      </div>
      <button class="btn btn-teal btn-block" style="margin-top:.75rem" type="submit">Verify &amp; Sign In →</button>
    </form>
  </div>

  <p style="text-align:center;margin-top:1.1rem;font-size:.82rem;color:var(--text3)">
    No account? <a href="/register" style="color:var(--teal2)">Register here</a>
    &nbsp;·&nbsp; <a href="/" style="color:var(--text3)">← Home</a>
  </p>
</div>
</div>
{% endblock %}""")
    return render_template_string(tmpl, title="Login", error=error)


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
        if not name: error = "Full name is required."
        elif not date: error = "Please choose a date."
        elif not time: error = "Please choose a time."
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
                qno = next_queue(date)
                with get_db() as c:
                    c.execute("INSERT INTO patients(name,age,contact,appt_date,appt_time,queue_no,symptoms) VALUES(?,?,?,?,?,?,?)",
                              (name,age,cont,date,time,qno,syms))
                    c.commit()
                success_data = {"name":name,"date":date,"time":time,"queue":qno}
            except ValueError:
                error = "Invalid date format. Use YYYY-MM-DD."

    today = datetime.now().strftime("%Y-%m-%d")
    chips = ["Fever","Cough","Headache","Sore Throat","Stomach Pain",
             "Dizziness","Fatigue","Rashes","Chest Pain","Shortness of Breath"]

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="page" style="align-items:flex-start;padding-top:2.5rem">
<div class="card card-wide" style="position:relative;z-index:1;margin:0 auto">

{% if success_data %}
  <div style="text-align:center;padding:.5rem 0">
    <div style="font-size:3.5rem;margin-bottom:.6rem">✅</div>
    <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.3rem">Appointment Booked!</h2>
    <p style="color:var(--text2);font-size:.85rem;margin-bottom:1rem">The doctor will see you when your number is called.</p>
    <div class="queue-display">
      <div class="queue-label">Your Queue Number</div>
      <div class="queue-number">{{ success_data.queue }}</div>
    </div>
    <div class="card" style="text-align:left;background:var(--card2);border-color:var(--border2)">
      <div class="info-row"><span class="info-lbl">Patient</span><span class="info-val">{{ success_data.name }}</span></div>
      <div class="info-row"><span class="info-lbl">Date</span><span class="info-val">{{ success_data.date }}</span></div>
      <div class="info-row"><span class="info-lbl">Time</span><span class="info-val">{{ success_data.time }}</span></div>
    </div>
    <a href="/admission" class="btn btn-ghost btn-block" style="margin-top:.8rem">Book Another</a>
    <a href="/"          class="btn btn-teal  btn-block" style="margin-top:.5rem">← Back to Home</a>
  </div>

{% else %}
  <h2 style="font-size:1.5rem;font-weight:800;margin-bottom:.25rem">🩺 Admission Form</h2>
  <p style="color:var(--text2);font-size:.84rem;margin-bottom:1.5rem">Choose your preferred date &amp; time — a queue number is assigned automatically</p>

  {% if error %}
  <div class="alert alert-err show">{{ error }}</div>
  {% endif %}

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
        <input name="appt_date" type="date" min="{{ today }}" value="{{ today }}" required></div>
      <div class="field"><label>Preferred Time *</label>
        <select name="appt_time" required>
          {% for h in range(8,18) %}
            {% for m in ['00','30'] %}
              {% set ampm = 'AM' if h < 12 else 'PM' %}
              {% set h12  = h if h <= 12 else h-12 %}
              <option value="{{ '%02d'|format(h) }}:{{ m }} {{ ampm }}">{{ '%02d'|format(h12) }}:{{ m }} {{ ampm }}</option>
            {% endfor %}
          {% endfor %}
        </select>
      </div>
    </div>
    <div class="field">
      <label>Symptoms / Reason</label>
      <div class="chip-row" id="chips">
        {% for chip in chips %}
        <span class="chip" onclick="toggleChip(this,'{{ chip }}')">{{ chip }}</span>
        {% endfor %}
      </div>
      <textarea name="symptoms" id="syms" rows="3" placeholder="Describe your symptoms..."></textarea>
    </div>
    <button class="btn btn-gold btn-block" type="submit">Submit Appointment Request</button>
  </form>
  <p style="text-align:center;margin-top:1rem;font-size:.82rem;color:var(--text3)">
    <a href="/" style="color:var(--text3)">← Back to Home</a>
  </p>
{% endif %}

</div>
</div>
<script>
var picked = new Set();
function toggleChip(el, val) {
  if (picked.has(val)) { picked.delete(val); el.classList.remove('selected'); }
  else                 { picked.add(val);    el.classList.add('selected'); }
  var ta = document.getElementById('syms');
  var manual = ta.value.split('\\n').filter(function(l){ return !Array.from(picked).includes(l.trim()) && l.trim(); });
  ta.value = Array.from(picked).concat(manual).join('\\n');
}
</script>
{% endblock %}""")
    return render_template_string(tmpl, title="Admission",
                                  error=error, success_data=success_data,
                                  today=today, chips=chips)


@app.route("/dashboard")
@login_required
def dashboard():
    flt = request.args.get("f","All")
    with get_db() as c:
        all_p = [dict(r) for r in c.execute(
            "SELECT * FROM patients ORDER BY appt_date ASC, queue_no ASC").fetchall()]
    counts = {"Waiting":0,"In Progress":0,"Done Appointing":0,"Cancelled":0}
    for p in all_p:
        if p["status"] in counts: counts[p["status"]] += 1

    def badge_class(s):
        return {"Waiting":"badge-wait","In Progress":"badge-prog",
                "Done Appointing":"badge-done","Cancelled":"badge-canc"}.get(s,"badge-wait")
    def sym_short(s, n=3):
        parts = [x.strip() for x in re.split(r'[\n,]+', s) if x.strip()]
        tags  = "".join(f'<span class="stag">{p}</span>' for p in parts[:n])
        if len(parts) > n: tags += f'<span class="stag" style="opacity:.5">+{len(parts)-n}</span>'
        return tags

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div class="dash-wrap">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sb-head">
      <div class="sb-role">{{ session.staff_role }}</div>
      <div class="sb-name">{{ session.staff_name }}</div>
    </div>
    <nav class="sb-nav">
      <a class="sb-link {% if flt=='All' %}active{% endif %}" href="/dashboard?f=All">
        📋 All Patients <span class="sb-count">{{ all_p|length }}</span>
      </a>
      <a class="sb-link {% if flt=='Waiting' %}active{% endif %}" href="/dashboard?f=Waiting">
        🟡 Waiting <span class="sb-count gold">{{ counts.Waiting }}</span>
      </a>
      <a class="sb-link {% if flt=='In Progress' %}active{% endif %}" href="/dashboard?f=In Progress">
        🔵 In Progress
      </a>
      <a class="sb-link {% if flt=='Done Appointing' %}active{% endif %}" href="/dashboard?f=Done Appointing">
        ✅ Done Appointing
      </a>
      <a class="sb-link {% if flt=='Cancelled' %}active{% endif %}" href="/dashboard?f=Cancelled">
        ❌ Cancelled
      </a>
    </nav>
    <div class="sb-foot">
      <a href="/logout" class="btn btn-ghost btn-sm btn-block">🚪 Sign Out</a>
    </div>
  </aside>

  <!-- Main -->
  <main class="main-content">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.2rem;flex-wrap:wrap;gap:.6rem">
      <h1 style="font-size:1.4rem;font-weight:800">Patient Queue</h1>
      <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
        <input class="search-input" id="srch" type="text" placeholder="Search patient..." oninput="doSearch()">
        <a href="/dashboard" class="btn btn-ghost btn-sm">↻ Refresh</a>
      </div>
    </div>

    <!-- Stats -->
    <div class="stats">
      <div class="stat teal">
        <div class="stat-val">{{ all_p|length }}</div>
        <div class="stat-lbl">Total</div>
      </div>
      <div class="stat gold">
        <div class="stat-val">{{ counts.Waiting }}</div>
        <div class="stat-lbl">Waiting</div>
      </div>
      <div class="stat teal">
        <div class="stat-val">{{ counts['In Progress'] }}</div>
        <div class="stat-lbl">In Progress</div>
      </div>
      <div class="stat green">
        <div class="stat-val">{{ counts['Done Appointing'] }}</div>
        <div class="stat-lbl">Done</div>
      </div>
      <div class="stat red">
        <div class="stat-val">{{ counts.Cancelled }}</div>
        <div class="stat-lbl">Cancelled</div>
      </div>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <div class="table-top">
        <span class="table-title">Appointments</span>
        <div class="filter-row">
          <button class="fbtn {% if flt=='All'            %}active{% endif %}" data-filter=""               onclick="filterTable('',this)">All</button>
          <button class="fbtn {% if flt=='Waiting'        %}active{% endif %}" data-filter="Waiting"        onclick="filterTable('Waiting',this)">Waiting</button>
          <button class="fbtn {% if flt=='In Progress'    %}active{% endif %}" data-filter="In Progress"    onclick="filterTable('In Progress',this)">In Progress</button>
          <button class="fbtn {% if flt=='Done Appointing'%}active{% endif %}" data-filter="Done Appointing"onclick="filterTable('Done Appointing',this)">Done</button>
          <button class="fbtn {% if flt=='Cancelled'      %}active{% endif %}" data-filter="Cancelled"      onclick="filterTable('Cancelled',this)">Cancelled</button>
        </div>
      </div>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Queue</th><th>Patient</th><th>Date</th><th>Time</th><th>Symptoms</th><th>Status</th><th>Action</th>
        </tr></thead>
        <tbody>
        {% if all_p %}
          {% for p in all_p %}
          {% if flt == 'All' or p.status == flt %}
          <tr data-status="{{ p.status }}" data-name="{{ p.name }}" data-queue="{{ p.queue_no }}">
            <td class="td-queue">#{{ p.queue_no }}</td>
            <td class="td-name">{{ p.name }}<br>
              <span style="font-size:.74rem;color:var(--text2);font-weight:400">{{ p.age }}{% if p.age and p.contact %} · {% endif %}{{ p.contact }}</span>
            </td>
            <td style="font-size:.82rem;color:var(--text2)">{{ p.appt_date }}</td>
            <td style="font-size:.82rem;color:var(--text2)">{{ p.appt_time }}</td>
            <td>{{ sym_short(p.symptoms)|safe }}</td>
            <td><span class="badge {{ badge_class(p.status) }}">{{ p.status }}</span></td>
            <td>
              <div class="action-btns">
                <a href="/examine/{{ p.id }}" class="btn btn-teal btn-sm">Examine</a>
              </div>
            </td>
          </tr>
          {% endif %}
          {% endfor %}
        {% else %}
          <tr><td colspan="7" style="text-align:center;padding:3rem;color:var(--text3)">
            No patients yet. Share the admission link with patients.
          </td></tr>
        {% endif %}
        </tbody>
      </table>
      </div>
    </div>
  </main>
</div>
{% endblock %}""")
    return render_template_string(tmpl, title="Dashboard",
                                  all_p=all_p, counts=counts, flt=flt,
                                  badge_class=badge_class, sym_short=sym_short)


@app.route("/examine/<int:pid>", methods=["GET","POST"])
@login_required
def examine(pid):
    error = ""; saved = ""
    with get_db() as c:
        patient = dict(c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone())

    if request.method == "POST":
        action   = request.form.get("action","save")
        diag     = request.form.get("diagnosis","").strip()
        notes    = request.form.get("notes","").strip()
        status   = "Done Appointing" if action == "done" else \
                   "Cancelled"       if action == "cancel" else "In Progress"
        if action in ("done","save") and not diag:
            error = "Diagnosis is required."
        else:
            with get_db() as c:
                c.execute("UPDATE patients SET diagnosis=?,notes=?,status=?,examined_by=? WHERE id=?",
                          (diag, notes, status, session["staff_name"], pid))
                c.commit()
                patient = dict(c.execute("SELECT * FROM patients WHERE id=?",(pid,)).fetchone())
            if action == "done" or action == "cancel":
                return redirect(url_for("dashboard"))
            saved = "Saved — marked as In Progress."

    def sym_tags(s):
        parts = [x.strip() for x in re.split(r'[\n,]+',s) if x.strip()]
        return "".join(f'<span class="stag">{p}</span>' for p in parts)

    tmpl = BASE.replace("{% block content %}{% endblock %}", """
{% block content %}
<div style="position:relative;z-index:1;padding:1.5rem;max-width:1100px;margin:0 auto">

  <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap">
    <a href="/dashboard" class="btn btn-ghost btn-sm">← Dashboard</a>
    <h1 style="font-size:1.3rem;font-weight:800">Patient Examination</h1>
    <span class="badge badge-wait" style="font-family:var(--mono);font-size:.85rem">Queue #{{ patient.queue_no }}</span>
  </div>

  <div class="exam-grid">

    <!-- Left: Patient Info -->
    <div>
      <div class="card" style="margin-bottom:1rem">
        <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:1rem">Patient Information</h3>
        <div class="info-row"><span class="info-lbl">Name</span>     <span class="info-val">{{ patient.name }}</span></div>
        <div class="info-row"><span class="info-lbl">Age</span>      <span class="info-val">{{ patient.age or '—' }}</span></div>
        <div class="info-row"><span class="info-lbl">Contact</span>  <span class="info-val">{{ patient.contact or '—' }}</span></div>
        <div class="info-row"><span class="info-lbl">Queue #</span>  <span class="info-val" style="font-family:var(--mono);font-size:1.1rem;color:var(--teal2)">#{{ patient.queue_no }}</span></div>
        <div class="info-row"><span class="info-lbl">Date</span>     <span class="info-val">{{ patient.appt_date }}</span></div>
        <div class="info-row"><span class="info-lbl">Time</span>     <span class="info-val">{{ patient.appt_time }}</span></div>
        <div class="info-row"><span class="info-lbl">Status</span>
          <span class="badge {{ badge_class(patient.status) }}">{{ patient.status }}</span>
        </div>
        {% if patient.examined_by %}
        <div class="info-row"><span class="info-lbl">Seen by</span> <span class="info-val" style="color:var(--teal2)">{{ patient.examined_by }}</span></div>
        {% endif %}
      </div>
      <div class="card">
        <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:.75rem">Symptoms</h3>
        <div>{{ sym_tags(patient.symptoms)|safe }}</div>
        {% if not patient.symptoms %}
        <p style="color:var(--text3);font-size:.83rem">None reported</p>
        {% endif %}
      </div>
    </div>

    <!-- Right: Examination Form -->
    <div class="card">
      <h3 style="font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text2);margin-bottom:1.2rem">📝 Doctor's Examination</h3>

      {% if error %}<div class="alert alert-err show">{{ error }}</div>{% endif %}
      {% if saved  %}<div class="alert alert-ok  show">{{ saved }}</div>{% endif %}

      <form method="POST">
        <div class="field">
          <label>Diagnosis *</label>
          <input name="diagnosis" type="text" placeholder="Enter diagnosis" value="{{ patient.diagnosis }}" required>
        </div>
        <div class="field">
          <label>Description / Notes</label>
          <textarea name="notes" rows="7" placeholder="Treatment plan, prescriptions, observations...">{{ patient.notes }}</textarea>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.6rem">
          <button class="btn btn-teal"  type="submit" name="action" value="save">💾 Save Progress</button>
          <button class="btn btn-green" type="submit" name="action" value="done"
                  onclick="return confirm('Mark as Done Appointing?')">✅ Done Examining</button>
        </div>
        <button class="btn btn-red btn-block" type="submit" name="action" value="cancel"
                onclick="return confirm('Cancel this appointment?')">✖ Cancel Appointment</button>
      </form>
    </div>

  </div>
</div>
{% endblock %}""")

    def badge_class(s):
        return {"Waiting":"badge-wait","In Progress":"badge-prog",
                "Done Appointing":"badge-done","Cancelled":"badge-canc"}.get(s,"badge-wait")

    return render_template_string(tmpl, title=f"Examine — {patient['name']}",
                                  patient=patient, error=error, saved=saved,
                                  badge_class=badge_class, sym_tags=sym_tags)


# ── API: quick status update ──────────────────────────────────────────
@app.route("/api/status/<int:pid>", methods=["POST"])
@login_required
def api_status(pid):
    status = request.json.get("status","")
    if status not in ("Waiting","In Progress","Done Appointing","Cancelled"):
        return jsonify({"ok":False,"error":"Invalid status"})
    with get_db() as c:
        c.execute("UPDATE patients SET status=? WHERE id=?", (status, pid))
        c.commit()
    return jsonify({"ok":True})


# ══════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    print()
    print("=" * 52)
    print("  MediCare Web App")
    print("=" * 52)
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://0.0.0.0:{port}")
    print()
    print("  Default login: Dr. Admin / admin123")
    print("=" * 52)
    app.run(host="0.0.0.0", port=port, debug=debug)
