#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خادمي — Free Fire 1.56.1
يعمل على Render بلا أي مكتبات خارجية (stdlib فقط).
المتغير الوحيد المطلوب: PORT (يمرره Render تلقائياً)
"""
import os, json, time, base64, hashlib, hmac, secrets, threading, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "1.56.1"

# ───────────── الهوية ─────────────
BASE_URL   = os.environ.get("BASE_URL", "https://flk1561.onrender.com")
APP_NAME   = os.environ.get("APP_NAME", "MY PROJECT")
GAMECONFIG_PATH = "/gameconfig/freefire-1561-production-server-settings-version.json"
GUARD_PATH      = "/android-guard/freefire-1561-guards-version-endpoint/live/"
VERIFY_PAGE     = "/verify"

# منبع الموارد (مؤقتاً مستودعهم العام — يعمل حتى لو أغلقوا خادمهم)
ASSET_UPSTREAM = "https://raw.githubusercontent.com/zeynsetiawan260/gameassets-/main/assets/"
ASSET_LAYOUT_VERSION = "1.56.10"   # تخطيط المجلدات في المستودع

# ───────────── الحسابات ─────────────
DATA_DIR   = os.environ.get("DATA_DIR", "/tmp")
ACC_FILE   = os.path.join(DATA_DIR, "accounts.json")
LOCK       = threading.Lock()
PBKDF2_ROUNDS = 120_000

def _load():
    try:
        with open(ACC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save(a):
    try:
        with open(ACC_FILE, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

def _hash(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return salt, dk.hex()

ACCOUNTS = _load()
# حساب افتراضي جاهز للتجربة
if not ACCOUNTS:
    s, h = _hash("12345678")
    ACCOUNTS["player1"] = dict(uid=1, salt=s, hash=h, vip=0, disabled=False, created=int(time.time()))
    ACCOUNTS["player2"] = dict(uid=2, salt=s, hash=h, vip=0, disabled=False, created=int(time.time()))
    _save(ACCOUNTS)

SESSIONS = {}

def log(msg):
    print("[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)

# ───────────── JSON ─────────────
def ver_json():
    return {
        "code": 0, "is_server_open": True, "is_firewall_open": False,
        "need_track_hotupdate": False, "min_hint_size": 0,
        "billboard_cdn_url": "", "billboard_msg": "", "patchnote_url": "",
        "web_url": "", "billboard_bg_url": "", "max_store": "", "max_web": "", "max_video": "",
        "remote_version": ASSET_LAYOUT_VERSION,
        "remote_option_version": "",
        "cdn_url": ASSET_UPSTREAM,
        "backup_cdn_url": ASSET_UPSTREAM,
        "abhotupdate_cdn_url": ASSET_UPSTREAM,
        "server_url": BASE_URL + "/login/",
        "is_review_server": False, "appstore_url": "",
        "force_to_restart_app": False, "country_code": "MA", "gdpr_version": 0,
        "client_ip": "127.0.0.1", "maintenance_announcement": "",
        "maintenance_region": "", "need_check_ip_list": [], "network_log_server": "",
        "login_failed_count": 0, "test_url": "", "img_cdn_url": "https://dl.aw.freefiremobile.com/common/",
        "core_url": BASE_URL + "/core/", "core_ip_list": [], "is_update_btn_show": False,
    }

def gameconfig_json():
    return [{
        "version": VERSION,
        "core_url": BASE_URL,
        "version_url": BASE_URL + "/live/",
        "resource_url": BASE_URL + "/cdn/",
        "android_guarded_version_url": BASE_URL + GUARD_PATH,
    }]

# ───────────── صفحات ─────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#0b0d10;color:#e8eaed;
     min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;direction:rtl}
.card{background:#15181d;border:1px solid #262b33;border-radius:16px;padding:28px;width:100%;max-width:390px;
      box-shadow:0 12px 40px rgba(0,0,0,.5)}
h1{font-size:21px;margin-bottom:4px;font-weight:700}
.sub{color:#8b94a3;font-size:13px;margin-bottom:22px}
label{display:block;font-size:12px;color:#8b94a3;margin-bottom:6px;font-weight:600}
input{width:100%;padding:13px 14px;border-radius:10px;border:1px solid #2b313b;background:#0e1116;
      color:#e8eaed;font-size:15px;margin-bottom:14px;outline:none}
input:focus{border-color:#f0703a}
button{width:100%;padding:14px;border-radius:10px;border:0;background:linear-gradient(135deg,#f0703a,#d1490f);
       color:#fff;font-size:15px;font-weight:700;cursor:pointer;margin-top:4px}
button:active{transform:scale(.98)}
.msg{padding:11px;border-radius:9px;font-size:13px;margin-bottom:14px;display:none}
.err{background:#3a1516;color:#ff8f8a;display:block}
.ok{background:#12301c;color:#6fe08a;display:block}
.foot{margin-top:18px;text-align:center;font-size:13px;color:#8b94a3}
.foot a{color:#f0703a;text-decoration:none;font-weight:600}
.brand{font-size:11px;letter-spacing:2px;color:#f0703a;font-weight:700;margin-bottom:10px}
"""

