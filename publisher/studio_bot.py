#!/usr/bin/env python3
"""studio_bot.py: run the weekly YouTube/Instagram publishing from your phone through a private Telegram bot.

Only talks OUT to Telegram (no ports to open) and only obeys the one chat in CHAT_ID. Secrets live in bot.env (see bot.env.example).
EASY MODE: send /menu (or any message) and tap the buttons. Anything that uploads asks "Haan / Nahi" first (120 seconds).
The old typed commands (/ytcheck /yt2upload /yt3upload /yt3 ID /igcheck /ig ID /update /confirm /cancel ...) still work.
"""
import csv, difflib, html, json, os, re, subprocess, sys, threading, time, zlib
from datetime import datetime
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
WEEK = HERE.parent / "week1"
RAW = "https://raw.githubusercontent.com/modhshubham3/reel-queue/ccr-cb619668-8pcm8x"
FILES = ("ig_publish.py", "yt_publish.py", "yt_hashtags.py", "yt_auth.py", "yt_make_public.py", "yt_stats.py", "studio_bot.py", "UPLOAD_MENU.bat", "UPDATE.bat", "run_studio_bot.bat")
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
def send(text, buttons=None, html_mode=False):
    """buttons = [[(label, callback_data), ...], ...]; callback_data is just a command like "/status" (max 64 bytes).
    html_mode=True: text may contain <b>/<code> tags (a <code> block copies with one tap on the phone)."""
    if html_mode and len(text) > 3900: html_mode = False; text = re.sub(r"<[^>]+>", "", text)   # never cut a tag in half
    chunks = [text[i:i + 3900] for i in range(0, max(len(text), 1), 3900)]
    for n, c in enumerate(chunks):
        data = {"chat_id": CHAT, "text": c}
        if html_mode: data["parse_mode"] = "HTML"
        if buttons and n == len(chunks) - 1:
            data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": l, "callback_data": d} for l, d in row] for row in buttons]})
        tg("sendMessage", data=data, t=30)

WEEK2 = HERE.parent / "week2"; Q2 = str(WEEK2 / "queue.csv")
WEEK3 = HERE.parent / "week3"; Q3 = str(WEEK3 / "queue.csv")
Q = str(WEEK / "queue.csv"); M = str(WEEK / "meta.json")
WEEK4 = HERE.parent / "week4"; Q4 = str(WEEK4 / "queue.csv")
WEEK5 = HERE.parent / "week5"; Q5 = str(WEEK5 / "queue.csv")
WEEK6 = HERE.parent / "week6"; Q6 = str(WEEK6 / "queue.csv")
WEEK7 = HERE.parent / "week7"; Q7 = str(WEEK7 / "queue.csv")
WEEKS = {"1": ("Week 1", Q), "2": ("Week 2", Q2), "3": ("Week 3", Q3), "4": ("Week 4", Q4), "5": ("Week 5 (v2)", Q5), "6": ("Week 6 (lambi kahani)", Q6), "7": ("Week 7 (Shorts parts)", Q7)}

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

def get_week(n):
    """download weekN/queue.csv and every video it lists from the public reel-queue repo (skips files already complete)"""
    W = HERE.parent / f"week{n}"
    def work():
        if not busy.acquire(blocking=False): send("Ek kaam pehle se chal raha hai, thoda ruko."); return
        try:
            send(f"▶ Week {n} download shuru...")
            (W / "videos").mkdir(parents=True, exist_ok=True)
            r = requests.get(f"{RAW}/week{n}/queue.csv", timeout=60); r.raise_for_status(); (W / "queue.csv").write_bytes(r.content)
            rows_ = list(csv.DictReader(open(W / "queue.csv", encoding="utf-8-sig"))); got = miss = 0; last = time.time()
            for row in rows_:
                dest = W / row["file"].strip()
                try:
                    h = requests.head(f"{RAW}/week{n}/{row['file'].strip()}", timeout=60, allow_redirects=True)
                    size = int(h.headers.get("Content-Length", 0))
                    if dest.exists() and size and dest.stat().st_size == size: got += 1; continue
                    with requests.get(f"{RAW}/week{n}/{row['file'].strip()}", stream=True, timeout=300) as rr:
                        rr.raise_for_status()
                        with open(dest, "wb") as fh:
                            for chunk in rr.iter_content(1 << 20): fh.write(chunk)
                    got += 1
                except Exception as e:
                    miss += 1; send(f"FAIL {row['id']}: {str(e)[:100]}")
                if time.time() - last > 25: send(f"... {got}/{len(rows_)} videos aa chuke"); last = time.time()
            send(f"✅ Week {n}: {got}/{len(rows_)} videos laptop par hain" + (f", {miss} fail (dobara dabao)" if miss else f". Ab YouTube ▶ Week {n} se check aur upload."), [[("▶️ YouTube", "/youtube"), ("🏠 Menu", "/menu")]])
        except Exception as e: send(f"Error: {e}")
        finally: busy.release()
    threading.Thread(target=work, daemon=True).start()

