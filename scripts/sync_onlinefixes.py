#!/usr/bin/env python3
"""Sync published online release ZIPs into onlinefixes.json without overwriting metadata."""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "vkmafioso1-ui/bypass")
MANIFEST = Path("onlinefixes.json")
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "VYRON-online-manifest-sync"}


def fetch_json(url):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def steam_name(app_id):
    url = "https://store.steampowered.com/api/appdetails?" + urllib.parse.urlencode(
        {"appids": app_id, "l": "english", "cc": "us"}
    )
    try:
        payload = fetch_json(url)
        entry = payload.get(str(app_id), {})
        if entry.get("success"):
            name = entry.get("data", {}).get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()[:160]
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as error:
        print(f"Steam name unavailable for {app_id}: {error}")
    return f"App ID {app_id}"


def release_assets():
    release = fetch_json(f"https://api.github.com/repos/{REPO}/releases/tags/online")
    url = release["assets_url"]
    page = 1
    while True:
        assets = fetch_json(f"{url}?per_page=100&page={page}")
        if not assets:
            break
        for asset in assets:
            if asset.get("state") != "uploaded":
                continue
            name = str(asset.get("name", ""))
            match = re.fullmatch(r"([1-9][0-9]*)\.zip", name, re.IGNORECASE)
            if match and int(asset.get("size", 0)) > 0:
                yield match.group(1)
        if len(assets) < 100:
            break
        page += 1


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("onlinefixes.json must contain a JSON object")
    ids = sorted(set(release_assets()), key=int)
    if not ids:
        raise RuntimeError("No uploaded online ZIPs found; refusing to change manifest")
    added = 0
    for app_id in ids:
        if app_id in manifest:
            continue
        name = steam_name(app_id)
        manifest[app_id] = {"name": name}
        added += 1
        print(f"Added {app_id}: {name}")
        time.sleep(0.2)
    if added:
        # Preserve original insertion order and every existing field/instruction.
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"Synced {len(ids)} published ZIPs, added {added} entries")


if __name__ == "__main__":
    main()
