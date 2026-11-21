#!/usr/bin/env python3
"""One-time Google sign-in for ONE YouTube channel (you sign in yourself in your browser; no password is shared).

  python yt_auth.py kahani        -> saves tokens/yt_kahani.json
  python yt_auth.py interview     -> saves tokens/yt_interview.json
  python yt_auth.py gta           -> saves tokens/yt_gta.json
Add --manual if no browser opens on this computer (open the link on your phone, then paste the address back).

Needs client_secret.json (OAuth client, type 'Desktop app', from Google Cloud) in THIS folder.
When Google asks which channel/account, choose the channel you are authorizing. Both files are secrets: never share or commit them.
"""
import os, sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
name = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
if not name: raise SystemExit("usage: python yt_auth.py <channel-name>   e.g. kahani | interview | gta")
secret = HERE / "client_secret.json"
if not secret.exists(): raise SystemExit("client_secret.json not found in this folder (see README).")
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
if "--manual" in sys.argv:
    flow.redirect_uri = "http://localhost:8080/"
    url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("\n1. Open this link on any device, sign in, and CHOOSE THE CHANNEL '%s':\n\n%s\n" % (name, url))
    print("2. Allow. The last page will say it cannot be reached (localhost): that is expected.")
    answer = input("3. Paste the FULL address from the address bar here:\n> ").strip()
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    flow.fetch_token(authorization_response=answer); creds = flow.credentials
else:
    creds = flow.run_local_server(port=0, prompt="consent")
(HERE / "tokens").mkdir(exist_ok=True)
(HERE / "tokens" / f"yt_{name}.json").write_text(creds.to_json())
print(f"Done: tokens/yt_{name}.json saved.")
