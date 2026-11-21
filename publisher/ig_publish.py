#!/usr/bin/env python3
"""Schedule Instagram Reels (caption, cover, AI label, first comment, time) through the Publora API, from week1/meta.json.

  python ig_publish.py ..\\week1\\meta.json --dry-run       show the plan (no network)
  python ig_publish.py ..\\week1\\meta.json --only i2       schedule just one video (test)
  python ig_publish.py ..\\week1\\meta.json --lanes interview,kahani   free plan: skip GTA
  python ig_publish.py ..\\week1\\meta.json                 schedule everything not done yet
  python ig_publish.py ..\\week1\\meta.json --plan          show plan limits (monthly posts, queue, how far ahead)
  python ig_publish.py ..\\week1\\meta.json --only i2 --now   post it RIGHT NOW (also works for a video already scheduled)

Put your Publora API key (Publora dashboard -> API) in publisher/publora_key.txt (one line) or set PUBLORA_API_KEY.
Each Instagram account must be connected in Publora (Channels). The account is matched by its Instagram username.
Flow (checked on docs.publora.com, 2026-11-21): create-post (draft) -> get-upload-url -> PUT video -> upload-instagram-cover
-> update-post (coverUrl + status scheduled + scheduledTime). ig_uploaded.json remembers finished rows (no duplicates).
"""
import json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("PUBLORA_BASE", "https://api.publora.com/api/v1")
IST = timezone(timedelta(hours=5, minutes=30))
done_path = HERE / "ig_uploaded.json"
done = json.loads(done_path.read_text()) if done_path.exists() else {}

def api_key():
    k = os.environ.get("PUBLORA_API_KEY", "").strip()
    f = HERE / "publora_key.txt"
    if not k and f.exists(): k = f.read_text().strip()
    return k

def call(method, path, key, **kw):
    h = {"x-publora-key": key}; h.update(kw.pop("headers", {}))
    r = requests.request(method, BASE + path, headers=h, timeout=120, **kw)
    try: data = r.json()
    except Exception: data = {"raw": r.text[:300]}
    if r.status_code >= 400 or data.get("success") is False:
        raise RuntimeError(f"{method} {path} -> {r.status_code}: {json.dumps(data)[:400]}")
    return data

def get_ctx(key):
    try: return call("GET", "/account-context", key)["context"]
    except Exception as e: print("   (plan check skipped:", str(e)[:140] + ")"); return None

def lim(q): return "unlimited" if q.get("limit") is None else q["limit"]

