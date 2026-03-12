"""
==============================================
  MediCare Clinic System
  Pure Python - NO external dependencies
  Run: python clinic.py
  Open: http://localhost:8080
==============================================
  Default Doctor: Dr. Admin / admin123
==============================================
  FLOW:
  1. Patient submits admission form -> status: Pending
  2. Doctor clicks patient row -> Examine page
  3. Doctor fills checkup + prescription -> status: Examined
  4. Doctor clicks Back -> Dashboard shows Examined (green)
==============================================
"""

import http.server
import urllib.parse
import sqlite3
import hashlib
import json
import os
import uuid
import re
from datetime import datetime
from http.cookies import SimpleCookie

DB = "clinic.db"
PORT = 8080
SESSIONS = {}


# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                qr_id TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_of_appointment TEXT NOT NULL,
                appointment_time TEXT NOT NULL,
                symptoms TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                diagnosis TEXT DEFAULT '',
                prescription TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                examined_at TEXT DEFAULT '',
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Migration: add examine columns if they don't exist
        for col, definition in [
            ("diagnosis", "TEXT DEFAULT ''"),
            ("prescription", "TEXT DEFAULT ''"),
            ("notes", "TEXT DEFAULT ''"),
            ("examined_at", "TEXT DEFAULT ''"),
        ]:
            try:
                db.execute(f"ALTER TABLE patients ADD COLUMN {col} {definition}")
                db.commit()
            except Exception:
                pass

        cur = db.execute("SELECT COUNT(*) as c FROM doctors")
        if cur.fetchone()["c"] == 0:
            pw = hashlib.sha256("admin123".encode()).hexdigest()
            qr = str(uuid.uuid4())
            db.execute("INSERT INTO doctors (name, password, qr_id) VALUES (?,?,?)",
                       ("Dr. Admin", pw, qr))
            db.commit()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ─────────────────────────────────────────────
#  HTML HELPERS
# ─────────────────────────────────────────────
def base_style():
    return """
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#0a1628;--navy2:#0f1f38;--teal:#0d9488;--teal-light:#14b8a6;--gold:#d4a853}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--navy);min-height:100vh;color:#fff}
.bg{position:fixed;inset:0;z-index:0;
  background:radial-gradient(ellipse at 20% 50%,rgba(13,148,136,.14) 0%,transparent 60%),
             radial-gradient(ellipse at 80% 20%,rgba(212,168,83,.09) 0%,transparent 50%)}
.grid{position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(rgba(255,255,255,.03) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,255,255,.03) 1px,transparent 1px);
  background-size:60px 60px}
nav{position:fixed;top:0;left:0;right:0;z-index:10;padding:1rem 2rem;
  display:flex;align-items:center;gap:.75rem;
  border-bottom:1px solid rgba(255,255,255,.06);backdrop-filter:blur(10px);
  background:rgba(10,22,40,.85)}
.logo{font-size:1.3rem;font-weight:700;color:#fff}
.back{margin-left:auto;color:rgba(255,255,255,.4);font-size:.85rem;text-decoration:none}
.back:hover{color:#fff}
main{position:relative;z-index:1;flex:1;display:flex;align-items:center;
  justify-content:center;padding:5rem 1rem 2rem;min-height:100vh}
.panel{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
  border-radius:24px;padding:2.5rem 2rem;width:100%;max-width:460px;
  animation:fadeUp .5s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.picon{width:58px;height:58px;background:linear-gradient(135deg,rgba(13,148,136,.25),rgba(13,148,136,.05));
  border:1px solid rgba(13,148,136,.3);border-radius:16px;
  display:flex;align-items:center;justify-content:center;font-size:1.7rem;margin-bottom:1.25rem}
h2{font-size:1.75rem;font-weight:700;margin-bottom:.35rem}
.sub{color:rgba(255,255,255,.4);font-size:.88rem;margin-bottom:1.75rem}
.field{margin-bottom:1.1rem}
label{display:block;font-size:.75rem;color:rgba(255,255,255,.45);
  margin-bottom:.45rem;letter-spacing:.06em;text-transform:uppercase}
input,textarea,select{width:100%;padding:.8rem 1rem;
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  border-radius:12px;color:#fff;font-size:.92rem;outline:none;
  transition:border-color .2s;font-family:inherit;resize:vertical}
input:focus,textarea:focus,select:focus{border-color:var(--teal)}
input::placeholder,textarea::placeholder{color:rgba(255,255,255,.2)}
input[type=date]::-webkit-calendar-picker-indicator,
input[type=time]::-webkit-calendar-picker-indicator{filter:invert(.5);cursor:pointer}
select option{background:#0f1f38;color:#fff}
.row{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.btn{width:100%;padding:.85rem;border:none;border-radius:12px;cursor:pointer;
  font-size:.92rem;font-weight:600;font-family:inherit;
  background:linear-gradient(135deg,var(--teal),var(--teal-light));color:#fff;
  transition:opacity .2s;margin-top:.4rem}
.btn:hover{opacity:.85}
.btn-gold{background:linear-gradient(135deg,var(--gold),#e8c06a);color:var(--navy)}
.msg{padding:.7rem 1rem;border-radius:10px;font-size:.83rem;margin-bottom:1rem;display:none}
.msg.error{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#fca5a5}
.msg.success{background:rgba(13,148,136,.15);border:1px solid rgba(13,148,136,.3);color:var(--teal-light)}
.tabs{display:flex;gap:.4rem;margin-bottom:1.5rem;background:rgba(0,0,0,.2);
  border-radius:12px;padding:4px}
.tab{flex:1;text-align:center;padding:.55rem;border-radius:9px;font-size:.83rem;
  cursor:pointer;color:rgba(255,255,255,.4);transition:all .2s;
  font-family:inherit;border:none;background:transparent}
.tab.active{background:rgba(13,148,136,.25);color:var(--teal-light);
  border:1px solid rgba(13,148,136,.3)}
.hidden{display:none!important}
</style>"""