def page_login():
    return """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>دخول — %(app)s</title><style>%(css)s</style></head><body>
<div class="card">
  <div class="brand">%(app)s</div>
  <h1>تسجيل الدخول</h1>
  <div class="sub">الإصدار %(ver)s · خادمك الخاص</div>
  <div id="m" class="msg"></div>
  <label>معرّف اللاعب</label>
  <input id="u" autocomplete="username" placeholder="player1" dir="ltr">
  <label>كلمة السر</label>
  <input id="p" type="password" autocomplete="current-password" placeholder="••••••••" dir="ltr">
  <button onclick="go()">دخول</button>
  <div class="foot"><a href="/chrono/register">إنشاء حساب جديد</a></div>
</div>
<script>
function say(t,c){var m=document.getElementById('m');m.textContent=t;m.className='msg '+c;}
async function go(){
  var u=document.getElementById('u').value.trim(), p=document.getElementById('p').value;
  if(!u||!p){say('املأ الحقلين','err');return;}
  say('جارٍ التحقق…','ok');
  try{
    var r=await fetch('/chrono/login',{method:'POST',headers:{'Content-Type':'application/json'},
             body:JSON.stringify({user_id:u,password:p})});
    var j=await r.json();
    if(!j.ok){say(j.error||'بيانات غير صحيحة','err');return;}
    var h={account_id:String(j.account_id),token:j.token,session_time:j.session_time,
           vip_time:j.vip_time,server_time:j.server_time};
    say('تم — جارٍ فتح اللعبة…','ok');
    location.replace('/chrono/complete?handoff='+encodeURIComponent(JSON.stringify(h)));
  }catch(e){say('تعذّر الاتصال بالخادم','err');}
}
document.getElementById('p').addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>""" % dict(app=APP_NAME, ver=VERSION, css=CSS)

def page_register():
    return """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>حساب جديد — %(app)s</title><style>%(css)s</style></head><body>
<div class="card">
  <div class="brand">%(app)s</div>
  <h1>إنشاء حساب</h1>
  <div class="sub">8 أحرف على الأقل لكلمة السر</div>
  <div id="m" class="msg"></div>
  <label>اختر معرّف اللاعب</label>
  <input id="u" placeholder="اسمك" dir="ltr">
  <label>كلمة السر</label>
  <input id="p" type="password" placeholder="8 أحرف أو أكثر" dir="ltr">
  <button onclick="go()">إنشاء الحساب</button>
  <div class="foot">لديك حساب؟ <a href="/chrono/login">تسجيل الدخول</a></div>
</div>
<script>
function say(t,c){var m=document.getElementById('m');m.textContent=t;m.className='msg '+c;}
async function go(){
  var u=document.getElementById('u').value.trim(), p=document.getElementById('p').value;
  if(u.length<3){say('المعرّف قصير جداً','err');return;}
  if(p.length<8){say('كلمة السر 8 أحرف على الأقل','err');return;}
  var r=await fetch('/chrono/register',{method:'POST',headers:{'Content-Type':'application/json'},
           body:JSON.stringify({user_id:u,password:p})});
  var j=await r.json();
  if(!j.ok){say(j.error||'تعذّر الإنشاء','err');return;}
  say('تم إنشاء الحساب: '+j.user_id+' — جارٍ الدخول…','ok');
  setTimeout(()=>location.replace('/chrono/login'),900);
}
</script></body></html>""" % dict(app=APP_NAME, css=CSS)

