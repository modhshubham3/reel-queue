#!/usr/bin/env python3
"""Pull the real numbers (views, likes, comments, public or not) of every video this tool uploaded and write yt_stats.json.
  python yt_stats.py            all channels that have tokens/yt_<channel>.json
Reads uploaded.json (queue id -> YouTube video id) and every weekN/queue.csv (queue id -> channel, title). Read-only.
Quota: videos.list costs 1 unit per call (50 ids per call), so a full refresh is a handful of units. Needs the same token as the upload."""
import csv, json, sys
from datetime import datetime, timezone
from pathlib import Path
import yt_publish as y   # reuses service(channel), the UTF-8 fix and uploaded.json

HERE = Path(__file__).resolve().parent
def main():
    rows = {}
    for q in sorted(HERE.parent.glob("week*/queue.csv")):
        for r in csv.DictReader(open(q, encoding="utf-8-sig")): rows[r["id"].strip()] = (r["channel"].strip(), r["title"].strip(), q.parent.name)
    by_ch = {}
    for rid, vid in y.done.items():
        if rid in rows: by_ch.setdefault(rows[rid][0], []).append((rid, vid if isinstance(vid, str) else str(vid.get("id", vid) if isinstance(vid, dict) else vid)))
    out = {"ts": int(datetime.now(timezone.utc).timestamp()), "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "channels": {}, "videos": {}}
    for ch, items in by_ch.items():
        if not (HERE / "tokens" / f"yt_{ch}.json").exists(): print(f"{ch}: no token, skipped"); continue
        yt = y.service(ch); ids = {v: rid for rid, v in items}; got = []
        for i in range(0, len(ids), 50):
            chunk = list(ids)[i:i + 50]
            for it in yt.videos().list(part="statistics,status,snippet", id=",".join(chunk)).execute().get("items", []):
                s = it.get("statistics", {}); rid = ids[it["id"]]
                v = {"id": rid, "yt": it["id"], "title": rows[rid][1][:70], "week": rows[rid][2], "privacy": it["status"]["privacyStatus"], "views": int(s.get("viewCount", 0)),
                     "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0)), "published": it["snippet"].get("publishedAt", "")[:16]}
                out["videos"][rid] = v; got.append(v)
        pub = [v for v in got if v["privacy"] == "public"]; top = sorted(pub, key=lambda v: -v["views"])[:3]
        out["channels"][ch] = {"uploaded": len(got), "public": len(pub), "views": sum(v["views"] for v in pub), "avg_views": round(sum(v["views"] for v in pub) / len(pub), 1) if pub else 0,
                               "zero_view_public": sum(v["views"] == 0 for v in pub), "comments": sum(v["comments"] for v in pub), "with_comments": [v["id"] for v in pub if v["comments"]],
                               "top": [{"id": v["id"], "title": v["title"], "views": v["views"]} for v in top]}
        print(f"{ch}: {len(pub)} public, {out['channels'][ch]['views']} views, avg {out['channels'][ch]['avg_views']}")
    (HERE / "yt_stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote yt_stats.json")

if __name__ == "__main__": main()
