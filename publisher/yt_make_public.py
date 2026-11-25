#!/usr/bin/env python3
"""Make videos that were uploaded as SCHEDULED (private + publishAt) public RIGHT NOW. Nothing is re-uploaded.
python yt_make_public.py ..\\week3\\queue.csv --dry-run     show what would change
python yt_make_public.py ..\\week3\\queue.csv               make every uploaded row of that queue public now
python yt_make_public.py ..\\week3\\queue.csv --channel kahani    only one channel
python yt_make_public.py ..\\week3\\queue.csv --only k19          only rows whose id contains k19
Uses uploaded.json (id -> YouTube video id) and the token of each channel (needs the 'youtube' scope: re-run yt_auth.py if it says permission).
videos.update(part=status) replaces the status part, so the current status is read first and sent back unchanged except
privacyStatus=public and without publishAt. Quota: videos.list 1 unit + videos.update 50 units per video (Google docs; [not verified] for this project).
"""
import csv, sys, time
from pathlib import Path
import yt_publish as y   # reuses service(channel), the UTF-8 fix and uploaded.json

KEEP = ("license", "embeddable", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")   # writable status fields we preserve

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: raise SystemExit(__doc__)
    dry = "--dry-run" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    only_ch = sys.argv[sys.argv.index("--channel") + 1].strip().lower() if "--channel" in sys.argv else None
    rows = list(csv.DictReader(open(Path(args[0]), encoding="utf-8-sig")))
    from googleapiclient.errors import HttpError
    n = 0
    for r in rows:
        rid = r["id"].strip(); ch = r["channel"].strip()
        if only and only not in rid: continue
        if only_ch and ch.lower() != only_ch: continue
        vid = y.done.get(rid)
        if not vid: print(f"skip   {rid}: abhi YouTube par upload hi nahi hua"); continue
        try:
            yt = y.service(ch)
            items = yt.videos().list(part="status", id=vid).execute().get("items", [])
            if not items: print(f"   FAILED {rid}: video {vid} channel par nahi mila (shayad delete ho gaya ya galat channel ka token)"); continue
            st = items[0]["status"]
            if st.get("privacyStatus") == "public": print(f"skip   {rid}: already public"); continue
            print(f"{'plan ' if dry else 'public'} {rid}: [{ch}] {r['title'][:60]!r}  ({st.get('privacyStatus')}" + (f", schedule {st['publishAt']}" if st.get("publishAt") else "") + ") -> PUBLIC NOW")
            if dry: continue
            body = {"id": vid, "status": {**{k: st[k] for k in KEEP if k in st}, "privacyStatus": "public"}}   # no publishAt: it goes live immediately
            yt.videos().update(part="status", body=body).execute()
            n += 1; print(f"   PUBLIC https://www.youtube.com/watch?v={vid}")
        except HttpError as e:
            if "quotaExceeded" in str(e): print(f"   STOP: Google project ki API quota khatam. Baaki rows kal dobara chalao. {str(e)[:200]}"); break
            if "insufficientPermissions" in str(e) or e.resp.status == 403: print(f"   FAILED {rid}: permission nahi hai. yt_auth.py se {ch} ke liye dobara sign-in karo. {str(e)[:160]}"); continue
            print(f"   FAILED {rid}: {str(e)[:250]}")
        except SystemExit as e: print(f"   FAILED {rid}: {e}")
    print(f"finished: {n} made public" + (" (dry run, nothing changed)" if dry else ""))

if __name__ == "__main__": main()
