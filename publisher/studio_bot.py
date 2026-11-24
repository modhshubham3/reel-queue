#!/usr/bin/env python3
"""studio_bot.py: run the weekly YouTube/Instagram publishing from your phone through a private Telegram bot.

Only talks OUT to Telegram (no ports to open) and only obeys the one chat in CHAT_ID. Secrets live in bot.env (see bot.env.example).
EASY MODE: send /menu (or any message) and tap the buttons. Anything that uploads asks "Haan / Nahi" first (120 seconds).
The old typed commands (/ytcheck /yt2upload /yt3upload /yt3 ID /igcheck /ig ID /update /confirm /cancel ...) still work.
"""
import csv, difflib, json, os, subprocess, sys, threading, time
from datetime import datetime
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
WEEK = HERE.parent / "week1"
RAW = "https://raw.githubusercontent.com/modhshubham3/reel-queue/ccr-cb619668-8pcm8x"
FILES = ("ig_publish.py", "yt_publish.py", "yt_hashtags.py", "yt_auth.py", "studio_bot.py", "yt_make_public.py", "UPLOAD_MENU.bat", "UPDATE.bat", "run_studio_bot.bat")
CONFIRM_SECONDS = 120

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
def send(text, buttons=None):
    """buttons = [[(label, callback_data), ...], ...]; callback_data is just a command like "/status" (max 64 bytes)"""
    chunks = [text[i:i + 3900] for i in range(0, max(len(text), 1), 3900)]
    for n, c in enumerate(chunks):
        data = {"chat_id": CHAT, "text": c}
        if buttons and n == len(chunks) - 1:
            data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": l, "callback_data": d} for l, d in row] for row in buttons]})
        tg("sendMessage", data=data, t=30)

WEEK2 = HERE.parent / "week2"; Q2 = str(WEEK2 / "queue.csv")
WEEK3 = HERE.parent / "week3"; Q3 = str(WEEK3 / "queue.csv")
Q = str(WEEK / "queue.csv"); M = str(WEEK / "meta.json")
WEEK4 = HERE.parent / "week4"; Q4 = str(WEEK4 / "queue.csv")
WEEK5 = HERE.parent / "week5"; Q5 = str(WEEK5 / "queue.csv")
WEEKS = {"1": ("Week 1", Q), "2": ("Week 2", Q2), "3": ("Week 3", Q3), "4": ("Week 4", Q4), "5": ("Week 5 (v2)", Q5)}

# ---------------------------------------------------------------- sending videos to the phone
def send_video(path, caption=""):
    p = Path(path)
    if not p.exists(): send(f"Video nahi mila: {p.name}"); return False
    if p.stat().st_size > 49 * 1024 * 1024: send(f"{p.name} 49 MB se bada hai, Telegram bot isse nahi bhej sakta."); return False
    with open(p, "rb") as fh:
        r = http.post(API + "sendVideo", data={"chat_id": CHAT, "caption": caption[:1000], "supports_streaming": "true"},
                      files={"video": (p.name, fh, "video/mp4")}, timeout=600).json()
    if not r.get("ok"): send(f"{p.name} nahi gaya: {str(r.get('description'))[:120]}")
    return bool(r.get("ok"))

video_lock = threading.Lock()
def watch(week, lane=""):
    """send the videos of one week's queue (optionally one lane) to the chat, one by one"""
    def work():
        if not video_lock.acquire(blocking=False): send("Videos pehle se bhej raha hoon, thoda ruko."); return
        try:
            rows = [r for r in qrows(WEEKS[week][1]) if not lane or r["channel"].strip() == lane]
            if not rows: send(f"{WEEKS[week][0]}: koi video nahi mila."); return
            send(f"🎬 {WEEKS[week][0]}" + (f" ({CH_LABEL.get(lane, lane)})" if lane else "") + f": {len(rows)} videos bhej raha hoon...")
            ok = 0
            for r in rows:
                ok += send_video(Path(WEEKS[week][1]).parent / r["file"].strip(), f"{r['id']} · {r['title']}")
            send(f"✅ {ok}/{len(rows)} videos bhej diye.", [[("📊 Status", "/status"), ("🏠 Menu", "/menu")]])
        except Exception as e: send(f"Error: {e}")
        finally: video_lock.release()
    threading.Thread(target=work, daemon=True).start()