def print_plan(ctx, conns):
    q = ctx["quotas"]; m, sq, h, c = q["monthlyPosts"], q["scheduledPosts"], q["scheduleHorizon"], q["connections"]
    print(f"Plan: {ctx['plan']['name']}")
    print(f"Is mahine ke posts: {m.get('used')}/{lim(m)}  (baaki {m.get('remaining')}, reset {str(m.get('resetAt'))[:10]})")
    print(f"Scheduled queue: {sq.get('used')}/{lim(sq)}  (baaki {sq.get('remaining')})")
    print(f"Kitna aage schedule ho sakta hai: {lim(h)} din (last date {str(h.get('maxScheduledDate'))[:10]})")
    print(f"Channels: {c.get('used')}/{lim(c)} use mein")
    print("Connected Instagram:", ", ".join(conns) or "none")

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv; go = "--now" in sys.argv; only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    lanes = sys.argv[sys.argv.index("--lanes") + 1].split(",") if "--lanes" in sys.argv else None   # e.g. interview,kahani
    if not args: raise SystemExit(__doc__)
    meta_path = Path(args[0]).resolve(); base = meta_path.parent
    rows = json.loads(meta_path.read_text(encoding="utf-8")); now = datetime.now(IST)
    key = api_key()
    if not dry and not key: raise SystemExit("No API key: put it in publisher/publora_key.txt (Publora dashboard -> API).")
    conns = {}
    if not dry:
        for c in call("GET", "/platform-connections", key)["connections"]:
            if c["platformId"].startswith("instagram-"): conns[c["username"].lower()] = c["platformId"]
        print("connected Instagram accounts:", ", ".join(conns) or "none")
    ctx = None if dry else get_ctx(key)
    if "--plan" in sys.argv:
        if ctx: print_plan(ctx, list(conns))
        return
    slots_left = monthly_left = horizon = None
    if ctx:
        q = ctx["quotas"]; slots_left = q["scheduledPosts"].get("remaining"); monthly_left = q["monthlyPosts"].get("remaining")
        mx = q["scheduleHorizon"].get("maxScheduledDate")
        if mx: horizon = datetime.fromisoformat(mx.replace("Z", "+00:00"))
    rows.sort(key=lambda v: v["slot"])
    n = 0
    for v in rows:
        rid = v["id"]
        if only and only not in rid: continue
        if lanes and v["lane"] not in lanes: continue
        if rid in done and go and not dry:
            try:   # already uploaded/scheduled earlier -> publish that same post immediately (docs: update-post publishNow)
                call("PUT", f"/update-post/{done[rid]}", key, json={"publishNow": True}, headers={"Idempotency-Key": f"w1-{rid}-now"})
                print(f"   OK {rid}: abhi publish ho raha hai (postGroupId {done[rid]}). 1-2 minute mein Instagram par aayega."); n += 1
            except Exception as e: print(f"   FAILED {rid}: {e}")
            continue
        if rid in done: print(f"skip   {rid}: already scheduled ({done[rid]})"); continue
        when = datetime.strptime(v["slot"], "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        if ctx and not dry:
            if monthly_left is not None and monthly_left <= 0: print("   STOP: is mahine ke posts khatam. Naye mahine se chalega."); break
            if not go and slots_left is not None and slots_left <= 0: print("   STOP: scheduled queue bhari hai. Ek post publish hote hi agla jayega."); break
            if not go and horizon and when.astimezone(timezone.utc) > horizon: print(f"later  {rid}: slot {when:%d %b %H:%M} abhi aage ki limit se bahar, baad mein ho jayega"); continue
        video = base / "videos" / f"{v['file']}.mp4"; cover = base / "covers" / f"{v['file']}.png"
        warn = "  !! time is in the past" if (when <= now and not go) else ""
        print(f"{'plan  ' if dry else 'upload'} {rid}: @{v['ig_handle']}  {when:%Y-%m-%d %H:%M} IST  {video.name}  cover={'yes' if cover.exists() else 'NO'}{warn}")
        if dry: continue
        if not video.exists(): print("   ERROR video missing:", video); continue
        cid = conns.get(v["ig_handle"].lower())
        if not cid: print(f"   ERROR @{v['ig_handle']} is not connected in Publora (Channels -> Add channel -> Instagram)"); continue
        try:
            body = {"content": v["ig"], "platforms": [cid], "platformSettings": {"instagram": {"videoType": "REELS", "aiGenerated": True}},
                    "firstComments": [{"text": v["comment"], "delaySeconds": 60}]}
            pg = call("POST", "/create-post", key, json=body, headers={"Idempotency-Key": f"w1-{rid}-create"})["postGroupId"]
            up = call("POST", "/get-upload-url", key, json={"fileName": video.name, "contentType": "video/mp4", "type": "video", "postGroupId": pg})
            with open(video, "rb") as f:
                r = requests.put(up["uploadUrl"], data=f, headers={"Content-Type": "video/mp4"}, timeout=600)
            if r.status_code >= 300: raise RuntimeError(f"video upload failed {r.status_code}: {r.text[:200]}")
            patch = {"publishNow": True} if go else {"status": "scheduled", "scheduledTime": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}
            if cover.exists():
                with open(cover, "rb") as f:
                    c = call("POST", "/upload-instagram-cover", key, files={"cover": (cover.name, f, "image/png")}, data={"postGroupId": pg})
                patch["platformSettings"] = {"instagram": {"coverUrl": c["cover"]["url"]}}
            res = call("PUT", f"/update-post/{pg}", key, json=patch)
            done[rid] = pg; done_path.write_text(json.dumps(done, indent=1)); n += 1
            if monthly_left is not None: monthly_left -= 1
            if slots_left is not None and not go: slots_left -= 1
            print(f"   OK {'publishing NOW' if go else 'scheduled for ' + str(res.get('scheduledTime', patch.get('scheduledTime')))}  (postGroupId {pg})")
        except Exception as e:
            print(f"   FAILED {rid}: {e}")
            if any(w in str(e).lower() for w in ("limit", "queue", "plan", "upgrade", "quota", "horizon", "ahead")):
                print("   >> Free plan limit reached (3 scheduled at a time / 15 posts a month / 7 days ahead). Run this again in 2-3 days."); break
    print(f"finished: {n} " + ("published now" if go else "scheduled") + (" (dry run)" if dry else ""))

if __name__ == "__main__": main()