def get_week2(): get_week("2")

# ---------------------------------------------------------------- Instagram MANUAL flow: pick channel + count -> video + caption + first comment -> you post -> tap Done
IG_CTA = {"interview": "Follow @interview.chai for C# and SQL explained simply ☕", "kahani": "Roz ek nayi kahani 🌙 Follow @kahaniyon.wali.raat", "gta": "Follow @bawaalmoments for how games really work 🎮"}
IG_ASK = {   # first-comment questions; one is picked per video from its id, so the same video always gets the same one
    "interview": ["Ye answer interview mein bolne se pehle pata tha? 1 likho agar haan, 2 agar nahi 👇", "Is topic ka agla video kaunsa chahiye? Comment mein likho 👇", "Save kar lo, interview se pehle ek baar dekh lena 📌", "Tumhare interview mein ye kabhi pucha gaya? Batao 👇"],
    "kahani": ["Is kahani se tumne kya seekha? Ek line mein comment karo 👇", "Ye kahani tumhe kisne sunayi thi? Dada, dadi, nana ya nani? 👇", "Agli kahani kaunsi chahiye? Naam likho 👇", "Kisi apne ko ye kahani bhejo jise sunna pasand ho 🌙"],
    "gta": ["Pata tha games mein ye aise hota hai? Haan ya Nahi 👇", "Agla kaunsa game trick samjhaun? Comment karo 👇", "Save kar lo, dost ko bhejo jo games ka shauqeen ho 🎮", "Sabse ajeeb game bug jo tumne dekha? Likho 👇"]}
IG_DROP_TAGS = {"#shorts", "#gta6"}       # #Shorts is a YouTube tag; #GTA6 would suggest an official GTA VI video (we say "not official" in the video)
IGM = HERE / "ig_manual.json"; IGB = HERE / "ig_batch.json"

def all_rows():
    """every row of every week's queue (unique id), oldest week and YouTube slot first"""
    seen = {}
    for n in sorted(WEEKS):
        base = Path(WEEKS[n][1]).parent
        for r in qrows(WEEKS[n][1]):
            rid = (r.get("id") or "").strip()
            if rid and rid not in seen: r = dict(r); r["_path"] = base / r["file"].strip(); r["_week"] = n; seen[rid] = r
    return sorted(seen.values(), key=lambda r: (r["_week"], (r.get("publish_at") or "").strip().replace("T", " "), r["id"].strip()))   # week 1 first, then by YouTube slot

def ig_done_ids():
    """-> (publora_ids, manual_ids). Publora = scheduled/posted by ig_publish.py, manual = you tapped Done"""
    return set(jload(HERE / "ig_uploaded.json")), set(jload(IGM))

def ig_pending(ch=None):
    """videos that are already on YouTube but not on Instagram yet (not in Publora, not marked done)"""
    yt = set(jload(HERE / "uploaded.json")); pub, man = ig_done_ids(); skip = pub | man
    return [r for r in all_rows() if r["id"].strip() in yt and r["id"].strip() not in skip and (not ch or r["channel"].strip() == ch)]

