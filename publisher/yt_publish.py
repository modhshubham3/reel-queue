#!/usr/bin/env python3
"""Upload every row of queue.csv to YouTube as a SCHEDULED video (private until publish_at, then public).

  python yt_publish.py queue.csv --dry-run     show what would happen (nothing is uploaded)
  python yt_publish.py queue.csv               upload everything not uploaded yet
  python yt_publish.py queue.csv --only g03    upload only rows whose 'id' contains 'g03'
  python yt_publish.py queue.csv --now         upload and make PUBLIC IMMEDIATELY (ignores publish_at)
  python yt_publish.py queue.csv --now --per-channel 2   same, but only the next 2 videos per channel in this run

queue.csv columns: id, channel, file, title, description, tags, publish_at, made_for_kids, synthetic
  channel      = kahani | interview | gta   (needs tokens/yt_<channel>.json from yt_auth.py)
  publish_at   = 2026-11-23 19:30           (India time, IST). Must be in the future, otherwise YouTube publishes at once.
  tags         = comma separated.   made_for_kids = no (default) | yes.   synthetic = yes (default; AI voice/animation disclosure)
Official YouTube Data API, videos.insert. Facts (checked on developers.google.com, 2026-11-21): status.publishAt works only when
privacyStatus is private; status.containsSyntheticMedia is the AI-disclosure flag; status.selfDeclaredMadeForKids is the kids flag.
uploaded.json remembers finished rows, so running again never uploads a duplicate.
"""
import csv, json, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles/pipes default to cp1252: an emoji in a title would crash print()
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

HERE = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
CATEGORY = {"kahani": "24", "interview": "27", "gta": "20"}  # Entertainment, Education, Gaming
done_path = HERE / "uploaded.json"
done = json.loads(done_path.read_text()) if done_path.exists() else {}

def clean(t):
    """YouTube rejects < and > in titles, descriptions and tags."""
    return t.replace("<", " less than ").replace(">", " greater than ").replace("  ", " ")

def with_hashtags(desc, tags, title=""):
    """Put 3-5 hashtags on the last line of the description (YouTube shows the first 3 above the title). Max 15 allowed."""
    import re
    if re.search(r"(^|\s)#\w", desc): return desc
    want = [t for t in re.findall(r"#\w+", title)]
    for t in tags:
        h = "#" + re.sub(r"[^A-Za-z0-9_]", "", t.lower().replace("c#", "csharp ").replace(".net", "dotnet ").title().replace(" ", ""))
        if len(h) > 2 and h not in want: want.append(h)
    if "#Shorts" not in want: want.insert(0, "#Shorts")
    return desc.rstrip() + "\n\n" + " ".join(want[:5])

def yes(v, default): v = (v or "").strip().lower(); return default if not v else v in ("yes", "y", "true", "1")

def body_for(r, now=False):
    when = datetime.strptime(r["publish_at"].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    tags = [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()]
    return {
        "snippet": {"title": clean(r["title"].strip())[:100], "description": clean(with_hashtags(r["description"].strip(), tags, r["title"]))[:5000], "tags": [clean(t) for t in tags], "categoryId": CATEGORY.get(r["channel"].strip(), "22")},
        "status": {**({"privacyStatus": "public"} if now else {"privacyStatus": "private", "publishAt": when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")}),
                   "selfDeclaredMadeForKids": yes(r.get("made_for_kids"), False), "containsSyntheticMedia": yes(r.get("synthetic"), True)},
    }, when

def service(channel):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    tok = HERE / "tokens" / f"yt_{channel}.json"
    if not tok.exists(): raise SystemExit(f"tokens/yt_{channel}.json missing: run  python yt_auth.py {channel}")
    return build("youtube", "v3", credentials=Credentials.from_authorized_user_file(str(tok)))

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv; only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    if not args: raise SystemExit(__doc__)
    q = Path(args[0]); rows = list(csv.DictReader(open(q, encoding="utf-8-sig")))
    now = datetime.now(IST); n = 0
    go = "--now" in sys.argv
    per = int(sys.argv[sys.argv.index("--per-channel") + 1]) if "--per-channel" in sys.argv else None; cnt = {}; blocked = set()
    only_ch = sys.argv[sys.argv.index("--channel") + 1].strip().lower() if "--channel" in sys.argv else None   # e.g. --channel kahani
    for r in rows:
        rid = r["id"].strip()
        if only and only not in rid: continue
        if rid in done: print(f"skip   {rid}: already uploaded ({done[rid]})"); continue
        f = (q.parent / r["file"].strip()).resolve()
        if not f.exists(): print(f"ERROR  {rid}: file not found: {f}"); continue
        ch = r["channel"].strip()
        if only_ch and ch.lower() != only_ch: continue
        if per is not None and cnt.get(ch, 0) >= per: continue
        if ch in blocked: print(f"skip   {rid}: [{ch}] channel ki daily upload limit lag chuki hai (baaki channels chalte rahenge)"); continue
        body, when = body_for(r, go)
        warn = "  !! publish_at is in the past: it would go public IMMEDIATELY" if when <= now else ""
        print(f"{'plan ' if dry else 'upload'} {rid}: [{r['channel']}] {body['snippet']['title']!r}  at {'NOW (public immediately)' if go else when.strftime('%Y-%m-%d %H:%M') + ' IST'}  kids={body['status']['selfDeclaredMadeForKids']} synthetic={body['status']['containsSyntheticMedia']}{warn}")
        if dry: continue
        from googleapiclient.http import MediaFileUpload
        yt = service(r["channel"].strip())
        req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(f), mimetype="video/mp4", resumable=True, chunksize=-1))
        resp = None; tries = 0; failed = False
        from googleapiclient.errors import HttpError
        while resp is None:
            try: _, resp = req.next_chunk()
            except HttpError as e:
                code = getattr(e.resp, "status", 0)
                if code in (500, 502, 503, 504) and tries < 5: tries += 1; print(f"   server busy ({code}), retry {tries}/5"); time.sleep(5); continue
                if "uploadLimitExceeded" in str(e):   # per-CHANNEL daily upload limit: skip only this channel, other channels keep going
                    blocked.add(ch); print(f"   LIMIT: [{ch}] channel ki daily upload limit ({code}). Is channel ke baaki rows skip, kal dobara chalao. Google ka message: {str(e)[:200]}"); failed = True; break
                if "quotaExceeded" in str(e): print(f"   STOP: Google project ki API quota khatam ({code}). Baaki rows kal dobara chalao, ye apne aap wahin se aage badhega. Google ka message: {str(e)[:200]}"); print(f"finished: {n} uploaded"); return
                print(f"   FAILED {rid}: {e}"); failed = True; break
            except Exception as e:
                if tries < 5: tries += 1; print(f"   network error, retry {tries}/5: {e}"); time.sleep(5); continue
                print(f"   FAILED {rid}: {e}"); failed = True; break
        if failed: continue
        done[rid] = resp["id"]; done_path.write_text(json.dumps(done, indent=1)); n += 1; cnt[ch] = cnt.get(ch, 0) + 1
        print(f"   OK https://www.youtube.com/watch?v={resp['id']}  " + ("(PUBLIC now)" if go else f"(private now, goes public at {when:%H:%M} IST)"))
    print(f"finished: {n} uploaded" + (" (dry run, nothing sent)" if dry else ""))

if __name__ == "__main__": main()