NEW_DIR = HERE.parent / "out" / "v2"; SEEN = HERE / "watch_sent.json"
OLD_V2 = ["v2-jwt", "v2-dhruv", "v2-fog", "v2-union", "v2-null", "v2-rank", "v2-bandar-pul", "v2-shravan", "v2-govardhan", "v2-inputbuffer", "v2-hitstop", "v2-navmesh"]
def watch_new_videos():
    """every finished new video in out/v2 goes to the phone by itself, once. 'Finished' = size unchanged for 2 checks and older than 60 s."""
    d = jload(SEEN); sent = d.get("mtimes") or {s: 0 for s in d.get("sent", OLD_V2)}   # stem -> mtime of the version already sent (0 = old, never resend)
    sizes = {}
    while True:
        try:
            for f in sorted(NEW_DIR.glob("*.mp4")) if NEW_DIR.exists() else []:
                st = f.stat(); prev = sent.get(f.stem)
                if prev is not None and (prev == 0 or st.st_mtime <= prev + 1): continue          # this version already sent
                if st.st_size < 200_000 or time.time() - st.st_mtime < 60 or sizes.get(f.stem) != st.st_size: sizes[f.stem] = st.st_size; continue
                sent[f.stem] = st.st_mtime; SEEN.write_text(json.dumps({"mtimes": sent}))           # remember first: never sent twice
                with video_lock:
                    send_video(f, f"🎬 {'UPDATED (theek kiya hua) version' if prev else 'Naya video bana'}: {f.stem}  ({st.st_size / 1048576:.1f} MB, {time.strftime('%H:%M')})")
                log(f"auto-sent new video {f.name}")
        except Exception as e: log(f"watch error: {e}")
        time.sleep(30)

OUTBOX = HERE / "outbox"
def outbox_loop():
    """Claude (or any local script) drops outbox/*.json = {"text": "...", "videos": [{"path": "...", "caption": "..."}]};
    the bot sends it and moves the file to outbox/sent/. No secrets are needed outside the bot."""
    (OUTBOX / "sent").mkdir(parents=True, exist_ok=True); (OUTBOX / "failed").mkdir(exist_ok=True)
    while True:
        try:
            for job in sorted(OUTBOX.glob("*.json")):
                try: d = json.loads(job.read_text(encoding="utf-8-sig"))   # -sig: files written on Windows often start with a BOM
                except Exception as e:
                    log(f"outbox bad file {job.name}: {e}"); job.rename(OUTBOX / "failed" / job.name); continue
                job.rename(OUTBOX / "sent" / job.name)            # claim it first: never sent twice
                if d.get("text"): send(d["text"], [[("📊 Status", "/status"), ("🏠 Menu", "/menu")]])
                with video_lock:
                    for v in d.get("videos", []): send_video((HERE / v["path"]).resolve() if not Path(v["path"]).is_absolute() else v["path"], v.get("caption", ""))
                log(f"outbox sent: {job.name}")
        except Exception as e: log(f"outbox error: {e}")
        time.sleep(20)
CHANNELS = ("interview", "kahani", "gta")
CH_LABEL = {"interview": "Interview", "kahani": "Kahani", "gta": "GTA"}

def qrows(path):
    p = Path(path)
    return list(csv.DictReader(open(p, encoding="utf-8-sig"))) if p.exists() else []
def jload(p): return json.loads(p.read_text()) if p.exists() else {}

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
            send(f"✅ Week 2: {got}/{len(rows2)} videos laptop par hain" + (f", {miss} fail (dobara dabao)" if miss else ". Ab YouTube ▶ Week 2 se check aur upload."), [[("▶️ YouTube", "/youtube"), ("🏠 Menu", "/menu")]])
        except Exception as e: send(f"Error: {e}")
        finally: busy.release()
    threading.Thread(target=work, daemon=True).start()

# ---------------------------------------------------------------- status
def week_progress(n):
    """-> (done, total, {channel: (done, total)}) for one week's YouTube queue, or None if its queue.csv is missing"""
    rows = qrows(WEEKS[n][1])
    if not rows: return None
    y = jload(HERE / "uploaded.json"); per = {}
    for r in rows:
        c = r["channel"].strip(); d, t = per.get(c, (0, 0)); per[c] = (d + (r["id"].strip() in y), t + 1)
    return sum(d for d, _ in per.values()), len(rows), per