def clean_title(r): return re.sub(r"\s*#\w+", "", r.get("title") or "").strip()

def ig_text(r):
    """-> (caption, first comment). Week 1: written text from meta.json. Other weeks: built from the YouTube row (hook, body, one follow line, up to 4 hashtags)."""
    rid = r["id"].strip(); ch = r["channel"].strip()
    try: meta = {m["id"]: m for m in json.loads((WEEK / "meta.json").read_text(encoding="utf-8-sig"))}
    except Exception: meta = {}
    if rid in meta and meta[rid].get("ig") and meta[rid].get("comment"): return meta[rid]["ig"].strip(), meta[rid]["comment"].strip()
    desc = (r.get("description") or "").strip()
    paras = [x.strip() for x in re.split(r"\n\s*\n", desc) if x.strip()]
    body = [x for x in paras if not x.startswith("#") and not re.match(r"(?i)(subscribe|follow|roz ek)", x)]
    last = paras[-1] if paras and paras[-1].startswith("#") else (r.get("title") or "")
    tags = [t for t in re.findall(r"#\w+", last) if t.lower() not in IG_DROP_TAGS][:4]
    cap = "\n\n".join([clean_title(r)] + body + [IG_CTA.get(ch, "")] + ([" ".join(tags)] if tags else [])).strip()
    asks = IG_ASK.get(ch) or IG_ASK["interview"]
    return cap[:2200], asks[zlib.crc32(rid.encode()) % len(asks)]

def ig_mark(ids, on=True):
    d = jload(IGM)
    for i in ids:
        if on: d[i] = {"at": datetime.now().strftime("%Y-%m-%d %H:%M")}
        else: d.pop(i, None)
    IGM.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")

def ig_counts():
    """-> {channel: (on YouTube, on Instagram, still to post on Instagram)}"""
    yt = set(jload(HERE / "uploaded.json")); pub, man = ig_done_ids(); ig = pub | man; rows = all_rows(); out = {}
    for ch in CHANNELS:
        ids = [r["id"].strip() for r in rows if r["channel"].strip() == ch]
        out[ch] = (sum(i in yt for i in ids), sum(i in ig for i in ids), sum(i in yt and i not in ig for i in ids))
    return out

def show_igman(ch=""):
    c = ig_counts()
    if ch not in CHANNELS:
        send("📲 Instagram manual post\nChannel chuno (bracket mein: YouTube par gaye lekin Instagram par abhi nahi):",
             [[(f"{CH_LABEL[n]} ({c[n][2]})", f"/igman {n}")] for n in CHANNELS] + [[("📊 Status", "/status"), ("⬅️ Wapas", "/instagram")]]); return
    yt, ig, left = c[ch]
    if not left: send(f"{CH_LABEL[ch]}: YouTube {yt} · Instagram {ig} · baaki 0. Sab ho gaya ✅", [[("⬅️ Wapas", "/igman")]]); return
    send(f"{CH_LABEL[ch]}: YouTube {yt} · Instagram {ig} · baaki {left}\nKitne videos chahiye? (video + caption + pehla comment aayega)",
         [[(str(k), f"/igsend {ch} {k}") for k in (1, 3, 5) if k < left] + [(f"Sab {left}" if left <= 10 else "10", f"/igsend {ch} {min(left, 10)}")], [("📋 List dekho", f"/iglist {ch}"), ("⬅️ Wapas", "/igman")]])