def page(title, body, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - MediCare</title>
{base_style()}
{extra_head}
</head>
<body>
<div class="bg"></div><div class="grid"></div>
{body}
</body>
</html>"""


# ─────────────────────────────────────────────
#  PAGE BUILDERS
# ─────────────────────────────────────────────
def page_landing():
    body = """
<nav>
  <span>🏥</span><span class="logo">MediCare Clinic</span>
</nav>
<main style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2rem">
  <div style="text-align:center;animation:fadeUp .6s ease">
    <div style="display:inline-block;border:1px solid rgba(13,148,136,.4);color:var(--teal-light);
      font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;padding:.4rem 1.2rem;
      border-radius:100px;margin-bottom:1.5rem;background:rgba(13,148,136,.08)">
      Patient &amp; Doctor Portal
    </div>
    <h1 style="font-size:clamp(2.2rem,5vw,4rem);line-height:1.15;margin-bottom:1rem">
      Healthcare Made <span style="color:var(--teal-light)">Simple</span>
    </h1>
    <p style="color:rgba(255,255,255,.4);max-width:440px;margin:0 auto;line-height:1.7;font-size:.95rem">
      Streamlined clinic management — book appointments and manage patient care.
    </p>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
    gap:1.25rem;max-width:800px;width:100%;padding:0 1rem;animation:fadeUp .7s .15s ease both">
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
      border-radius:20px;padding:2rem 1.75rem;text-align:center">
      <div style="font-size:2.5rem;margin-bottom:1rem">👨‍⚕️</div>
      <div style="font-size:1.2rem;font-weight:700;margin-bottom:.5rem">Doctor Portal</div>
      <p style="color:rgba(255,255,255,.35);font-size:.83rem;line-height:1.6;margin-bottom:1.5rem">
        Access dashboard, view appointments, manage patient records.
      </p>
      <div style="display:flex;gap:.6rem;justify-content:center;flex-wrap:wrap">
        <a href="/doctor/login" style="background:linear-gradient(135deg,var(--teal),var(--teal-light));
          color:#fff;padding:.6rem 1.3rem;border-radius:100px;text-decoration:none;font-size:.83rem;font-weight:600">
          Sign In
        </a>
        <a href="/doctor/register" style="background:transparent;border:1px solid rgba(13,148,136,.4);
          color:var(--teal-light);padding:.6rem 1.3rem;border-radius:100px;text-decoration:none;font-size:.83rem">
          Register
        </a>
      </div>
    </div>
    <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
      border-radius:20px;padding:2rem 1.75rem;text-align:center">
      <div style="font-size:2.5rem;margin-bottom:1rem">🩺</div>
      <div style="font-size:1.2rem;font-weight:700;margin-bottom:.5rem">Patient Admission</div>
      <p style="color:rgba(255,255,255,.35);font-size:.83rem;line-height:1.6;margin-bottom:1.5rem">
        Submit your appointment form with name, date, time and symptoms.
      </p>
      <a href="/patient/admission" style="display:inline-block;
        background:linear-gradient(135deg,var(--gold),#e8c06a);
        color:#0a1628;padding:.6rem 1.5rem;border-radius:100px;
        text-decoration:none;font-size:.83rem;font-weight:700">
        Book Appointment
      </a>
    </div>
  </div>
</main>"""
    return page("Home", body)


def page_doctor_register(error="", success_qr="", success_name=""):
    if success_qr:
        body = f"""
<nav><span>🏥</span><span class="logo">MediCare</span>
  <a href="/" class="back">← Home</a></nav>
<main>
  <div class="panel" style="text-align:center">
    <div style="font-size:3.5rem;margin-bottom:1rem">✅</div>
    <h2>Account Created!</h2>
    <p class="sub">Your QR code is below — save it to log in via QR scan</p>
    <div style="background:#fff;border-radius:16px;padding:1.25rem;display:inline-block;margin-bottom:1.25rem">
      <div id="qrcode"></div>
    </div>
    <div style="background:rgba(212,168,83,.1);border:1px solid rgba(212,168,83,.3);
      border-radius:10px;padding:.9rem;font-size:.8rem;color:rgba(212,168,83,.9);
      margin-bottom:1.5rem;text-align:left;line-height:1.6">
      <strong style="display:block;margin-bottom:.3rem">Save your QR code!</strong>
      Screenshot this QR code now — it is your secure login key.
    </div>
    <a href="/doctor/login" class="btn" style="display:block;text-decoration:none;text-align:center">
      Go to Login
    </a>
  </div>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
new QRCode(document.getElementById("qrcode"),{{
  text:"{success_qr}",width:200,height:200,
  colorDark:"#0a1628",colorLight:"#ffffff",
  correctLevel:QRCode.CorrectLevel.H
}});
</script>"""
        return page("Registered", body)

    err_html = f'<div class="msg error" style="display:block">{error}</div>' if error else ""
    body = f"""
<nav><span>🏥</span><span class="logo">MediCare</span>
  <a href="/" class="back">← Home</a></nav>
<main>
  <div class="panel">
    <div class="picon">📋</div>
    <h2>Create Account</h2>
    <p class="sub">Register as a doctor — a unique QR ID will be generated</p>
    {err_html}
    <form method="POST" action="/doctor/register">
      <div class="field">
        <label>Full Name</label>
        <input name="name" type="text" placeholder="e.g. Dr. Maria Santos" required autocomplete="off">
      </div>
      <div class="field">
        <label>Password</label>
        <input name="password" type="password" placeholder="At least 6 characters" required>
      </div>
      <button class="btn" type="submit">Create Account &amp; Get QR</button>
    </form>
    <p style="text-align:center;margin-top:1.25rem;font-size:.83rem;color:rgba(255,255,255,.3)">
      Already have an account? <a href="/doctor/login" style="color:var(--teal-light)">Sign in</a>
    </p>
  </div>
</main>"""
    return page("Register", body)


def page_doctor_login(error=""):
    err_html = f'<div class="msg error" style="display:block">{error}</div>' if error else ""
    body = f"""
<nav><span>🏥</span><span class="logo">MediCare</span>
  <a href="/" class="back">← Home</a></nav>
<main>
  <div class="panel">
    <div class="picon">👨‍⚕️</div>
    <h2>Doctor Sign In</h2>
    <p class="sub">Access your clinic dashboard</p>
    <div class="tabs">
      <button class="tab active" onclick="switchTab('pw',this)">🔑 Password</button>
      <button class="tab" onclick="switchTab('qr',this)">📷 QR Scan</button>
    </div>
    <div id="tab-pw">
      {err_html}
      <form method="POST" action="/doctor/login">
        <div class="field">
          <label>Full Name</label>
          <input name="name" type="text" placeholder="e.g. Dr. Admin" required autocomplete="off">
        </div>
        <div class="field">
          <label>Password</label>
          <input name="password" type="password" placeholder="Enter your password" required>
        </div>
        <button class="btn" type="submit">Sign In to Dashboard</button>
      </form>
    </div>
    <div id="tab-qr" class="hidden">
      <div style="background:rgba(13,148,136,.08);border:1px solid rgba(13,148,136,.15);
        border-radius:10px;padding:.75rem;font-size:.8rem;color:rgba(255,255,255,.35);
        text-align:center;margin-bottom:1rem">
        📋 Show your QR code to the camera
      </div>
      <div id="qr-reader" style="width:100%;border-radius:12px;overflow:hidden"></div>
      <div id="qr-status" class="msg" style="margin-top:.75rem"></div>
    </div>
  </div>
</main>
<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
<script>
let scanner=null;
function switchTab(tab,btn){{
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-pw').classList.toggle('hidden',tab!=='pw');
  document.getElementById('tab-qr').classList.toggle('hidden',tab!=='qr');
  if(tab==='qr') startQR(); else stopQR();
}}
function startQR(){{
  if(scanner) return;
  scanner=new Html5Qrcode("qr-reader");
  scanner.start({{facingMode:"environment"}},{{fps:10,qrbox:{{width:240,height:240}}}},
    async(text)=>{{
      stopQR();
      const st=document.getElementById('qr-status');
      st.className='msg success';st.style.display='block';st.textContent='Verifying...';
      const r=await fetch('/doctor/qr-verify',{{method:'POST',
        headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{qr_id:text}})}});
      const d=await r.json();
      if(d.success){{st.textContent='Welcome '+d.name+'! Redirecting...';
        setTimeout(()=>location.href='/doctor/dashboard',1000);}}
      else{{st.className='msg error';st.textContent='Invalid QR';
        setTimeout(startQR,2000);}}
    }},()=>{{}}).catch(()=>{{
      const st=document.getElementById('qr-status');
      st.className='msg error';st.style.display='block';
      st.textContent='Camera unavailable. Use password login.';
    }});
}}
function stopQR(){{
  if(scanner){{scanner.stop().catch(()=>{{}});scanner=null;}}
}}
</script>"""
    return page("Login", body)


def page_patient_admission(error=""):
    err_html = f'<div class="msg error" style="display:block">{error}</div>' if error else ""
    today = datetime.now().strftime("%Y-%m-%d")
    body = f"""
<nav><span>🏥</span><span class="logo">MediCare</span>
  <a href="/" class="back">← Home</a></nav>
<main>
  <div class="panel" style="max-width:520px">
    <div class="picon" style="background:linear-gradient(135deg,rgba(212,168,83,.25),rgba(212,168,83,.05));
      border-color:rgba(212,168,83,.3)">🩺</div>
    <h2>Admission Form</h2>
    <p class="sub">Fill in your details to book an appointment</p>
    {err_html}
    <form method="POST" action="/patient/admission">
      <div class="field">
        <label>Full Name *</label>
        <input name="name" type="text" placeholder="Enter your full name" required>
      </div>
      <div class="row">
        <div class="field">
          <label>Date *</label>
          <input name="date" type="date" min="{today}" value="{today}" required>
        </div>
        <div class="field">
          <label>Time *</label>
          <input name="time" type="time" value="09:00" required>
        </div>
      </div>
      <div class="field">
        <label>Symptoms *</label>
        <div id="chips" style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.6rem"></div>
        <textarea name="symptoms" id="syms" placeholder="Describe your symptoms..." rows="3" required></textarea>
      </div>
      <button class="btn btn-gold" type="submit">Submit Appointment</button>
    </form>
  </div>
</main>
<script>
const COMMON=['Fever','Cough','Headache','Sore Throat','Stomach Pain','Dizziness','Fatigue','Rashes','Chest Pain','Shortness of Breath'];
const sel=new Set();
const chips=document.getElementById('chips');
COMMON.forEach(s=>{{
  const b=document.createElement('button');b.type='button';
  b.textContent=s;b.style.cssText='padding:.3rem .8rem;border-radius:100px;font-size:.75rem;cursor:pointer;border:1px solid rgba(255,255,255,.15);color:rgba(255,255,255,.45);background:transparent;transition:all .2s;font-family:inherit';
  b.onclick=()=>{{
    const on=sel.has(s);
    if(on){{sel.delete(s);b.style.background='transparent';b.style.color='rgba(255,255,255,.45)';b.style.borderColor='rgba(255,255,255,.15)';}}
    else{{sel.add(s);b.style.background='rgba(212,168,83,.15)';b.style.color='#d4a853';b.style.borderColor='rgba(212,168,83,.4)';}}
    const ta=document.getElementById('syms');
    const manual=ta.value.split('\\n').filter(l=>!COMMON.includes(l.trim())&&l.trim());
    ta.value=[...sel,...manual].join('\\n');
  }};
  chips.appendChild(b);
}});
</script>"""
    return page("Admission", body)


def page_patient_success(name, date, time_val, symptoms):
    try:
        d = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        d = date
    try:
        t = datetime.strptime(time_val, "%H:%M").strftime("%I:%M %p")
    except Exception:
        t = time_val
    sym_tags = "".join(
        f'<span style="display:inline-block;background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.2);color:var(--teal-light);font-size:.72rem;padding:.2rem .6rem;border-radius:100px;margin:.15rem">{s.strip()}</span>'
        for s in re.split(r'[\n,]+', symptoms) if s.strip()
    )
    body = f"""