def status():
    i = jload(HERE / "ig_uploaded.json")
    toks = [n for n in CHANNELS if (HERE / "tokens" / f"yt_{n}.json").exists()]
    out = ["📊 STATUS", "", "YouTube (upload ho gaye / kul):"]
    todo = []
    for n in ("1", "2", "3", "4", "5"):
        p = week_progress(n)
        if p is None: out.append(f" {WEEKS[n][0]}: queue file nahi mili"); continue
        d, t, per = p
        line = f" {WEEKS[n][0]}: {d}/{t}" + ("  ✅ poora" if d == t else "  (" + " · ".join(f"{CH_LABEL.get(c, c)} {a}/{b}" for c, (a, b) in per.items()) + ")")
        out.append(line)
        if d < t: todo.append((n, t - d))
    out += ["", f"Instagram schedule hue: {len(i)}",
            f"YouTube sign-in: {', '.join(CH_LABEL[t] for t in toks) or 'koi nahi'}" + ("" if len(toks) == 3 else "  ⚠ baaki channels ka sign-in chahiye (yt_auth.py)"),
            f"Publora key: {'haan' if (HERE / 'publora_key.txt').exists() else 'NAHI'}", ""]
    nxt = next((t for t in todo if t[0] == "5"), todo[-1] if todo else None)    # the new v2 week first
    out.append("👉 Agla kaam: " + (f"{WEEKS[nxt[0]][0]} ke {nxt[1]} video baaki hain. YouTube ▶ {WEEKS[nxt[0]][0]} dabao." if nxt else "YouTube par kuch baaki nahi."))
    out.append("ℹ️ Week 3 ke Interview/Kahani YouTube ki upload limit se ruke hain (channel phone-verify karo). Week 4 purane style ka hai.")
    return "\n".join(out)

