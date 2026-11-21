#!/usr/bin/env python3
"""Publish due Instagram Reels through Meta's official Instagram API (Instagram Login). Runs from GitHub Actions every 30 minutes.

queue.json rows: id, lane (kahani|interview|gta), ig_handle, slot ("YYYY-MM-DD HH:MM" IST), file (videos/<file>.mp4), ig (caption), comment.
A row is published when its slot time has passed and it is not in state.json yet. Tokens come from env IG_TOKEN_<LANE>.
Official flow (developers.facebook.com, checked 2026-11-21): POST /<IG_ID>/media (REELS, video_url, caption, cover_url, share_to_feed,
is_ai_generated) -> GET /<container>?fields=status_code until FINISHED -> POST /<IG_ID>/media_publish.
  python bot/meta_publish.py --dry-run            show what is due
  python bot/meta_publish.py --only i2            publish only this id (test; ignores the slot time)
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
GRAPH = os.environ.get("IG_GRAPH", "https://graph.instagram.com/v27.0")
IST = timezone(timedelta(hours=5, minutes=30))
MAX_AGE = timedelta(days=3)   # a missed post older than this is skipped, not published late
state_path = ROOT / "state.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}

def pages_base():
    b = os.environ.get("PAGES_BASE")
    if b: return b.rstrip("/")
    owner, repo = os.environ["GITHUB_REPOSITORY"].split("/")
    return f"https://{owner.lower()}.github.io/{repo}"

def req(method, url, **kw):
    r = requests.request(method, url, timeout=120, **kw)
    try: d = r.json()
    except Exception: d = {"raw": r.text[:300]}
    if r.status_code >= 400 or "error" in d: raise RuntimeError(f"{method} {url.split('?')[0]} -> {r.status_code}: {json.dumps(d)[:500]}")
    return d

def publish(v, token, base):
    me = req("GET", f"{GRAPH}/me", params={"fields": "user_id,username", "access_token": token})
    me = me["data"][0] if isinstance(me.get("data"), list) else me
    ig_id, uname = me.get("user_id") or me["id"], me["username"]
    if uname.lower() != v["ig_handle"].lower(): raise RuntimeError(f"token belongs to @{uname}, expected @{v['ig_handle']}: wrong secret?")
    video = f"{base}/{v['file']}"; cover = f"{base}/{v['file'].replace('videos/', 'covers/').rsplit('.', 1)[0]}.jpg"
    c = req("POST", f"{GRAPH}/{ig_id}/media", data={"media_type": "REELS", "video_url": video, "cover_url": cover, "caption": v["ig"],
            "share_to_feed": "true", "is_ai_generated": "true", "access_token": token})["id"]
    for _ in range(60):                       # up to ~10 minutes
        s = req("GET", f"{GRAPH}/{c}", params={"fields": "status_code,status", "access_token": token})
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") in ("ERROR", "EXPIRED"): raise RuntimeError(f"container {s}")
        time.sleep(10)
    else: raise RuntimeError("container not FINISHED in 10 minutes")
    media_id = req("POST", f"{GRAPH}/{ig_id}/media_publish", data={"creation_id": c, "access_token": token})["id"]
    note = ""
    if v.get("comment"):
        try: req("POST", f"{GRAPH}/{media_id}/comments", data={"message": v["comment"], "access_token": token})
        except Exception as e: note = f" (first comment failed: {str(e)[:160]})"
    return media_id, note

def main():
    dry = "--dry-run" in sys.argv; only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    rows = json.loads((ROOT / "queue.json").read_text(encoding="utf-8")); now = datetime.now(IST); n = 0; bad = 0
    base = pages_base() if not dry or os.environ.get("GITHUB_REPOSITORY") or os.environ.get("PAGES_BASE") else "https://OWNER.github.io/REPO"
    for v in sorted(rows, key=lambda r: r["slot"]):
        rid = v["id"]
        if only and only != rid: continue
        when = datetime.strptime(v["slot"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        if rid in state: continue
        if not only and when > now: continue
        if not only and now - when > MAX_AGE: print(f"skip {rid}: more than 3 days late"); continue
        print(f"{'due ' if dry else 'post'} {rid}: @{v['ig_handle']} slot {when:%Y-%m-%d %H:%M} IST  {v['file']}")
        if dry: continue
        token = os.environ.get(f"IG_TOKEN_{v['lane'].upper()}")
        if not token: print(f"   ERROR secret IG_TOKEN_{v['lane'].upper()} missing"); bad += 1; continue
        try:
            mid, note = publish(v, token, base); state[rid] = {"media_id": mid, "at": now.isoformat()}
            state_path.write_text(json.dumps(state, indent=1)); n += 1; print(f"   OK published media {mid}{note}")
        except Exception as e: print(f"   FAILED {rid}: {e}"); bad += 1
    print(f"finished: {n} published, {bad} failed" + (" (dry run)" if dry else ""))
    if bad: sys.exit(1)

if __name__ == "__main__": main()