<nav><span>🏥</span><span class="logo">MediCare</span>
  <a href="/" class="back">← Home</a></nav>
<main>
  <div class="panel" style="text-align:center">
    <div style="font-size:3.5rem;margin-bottom:1rem">✅</div>
    <h2>Appointment Booked!</h2>
    <p class="sub">Your form has been submitted. The doctor will see your request shortly.</p>
    <div style="background:rgba(13,148,136,.08);border:1px solid rgba(13,148,136,.2);
      border-radius:14px;padding:1.25rem;margin:1.25rem 0;text-align:left">
      <div style="display:flex;justify-content:space-between;padding:.45rem 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:.85rem">
        <span style="color:rgba(255,255,255,.4)">Patient</span><span style="font-weight:600">{name}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:.45rem 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:.85rem">
        <span style="color:rgba(255,255,255,.4)">Date</span><span>{d}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:.45rem 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:.85rem">
        <span style="color:rgba(255,255,255,.4)">Time</span><span>{t}</span>
      </div>
      <div style="padding:.45rem 0;font-size:.85rem">
        <div style="color:rgba(255,255,255,.4);margin-bottom:.4rem">Symptoms</div>
        <div>{sym_tags}</div>
      </div>
    </div>
    <a href="/" class="btn" style="display:block;text-decoration:none;text-align:center">Back to Home</a>
  </div>
</main>"""
    return page("Booked", body)


# ─────────────────────────────────────────────
#  PATIENT EXAMINE PAGE
# ─────────────────────────────────────────────
def page_examine(doctor_name, patient, success=False):
    p = patient
    try:
        d = datetime.strptime(p["date_of_appointment"], "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        d = p["date_of_appointment"]
    try:
        t = datetime.strptime(p["appointment_time"], "%H:%M").strftime("%I:%M %p")
    except Exception:
        t = p["appointment_time"]

    syms = [s.strip() for s in re.split(r'[\n,]+', p["symptoms"]) if s.strip()]
    sym_tags = "".join(
        f'<span style="display:inline-block;background:rgba(212,168,83,.12);border:1px solid rgba(212,168,83,.25);color:var(--gold);font-size:.75rem;padding:.22rem .65rem;border-radius:100px;margin:.15rem">{s}</span>'
        for s in syms
    )

    is_examined = p["status"] == "Examined"
    diagnosis_val    = p.get("diagnosis") or ""
    prescription_val = p.get("prescription") or ""
    notes_val        = p.get("notes") or ""
    examined_at      = p.get("examined_at") or ""

    banner = ""
    if success:
        banner = """
        <div style="background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);
          border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.75rem">
          <span style="font-size:1.4rem">✅</span>
          <div>
            <div style="font-weight:600;color:#86efac;font-size:.95rem">Examination Saved!</div>
            <div style="color:rgba(255,255,255,.4);font-size:.8rem">Patient status is now Examined. Receipt is ready below.</div>
          </div>
        </div>"""

    # Receipt (shown after examination)
    receipt_section = ""
    if is_examined and diagnosis_val:
        sym_receipt = "".join(
            f'<span style="display:inline-block;background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.2);color:var(--teal-light);font-size:.75rem;padding:.22rem .65rem;border-radius:100px;margin:.15rem">{s}</span>'
            for s in syms
        )
        notes_block = ""
        if notes_val:
            notes_block = f"""
            <div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:.9rem">
              <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Doctor Notes</div>
              <div style="font-size:.83rem;white-space:pre-line">{notes_val}</div>
            </div>"""
        receipt_section = f"""
        <div id="receipt-section" style="margin-top:2rem">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
            <div style="font-size:1rem;font-weight:700;color:var(--teal-light)">🧾 Medical Receipt</div>
            <button onclick="window.print()" class="no-print"
              style="padding:.4rem .9rem;border-radius:8px;font-size:.78rem;cursor:pointer;
                border:1px solid rgba(13,148,136,.4);background:rgba(13,148,136,.12);
                color:var(--teal-light);font-family:inherit">
              🖨 Print Receipt
            </button>
          </div>
          <div id="receipt-card" style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem">
            <div style="text-align:center;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:1rem">
              <div style="font-size:1.3rem;font-weight:700">🏥 MediCare Clinic</div>
              <div style="font-size:.75rem;color:rgba(255,255,255,.35);margin-top:.2rem">Official Medical Receipt</div>
              <div style="font-size:.72rem;color:rgba(255,255,255,.25);margin-top:.2rem">Examined: {examined_at}</div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;font-size:.84rem">
              <div><span style="color:rgba(255,255,255,.4)">Patient:</span> <strong>{p['name']}</strong></div>
              <div><span style="color:rgba(255,255,255,.4)">Date:</span> {d}</div>
              <div><span style="color:rgba(255,255,255,.4)">Time:</span> {t}</div>
              <div><span style="color:rgba(255,255,255,.4)">Doctor:</span> {doctor_name}</div>
            </div>
            <div style="background:rgba(212,168,83,.07);border:1px solid rgba(212,168,83,.15);border-radius:10px;padding:.9rem">
              <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.4rem">Symptoms Reported</div>
              {sym_receipt}
            </div>
            <div style="background:rgba(13,148,136,.07);border:1px solid rgba(13,148,136,.15);border-radius:10px;padding:.9rem">
              <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Diagnosis</div>
              <div style="font-size:.88rem;font-weight:500">{diagnosis_val}</div>
            </div>
            <div style="background:rgba(139,92,246,.07);border:1px solid rgba(139,92,246,.15);border-radius:10px;padding:.9rem">
              <div style="font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.35rem">Prescription</div>
              <div style="font-size:.83rem;white-space:pre-line">{prescription_val}</div>
            </div>
            {notes_block}
            <div style="text-align:center;padding-top:.75rem;border-top:1px solid rgba(255,255,255,.07);font-size:.72rem;color:rgba(255,255,255,.2)">
              Thank you for trusting MediCare Clinic · Keep this receipt for your records
            </div>
          </div>
        </div>"""

    # Form state
    readonly = 'readonly' if is_examined else ''
    form_style = 'opacity:.65;pointer-events:none' if is_examined else ''
    status_badge = (
        '<span style="background:rgba(34,197,94,.15);border:1px solid rgba(34,197,94,.3);color:#86efac;padding:.35rem .9rem;border-radius:100px;font-size:.78rem;font-weight:600">✅ Examined</span>'
        if is_examined else
        '<span style="background:rgba(212,168,83,.15);border:1px solid rgba(212,168,83,.3);color:var(--gold);padding:.35rem .9rem;border-radius:100px;font-size:.78rem;font-weight:600">🟡 Pending</span>'
    )
    save_btn = (
        '<div style="text-align:center;padding:.75rem;background:rgba(34,197,94,.07);border:1px solid rgba(34,197,94,.2);border-radius:10px;color:#86efac;font-size:.85rem">✅ Examination already completed</div>'
        if is_examined else
        '<button type="submit" style="width:100%;padding:.9rem;border:none;border-radius:12px;cursor:pointer;font-size:.95rem;font-weight:700;font-family:inherit;background:linear-gradient(135deg,#22c55e,#16a34a);color:#fff;transition:opacity .2s" onmouseover="this.style.opacity=\'.85\'" onmouseout="this.style.opacity=\'1\'">✅ Save Examination &amp; Generate Receipt</button>'
    )

    body = f"""
