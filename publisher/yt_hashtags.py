#!/usr/bin/env python3
"""Add hashtags to the description of videos that are ALREADY on YouTube (uses uploaded.json + queue.csv).

  python yt_hashtags.py ..\\week1\\queue.csv --dry-run    show what would change
  python yt_hashtags.py ..\\week1\\queue.csv              do it (videos that already have a #hashtag are skipped)

Needs the broader sign-in (yt_auth.py now asks for the 'youtube' scope). If you signed in before this change, sign in again
(menu 8, 9, 10) so Google gives edit permission. Cost: ~50 quota units per video.
"""
import csv, json, sys
from pathlib import Path
import yt_publish as Y

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args: raise SystemExit(__doc__)
    rows = {r["id"].strip(): r for r in csv.DictReader(open(args[0], encoding="utf-8-sig"))}
    svc = {}; n = 0
    for rid, vid in Y.done.items():
        r = rows.get(rid)
        if not r: print(f"skip   {rid}: not in queue.csv"); continue
        ch = r["channel"].strip()
        try:
            yt = svc.get(ch) or svc.setdefault(ch, Y.service(ch))
            items = yt.videos().list(part="snippet", id=vid).execute().get("items", [])
            if not items: print(f"skip   {rid}: video {vid} not found on this channel"); continue
            sn = items[0]["snippet"]; desc = sn.get("description", "")
            tags = [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()]
            new = Y.clean(Y.with_hashtags(desc, tags, sn.get("title", "")))
            if new == desc: print(f"skip   {rid}: already has hashtags"); continue
            print(f"{'plan ' if dry else 'update'} {rid} [{ch}] -> ..." + new[-60:].replace("\n", " "))
            if dry: continue
            body = {"id": vid, "snippet": {"title": sn["title"], "description": new[:5000], "categoryId": sn["categoryId"], "tags": sn.get("tags", [])}}
            if sn.get("defaultLanguage"): body["snippet"]["defaultLanguage"] = sn["defaultLanguage"]
            yt.videos().update(part="snippet", body=body).execute(); n += 1
        except Exception as e:
            s = str(e)
            if "insufficientPermissions" in s or "scope" in s.lower(): print(f"   FAILED {rid}: edit permission nahi hai. yt_auth.py se {ch} ke liye dobara sign-in karo (menu 8/9/10)."); continue
            if "quotaExceeded" in s: print("   STOP: aaj ki limit khatam, kal dobara chalao."); break
            print(f"   FAILED {rid}: {s[:200]}")
    print(f"finished: {n} updated" + (" (dry run)" if dry else ""))

if __name__ == "__main__": main()
