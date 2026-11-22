#!/usr/bin/env python3
"""studio_bot.py: run the weekly YouTube/Instagram publishing from your phone through a private Telegram bot.

Only talks OUT to Telegram (no ports to open) and only obeys the one chat in CHAT_ID. Secrets live in bot.env (see bot.env.example).
Commands: /status /ytcheck /yttest /ytupload /yt ID /igcheck /igtest /igfree /igall /ig ID /update /confirm /cancel /help
Anything that uploads or schedules asks for /confirm first (60 seconds).
"""
import csv, json, os, subprocess, sys, threading, time
from datetime import datetime
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
WEEK = HERE.parent / "week1"
RAW = "https://raw.githubusercontent.com/modhshubham3/reel-queue/ccr-cb619668-8pcm8x"
FILES = ("ig_publish.py", "yt_publish.py", "yt_hashtags.py", "yt_auth.py", "studio_bot.py", "UPLOAD_MENU.bat", "UPDATE.bat", "run_studio_bot.bat")

def load_env():
    f = HERE / "bot.env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"'))
load_env()
TOKEN = os.environ.get("BOT_TOKEN", ""); CHAT = str(os.environ.get("CHAT_ID", "")).strip()
API = os.environ.get("TELEGRAM_API", "https://api.telegram.org") + f"/bot{TOKEN}/"
http = requests.Session(); pending = {}; busy = threading.Lock()

def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
def tg(method, **kw):
    r = http.post(API + method, timeout=kw.pop("t", 70), **kw); return r.json()
def send(text):
    for i in range(0, max(len(text), 1), 3900): tg("sendMessage", data={"chat_id": CHAT, "text": text[i:i + 3900]}, t=30)

def rows():
    f = WEEK / "queue.csv"
    return list(csv.DictReader(open(f, encoding="utf-8-sig"))) if f.exists() else []
WEEK2 = HERE.parent / "week2"; Q2 = str(WEEK2 / "queue.csv")

def get_week2():
    """download week2/queue.csv and every video it lists from the public reel-queue repo (skips files already complete)"""
    def work():
        if not busy.acquire(blocking=False): send("Ek kaam pehle se chal raha hai, thoda ruko."); return
        try:
            send("▶ Week 2 download shuru...")
            (WEEK2 / "videos").mkdir(parents=True, exist_ok=True)
            r = requests.get(f"{RAW}/week2/queue.csv", timeout=60); r.raise_for_status(); (WEEK2 / "queue.csv").write_bytes(r.content)
            rows2 = list(csv.DictReader(open(WEEK2 / "queue.csv", encoding="utf-8-sig"))); got = miss = 0; last = time.time()
            for row in rows2:
                dest = WEEK2 / row["file"].strip()
                try:
                    h = requests.head(f"{RAW}/week2/{row['file'].strip()}", timeout=60, allow_redirects=True)
                    size = int(h.headers.get("Content-Length", 0))
                    if dest.exists() and size and dest.stat().st_size == size: got += 1; continue
                    with requests.get(f"{RAW}/week2/{row['file'].strip()}", stream=True, timeout=300) as rr:
                        rr.raise_for_status()
                        with open(dest, "wb") as fh:
                            for chunk in rr.iter_content(1 << 20): fh.write(chunk)
                    got += 1
                except Exception as e:
                    miss += 1; send(f"FAIL {row['id']}: {str(e)[:100]}")
                if time.time() - last > 25: send(f"... {got}/{len(rows2)} videos aa chuke"); last = time.time()
            send(f"✅ Week 2: {got}/{len(rows2)} videos laptop par hain" + (f", {miss} fail (/w2get dobara chalao)" if miss else ". Ab /yt2check phir /yt2upload."))
        except Exception as e: send(f"Error: {e}")
        finally: busy.release()
    threading.Thread(target=work, daemon=True).start()

def jload(p): return json.loads(p.read_text()) if p.exists() else {}