# ---------------------------------------------------------------- running scripts
def run(cmd, label):
    """run a script in a thread, send its output back as it appears, then a plain-language summary"""
    def work():
        if not busy.acquire(blocking=False): send("Ek kaam pehle se chal raha hai, thoda ruko."); return
        try:
            send(f"▶ {label} shuru... (bas intezaar karo, ye khud batayega)")
            p = subprocess.Popen([sys.executable, "-u"] + cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
            buf, last = [], time.time(); ok = fail = limit = skip = plan = pub = held = 0
            for line in p.stdout:
                line = line.rstrip()
                if line.startswith("   PUBLIC"): pub += 1
                elif line.startswith("   OK"): ok += 1
                elif line.startswith("   FAILED") or line.startswith("   ERROR") or line.startswith("ERROR"): fail += 1
                elif line.startswith("   LIMIT") or line.startswith("   STOP"): limit += 1
                elif line.startswith("skip") and ("limit" in line or "Limit" in line): held += 1      # skipped because the channel hit its daily limit: NOT done
                elif line.startswith("skip"): skip += 1                                               # already uploaded / already public / already scheduled
                elif line.startswith("plan"): plan += 1
                if line and not line.startswith("skip"): buf.append(line[:300])   # 'skip' lines are counted, not spammed
                if buf and time.time() - last > 25: send("\n".join(buf)); buf, last = [], time.time()
            p.wait()
            if buf: send("\n".join(buf))
            bits = []
            if plan: bits.append(f"{plan} videos ka plan dikha (kuch upload nahi hua)")
            if ok: bits.append(f"{ok} upload ho gaye ✅")
            if pub: bits.append(f"{pub} video abhi PUBLIC ho gaye ✅")
            if skip: bits.append(f"{skip} pehle se ho chuke the (dobara nahi bheje)")
            if limit or held: bits.append(f"⚠ {limit + held} video LIMIT ki wajah se NAHI gaye: abhi bhi baaki hain. Kal dobara dabao.")
            if fail: bits.append(f"{fail} fail ❌ (upar ka message dekho)")
            bad = fail or ((limit or held) and not (ok or pub))
            head = ("✅" if p.returncode == 0 and not bad else "⚠") + f" {label} khatam."
            send(head + ("\n" + "\n".join("• " + b for b in bits) if bits else "") + ("" if p.returncode == 0 else f"\n(code {p.returncode})"), [[("📊 Status", "/status"), ("🏠 Menu", "/menu")]])
        except Exception as e: send(f"Error: {e}")
        finally: busy.release()
    threading.Thread(target=work, daemon=True).start()

def ask(argv, label, text):
    """real uploads: remember the job and ask with Haan / Nahi buttons (also /confirm and /cancel as text)"""
    pending["p"] = (time.time() + CONFIRM_SECONDS, argv, label)
    send(text + f"\n\nKarun? ({CONFIRM_SECONDS} second ke andar jawab do)", [[("✅ Haan, karo", "/confirm"), ("❌ Nahi", "/cancel")]])

ACTIONS = {  # name -> (needs confirm, argv, label)
    "ytcheck": (False, ["yt_publish.py", Q, "--dry-run"], "YouTube Week 1 check"),
    "yttest": (True, ["yt_publish.py", Q, "--only", "i1"], "YouTube test (i1)"),
    "ytupload": (True, ["yt_publish.py", Q], "YouTube Week 1 upload"),
    "yt2check": (False, ["yt_publish.py", Q2, "--dry-run"], "YouTube Week 2 check"),
    "yt2upload": (True, ["yt_publish.py", Q2], "YouTube Week 2 upload (schedule ke saath)"),
    "yt3check": (False, ["yt_publish.py", Q3, "--dry-run"], "YouTube Week 3 check"),
    "yt3upload": (True, ["yt_publish.py", Q3], "YouTube Week 3 upload (schedule ke saath)"),
    "yt4check": (False, ["yt_publish.py", Q4, "--dry-run"], "YouTube Week 4 check"),
    "yt4upload": (True, ["yt_publish.py", Q4], "YouTube Week 4 upload (schedule ke saath)"),
    "yt5check": (False, ["yt_publish.py", Q5, "--dry-run"], "YouTube Week 5 check"),
    "yt5upload": (True, ["yt_publish.py", Q5], "YouTube Week 5 upload (schedule ke saath)"),
    "ythash": (True, ["yt_hashtags.py", Q], "YouTube: purane videos mein hashtags"),
    "igcheck": (False, ["ig_publish.py", M, "--dry-run"], "Instagram check"),
    "igtest": (True, ["ig_publish.py", M, "--only", "i2"], "Instagram test (i2)"),
    "igplan": (False, ["ig_publish.py", M, "--plan"], "Instagram plan/limits"),
    "igfree": (True, ["ig_publish.py", M, "--lanes", "interview,kahani"], "Instagram free-plan (interview+kahani)"),
    "igall": (True, ["ig_publish.py", M], "Instagram poora hafta"),
}
EXPLAIN = {  # one plain sentence shown before the Haan/Nahi question
    "yttest": "Sirf test: Week 1 ka ek video (i1) upload hoga.",
    "ytupload": "Week 1 ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge.",
    "yt2upload": "Week 2 ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge.",
    "yt3upload": "Week 3 ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge (28 Nov se 2 Dec). Jo ho chuke wo dobara nahi jayenge.",
    "yt5upload": "Week 5 (naye v2 style) ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge. Jo ho chuke wo dobara nahi jayenge.",
    "yt4upload": "Week 4 ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge (3 Dec se 7 Dec). Jo ho chuke wo dobara nahi jayenge.",
    "ythash": "Purane YouTube videos ke description mein hashtags jode jayenge.",
    "igtest": "Sirf test: Instagram par ek video (i2).",
    "igfree": "Instagram par Interview + Kahani ke video schedule honge (free plan ki limit ke andar).",
    "igall": "Instagram par poora hafta schedule hoga (limit lag sakti hai).",
}

# ---------------------------------------------------------------- menus
def b_menu(): return [("🏠 Menu", "/menu")]
def check_cmd(n): return "/ytcheck" if n == "1" else f"/yt{n}check"
def upload_cmd(n): return "/ytupload" if n == "1" else f"/yt{n}upload"

def show_menu(prefix=""):
    send((prefix + "\n\n" if prefix else "") + "Kya karna hai? Button dabao 👇\n(Kuch bhi upload hone se pehle main 'Haan / Nahi' poochhunga.)",
         [[("📊 Status: kya ho chuka", "/status")], [("▶️ YouTube upload", "/youtube")], [("📸 Instagram", "/instagram")], [("⚙️ Aur options", "/more")]])

def show_youtube():
    send("YouTube: kaunsa week?\n(Week 5 = naye v2 style ke 30 videos | Week 4 = purana style | Week 3 = 28 Nov - 2 Dec)", [[("⭐ Week 5 (v2, 30)", "/week 5")], [("Week 4 (30)", "/week 4")], [("Week 3 (30)", "/week 3")], [("Week 2 (30)", "/week 2"), ("Week 1 (21)", "/week 1")], [b_menu()[0]]])

def show_week(n):
    if n not in WEEKS: return show_youtube()
    name = WEEKS[n][0]; p = week_progress(n)
    if p is None: send(f"{name}: queue file laptop par nahi mili." + (" Pehle 'Aur options' ▶ Week 2 download." if n == "2" else ""), [[("⬅️ Wapas", "/youtube")]]); return
    d, t, per = p
    lines = [f"{name}: {d}/{t} YouTube par ho chuke."] + [f" {CH_LABEL.get(c, c)}: {a}/{b}" for c, (a, b) in per.items()] + ["", "1) Pehle 🔍 Check dabao (kuch upload nahi hota, sirf plan dikhta hai).", "2) Phir ⬆️ Upload. Channel ki limit lage to 'Sirf ek channel' se baaki channels chalao."]
    kb = [[("🔍 Pehle check (safe)", check_cmd(n))], [("⬆️ Saare baaki upload", upload_cmd(n))],
          [(f"Sirf {CH_LABEL[c]}", f"/ytch {n} {c}") for c in CHANNELS]]
    kb.append([(f"🎬 {CH_LABEL[c]} phone par", f"/watch {n} {c}") for c in CHANNELS])
    kb.append([("⚡ Jo upload ho chuke, abhi PUBLIC karo", f"/ytpub {n}")])
    kb.append([("🔍 Public check (kuch nahi badlega)", f"/ytpubcheck {n}")])
    if n == "2": kb.append([("⚡ Turant public (har channel ke 2)", "/yt2now 2")])
    kb.append([("⬅️ Wapas", "/youtube"), b_menu()[0]])
    send("\n".join(lines), kb)

def show_instagram():
    send("Instagram:\n• ⚡ Abhi post = agle video TURANT Instagram par (schedule nahi). Har post 15/mahine ki free limit mein se katega.\n• Check = sirf dekho (kuch post nahi)\n• Plan = limits dekho\n• Schedule = time par post hoga\nAuto: bot khud har 3 ghante mein agla video schedule karta hai.\nSirf jo Instagram account Publora mein connected hai, wahi chalega.",
         [[("⚡ Abhi post: agla 1", "/igpost 1"), ("⚡ Abhi post: agle 3", "/igpost 3")], [("🔍 Check (safe)", "/igcheck"), ("📋 Plan/limits", "/igplan")], [("🗓️ Schedule (free plan)", "/igfree")], [("🗓️ Schedule poora hafta", "/igall")],
          [("🤖 Auto ON", "/igauto on"), ("Auto OFF", "/igauto off")], [b_menu()[0]]])

def show_more():
    send("Aur options:", [[("🔄 Naye scripts download (/update)", "/update")], [("⬇️ Week 2 videos download", "/w2get")], [("🏷️ Purane YouTube videos mein hashtags", "/ythash")], [("❌ Cancel", "/cancel"), b_menu()[0]]])

HELP = ("Bas /menu bhejo aur button dabao. Kuch type karne ki zaroorat nahi.\n\n"
        "Short list:\n/menu  main buttons\n/status  kya ho chuka, kya baaki\n/youtube  YouTube upload (week chuno)\n/instagram  Instagram\n/more  aur options\n/cancel  rok do\n\n"
        "Purane commands bhi chalte hain: /yt3check /yt3upload /yt3 ID /yt2upload /ytcheck /igcheck /update ...")
KNOWN = set(ACTIONS) | {"menu", "status", "youtube", "instagram", "more", "help", "start", "update", "cancel", "confirm", "w2get", "yt2now", "igauto", "ignow", "yt3", "yt", "ig", "week", "ytch", "ytpub", "ytpubcheck", "watch", "igpost"}

SAFE_SUGGEST = {"menu", "status", "youtube", "instagram", "more", "help", "cancel", "start"}
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
                out = subprocess.run([sys.executable, str(HERE / "ig_publish.py"), M, "--lanes", "interview,kahani"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800, cwd=str(HERE)).stdout
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

# ---------------------------------------------------------------- command handling (typed text and button taps both land here)
def handle(text):
    t = text.strip(); cmd, _, arg = t.partition(" "); cmd = cmd.lower().split("@")[0].lstrip("/"); arg = arg.strip()
    if cmd in ("start", "menu"): show_menu()
    elif cmd == "help": send(HELP, [b_menu()])
    elif cmd == "status": send(status(), [[("▶️ YouTube", "/youtube"), b_menu()[0]]])
    elif cmd == "youtube": show_youtube()
    elif cmd == "instagram": show_instagram()
    elif cmd == "more": show_more()
    elif cmd == "week": show_week(arg)
    elif cmd == "update": update()
    elif cmd == "cancel": pending.clear(); send("Cancel kar diya. Kuch nahi hua.", [b_menu()])
    elif cmd == "confirm":
        p = pending.pop("p", None)
        if not p or time.time() > p[0]: send("Koi pending kaam nahi (ya time khatam ho gaya). Menu se dobara chuno.", [b_menu()])
        else: run(p[1], p[2])
    elif cmd == "w2get": get_week2()
    elif cmd == "yt2now":
        ask(["yt_publish.py", Q2, "--now"] + (["--per-channel", arg] if arg.isdigit() else []), "YouTube Week 2 TURANT PUBLIC",
            "⚠ Week 2: " + (f"har channel ke agle {arg} video" if arg.isdigit() else "saare baaki video") + " abhi PUBLIC ho jayenge (schedule nahi).")
    elif cmd == "igauto":
        if arg.lower() == "on": set_auto(True); kick.set(); send("Auto Instagram ON. Abhi ek round chalega, phir har 3 ghante mein jo slot khaali hoga usme agla video schedule hoga.", [b_menu()])
        elif arg.lower() == "off": set_auto(False); send("Auto Instagram OFF.", [b_menu()])
        else: send("Auto Instagram abhi: " + ("ON" if auto_on() else "OFF"), [[("🤖 ON", "/igauto on"), ("OFF", "/igauto off")]])
    elif cmd == "igpost":    # "/igpost 3": publish the next N not-yet-posted videos RIGHT NOW (never re-publishes scheduled ones)
        k = arg if arg.isdigit() and 1 <= int(arg) <= 5 else "1"
        ask(["ig_publish.py", M, "--now", "--max", k], f"Instagram: agle {k} abhi post", f"⚡ Instagram par agle {k} video TURANT post honge (schedule nahi). Har ek 15/mahine ki free limit mein se katega. Jo account Publora mein connected nahi, uske video skip honge.")
    elif cmd == "ignow" and arg: ask(["ig_publish.py", M, "--only", arg, "--now"], f"IG {arg} ABHI POST", f"Instagram par {arg} turant post hoga (schedule nahi).")
    elif cmd == "watch":     # "/watch 5 kahani": send that week's videos to the phone
        w, _, ln = arg.partition(" ")
        if w in WEEKS: watch(w, ln.strip().lower() if ln.strip().lower() in CHANNELS else "")
        else: show_youtube()
    elif cmd == "ytpub":     # "/ytpub 3": videos already uploaded as SCHEDULED become public right now (no re-upload)
        w = arg.strip()
        if w in WEEKS: ask(["yt_make_public.py", WEEKS[w][1]], f"YouTube {WEEKS[w][0]}: ABHI PUBLIC", f"⚠ {WEEKS[w][0]} ke jo video schedule ke saath upload hue the (abhi private), wo TURANT PUBLIC ho jayenge. Schedule ka time ignore hoga. Ye wapas nahi hota (chaho to Studio mein dobara private kar sakte ho).")
        else: show_youtube()
    elif cmd == "ytpubcheck":
        w = arg.strip()
        if w in WEEKS: run(["yt_make_public.py", WEEKS[w][1], "--dry-run"], f"YouTube {WEEKS[w][0]}: public check")
        else: show_youtube()
    elif cmd == "ytch":      # "/ytch 3 kahani": one channel of one week
        w, _, ch = arg.partition(" ")
        if w in WEEKS and ch.strip().lower() in CHANNELS: ask(["yt_publish.py", WEEKS[w][1], "--channel", ch.strip().lower()], f"YouTube {WEEKS[w][0]}: sirf {CH_LABEL[ch.strip().lower()]}", f"{WEEKS[w][0]}: sirf {CH_LABEL[ch.strip().lower()]} channel ke baaki video upload/schedule honge.")
        else: show_youtube()
    elif cmd == "yt3" and arg: ask(["yt_publish.py", Q3, "--only", arg], f"YT Week 3 {arg}", f"Week 3 ka video {arg} upload/schedule hoga.")
    elif cmd in ("yt", "ig") and arg:
        ask((["yt_publish.py", Q, "--only", arg] if cmd == "yt" else ["ig_publish.py", M, "--only", arg]), f"{cmd.upper()} {arg}", f"{cmd.upper()} {arg} upload/schedule hoga.")
    elif cmd in ACTIONS:
        need, argv, label = ACTIONS[cmd]
        if not need: run(argv, label)
        else: ask(argv, label, f"{label}\n{EXPLAIN.get(cmd, 'Ye asli upload/schedule karega.')}")
    else:
        near = difflib.get_close_matches(cmd, sorted(KNOWN), n=1, cutoff=0.6) if cmd else []
        if near and near[0] in SAFE_SUGGEST: send(f"'{t[:30]}' samajh nahi aaya. Kya tumhara matlab /{near[0]} tha?", [[(f"✅ Haan: /{near[0]}", f"/{near[0]}")], [b_menu()[0]]])
        elif near and near[0].startswith(("yt", "ig")):     # never suggest a real upload command from a typo: show the menu with the week/channel choice instead
            send(f"'{t[:30]}' samajh nahi aaya. Upload karna hai? Neeche se week chuno, galat command se bachne ke liye.", [[("▶️ YouTube upload", "/youtube")], [("📸 Instagram", "/instagram")], [b_menu()[0]]])
        else: show_menu("Ye samajh nahi aaya.")

BOT_COMMANDS = [("menu", "Main buttons"), ("status", "Kya ho chuka, kya baaki"), ("youtube", "YouTube upload"), ("instagram", "Instagram"), ("more", "Aur options"), ("cancel", "Rok do"), ("help", "Madad")]

def main():
    if not TOKEN or not CHAT: raise SystemExit("bot.env mein BOT_TOKEN aur CHAT_ID chahiye (bot.env.example dekho).")
    threading.Thread(target=autopilot, daemon=True).start()
    threading.Thread(target=outbox_loop, daemon=True).start()
    threading.Thread(target=watch_new_videos, daemon=True).start()
    log("studio bot chalu"); OFF = HERE / "tg_offset.txt"
    try: offset = int(OFF.read_text().strip())      # last handled update, so /update (which exits) is never replayed
    except Exception: offset = None
    try: tg("setMyCommands", data={"commands": json.dumps([{"command": c, "description": d} for c, d in BOT_COMMANDS])}, t=30)   # the "/" list shows only these 7
    except Exception as e: log(f"setMyCommands failed: {e}")
    try: show_menu("Studio bot chalu ✅")
    except Exception as e: log(f"startup send failed: {e}")
    while True:
        try:
            d = tg("getUpdates", data={"timeout": 50, **({"offset": offset} if offset else {})}, t=70)
            for u in d.get("result", []):
                offset = u["update_id"] + 1
                try: OFF.write_text(str(offset))   # remember BEFORE handling (at-most-once)
                except Exception: pass
                cq = u.get("callback_query")
                if cq:                              # a button tap
                    if str(((cq.get("message") or {}).get("chat") or {}).get("id")) != CHAT: continue
                    try: tg("answerCallbackQuery", data={"callback_query_id": cq.get("id")}, t=15)
                    except Exception: pass
                    log(f"button: {str(cq.get('data'))[:40]}"); handle(cq.get("data") or ""); continue
                m = u.get("message") or {}
                if str((m.get("chat") or {}).get("id")) != CHAT or not m.get("text"): continue
                log(f"cmd: {m['text'][:40]}"); handle(m["text"])
        except Exception as e: log(f"poll error: {e}"); time.sleep(5)

if __name__ == "__main__": main()