<style>
.exam-wrap{{min-height:100vh;padding-top:70px}}
.exam-content{{max-width:860px;margin:0 auto;padding:1.75rem 1.25rem 3rem}}
.info-card{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:1.25rem 1.5rem;margin-bottom:1.5rem}}
.form-card{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:1.5rem}}
.section-title{{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.35);margin-bottom:.85rem;font-weight:500}}
.field-inner{{width:100%;padding:.8rem 1rem;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:12px;color:#fff;font-size:.92rem;outline:none;font-family:inherit;transition:border-color .2s}}
.field-inner:focus{{border-color:var(--teal)}}
.field-inner::placeholder{{color:rgba(255,255,255,.2)}}
textarea.field-inner{{resize:vertical}}
@media print{{
  .no-print{{display:none!important}}
  body{{background:#fff!important;color:#000!important}}
  .bg,.grid{{display:none!important}}
  #receipt-card{{background:#fff!important;border:1px solid #ccc!important}}
  #receipt-card *{{color:#000!important;border-color:#ccc!important;background:transparent!important}}
  .exam-wrap{{padding-top:0!important}}
}}
</style>

<nav class="no-print">
  <span>🏥</span><span class="logo">MediCare</span>
  <div style="margin-left:auto;display:flex;align-items:center;gap:.75rem">
    <span style="font-size:.82rem;color:rgba(255,255,255,.35)">👨‍⚕️ {doctor_name}</span>
    <a href="/doctor/dashboard"
      style="background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);
        color:rgba(255,255,255,.7);padding:.45rem 1.1rem;border-radius:100px;
        text-decoration:none;font-size:.83rem;font-weight:500;transition:all .2s"
      onmouseover="this.style.background='rgba(13,148,136,.2)';this.style.color='var(--teal-light)'"
      onmouseout="this.style.background='rgba(255,255,255,.07)';this.style.color='rgba(255,255,255,.7)'">
      ← Back to Dashboard
    </a>
  </div>
</nav>

<div class="exam-wrap">
  <div class="exam-content">

    <!-- Header -->
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap" class="no-print">
      <div style="width:48px;height:48px;background:linear-gradient(135deg,rgba(13,148,136,.3),rgba(13,148,136,.08));
        border:1px solid rgba(13,148,136,.35);border-radius:14px;display:flex;align-items:center;
        justify-content:center;font-size:1.4rem;flex-shrink:0">🩺</div>
      <div style="flex:1;min-width:180px">
        <div style="font-size:1.4rem;font-weight:700">Patient Examination</div>
        <div style="font-size:.82rem;color:rgba(255,255,255,.35)">Fill in diagnosis and prescription, then save</div>
      </div>
      <div>{status_badge}</div>
    </div>

    {banner}

    <!-- Patient Info -->
    <div class="info-card no-print">
      <div class="section-title">Patient Information</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.75rem;margin-bottom:.9rem">
        <div style="font-size:.85rem"><span style="color:rgba(255,255,255,.35)">Name:</span> <strong>{p['name']}</strong></div>
        <div style="font-size:.85rem"><span style="color:rgba(255,255,255,.35)">Date:</span> {d}</div>
        <div style="font-size:.85rem"><span style="color:rgba(255,255,255,.35)">Time:</span> {t}</div>
        <div style="font-size:.85rem"><span style="color:rgba(255,255,255,.35)">Patient ID:</span> #{p['id']}</div>
      </div>
      <div>
        <div style="font-size:.72rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.07em;margin-bottom:.45rem">Reported Symptoms</div>
        <div>{sym_tags}</div>
      </div>
    </div>

    <!-- Examination Form -->
    <div class="form-card no-print" style="{form_style}">
      <div class="section-title">Checkup Details</div>
      <form method="POST" action="/doctor/patient/{p['id']}/examine">
        <div style="margin-bottom:1.1rem">
          <label style="display:block;font-size:.75rem;color:rgba(255,255,255,.45);margin-bottom:.45rem;letter-spacing:.06em;text-transform:uppercase">
            Diagnosis *
          </label>
          <input name="diagnosis" type="text" class="field-inner"
            value="{diagnosis_val}"
            placeholder="e.g. Viral Upper Respiratory Tract Infection"
            required {readonly}>
        </div>
        <div style="margin-bottom:1.1rem">
          <label style="display:block;font-size:.75rem;color:rgba(255,255,255,.45);margin-bottom:.45rem;letter-spacing:.06em;text-transform:uppercase">
            Prescription *
          </label>
          <textarea name="prescription" rows="4" class="field-inner" required {readonly}
            placeholder="e.g. Paracetamol 500mg — 1 tablet every 6 hours&#10;Vitamin C 500mg — 1 tablet once daily&#10;Rest for 3 days">{prescription_val}</textarea>
        </div>
        <div style="margin-bottom:1.5rem">
          <label style="display:block;font-size:.75rem;color:rgba(255,255,255,.45);margin-bottom:.45rem;letter-spacing:.06em;text-transform:uppercase">
            Doctor Notes <span style="color:rgba(255,255,255,.2);font-size:.7rem">(optional)</span>
          </label>
          <textarea name="notes" rows="2" class="field-inner" {readonly}
            placeholder="Follow-up instructions, schedule, warnings...">{notes_val}</textarea>
        </div>
        {save_btn}
      </form>
    </div>

    {receipt_section}

  </div>
</div>"""
    return page(f"Examine — {p['name']}", body)


# ─────────────────────────────────────────────
#  STATISTICS PAGE
# ─────────────────────────────────────────────
def page_statistics(doctor_name, patients):
    import collections as _col
    total     = len(patients)
    examined  = sum(1 for p in patients if p["status"] == "Examined")
    pending   = sum(1 for p in patients if p["status"] == "Pending")
    confirmed = sum(1 for p in patients if p["status"] == "Confirmed")
    cancelled = sum(1 for p in patients if p["status"] == "Cancelled")

    # Monthly admissions
    monthly = _col.Counter()
    for p in patients:
        try:
            m = datetime.strptime(p["submitted_at"][:10], "%Y-%m-%d").strftime("%b")
            monthly[m] += 1
        except Exception:
            pass
    months_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly_vals = [monthly.get(m, 0) for m in months_order]

    # Status by month
    ex_monthly   = _col.Counter()
    pend_monthly = _col.Counter()
    for p in patients:
        try:
            m = datetime.strptime(p["submitted_at"][:10], "%Y-%m-%d").strftime("%b")
            if p["status"] == "Examined": ex_monthly[m] += 1
            elif p["status"] == "Pending": pend_monthly[m] += 1
        except Exception:
            pass
    ex_vals   = [ex_monthly.get(m, 0) for m in months_order]
    pend_vals = [pend_monthly.get(m, 0) for m in months_order]

    # Top symptoms
    sym_counter = _col.Counter()
    for p in patients:
        for s in re.split(r'[\n,]+', p["symptoms"]):
            s = s.strip()
            if s: sym_counter[s] += 1
    top_syms = sym_counter.most_common(8)
    sym_labels = json.dumps([x[0] for x in top_syms])
    sym_vals   = json.dumps([x[1] for x in top_syms])

    # Top diagnoses
    diag_counter = _col.Counter()
    for p in patients:
        if p["status"] == "Examined" and p.get("diagnosis","").strip():
            diag_counter[p["diagnosis"].strip()] += 1
    top_diags  = diag_counter.most_common(6)
    diag_labels = json.dumps([x[0] for x in top_diags])
    diag_vals   = json.dumps([x[1] for x in top_diags])

    # Appointments by day-of-week
    dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    dow_counter = _col.Counter()
    for p in patients:
        try:
            dt = datetime.strptime(p["date_of_appointment"], "%Y-%m-%d")
            dow_counter[dow_names[dt.weekday()]] += 1
        except Exception:
            pass
    dow_vals_list = json.dumps([dow_counter.get(d, 0) for d in dow_names])

    # Exam rate
    exam_rate = round(examined / total * 100, 1) if total else 0

    body = f"""
<style>
.sidebar{{position:fixed;top:0;left:0;bottom:0;width:240px;
  background:rgba(15,31,56,.97);border-right:1px solid rgba(255,255,255,.07);
  display:flex;flex-direction:column;z-index:100}}
.s-head{{padding:1.5rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.07)}}
.s-nav{{flex:1;padding:1.25rem .6rem;display:flex;flex-direction:column;gap:.25rem}}
.s-item{{display:flex;align-items:center;gap:.6rem;padding:.62rem .85rem;
  border-radius:10px;color:rgba(255,255,255,.4);font-size:.85rem;
  border:none;background:transparent;width:100%;text-align:left;
  cursor:pointer;font-family:inherit;text-decoration:none;transition:all .2s}}
.s-item:hover,.s-item.active{{background:rgba(13,148,136,.15);color:var(--teal-light)}}
.s-foot{{padding:1rem 1.25rem;border-top:1px solid rgba(255,255,255,.07)}}
.smain{{margin-left:240px;min-height:100vh;padding:0}}
.stopbar{{padding:1.1rem 1.75rem;border-bottom:1px solid rgba(255,255,255,.07);
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(10,22,40,.85);backdrop-filter:blur(10px);
  position:sticky;top:0;z-index:50}}
.scontent{{padding:1.5rem;display:flex;flex-direction:column;gap:1.25rem}}
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:.85rem}}
.kpi{{border-radius:16px;padding:1.4rem 1.2rem;border:1px solid;min-width:0;overflow:hidden}}
.kpi-lbl{{font-size:.7rem;color:rgba(255,255,255,.55);text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:.3rem;overflow:hidden;text-overflow:ellipsis}}
.kpi-val{{font-size:2.4rem;font-weight:800;line-height:1.1;
  margin:.15rem 0 .3rem;display:block}}
.kpi-note{{font-size:.75rem;color:rgba(255,255,255,.4);overflow:hidden;text-overflow:ellipsis}}
.charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem}}
.charts-grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.1rem}}
.chart-card{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:16px;padding:1.1rem;min-width:0}}
.chart-title{{font-size:.85rem;font-weight:700;color:rgba(255,255,255,.8);
  margin-bottom:.85rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
.chart-sub{{font-size:.7rem;color:rgba(255,255,255,.35);margin-left:auto}}
@media(max-width:1100px){{.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}
@media(max-width:800px){{
  .kpi-grid{{grid-template-columns:repeat(2,1fr)}}
  .charts-grid,.charts-grid-3{{grid-template-columns:1fr}}
}}
.jnav{{display:inline-flex;align-items:center;gap:.3rem;
  padding:.3rem .75rem;border-radius:100px;font-size:.78rem;font-weight:500;
  color:rgba(255,255,255,.5);text-decoration:none;
  border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);
  transition:all .2s;white-space:nowrap}}
.jnav:hover{{background:rgba(13,148,136,.2);border-color:rgba(13,148,136,.5);color:#14b8a6}}
.sec-hdr{{font-size:.78rem;text-transform:uppercase;letter-spacing:.1em;
  color:rgba(255,255,255,.4);margin-bottom:.6rem;
  display:flex;align-items:center;gap:.5rem;font-weight:600}}
.sec-bar{{display:inline-block;width:3px;height:14px;border-radius:2px;flex-shrink:0}}
</style>

<div class="sidebar">
  <div class="s-head">
    <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem">
      <div style="width:34px;height:34px;background:linear-gradient(135deg,var(--teal),var(--teal-light));
        border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1rem">🏥</div>
      <span style="font-weight:700;font-size:1.1rem">MediCare</span>
    </div>
    <div style="font-size:.75rem;color:rgba(255,255,255,.35)">Logged in as</div>
    <div style="font-size:.9rem;color:var(--teal-light);font-weight:500;margin-top:.15rem">👨‍⚕️ {doctor_name}</div>
  </div>
  <nav class="s-nav">
    <a class="s-item" href="/doctor/dashboard">📋 All Patients</a>
    <a class="s-item" href="/doctor/dashboard">🟡 Pending
      <span style="margin-left:auto;background:rgba(212,168,83,.3);color:var(--gold);font-size:.68rem;padding:.1rem .45rem;border-radius:100px">{pending}</span>
    </a>
    <a class="s-item active" href="/doctor/statistics">📊 Statistics</a>
  </nav>
  <div class="s-foot">
    <a href="/doctor/logout" style="display:flex;align-items:center;gap:.5rem;
      color:rgba(255,255,255,.3);font-size:.83rem;text-decoration:none;padding:.4rem;
      border-radius:8px;transition:all .2s"
      onmouseover="this.style.color='rgba(239,68,68,.7)';this.style.background='rgba(239,68,68,.07)'"
      onmouseout="this.style.color='rgba(255,255,255,.3)';this.style.background='transparent'">
      🚪 Sign Out
    </a>
  </div>
</div>

<div class="smain">

  <!-- TOP BAR -->
  <div class="stopbar">
    <div style="font-size:1.35rem;font-weight:700">&#128202; Statistics &amp; Analytics</div>
    <div style="font-size:.83rem;color:rgba(255,255,255,.35)">{total} total patients</div>
  </div>

  <!-- SECTION JUMP NAV -->
  <div style="position:sticky;top:53px;z-index:40;
    background:rgba(10,22,40,.97);backdrop-filter:blur(10px);
    border-bottom:1px solid rgba(255,255,255,.08);
    padding:.55rem 1.5rem;display:flex;align-items:center;gap:.4rem;flex-wrap:wrap">
    <span style="font-size:.72rem;color:rgba(255,255,255,.3);margin-right:.3rem;text-transform:uppercase;letter-spacing:.08em">Jump to:</span>
    <a href="#sec-overview"  class="jnav">&#8963; Overview</a>
    <a href="#sec-monthly"   class="jnav">&#8963; Monthly Admissions</a>
    <a href="#sec-status"    class="jnav">&#8963; Status Trend</a>
    <a href="#sec-symptoms"  class="jnav">&#8963; Symptoms</a>
    <a href="#sec-diagnoses" class="jnav">&#8963; Diagnoses</a>
    <a href="#sec-dow"       class="jnav">&#8963; By Day</a>
    <a href="#sec-allstatus" class="jnav">&#8963; All Status</a>
  </div>

  <div class="scontent">

    <!-- SECTION: Overview KPIs -->
    <div id="sec-overview">
      <div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.12em;
        color:rgba(255,255,255,.35);margin-bottom:.6rem;display:flex;align-items:center;gap:.5rem">
        <span style="display:inline-block;width:3px;height:14px;background:#14b8a6;border-radius:2px"></span>
        Overview
      </div>
      <div class="kpi-grid">
        <div class="kpi" style="background:rgba(13,148,136,.12);border-color:rgba(13,148,136,.4)">
          <div class="kpi-lbl">Total Patients</div>
          <div class="kpi-val" style="color:#14b8a6">{total}</div>
          <div class="kpi-note">All records</div>
        </div>
        <div class="kpi" style="background:rgba(34,197,94,.10);border-color:rgba(34,197,94,.4)">
          <div class="kpi-lbl">Examined</div>
          <div class="kpi-val" style="color:#4ade80">{examined}</div>
          <div class="kpi-note">Exam rate: {exam_rate}%</div>
        </div>
        <div class="kpi" style="background:rgba(212,168,83,.10);border-color:rgba(212,168,83,.4)">
          <div class="kpi-lbl">Pending</div>
          <div class="kpi-val" style="color:#fbbf24">{pending}</div>
          <div class="kpi-note">Awaiting exam</div>
        </div>
        <div class="kpi" style="background:rgba(59,130,246,.10);border-color:rgba(59,130,246,.4)">
          <div class="kpi-lbl">Confirmed</div>
          <div class="kpi-val" style="color:#60a5fa">{confirmed}</div>
          <div class="kpi-note">Ready for visit</div>
        </div>
        <div class="kpi" style="background:rgba(239,68,68,.10);border-color:rgba(239,68,68,.4)">
          <div class="kpi-lbl">Cancelled</div>
          <div class="kpi-val" style="color:#f87171">{cancelled}</div>
          <div class="kpi-note">Did not proceed</div>
        </div>
      </div>
    </div>

    <!-- SECTION: Monthly Admissions -->
    <div id="sec-monthly">
      <div class="sec-hdr"><span class="sec-bar" style="background:#14b8a6"></span>Monthly Patient Admissions</div>
      <div class="chart-card">
        <div class="chart-title">Admissions per Month <span class="chart-sub">Line chart</span></div>
        <canvas id="chartMonthly" height="120"></canvas>
      </div>
    </div>

    <!-- SECTION: Status Trend -->
    <div id="sec-status">
      <div class="sec-hdr"><span class="sec-bar" style="background:#4ade80"></span>Examined vs Pending by Month</div>
      <div class="chart-card">
        <div class="chart-title">Examined vs Pending <span class="chart-sub">Line chart</span></div>
        <canvas id="chartStatus" height="120"></canvas>
      </div>
    </div>

    <!-- SECTION: Symptoms + Diagnoses side by side -->
    <div class="charts-grid">
      <div id="sec-symptoms">
        <div class="sec-hdr"><span class="sec-bar" style="background:#f472b6"></span>Top Symptoms Reported</div>
        <div class="chart-card">
          <div class="chart-title">Symptom Frequency <span class="chart-sub">Line chart</span></div>
          <canvas id="chartSymptoms" height="160"></canvas>
        </div>
      </div>
      <div id="sec-diagnoses">
        <div class="sec-hdr"><span class="sec-bar" style="background:#818cf8"></span>Top Diagnoses</div>
        <div class="chart-card">
          <div class="chart-title">Diagnosis Frequency <span class="chart-sub">Line chart</span></div>
          <canvas id="chartDiagnoses" height="160"></canvas>
        </div>
      </div>
    </div>

    <!-- SECTION: Day of Week -->
    <div id="sec-dow">
      <div class="sec-hdr"><span class="sec-bar" style="background:#f97316"></span>Appointments by Day of Week</div>
      <div class="chart-card">
        <div class="chart-title">Busiest Days <span class="chart-sub">Line chart</span></div>
        <canvas id="chartDow" height="110"></canvas>
      </div>
    </div>

    <!-- SECTION: All Status Over Months -->
    <div id="sec-allstatus">
      <div class="sec-hdr"><span class="sec-bar" style="background:#fbbf24"></span>All Status Distribution Over Months</div>
      <div class="chart-card">
        <div class="chart-title">Examined / Pending / Confirmed / Cancelled <span class="chart-sub">Multi-line</span></div>
        <canvas id="chartAllStatus" height="110"></canvas>
      </div>
    </div>

  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
Chart.defaults.color = 'rgba(255,255,255,0.5)';
Chart.defaults.borderColor = 'rgba(255,255,255,0.07)';
Chart.defaults.font.family = "'Segoe UI', system-ui, sans-serif";

const MONTHS = {json.dumps(months_order)};
const MONTHLY = {json.dumps(monthly_vals)};
const EX_M    = {json.dumps(ex_vals)};
const PEND_M  = {json.dumps(pend_vals)};
const SYM_LBL = {sym_labels};
const SYM_VAL = {sym_vals};
const DIAG_LBL= {diag_labels};
const DIAG_VAL= {diag_vals};
const DOW_LBL = {json.dumps(dow_names)};
const DOW_VAL = {dow_vals_list};

function lineOpts(title) {{
  return {{
    responsive:true,
    plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'rgba(10,22,40,.95)',
      titleColor:'#fff',bodyColor:'rgba(255,255,255,.7)',borderColor:'rgba(13,148,136,.4)',borderWidth:1}}}},
    scales:{{
      x:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'rgba(255,255,255,.45)',font:{{size:10}}}}}},
      y:{{grid:{{color:'rgba(255,255,255,.05)'}},ticks:{{color:'rgba(255,255,255,.45)',font:{{size:10}}}},beginAtZero:true}}
    }}
  }};
}}