def ig_send(ch, n):
    def work():
        if not video_lock.acquire(blocking=False): send("Videos pehle se bhej raha hoon, thoda ruko."); return
        try:
            pend = ig_pending(ch)
            if not pend: send(f"{CH_LABEL[ch]}: Instagram ke liye kuch baaki nahi ✅", [[("⬅️ Wapas", "/igman")]]); return
            take = pend[:n]; done_now = []
            send(f"📲 {CH_LABEL[ch]}: {len(pend)} baaki. Abhi {len(take)} bhej raha hoon...")
            for r in take:
                rid = r["id"].strip(); cap, com = ig_text(r)
                if not send_video(r["_path"], f"📲 {rid} · {CH_LABEL[ch]}\n{clean_title(r)}"): send(f"⚠ {rid}: video nahi gaya, isko chhod diya (upar wala message dekho)."); continue
                send(f"<b>{html.escape(rid)}</b> · {html.escape(clean_title(r))}\n\n📝 <b>CAPTION</b> (tap karke copy):\n<code>{html.escape(cap)}</code>\n\n💬 <b>PEHLA COMMENT</b> (post ke baad daalo):\n<code>{html.escape(com)}</code>\n\n⚠ Post karte waqt Instagram mein 'AI label' ON karo.",
                     [[("✅ Post kar diya", f"/igdone {rid}")]], html_mode=True)
                done_now.append(rid)
            IGB.write_text(json.dumps(done_now))
            if done_now: send(f"✅ {len(done_now)} video bheje.\nHar video post karne ke baad uske neeche ✅ dabao, ya sab ek saath post kar chuke ho to neeche wala button.",
                              [[(f"✅ Sab {len(done_now)} post ho gaye", "/igdoneall")], [("📲 Aur chahiye", f"/igman {ch}"), ("🏠 Menu", "/menu")]])
        except Exception as e: send(f"Error: {e}")
        finally: video_lock.release()
    threading.Thread(target=work, daemon=True).start()

def ig_done_cmd(arg, on=True):
    rows = {r["id"].strip(): r for r in all_rows()}; ids = [i for i in re.split(r"[\s,]+", arg) if i]
    bad = [i for i in ids if i not in rows]; ids = [i for i in ids if i in rows]
    if not ids: send("Aise video ID nahi mila: " + (", ".join(bad) or "(ID likho, jaise /igdone i39)"), [[("📲 Manual post", "/igman")]]); return
    ig_mark(ids, on); c = ig_counts(); ch = rows[ids[0]]["channel"].strip()
    send(("✅ Done mark kiya: " if on else "↩️ Wapas baaki kiya: ") + ", ".join(ids) + (f"\n(ID nahi mile: {', '.join(bad)})" if bad else "") + f"\n{CH_LABEL.get(ch, ch)}: Instagram par baaki {c[ch][2]}",
         [[(f"📲 {CH_LABEL.get(ch, ch)}: agla", f"/igman {ch}"), ("📊 Status", "/status")]])

def ig_list(ch):
    rows = ig_pending(ch)
    if not rows: send(f"{CH_LABEL.get(ch, ch)}: Instagram ke liye kuch baaki nahi ✅", [[("⬅️ Wapas", "/igman")]]); return
    send(f"{CH_LABEL.get(ch, ch)}: Instagram par baaki {len(rows)}\n\n" + "\n".join(f"{r['id'].strip()} · {clean_title(r)[:55]}" for r in rows[:40]) + ("\n..." if len(rows) > 40 else ""),
         [[("📲 Bhejo", f"/igman {ch}"), ("⬅️ Wapas", "/igman")]])

# ---------------------------------------------------------------- Friday bridge: the Friday phone app <-> this bot, through ntfy.sh (no open ports, no accounts)
# Phone reads  <topic>-status  (counts + real YouTube numbers, no secrets) and writes  <topic>-cmd  (signed commands from a SAFE list).
# Topic + secret are made once, kept in bot.env, and shown only in your private Telegram chat as a pairing code ( /friday ).
# Commands never upload anything: uploads still need the Haan/Nahi button in Telegram. Replies to a command appear in Telegram.
import hashlib, hmac, secrets
BRIDGE_HOST = os.environ.get("BRIDGE_HOST", "https://ntfy.sh").rstrip("/")
BRIDGE_SAFE = re.compile(r"^/?(status|menu|stats|igman( (interview|kahani|gta))?|igsend (interview|kahani|gta) \d{1,2}|iglist (interview|kahani|gta)|igdone [\w, ]{1,80}|igundo [\w ]{1,40}|watch [1-7] (interview|kahani|gta)|week [1-7]|ytcheck|yt[2-7]check|ytpubcheck [1-7])$")
BSEEN = HERE / "bridge_seen.json"

