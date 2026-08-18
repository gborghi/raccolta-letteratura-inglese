#!/usr/bin/env python3
"""Send an email through the wiligelmo-gas Apps Script Execution API.

Shell-callable so a DETACHED bash runner (e.g. run_dickens_all.sh's BOOK END hook)
can notify by e-mail without an MCP client in the loop. Uses the OAuth refresh-token
already minted for the wiligelmo-gas MCP: refreshes an access token, then POSTs
    https://script.googleapis.com/v1/scripts/<SCRIPT_ID>:run
    {"function":"exec","parameters":["mail.send", "<json>"]}
which dispatches to mailSend_(p) in Code.gs (requires "to" + "subject").

stdlib only (runs under /usr/bin/python3 3.9.6). Best-effort: exit 0 on success,
non-zero on any failure, so the caller can `|| log` without ever crashing the run.

Usage:  notify_gas_mail.py --to a@b.com --subject "..." [--body "..."]
        (if --body is omitted, the body is read from stdin)
Env:    GAS_DIR (dir with credentials.json + token.json),
        WILIGELMO_GAS_SCRIPT_ID (override the script id).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

GAS_DIR = os.environ.get(
    "GAS_DIR",
    "/Users/g.borghi/Library/CloudStorage/Dropbox/insegnamento/ICT/claude/mcp/appsscripts/wiligelmo-gas",
)
SCRIPT_ID = os.environ.get(
    "WILIGELMO_GAS_SCRIPT_ID",
    "1lnIqU7q0AAK6coJfpvaYgeD7NaHYAiPKeHAlB2lFNRFrT4nC5Xnk5eav",
)


def _post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _access_token():
    creds = json.load(open(os.path.join(GAS_DIR, "credentials.json")))["installed"]
    tok = json.load(open(os.path.join(GAS_DIR, "token.json")))
    body = urllib.parse.urlencode(
        {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": tok["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    res = _post(creds["token_uri"], body, {"Content-Type": "application/x-www-form-urlencoded"})
    return res["access_token"]


def send(to, subject, body):
    at = _access_token()
    payload = json.dumps(
        {
            "function": "exec",
            "parameters": ["mail.send", json.dumps({"to": to, "subject": subject, "body": body})],
            "devMode": True,  # run the latest saved code, no API-executable deployment needed
        }
    ).encode("utf-8")
    url = "https://script.googleapis.com/v1/scripts/%s:run" % SCRIPT_ID
    res = _post(url, payload, {"Authorization": "Bearer " + at, "Content-Type": "application/json"})
    # scripts.run returns an Operation: script exceptions surface as top-level "error".
    if res.get("error"):
        raise RuntimeError("scripts.run error: " + json.dumps(res.get("error"))[:600])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default=None)
    a = ap.parse_args()
    body = a.body if a.body is not None else sys.stdin.read()
    try:
        send(a.to, a.subject, body)
    except Exception as e:  # best-effort: never crash the caller
        sys.stderr.write("notify_gas_mail: FAILED: %s\n" % e)
        return 1
    print("notify_gas_mail: sent to %s" % a.to)
    return 0


if __name__ == "__main__":
    sys.exit(main())