function mkLine(id, labels, datasets) {{
  new Chart(document.getElementById(id), {{
    type:'line', data:{{labels, datasets}}, options:lineOpts()
  }});
}}

function ds(label, data, color, fill=true) {{
  return {{label, data, borderColor:color, backgroundColor: fill ? color+'22':'transparent',
    borderWidth:2.5, pointBackgroundColor:color, pointRadius:4,
    pointHoverRadius:6, tension:.35, fill}};
}}

// 1. Monthly admissions
mkLine('chartMonthly', MONTHS, [ds('Admissions', MONTHLY, '#14b8a6')]);

// 2. Examined vs Pending
new Chart(document.getElementById('chartStatus'), {{
  type:'line',
  data:{{labels:MONTHS, datasets:[
    ds('Examined', EX_M,   '#22c55e'),
    ds('Pending',  PEND_M, '#fbbf24')
  ]}},
  options:{{...lineOpts(), plugins:{{...lineOpts().plugins, legend:{{display:true,
    labels:{{color:'rgba(255,255,255,.6)',font:{{size:11}}}}}}}}}}
}});

// 3. Top symptoms
mkLine('chartSymptoms', SYM_LBL, [ds('Cases', SYM_VAL, '#f472b6')]);

// 4. Top diagnoses
mkLine('chartDiagnoses', DIAG_LBL, [ds('Cases', DIAG_VAL, '#818cf8')]);