def bridge_conf():
    """-> (topic, secret); created and saved to bot.env the first time"""
    if not os.environ.get("BRIDGE_TOPIC") or not os.environ.get("BRIDGE_SECRET"):
        t, k = "friday-" + secrets.token_urlsafe(18).replace("_", "x").replace("-", "y"), secrets.token_hex(16)
        with open(HERE / "bot.env", "a", encoding="utf-8") as f: f.write(f"\nBRIDGE_TOPIC={t}\nBRIDGE_SECRET={k}\n")
        os.environ["BRIDGE_TOPIC"], os.environ["BRIDGE_SECRET"] = t, k
    return os.environ["BRIDGE_TOPIC"], os.environ["BRIDGE_SECRET"]

def bridge_pairing():
    t, k = bridge_conf()
    send("🔗 Friday app pairing\nApp mein: Settings > Studio > ye poori line paste karo (sirf tumhare liye, kisi ko mat dena):\n\n" + f"friday-pair:{t}:{k}" +
         "\n\nIske baad Friday se bolo: 'studio ka status batao'. Bot apni taraf se har ~2 minute mein status bhejta hai, aur app ke hukum sirf ek safe list se chalte hain (upload kabhi nahi).", [b_menu()])

def sign(secret, mid, ts, cmd): return hmac.new(secret.encode(), f"{mid}|{ts}|{cmd}".encode(), hashlib.sha256).hexdigest()

def bridge_status():
    c = ig_counts(); weeks = {}
    for n in WEEKS:
        pr = week_progress(n)
        if pr: weeks[n] = {"name": WEEKS[n][0], "yt": pr[0], "total": pr[1]}
    st = jload(HERE / "yt_stats.json"); ch = st.get("channels", {})
    return {"v": 1, "ts": int(time.time()), "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "weeks": weeks,
            "ig": {n: {"yt": c[n][0], "ig": c[n][1], "left": c[n][2]} for n in CHANNELS}, "auto_ig": auto_on(), "busy": busy.locked(),
            "stats_at": st.get("at"), "stats": {n: {k: ch[n][k] for k in ("uploaded", "public", "views", "avg_views", "zero_view_public", "comments", "top") if k in ch[n]} for n in ch}}

def bridge_loop():
    """every ~2 min: publish the status; every ~20 s: look for signed commands from the phone"""
    topic, secret = bridge_conf(); seen = set(jload(BSEEN).get("ids", [])); last_pub = 0.0; since = "5m"
    while True:
        try:
            if time.time() - last_pub > 120:
                body = json.dumps(bridge_status(), ensure_ascii=False, separators=(",", ":"))
                requests.post(f"{BRIDGE_HOST}/{topic}-status", data=body.encode("utf-8"), headers={"Cache": "yes", "Title": "studio-status"}, timeout=20); last_pub = time.time()
            r = requests.get(f"{BRIDGE_HOST}/{topic}-cmd/json", params={"poll": "1", "since": since}, timeout=30)
            for line in r.text.splitlines():
                try: ev = json.loads(line)
                except Exception: continue
                if ev.get("event") != "message": continue
                since = ev.get("id", since)
                try: c = json.loads(ev.get("message", ""))
                except Exception: continue
                mid, ts, cmd, sig = str(c.get("id", "")), int(c.get("ts", 0)), str(c.get("cmd", "")).strip(), str(c.get("sig", ""))
                ok = bool(mid) and mid not in seen and abs(time.time() - ts) < 600 and hmac.compare_digest(sig, sign(secret, mid, ts, cmd)) and bool(BRIDGE_SAFE.match(cmd))
                if mid: seen.add(mid); BSEEN.write_text(json.dumps({"ids": sorted(seen)[-300:]}))
                msg = "ok" if ok else "refused (signature, time, repeat or not on the safe list)"
                log(f"bridge cmd {cmd[:40]}: {msg}")
                try: requests.post(f"{BRIDGE_HOST}/{topic}-ack", data=json.dumps({"id": mid, "ok": ok, "msg": msg}).encode(), timeout=15)
                except Exception: pass
                if ok:
                    send(f"🤖 Friday app ne bheja: {cmd}"); handle(cmd if cmd.startswith("/") else "/" + cmd); last_pub = 0.0
        except Exception as e: log(f"bridge error: {str(e)[:120]}")
        time.sleep(20)

