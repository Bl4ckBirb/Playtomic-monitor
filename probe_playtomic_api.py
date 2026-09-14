#!/usr/bin/env python3
"""Connectivity probe for the Playtomic app API (api.app.playtomic.io).

This is a THROWAWAY DIAGNOSTIC, not part of the monitor. The public endpoint
playtomic.com/api/clubs/availability returns HTTP 403 from GitHub Actions
runners (server=CloudFront, i.e. blocked at the CDN edge, not an auth problem).
This script asks one question from whatever network it runs on: is the app API
host reachable at all?

How to read the result per endpoint:
- HTTP 200                      -> reachable AND (for that call) authorized.
- HTTP 401 / 403 with a JSON    -> reachable; only authentication/authorization
  body (app-level error)           is missing. This is the GOOD outcome for an
                                   unauthenticated probe.
- HTTP 403 with an HTML body /  -> blocked at the edge (CloudFront/WAF), same
  server=CloudFront                wall as the public endpoint. Bad outcome.
- URLError / timeout            -> host not reachable from this network at all.

Auth is optional: set PLAYTOMIC_ACCESS_TOKEN to send a Bearer token. Without a
token an auth error is expected and still proves reachability.

Env:
- PLAYTOMIC_ACCESS_TOKEN  optional Bearer token for the app API
- PLAYTOMIC_API_BASE      override base URL (default https://api.app.playtomic.io)
- PLAYTOMIC_CONFIG        config path to read the tenant_id from (default config.shared.toml)
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from playtomic_core import get_club_sections, load_config, resolve_config_path

API_BASE = os.environ.get("PLAYTOMIC_API_BASE", "").strip() or "https://api.app.playtomic.io"

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
    token = os.environ.get("PLAYTOMIC_ACCESS_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _verdict(status: int, content_type: str, server: str) -> str:
    ct = (content_type or "").lower()
    if status == 200:
        return "REACHABLE + AUTHORIZED"
    if status in (401, 403) and "json" in ct:
        return "REACHABLE (only auth missing) — good"
    if status == 403:
        return f"EDGE BLOCK (server={server or '?'}, {content_type or '?'}) — bad"
    return f"OTHER ({status})"


def probe(label: str, url: str) -> None:
    headers = _headers()
    print(f"\n=== {label} ===")
    print(f"GET {url}")
    print("auth:", "Bearer <token set>" if "Authorization" in headers else "<none>")
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", "replace")
            status = response.status
            server = response.headers.get("server")
            content_type = response.headers.get("content-type")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        status = exc.code
        server = exc.headers.get("server") if exc.headers else None
        content_type = exc.headers.get("content-type") if exc.headers else None
    except urllib.error.URLError as exc:
        print(f"NETWORK ERROR: {exc}")
        print("VERDICT: NOT REACHABLE from this network")
        return

    print(f"status: {status}")
    print(f"server: {server}")
    print(f"content-type: {content_type}")
    print(f"body[:1000]: {body[:1000]!r}")
    print(f"VERDICT: {_verdict(status, content_type, server)}")


def main() -> int:
    config_env = os.environ.get("PLAYTOMIC_CONFIG", "").strip() or None
    config = load_config(resolve_config_path(config_env))
    club = get_club_sections(config)[0]
    tenant_id = club["tenant_id"]
    sport_id = club.get("sport_id", "PADEL")

    print(f"API base : {API_BASE}")
    print(f"Club     : {club.get('name', '?')}")
    print(f"Tenant   : {tenant_id}")
    print(f"Sport    : {sport_id}")

    today = date.today()
    start_min = f"{today.isoformat()}T00:00:00"
    start_max = f"{(today + timedelta(days=1)).isoformat()}T00:00:00"

    # Tenant detail: cheapest reachability check.
    probe("tenant detail", f"{API_BASE}/v1/tenants/{tenant_id}")

    # Availability: the data the monitor actually needs.
    query = urllib.parse.urlencode(
        {
            "user_id": "me",
            "tenant_id": tenant_id,
            "sport_id": sport_id,
            "local_start_min": start_min,
            "local_start_max": start_max,
        }
    )
    probe("availability", f"{API_BASE}/v1/availability?{query}")

    print(
        "\nNote: exact app-API paths/params are best-effort and may need tweaking; "
        "the point of this run is the reachability VERDICT, not correct data.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