// 5. Day of week
mkLine('chartDow', DOW_LBL, [ds('Appointments', DOW_VAL, '#f97316')]);

// 6. All 4 statuses monthly
const conf_m = {json.dumps([_col.Counter(datetime.strptime(p['submitted_at'][:10],'%Y-%m-%d').strftime('%b') for p in patients if p['status']=='Confirmed').get(m,0) for m in months_order])};
const canc_m = {json.dumps([_col.Counter(datetime.strptime(p['submitted_at'][:10],'%Y-%m-%d').strftime('%b') for p in patients if p['status']=='Cancelled').get(m,0) for m in months_order])};
new Chart(document.getElementById('chartAllStatus'), {{
  type:'line',
  data:{{labels:MONTHS, datasets:[
    ds('Examined',  EX_M,    '#22c55e'),
    ds('Pending',   PEND_M,  '#fbbf24'),
    ds('Confirmed', conf_m,  '#3b82f6'),
    ds('Cancelled', canc_m,  '#ef4444')
  ]}},
  options:{{...lineOpts(), plugins:{{...lineOpts().plugins,
    legend:{{display:true,labels:{{color:'rgba(255,255,255,.6)',font:{{size:11}}}}}}}}}}
}});
</script>

<!-- Scroll UP button -->
<button id="scrollUpBtn" onclick="window.scrollTo({{top:0,behavior:'smooth'}})"
  title="Back to top"
  style="position:fixed;bottom:80px;right:1.5rem;z-index:999;
    width:44px;height:44px;border-radius:50%;border:none;cursor:pointer;
    background:linear-gradient(135deg,var(--teal),var(--teal-light));
    color:#fff;font-size:1.2rem;font-weight:700;
    box-shadow:0 4px 18px rgba(13,148,136,.5);
    display:none;align-items:center;justify-content:center;
    transition:opacity .2s,transform .2s">&#8679;</button>

<!-- Scroll DOWN button -->
<button id="scrollDownBtn" onclick="window.scrollBy({{top:window.innerHeight*.85,behavior:'smooth'}})"
  title="Scroll down"
  style="position:fixed;bottom:1.5rem;right:1.5rem;z-index:999;
    width:44px;height:44px;border-radius:50%;border:none;cursor:pointer;
    background:linear-gradient(135deg,var(--teal),var(--teal-light));
    color:#fff;font-size:1.2rem;font-weight:700;
    box-shadow:0 4px 18px rgba(13,148,136,.5);
    display:flex;align-items:center;justify-content:center;
    transition:opacity .2s,transform .2s">&#8681;</button>

<script>
const upBtn   = document.getElementById('scrollUpBtn');
const downBtn = document.getElementById('scrollDownBtn');
window.addEventListener('scroll', () => {{
  const scrolled = window.scrollY > 200;
  const atBottom = window.scrollY + window.innerHeight >= document.body.scrollHeight - 50;
  upBtn.style.display   = scrolled ? 'flex' : 'none';
  downBtn.style.opacity = atBottom ? '0.3' : '1';
  downBtn.style.pointerEvents = atBottom ? 'none' : 'auto';
}});
</script>"""
    return page("Statistics", body)


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard(doctor_name, patients):
    total     = len(patients)
    pending   = sum(1 for p in patients if p["status"] == "Pending")
    confirmed = sum(1 for p in patients if p["status"] == "Confirmed")
    examined  = sum(1 for p in patients if p["status"] == "Examined")
    cancelled = sum(1 for p in patients if p["status"] == "Cancelled")

    patients_json = json.dumps([dict(p) for p in patients])

    body = """
<style>
.sidebar{position:fixed;top:0;left:0;bottom:0;width:240px;
  background:rgba(15,31,56,.97);border-right:1px solid rgba(255,255,255,.07);
  display:flex;flex-direction:column;z-index:100}
.s-head{padding:1.5rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.07)}
.s-nav{flex:1;padding:1.25rem .6rem;display:flex;flex-direction:column;gap:.25rem}
.s-item{display:flex;align-items:center;gap:.6rem;padding:.62rem .85rem;
  border-radius:10px;color:rgba(255,255,255,.4);font-size:.85rem;
  border:none;background:transparent;width:100%;text-align:left;
  cursor:pointer;font-family:inherit;transition:all .2s}
.s-item:hover,.s-item.active{background:rgba(13,148,136,.15);color:var(--teal-light)}
.s-foot{padding:1rem 1.25rem;border-top:1px solid rgba(255,255,255,.07)}
.main{margin-left:240px;min-height:100vh}
.topbar{padding:1.1rem 1.75rem;border-bottom:1px solid rgba(255,255,255,.07);
  display:flex;align-items:center;justify-content:space-between;
  background:rgba(10,22,40,.85);backdrop-filter:blur(10px);
  position:sticky;top:0;z-index:50}
.content{padding:1.75rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:1rem;margin-bottom:1.75rem}
.stat{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:1.25rem 1rem}
.stat.t{border-color:rgba(13,148,136,.3);background:rgba(13,148,136,.07)}
.stat.g{border-color:rgba(212,168,83,.3);background:rgba(212,168,83,.07)}
.stat.gr{border-color:rgba(34,197,94,.3);background:rgba(34,197,94,.07)}
.stat-lbl{font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.4rem}
.stat-val{font-size:1.9rem;font-weight:700;margin-bottom:.15rem}
.stat.t .stat-val{color:var(--teal-light)}
.stat.g .stat-val{color:var(--gold)}
.stat.gr .stat-val{color:#86efac}
.tw{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:18px;overflow:hidden}
.th{padding:1.1rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.07);
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
table{width:100%;border-collapse:collapse}
thead th{text-align:left;padding:.75rem 1rem;font-size:.7rem;
  color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.1em;
  border-bottom:1px solid rgba(255,255,255,.06);font-weight:400}
tbody tr{cursor:pointer;transition:background .15s}
tbody tr:hover td{background:rgba(13,148,136,.06)}
tbody tr:not(:last-child) td{border-bottom:1px solid rgba(255,255,255,.04)}
.srch{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  border-radius:10px;padding:.55rem .9rem;color:#fff;font-size:.83rem;
  width:200px;outline:none;font-family:inherit}
.srch:focus{border-color:var(--teal)}
.srch::placeholder{color:rgba(255,255,255,.25)}
.fb{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);
  color:rgba(255,255,255,.45);padding:.5rem .9rem;border-radius:9px;
  font-size:.78rem;cursor:pointer;font-family:inherit;transition:all .2s}
