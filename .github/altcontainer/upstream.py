#!/usr/bin/env python3
"""Resolve official release assets. Never fall back to an arbitrary IPA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

APPS = {
    "altstore": ("altstoreio/AltStore", r"AltStore_Classic_Notarized_.*\.ipa"),
    "stikdebug": ("StikDebug/StikDebug", r"StikDebug-.*\.ipa"),
}


def request(url):
    headers = {"User-Agent": "AltContainer-upstream-monitor", "Accept": "application/vnd.github+json"}
    # GitHub tokens must never be sent to release-asset redirects/third parties.
    if url.startswith("https://api.github.com/") and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120)


def resolve():
    result = {}
    for name, (repository, pattern) in APPS.items():
        with request(f"https://api.github.com/repos/{repository}/releases/latest") as response:
            release = json.load(response)
        assets = [asset for asset in release["assets"] if re.fullmatch(pattern, asset["name"])]
        if len(assets) != 1:
            raise RuntimeError(f"{repository}: expected one matching IPA, found {len(assets)}")
        asset = assets[0]
        result[name] = {"repository": repository, "tag": release["tag_name"],
                        "asset_id": asset["id"], "name": asset["name"],
                        "url": asset["browser_download_url"], "digest": asset.get("digest")}
    return result


def download(manifest, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name, asset in manifest.items():
        path = destination / f"{name}.ipa"
        with request(asset["url"]) as response, path.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if asset.get("digest") and asset["digest"] != digest:
            raise RuntimeError(f"Digest mismatch for {name}")
        asset["downloaded_digest"] = digest
    (destination / "upstream.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", type=Path)
    args = parser.parse_args()
    manifest = resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    if args.download:
        download(manifest, args.download)
    print(json.dumps(manifest, indent=2))