def stats_loop():
    """real YouTube numbers every 3 hours (read-only, ~a few quota units); also on /stats"""
    time.sleep(90)
    while True:
        try:
            if (HERE / "tokens").exists():
                subprocess.run([sys.executable, str(HERE / "yt_stats.py")], cwd=HERE, capture_output=True, timeout=600, env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        except Exception as e: log(f"stats error: {str(e)[:100]}")
        time.sleep(3 * 3600)

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
    for n in ("1", "2", "3", "4", "5", "6", "7"):
        p = week_progress(n)
        if p is None: out.append(f" {WEEKS[n][0]}: queue file nahi mili"); continue
        d, t, per = p
        line = f" {WEEKS[n][0]}: {d}/{t}" + ("  ✅ poora" if d == t else "  (" + " · ".join(f"{CH_LABEL.get(c, c)} {a}/{b}" for c, (a, b) in per.items()) + ")")
        out.append(line)
        if d < t: todo.append((n, t - d))
    c = ig_counts(); man = jload(IGM)
    out += ["", "Instagram (jo YouTube par gaye, unme se):"] + [f" {CH_LABEL[n]}: YouTube {c[n][0]} · Instagram {c[n][1]} · baaki {c[n][2]}" for n in CHANNELS]
    out += [f" (Instagram = Publora schedule {len(i)} + haath se post {len(man)})"]
    out += ["", f"Instagram schedule hue: {len(i)}",
            f"YouTube sign-in: {', '.join(CH_LABEL[t] for t in toks) or 'koi nahi'}" + ("" if len(toks) == 3 else "  ⚠ baaki channels ka sign-in chahiye (yt_auth.py)"),
            f"Publora key: {'haan' if (HERE / 'publora_key.txt').exists() else 'NAHI'}", ""]
    nxt = next((t for t in todo if t[0] == "5"), next((t for t in todo if t[0] == "6"), todo[-1] if todo else None))    # oldest unfinished v2 week first
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
    "yt6check": (False, ["yt_publish.py", Q6, "--dry-run"], "YouTube Week 6 check"),
    "yt6upload": (True, ["yt_publish.py", Q6], "YouTube Week 6 upload (schedule ke saath)"),
    "yt7check": (False, ["yt_publish.py", Q7, "--dry-run"], "YouTube Week 7 check"),
    "yt7upload": (True, ["yt_publish.py", Q7], "YouTube Week 7 upload (schedule ke saath)"),
    "stats": (False, ["yt_stats.py"], "YouTube numbers (views, likes, comments)"),
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
    "yt7upload": "Week 7 (3 kahaniyon ke 4-4 Shorts parts, 29 Nov) ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge. YouTube ka upload quota ~6 video/din hai: quota khatam ho to kal dobara dabao, jo ho chuke wo dobara nahi jayenge.",
    "yt6upload": "Week 6 (lambi kahani style, 13-17 Dec) ke jo video abhi YouTube par nahi gaye, wo schedule hoke upload honge. Jo ho chuke wo dobara nahi jayenge.",
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
    send("YouTube: kaunsa week?\n(Week 6 = naya lamba storyteller style, 13-17 Dec | Week 5 = v2 style, 8-12 Dec | Week 4 = purana style)", [[("🧩 Week 7 (Shorts parts, 12)", "/week 7")], [("🆕 Week 6 (lambi, 30)", "/week 6"), ("⭐ Week 5 (v2, 30)", "/week 5")], [("Week 4 (30)", "/week 4")], [("Week 3 (30)", "/week 3")], [("Week 2 (30)", "/week 2"), ("Week 1 (21)", "/week 1")], [b_menu()[0]]])

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
         [[("📲 Manual post (video + caption)", "/igman")], [("⚡ Abhi post: agla 1", "/igpost 1"), ("⚡ Abhi post: agle 3", "/igpost 3")], [("🔍 Check (safe)", "/igcheck"), ("📋 Plan/limits", "/igplan")], [("🗓️ Schedule (free plan)", "/igfree")], [("🗓️ Schedule poora hafta", "/igall")],
          [("🤖 Auto ON", "/igauto on"), ("Auto OFF", "/igauto off")], [b_menu()[0]]])