.fb.on,.fb:hover{background:rgba(13,148,136,.15);border-color:var(--teal);color:var(--teal-light)}
</style>
""" + f"""
<div class="sidebar">
  <div class="s-head">
    <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem">
      <div style="width:34px;height:34px;background:linear-gradient(135deg,var(--teal),var(--teal-light));
        border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1rem">🏥</div>
      <span style="font-weight:700;font-size:1.1rem">MediCare</span>
    </div>
    <div style="font-size:.75rem;color:rgba(255,255,255,.35)">Logged in as</div>
    <div style="font-size:.9rem;color:var(--teal-light);font-weight:500;margin-top:.15rem">👨‍⚕️ {doctor_name}</div>
  </div>
  <nav class="s-nav">
    <button class="s-item active" onclick="filterStatus(null,this)">📋 All Patients
      <span style="margin-left:auto;background:var(--teal);color:#fff;font-size:.68rem;padding:.1rem .45rem;border-radius:100px">{total}</span>
    </button>
    <button class="s-item" onclick="filterStatus('Pending',this)">🟡 Pending
      <span style="margin-left:auto;background:rgba(212,168,83,.3);color:var(--gold);font-size:.68rem;padding:.1rem .45rem;border-radius:100px">{pending}</span>
    </button>
    <button class="s-item" onclick="filterStatus('Confirmed',this)">🟢 Confirmed</button>
    <button class="s-item" onclick="filterStatus('Examined',this)">✅ Examined
      <span style="margin-left:auto;background:rgba(34,197,94,.25);color:#86efac;font-size:.68rem;padding:.1rem .45rem;border-radius:100px">{examined}</span>
    </button>
    <button class="s-item" onclick="filterStatus('Cancelled',this)">🔴 Cancelled</button>
    <a class="s-item" href="/doctor/statistics" style="text-decoration:none;margin-top:.5rem;border-top:1px solid rgba(255,255,255,.06);padding-top:.75rem">📊 Statistics</a>
  </nav>
  <div class="s-foot">
    <a href="/doctor/logout" style="display:flex;align-items:center;gap:.5rem;
      color:rgba(255,255,255,.3);font-size:.83rem;text-decoration:none;padding:.4rem;
      border-radius:8px;transition:all .2s"
      onmouseover="this.style.color='rgba(239,68,68,.7)';this.style.background='rgba(239,68,68,.07)'"
      onmouseout="this.style.color='rgba(255,255,255,.3)';this.style.background='transparent'">
      🚪 Sign Out
    </a>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <div style="font-size:1.35rem;font-weight:700">Patient Dashboard</div>
    <div style="display:flex;gap:.75rem;align-items:center;flex-wrap:wrap">
      <input class="srch" type="text" id="search" placeholder="Search patients..." oninput="render()">
      <button class="fb" onclick="location.reload()">↻ Refresh</button>
    </div>
  </div>
  <div class="content">
    <div class="stats">
      <div class="stat t"><div class="stat-lbl">Total</div><div class="stat-val">{total}</div><div style="font-size:.75rem;color:rgba(255,255,255,.3)">Appointments</div></div>
      <div class="stat g"><div class="stat-lbl">Pending</div><div class="stat-val">{pending}</div><div style="font-size:.75rem;color:rgba(255,255,255,.3)">Awaiting</div></div>
      <div class="stat"><div class="stat-lbl">Confirmed</div><div class="stat-val">{confirmed}</div><div style="font-size:.75rem;color:rgba(255,255,255,.3)">Ready</div></div>
      <div class="stat gr"><div class="stat-lbl">Examined</div><div class="stat-val">{examined}</div><div style="font-size:.75rem;color:rgba(255,255,255,.3)">Done ✓</div></div>
    </div>

    <div style="background:rgba(13,148,136,.07);border:1px solid rgba(13,148,136,.2);border-radius:12px;
      padding:.8rem 1.1rem;margin-bottom:1.25rem;font-size:.82rem;color:rgba(255,255,255,.5);
      display:flex;align-items:center;gap:.5rem">
      <span style="color:var(--teal-light);font-size:1rem">💡</span>
      Click any patient row to open the <strong style="color:var(--teal-light)">Examination Page</strong> — do the checkup, write prescription and generate receipt.
    </div>

    <div class="tw">
      <div class="th">
        <div style="font-size:1rem;font-weight:600">Appointment Queue</div>
        <div style="display:flex;gap:.4rem;flex-wrap:wrap">
          <button class="fb on" onclick="filterStatus(null,this)">All</button>
          <button class="fb" onclick="filterStatus('Pending',this)">Pending</button>
          <button class="fb" onclick="filterStatus('Confirmed',this)">Confirmed</button>
          <button class="fb" onclick="filterStatus('Examined',this)">Examined</button>
          <button class="fb" onclick="filterStatus('Cancelled',this)">Cancelled</button>
        </div>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Patient Name</th><th>Date</th><th>Time</th>
              <th>Symptoms</th><th>Status</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
const ALL=PATIENTS_JSON_PLACEHOLDER;
let curFilter=null;

function filterStatus(f,btn){{
  curFilter=f;
  document.querySelectorAll('.fb,.s-item').forEach(b=>b.classList.remove('on','active'));
  if(btn)btn.classList.add(btn.classList.contains('fb')?'on':'active');
  render();
}}

function render(){{
  const q=document.getElementById('search').value.toLowerCase();
  let data=ALL.filter(p=>(!curFilter||p.status===curFilter)&&
    (!q||p.name.toLowerCase().includes(q)||p.symptoms.toLowerCase().includes(q)));
  const tbody=document.getElementById('tbody');
  if(!data.length){{
    tbody.innerHTML='<tr><td colspan="7" style="padding:3rem;text-align:center;color:rgba(255,255,255,.2)"><div style="font-size:2rem;margin-bottom:.5rem">🗂️</div>No patients found</td></tr>';
    return;
  }}
  const scMap={{
    Pending:  ['rgba(212,168,83,.15)','rgba(212,168,83,.3)','#d4a853'],
    Confirmed:['rgba(13,148,136,.15)','rgba(13,148,136,.3)','var(--teal-light)'],
    Examined: ['rgba(34,197,94,.15)','rgba(34,197,94,.3)','#86efac'],
    Cancelled:['rgba(239,68,68,.12)','rgba(239,68,68,.25)','#fca5a5']
  }};
  const iconMap={{Pending:'🟡',Confirmed:'🟢',Examined:'✅',Cancelled:'🔴'}};
  tbody.innerHTML=data.map((p,i)=>{{
    const d=new Date(p.date_of_appointment+'T00:00:00').toLocaleDateString('en-US',{{month:'short',day:'numeric',year:'numeric'}});
    const t=new Date('1970-01-01T'+p.appointment_time).toLocaleTimeString('en-US',{{hour:'numeric',minute:'2-digit',hour12:true}});
    const syms=p.symptoms.split(/[\\n,]+/).map(s=>s.trim()).filter(Boolean);
    const symH=syms.slice(0,3).map(s=>`<span style="display:inline-block;background:rgba(13,148,136,.12);border:1px solid rgba(13,148,136,.2);color:var(--teal-light);font-size:.7rem;padding:.18rem .55rem;border-radius:100px;margin:.1rem">${{s}}</span>`).join('')+(syms.length>3?`<span style="background:rgba(255,255,255,.06);color:rgba(255,255,255,.4);font-size:.7rem;padding:.18rem .55rem;border-radius:100px;margin:.1rem">+${{syms.length-3}}</span>`:'');
    const sc=scMap[p.status]||scMap.Pending;
    const icon=iconMap[p.status]||'🟡';
    return `<tr onclick="window.location='/doctor/patient/${{p.id}}/examine'" title="Click to examine">
      <td style="color:rgba(255,255,255,.3);padding:.9rem 1rem">${{i+1}}</td>
      <td style="padding:.9rem .75rem;font-weight:600">${{p.name}}</td>
      <td style="padding:.9rem .75rem;color:rgba(255,255,255,.5);font-size:.83rem">${{d}}</td>
      <td style="padding:.9rem .75rem;color:rgba(255,255,255,.5);font-size:.83rem">${{t}}</td>
      <td style="padding:.9rem .75rem;font-size:.82rem;max-width:220px">${{symH}}</td>
      <td style="padding:.9rem .75rem">
        <span style="display:inline-block;background:${{sc[0]}};border:1px solid ${{sc[1]}};color:${{sc[2]}};padding:.3rem .75rem;border-radius:100px;font-size:.78rem;font-weight:500">
          ${{icon}} ${{p.status}}
        </span>
      </td>
      <td style="padding:.9rem .75rem" onclick="event.stopPropagation()">
        <button onclick="window.location='/doctor/patient/${{p.id}}/examine'"
          style="padding:.32rem .75rem;border-radius:8px;font-size:.76rem;cursor:pointer;
            border:1px solid rgba(13,148,136,.35);background:rgba(13,148,136,.12);
            color:var(--teal-light);font-family:inherit;margin-right:.3rem;font-weight:500">
          🩺 Examine
        </button>
        <button onclick="delPt(${{p.id}})"
          style="padding:.32rem .7rem;border-radius:8px;font-size:.76rem;cursor:pointer;
            border:1px solid rgba(239,68,68,.25);background:rgba(239,68,68,.08);
            color:#fca5a5;font-family:inherit">
          🗑
        </button>
      </td>
    </tr>`;
  }}).join('');
}}

async function delPt(id){{
  if(!confirm('Delete this patient record?')) return;
  await fetch(`/doctor/patient/${{id}}/delete`,{{method:'POST'}});
  location.reload();
}}