def status():
    q = rows(); y = jload(HERE / "uploaded.json"); i = jload(HERE / "ig_uploaded.json")
    toks = [n for n in ("kahani", "interview", "gta") if (HERE / "tokens" / f"yt_{n}.json").exists()]
    pub = (HERE / "publora_key.txt").exists()
    q2 = [r for r in csv.DictReader(open(WEEK2 / "queue.csv", encoding="utf-8-sig"))] if (WEEK2 / "queue.csv").exists() else []
    out = [f"Videos in queue: {len(q)} (+{len(q2)} Week 2) | YouTube uploaded: {len(y)} | Instagram scheduled: {len(i)}",
           f"YouTube sign-ins: {', '.join(toks) or 'none'} | Publora key: {'yes' if pub else 'NO'}", "", "Next 6 by time (Y=YouTube, I=Instagram):"]
    for r in sorted(q, key=lambda r: r["publish_at"])[:40]:
        if r["id"] in y and r["id"] in i: continue
        out.append(f"{r['publish_at']}  {r['id']:3s} {r['channel']:9s} Y{'✓' if r['id'] in y else '·'} I{'✓' if r['id'] in i else '·'}")
        if len(out) > 9: break
    return "\n".join(out)

def run(cmd, label):
    """run a script in a thread, send its output back as it appears"""
    def work():
        if not busy.acquire(blocking=False): send("Ek kaam pehle se chal raha hai, thoda ruko."); return
        try:
            send(f"▶ {label} shuru...")
            p = subprocess.Popen([sys.executable, "-u"] + cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            buf, last = [], time.time()
            for line in p.stdout:
                line = line.rstrip()
                if line: buf.append(line[:300])
                if buf and time.time() - last > 25: send("\n".join(buf)); buf, last = [], time.time()
            p.wait()
            if buf: send("\n".join(buf))
            send(("✅" if p.returncode == 0 else "⚠") + f" {label} khatam (code {p.returncode})")
        except Exception as e: send(f"Error: {e}")
        finally: busy.release()
    threading.Thread(target=work, daemon=True).start()

Q = str(WEEK / "queue.csv"); M = str(WEEK / "meta.json")
ACTIONS = {  # name -> (needs confirm, argv, label)
    "ytcheck": (False, ["yt_publish.py", Q, "--dry-run"], "YouTube check"),
    "yttest": (True, ["yt_publish.py", Q, "--only", "i1"], "YouTube test (i1)"),
    "ytupload": (True, ["yt_publish.py", Q], "YouTube poora hafta"),
    "yt2check": (False, ["yt_publish.py", Q2, "--dry-run"], "YouTube Week 2 check"),
    "yt2upload": (True, ["yt_publish.py", Q2], "YouTube Week 2 (30 videos, schedule ke saath)"),
    "ythash": (True, ["yt_hashtags.py", Q], "YouTube: purane videos mein hashtags"),
    "igcheck": (False, ["ig_publish.py", M, "--dry-run"], "Instagram check"),
    "igtest": (True, ["ig_publish.py", M, "--only", "i2"], "Instagram test (i2)"),
    "igplan": (False, ["ig_publish.py", M, "--plan"], "Instagram plan/limits"),
    "igfree": (True, ["ig_publish.py", M, "--lanes", "interview,kahani"], "Instagram free-plan (interview+kahani)"),
    "igall": (True, ["ig_publish.py", M], "Instagram poora hafta"),
}
HELP = ("Commands:\n/status  kya ho chuka, kya baaki\n/ytcheck  /yttest  /ytupload  /yt ID  (YouTube)\n/ythash  purane YouTube videos mein hashtags\n/w2get  /yt2check  /yt2upload  Week 2 ke 30 naye videos (download, check, upload)\n/igcheck  /igtest  /igfree  /igall  /ig ID  (Instagram schedule)\n/ignow ID  turant post (jaise /ignow i2)\n/igplan  plan ki limits dekho\n/igauto on|off  khud hi har 3 ghante mein agle video schedule karta rahe\n"
        "/update  naye scripts download\n/confirm  upload se pehle haan\n/cancel\nUpload wale commands pehle /confirm maangte hain.")

AUTO = HERE / "auto.json"; kick = threading.Event()
def auto_on(): return bool(jload(AUTO).get("on"))
def set_auto(v): AUTO.write_text(json.dumps({"on": v}))
def autopilot():
    last = 0.0
    while True:
        kick.wait(30)
        try:
            forced = kick.is_set(); kick.clear()
            if not auto_on() or (not forced and time.time() - last < 3 * 3600): continue
            if not busy.acquire(blocking=False): continue
            try:
                last = time.time()
                out = subprocess.run([sys.executable, str(HERE / "ig_publish.py"), M, "--lanes", "interview,kahani"], capture_output=True, text=True, timeout=1800, cwd=str(HERE)).stdout
                keep = [l.strip()[:200] for l in out.splitlines() if l.startswith(("upload", "   OK", "   FAILED", "   ERROR", "   STOP", "No API"))]
                if any(("OK" in l or "FAILED" in l or "ERROR" in l) for l in keep): send("Auto Instagram:\n" + "\n".join(keep))
            finally: busy.release()
        except Exception as e: log(f"autopilot error: {e}")

def update():
    ok = []
    for f in FILES:
        try:
            r = requests.get(f"{RAW}/publisher/{f}", timeout=60); r.raise_for_status()
            (HERE / f).write_bytes(r.content); ok.append(f)
        except Exception as e: ok.append(f"{f} FAIL ({str(e)[:60]})")
    for f in ("meta.json", "queue.csv"):
        try:
            r = requests.get(f"{RAW}/week1/{f}", timeout=60); r.raise_for_status(); WEEK.mkdir(exist_ok=True); (WEEK / f).write_bytes(r.content); ok.append("week1/" + f)
        except Exception as e: ok.append(f"week1/{f} FAIL ({str(e)[:60]})")
    send("Update:\n" + "\n".join(ok) + "\n\nBot dobara chalu karne ke liye run_studio_bot.bat apne aap restart karega (agar wo chal raha hai).")
    if all("FAIL" not in x for x in ok): os._exit(3)   # supervisor (run_studio_bot.bat) restarts with the new code

def handle(text):
    t = text.strip(); cmd, _, arg = t.partition(" "); cmd = cmd.lower().split("@")[0].lstrip("/"); arg = arg.strip()
    if cmd in ("start", "help"): send(HELP)
    elif cmd == "status": send(status())
    elif cmd == "update": update()
    elif cmd == "cancel": pending.clear(); send("Cancel kar diya.")
    elif cmd == "confirm":
        p = pending.pop("p", None)
        if not p or time.time() > p[0]: send("Koi pending kaam nahi (ya 60 second beet gaye).")
        else: run(p[1], p[2])
    elif cmd == "w2get": get_week2()
    elif cmd == "igauto":
        if arg.lower() == "on": set_auto(True); kick.set(); send("Auto Instagram ON. Abhi ek round chalega, phir har 3 ghante mein jo slot khaali hoga usme agla video schedule hoga. Kuch hone par yahin batayunga. Band: /igauto off")
        elif arg.lower() == "off": set_auto(False); send("Auto Instagram OFF.")
        else: send("Auto Instagram abhi: " + ("ON" if auto_on() else "OFF") + "\n/igauto on  ya  /igauto off")
    elif cmd == "ignow" and arg:
        pending["p"] = (time.time() + 60, ["ig_publish.py", M, "--only", arg, "--now"], f"IG {arg} ABHI POST"); send(f"IG {arg} ABHI Instagram par post karun (schedule nahi, turant)? Haan ke liye /confirm (60 second)")
    elif cmd in ("yt", "ig") and arg:
        argv = (["yt_publish.py", Q, "--only", arg] if cmd == "yt" else ["ig_publish.py", M, "--only", arg]); pending["p"] = (time.time() + 60, argv, f"{cmd.upper()} {arg}")
        send(f"{cmd.upper()} {arg} upload/schedule karun? Haan ke liye /confirm (60 second)")
    elif cmd in ACTIONS:
        need, argv, label = ACTIONS[cmd]
        if not need: run(argv, label)
        else: pending["p"] = (time.time() + 60, argv, label); send(f"{label}: ye asli upload/schedule karega.\nHaan ke liye /confirm bhejo (60 second). Nahi ke liye /cancel.")
    else: send("Samajh nahi aaya. /help")

def main():
    if not TOKEN or not CHAT: raise SystemExit("bot.env mein BOT_TOKEN aur CHAT_ID chahiye (bot.env.example dekho).")
    threading.Thread(target=autopilot, daemon=True).start()
    log("studio bot chalu"); OFF = HERE / "tg_offset.txt"
    try: offset = int(OFF.read_text().strip())      # last handled update, so /update (which exits) is never replayed
    except Exception: offset = None
    try: send("Studio bot chalu ✅  /help")
    except Exception as e: log(f"startup send failed: {e}")
    while True:
        try:
            d = tg("getUpdates", data={"timeout": 50, **({"offset": offset} if offset else {})}, t=70)
            for u in d.get("result", []):
                offset = u["update_id"] + 1; m = u.get("message") or {}
                try: OFF.write_text(str(offset))   # remember BEFORE handling (at-most-once)
                except Exception: pass
                if str((m.get("chat") or {}).get("id")) != CHAT or not m.get("text"): continue
                log(f"cmd: {m['text'][:40]}"); handle(m["text"])
        except Exception as e: log(f"poll error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