def page_complete():
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>…</title><style>body{background:#0b0d10;color:#8b94a3;font-family:system-ui;display:flex;
align-items:center;justify-content:center;height:100vh;direction:rtl}</style></head>
<body>جارٍ فتح اللعبة…</body></html>"""

def page_info():
    return """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(app)s</title><style>%(css)s
.row{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #22272f;font-size:13px}
.k{color:#8b94a3}.v{color:#6fe08a;font-weight:600;font-family:monospace;direction:ltr}
</style></head><body><div class="card" style="max-width:460px">
<div class="brand">%(app)s</div><h1>الخادم يعمل</h1>
<div class="sub">Free Fire %(ver)s</div>
<div class="row"><span class="k">الإصدار</span><span class="v">%(ver)s</span></div>
<div class="row"><span class="k">الحسابات</span><span class="v">%(n)d</span></div>
<div class="row"><span class="k">الجلسات</span><span class="v">%(s)d</span></div>
<div class="row"><span class="k">gameconfig</span><span class="v">%(gp)s</span></div>
<div class="foot"><a href="/chrono/login">صفحة الدخول</a> · <a href="/chrono/register">حساب جديد</a> · <a href="/admin">اللوحة</a></div>
</div></body></html>""" % dict(app=APP_NAME, ver=VERSION, css=CSS,
        n=len(ACCOUNTS), s=len(SESSIONS), gp=GAMECONFIG_PATH)

def page_verify():
    return """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>تحقق</title><style>%(css)s</style>
</head><body><div class="card"><div class="brand">%(app)s</div><h1>التحقق من الحساب</h1>
<div class="sub">أدخل معرّفك للتأكد من وجوده</div>
<div id="m" class="msg"></div>
<label>معرّف اللاعب</label><input id="u" dir="ltr">
<button onclick="go()">تحقق</button>
<div class="foot"><a href="/chrono/login">دخول</a></div></div>
<script>
function say(t,c){var m=document.getElementById('m');m.textContent=t;m.className='msg '+c;}
async function go(){
  var u=document.getElementById('u').value.trim();
  var r=await fetch('/api/check?u='+encodeURIComponent(u));
  var j=await r.json();
  say(j.exists ? 'الحساب موجود ✅' : 'لا يوجد حساب بهذا المعرّف ❌', j.exists?'ok':'err');
}
</script></body></html>""" % dict(app=APP_NAME, css=CSS)

# ───────────── المعالج ─────────────
class H(BaseHTTPRequestHandler):
    server_version = "MyProject/1.0"

    def log_message(self, fmt, *a):
        log("%s %s" % (self.address_string(), fmt % a))

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return {}

    # ── GET ──
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        if p == "/":                          return self._send(200, page_info(), "text/html; charset=utf-8")
        if p == VERIFY_PAGE:                  return self._send(200, page_verify(), "text/html; charset=utf-8")
        if p == "/api/check":
            u = (q.get("u") or [""])[0]
            with LOCK:
                return self._send(200, {"exists": u in ACCOUNTS, "user_id": u})

        # الإعدادات
        if p == GAMECONFIG_PATH:              return self._send(200, gameconfig_json())
        if p in ("/live", "/live/", "/live/ver.php"):
            return self._send(200, ver_json())
        if p.startswith("/android-guard/"):
            return self._send(200, ver_json())

        # الدخول
        if p in ("/chrono/login", "/chrono/login/"):       return self._send(200, page_login(), "text/html; charset=utf-8")
        if p in ("/chrono/register", "/chrono/register/"): return self._send(200, page_register(), "text/html; charset=utf-8")
        if p.startswith("/chrono/complete"):               return self._send(200, page_complete(), "text/html; charset=utf-8")
        if p.startswith("/chrono/consent/config"):
            return self._send(200, {"terms_version": "1", "privacy_version": "1",
                                    "terms_url": "/chrono/terms", "privacy_url": "/chrono/privacy",
                                    "csrf_token": secrets.token_hex(16),
                                    "expires_at": int(time.time()) + 7200})
        if p in ("/chrono/terms", "/chrono/privacy"):
            return self._send(200, "<html><body style='background:#0b0d10;color:#e8eaed;padding:24px;"
                                   "font-family:system-ui;direction:rtl'>سياسة المشروع</body></html>",
                              "text/html; charset=utf-8")

        # لوحة التحكم
        if p == "/admin":
            with LOCK:
                rows = "".join(
                    "<tr><td>%s</td><td>%d</td><td style='color:%s'>%s</td></tr>" %
                    (k, v.get("uid", 0), "#ff8f8a" if v.get("disabled") else "#6fe08a",
                     "معطّل" if v.get("disabled") else "نشط")
                    for k, v in sorted(ACCOUNTS.items()))
                tbl = ("<table style='width:100%;font-size:13px;border-collapse:collapse'>"
                       "<tr style='color:#8b94a3'><th>المعرّف</th><th>UID</th><th>الحالة</th></tr>" + rows + "</table>")
            head = ("<html><body style='background:#0b0d10;color:#e8eaed;padding:24px;"
                    "font-family:system-ui;direction:rtl'><h2>" + APP_NAME + "</h2>"
                    "<p style='color:#8b94a3'>حسابات: " + str(len(ACCOUNTS)) +
                    " · جلسات: " + str(len(SESSIONS)) + "</p>")
            return self._send(200, head + tbl + "</body></html>", "text/html; charset=utf-8")

        # الموارد — تمرير للمنبع
        if p.startswith("/cdn/"):
            rel = p[5:].lstrip("/")
            if ".." in rel:
                return self._send(400, {"error": "bad_path"})
            try:
                req = urllib.request.Request(ASSET_UPSTREAM + rel,
                                             headers={"User-Agent": "MyProject/1.0"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    data = r.read()
                log("CDN %s (%d)" % (rel, len(data)))
                return self._send(200, data, "application/octet-stream")
            except Exception as e:
                log("CDN فشل %s: %s" % (rel, e))
                return self._send(404, {"error": "not_found", "path": rel})

        return self._send(404, {"error": "not_found", "path": p})

    # ── POST ──
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        b = self._body()
        uid = str(b.get("user_id") or "").strip()
        pw  = str(b.get("password") or "")

        if p == "/chrono/register":
            if len(uid) < 3:
                return self._send(400, {"ok": False, "error": "المعرّف قصير جداً"})
            if len(pw) < 8:
                return self._send(400, {"ok": False, "error": "كلمة السر 8 أحرف على الأقل"})
            with LOCK:
                if uid in ACCOUNTS:
                    return self._send(409, {"ok": False, "error": "المعرّف مستخدم"})
                s, h = _hash(pw)
                n = max([v.get("uid", 0) for v in ACCOUNTS.values()] or [0]) + 1
                ACCOUNTS[uid] = dict(uid=n, salt=s, hash=h, vip=0, disabled=False, created=int(time.time()))
                _save(ACCOUNTS)
            log("حساب جديد: %s (UID %d)" % (uid, n))
            return self._send(200, {"ok": True, "user_id": uid, "account_id": n})

        if p == "/chrono/login":
            with LOCK:
                acc = ACCOUNTS.get(uid)
            if not acc:
                return self._send(401, {"ok": False, "error": "المعرّف أو كلمة السر غير صحيحة",
                                        "code": "INVALID_CREDENTIALS"})
            if acc.get("disabled"):
                return self._send(403, {"ok": False, "error": "الحساب معطّل", "code": "ACCOUNT_DISABLED"})
            _, calc = _hash(pw, acc["salt"])
            if not hmac.compare_digest(calc, acc["hash"]):
                return self._send(401, {"ok": False, "error": "المعرّف أو كلمة السر غير صحيحة",
                                        "code": "INVALID_CREDENTIALS"})
            tok = secrets.token_urlsafe(32)
            now = int(time.time())
            with LOCK:
                SESSIONS[tok] = dict(uid=acc["uid"], user=uid, exp=now + 7200)
            log("دخول ناجح: %s" % uid)
            return self._send(200, {"ok": True, "account_id": acc["uid"], "token": tok,
                                    "session_time": 7200, "vip_time": int(acc.get("vip", 0)),
                                    "server_time": now})

        return self._send(404, {"error": "not_found", "path": p})

    def do_HEAD(self):
        self.do_GET()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    log("=" * 58)
    log("%s — Free Fire %s" % (APP_NAME, VERSION))
    log("القاعدة : %s" % BASE_URL)
    log("المنفذ  : %d" % port)
    log("الحسابات: %d" % len(ACCOUNTS))
    log("=" * 58)
    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