render();
</script>
""".replace("PATIENTS_JSON_PLACEHOLDER", patients_json)

    return page("Dashboard", body)


# ─────────────────────────────────────────────
#  REQUEST HANDLER
# ─────────────────────────────────────────────
class ClinicHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} - {fmt % args}")

    def get_session(self):
        cookie_header = self.headers.get("Cookie", "")
        sc = SimpleCookie()
        sc.load(cookie_header)
        sid = sc.get("session_id")
        if sid:
            return SESSIONS.get(sid.value)
        return None

    def set_session(self, doctor_id, doctor_name):
        sid = str(uuid.uuid4())
        SESSIONS[sid] = {"doctor_id": doctor_id, "doctor_name": doctor_name}
        return sid

    def send_html(self, html, status=200, extra_headers=None):
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def read_form(self):
        body = self.read_body().decode("utf-8")
        return urllib.parse.parse_qs(body, keep_blank_values=True)

    def read_json(self):
        return json.loads(self.read_body())

    # ── GET ──────────────────────────────────
    def do_GET(self):
        p = self.path.split("?")[0]

        if p in ("/", "/landing"):
            return self.send_html(page_landing())

        elif p == "/doctor/register":
            return self.send_html(page_doctor_register())

        elif p == "/doctor/login":
            return self.send_html(page_doctor_login())

        elif p == "/doctor/logout":
            cookie_header = self.headers.get("Cookie", "")
            sc = SimpleCookie(); sc.load(cookie_header)
            sid = sc.get("session_id")
            if sid and sid.value in SESSIONS:
                del SESSIONS[sid.value]
            self.send_response(302)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", "session_id=; Max-Age=0; Path=/")
            self.end_headers()

        elif p == "/doctor/dashboard":
            sess = self.get_session()
            if not sess:
                return self.redirect("/doctor/login")
            with get_db() as db:
                pts = db.execute(
                    "SELECT * FROM patients ORDER BY date_of_appointment ASC, appointment_time ASC"
                ).fetchall()
            return self.send_html(page_dashboard(sess["doctor_name"], [dict(r) for r in pts]))

        elif re.match(r"^/doctor/patient/\d+/examine$", p):
            sess = self.get_session()
            if not sess:
                return self.redirect("/doctor/login")
            pid = int(p.split("/")[3])
            with get_db() as db:
                pt = db.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
            if not pt:
                return self.send_html("<h1 style='font-family:sans-serif;padding:2rem'>Patient not found</h1>", 404)
            return self.send_html(page_examine(sess["doctor_name"], dict(pt)))

        elif p == "/doctor/statistics":
            sess = self.get_session()
            if not sess:
                return self.redirect("/doctor/login")
            with get_db() as db:
                pts = db.execute("SELECT * FROM patients").fetchall()
            return self.send_html(page_statistics(sess["doctor_name"], [dict(r) for r in pts]))

        elif p == "/patient/admission":
            return self.send_html(page_patient_admission())

        else:
            self.send_html("<h1 style='font-family:sans-serif;padding:2rem'>404 Not Found</h1>", 404)

    # ── POST ─────────────────────────────────
    def do_POST(self):
        p = self.path.split("?")[0]

        # ── Doctor Register ──
        if p == "/doctor/register":
            form = self.read_form()
            name = form.get("name", [""])[0].strip()
            pw   = form.get("password", [""])[0].strip()
            if not name or not pw:
                return self.send_html(page_doctor_register(error="Name and password are required"))
            if len(pw) < 6:
                return self.send_html(page_doctor_register(error="Password must be at least 6 characters"))
            qr_id = str(uuid.uuid4())
            try:
                with get_db() as db:
                    db.execute("INSERT INTO doctors (name, password, qr_id) VALUES (?,?,?)",
                               (name, hash_pw(pw), qr_id))
                    db.commit()
                return self.send_html(page_doctor_register(success_qr=qr_id, success_name=name))
            except sqlite3.IntegrityError:
                return self.send_html(page_doctor_register(error="Doctor name already exists"))

        # ── Doctor Login ──
        elif p == "/doctor/login":
            form = self.read_form()
            name = form.get("name", [""])[0].strip()
            pw   = form.get("password", [""])[0].strip()
            with get_db() as db:
                doc = db.execute("SELECT * FROM doctors WHERE name=? AND password=?",
                                 (name, hash_pw(pw))).fetchone()
            if doc:
                sid = self.set_session(doc["id"], doc["name"])
                self.send_response(302)
                self.send_header("Location", "/doctor/dashboard")
                self.send_header("Set-Cookie", f"session_id={sid}; Path=/; HttpOnly")
                self.end_headers()
            else:
                self.send_html(page_doctor_login(error="Invalid name or password"))

        # ── QR Verify ──
        elif p == "/doctor/qr-verify":
            data = self.read_json()
            qr_id = data.get("qr_id", "").strip()
            with get_db() as db:
                doc = db.execute("SELECT * FROM doctors WHERE qr_id=?", (qr_id,)).fetchone()
            if doc:
                sid = self.set_session(doc["id"], doc["name"])
                self.send_json(
                    {"success": True, "name": doc["name"]},
                    extra_headers={"Set-Cookie": f"session_id={sid}; Path=/; HttpOnly"}
                )
            else:
                self.send_json({"success": False, "message": "Invalid QR code"})

        # ── Patient Admission ──
        elif p == "/patient/admission":
            ct = self.headers.get("Content-Type", "")
            if "application/json" in ct:
                data = self.read_json()
                name     = data.get("name", "").strip()
                date     = data.get("date", "").strip()
                time_val = data.get("time", "").strip()
                symptoms = data.get("symptoms", "").strip()
                if not all([name, date, time_val, symptoms]):
                    return self.send_json({"success": False, "message": "All fields required"})
                with get_db() as db:
                    db.execute("INSERT INTO patients (name,date_of_appointment,appointment_time,symptoms) VALUES (?,?,?,?)",
                               (name, date, time_val, symptoms))
                    db.commit()
                return self.send_json({"success": True})
            else:
                form = self.read_form()
                name     = form.get("name", [""])[0].strip()
                date     = form.get("date", [""])[0].strip()
                time_val = form.get("time", [""])[0].strip()
                symptoms = form.get("symptoms", [""])[0].strip()
                if not all([name, date, time_val, symptoms]):
                    return self.send_html(page_patient_admission(error="All fields are required"))
                with get_db() as db:
                    db.execute("INSERT INTO patients (name,date_of_appointment,appointment_time,symptoms) VALUES (?,?,?,?)",
                               (name, date, time_val, symptoms))
                    db.commit()
                return self.send_html(page_patient_success(name, date, time_val, symptoms))

        # ── Save Examination (POST) ──
        elif re.match(r"^/doctor/patient/\d+/examine$", p):
            sess = self.get_session()
            if not sess:
                return self.redirect("/doctor/login")
            pid = int(p.split("/")[3])
            form = self.read_form()
            diagnosis    = form.get("diagnosis", [""])[0].strip()
            prescription = form.get("prescription", [""])[0].strip()
            notes        = form.get("notes", [""])[0].strip()
            if not diagnosis or not prescription:
                with get_db() as db:
                    pt = db.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
                return self.send_html(page_examine(sess["doctor_name"], dict(pt), success=False))
            examined_at = datetime.now().strftime("%B %d, %Y %I:%M %p")
            with get_db() as db:
                db.execute(
                    "UPDATE patients SET status='Examined', diagnosis=?, prescription=?, notes=?, examined_at=? WHERE id=?",
                    (diagnosis, prescription, notes, examined_at, pid)
                )
                db.commit()
                pt = db.execute("SELECT * FROM patients WHERE id=?", (pid,)).fetchone()
            return self.send_html(page_examine(sess["doctor_name"], dict(pt), success=True))

        # ── Delete Patient ──
        elif re.match(r"^/doctor/patient/\d+/delete$", p):
            sess = self.get_session()
            if not sess:
                return self.send_json({"success": False})
            pid = int(p.split("/")[3])
            with get_db() as db:
                db.execute("DELETE FROM patients WHERE id=?", (pid,))
                db.commit()
            self.send_json({"success": True})

        else:
            self.send_html("<h1>404</h1>", 404)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    server = http.server.HTTPServer(("", PORT), ClinicHandler)
    print()
    print("=" * 50)
    print("   MediCare Clinic System")
    print("=" * 50)
    print(f"   URL  : http://localhost:{PORT}")
    print(f"   DB   : {os.path.abspath(DB)}")
    print()
    print("   Default Doctor Login:")
    print("     Name    : Dr. Admin")
    print("     Password: admin123")
    print()
    print("   PATIENT FLOW:")
    print("   1. Patient books -> status: Pending")
    print("   2. Doctor clicks row -> Examination page")
    print("   3. Doctor saves checkup + prescription")
    print("      -> status: Examined + receipt generated")
    print("   4. Back to dashboard -> shows Examined")
    print("=" * 50)
    print("   Press Ctrl+C to stop")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Server stopped.")