def show_more():
    send("Aur options:", [[("🔄 Naye scripts download (/update)", "/update")], [("⬇️ Week 7 videos download", "/w7get")], [("📈 YouTube numbers (stats)", "/stats")], [("🔗 Friday app pairing", "/friday")], [("⬇️ Week 2 videos download", "/w2get")], [("🏷️ Purane YouTube videos mein hashtags", "/ythash")], [("❌ Cancel", "/cancel"), b_menu()[0]]])

HELP = ("Bas /menu bhejo aur button dabao. Kuch type karne ki zaroorat nahi.\n\n"
        "Short list:\n/menu  main buttons\n/status  kya ho chuka, kya baaki\n/youtube  YouTube upload (week chuno)\n/instagram  Instagram\n/more  aur options\n/cancel  rok do\n\n"
        "Purane commands bhi chalte hain: /yt3check /yt3upload /yt3 ID /yt2upload /ytcheck /igcheck /update ...\n\nInstagram haath se: /igman (channel + kitne videos), /igdone ID (post ho gaya), /igundo ID, /iglist kahani")
KNOWN = set(ACTIONS) | {"menu", "status", "youtube", "instagram", "more", "help", "start", "update", "cancel", "confirm", "w2get", "w7get", "friday", "yt2now", "igauto", "ignow", "yt3", "yt", "ig", "week", "ytch", "ytpub", "ytpubcheck", "watch", "igpost", "igman", "igsend", "igdone", "igdoneall", "igundo", "iglist"}

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
    elif cmd == "w7get": get_week("7")
    elif cmd == "friday": bridge_pairing()
    elif cmd == "yt2now":
        ask(["yt_publish.py", Q2, "--now"] + (["--per-channel", arg] if arg.isdigit() else []), "YouTube Week 2 TURANT PUBLIC",
            "⚠ Week 2: " + (f"har channel ke agle {arg} video" if arg.isdigit() else "saare baaki video") + " abhi PUBLIC ho jayenge (schedule nahi).")
    elif cmd == "igauto":
        if arg.lower() == "on": set_auto(True); kick.set(); send("Auto Instagram ON. Abhi ek round chalega, phir har 3 ghante mein jo slot khaali hoga usme agla video schedule hoga.", [b_menu()])
        elif arg.lower() == "off": set_auto(False); send("Auto Instagram OFF.", [b_menu()])
        else: send("Auto Instagram abhi: " + ("ON" if auto_on() else "OFF"), [[("🤖 ON", "/igauto on"), ("OFF", "/igauto off")]])
    elif cmd == "igman": show_igman(arg.lower())
    elif cmd == "igsend":    # "/igsend kahani 3": send the next 3 videos with caption + first comment
        ch, _, k = arg.lower().partition(" ")
        if ch in CHANNELS and k.strip().isdigit() and 1 <= int(k) <= 10: ig_send(ch, int(k))
        else: show_igman()
    elif cmd == "igdone": ig_done_cmd(arg)
    elif cmd == "igundo": ig_done_cmd(arg, on=False)
    elif cmd == "igdoneall":
        ids = json.loads(IGB.read_text()) if IGB.exists() else []
        if ids: ig_done_cmd(" ".join(ids)); IGB.write_text("[]")
        else: send("Abhi koi bheja hua batch nahi hai. Video ke neeche ✅ dabao ya /igdone ID likho.", [[("📲 Manual post", "/igman")]])
    elif cmd == "iglist": ig_list(arg.lower())
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
    threading.Thread(target=bridge_loop, daemon=True).start()
    threading.Thread(target=stats_loop, daemon=True).start()
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
