#!/usr/bin/env python3
"""Package unencrypted upstream IPAs without modifying their source archives."""
import argparse
import hashlib
import json
import plistlib
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path


def load(path):
    return plistlib.loads(path.read_bytes())


def save(path, value):
    path.write_bytes(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))


def extract_ipa(ipa, destination, expected_id):
    with zipfile.ZipFile(ipa) as archive:
        for name in archive.namelist():
            target = (destination / name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError(f"Unsafe archive path: {name}")
        archive.extractall(destination)
    apps = list((destination / "Payload").glob("*.app"))
    if len(apps) != 1:
        raise ValueError("Expected exactly one application in Payload")
    app = apps[0]
    info = load(app / "Info.plist")
    if info.get("CFBundleIdentifier") != expected_id:
        raise ValueError(f"Unexpected bundle identifier: {info.get('CFBundleIdentifier')}")
    validate_executable(app / info["CFBundleExecutable"])
    return app


def validate_executable(path):
    data = path.read_bytes()
    if data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("Expected a thin arm64 Mach-O; upstream format changed")
    if struct.unpack_from("<I", data, 4)[0] != 0x100000C:
        raise ValueError("Expected arm64")
    offset = 32
    for _ in range(struct.unpack_from("<I", data, 16)[0]):
        command, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > len(data):
            raise ValueError("Malformed Mach-O load command")
        if command == 0x2C and struct.unpack_from("<I", data, offset + 16)[0]:
            raise ValueError("Encrypted IPA cannot be embedded")
        offset += size


def add_schemes(info, schemes):
    types = info.setdefault("CFBundleURLTypes", [])
    existing = {s for t in types for s in t.get("CFBundleURLSchemes", [])}
    missing = [s for s in schemes if s not in existing]
    if missing:
        types.append({"CFBundleURLName": "AltContainer bundled apps", "CFBundleURLSchemes": missing})


def package(host, altstore, stikdebug, dylibify, output):
    with tempfile.TemporaryDirectory(prefix="altcontainer-") as temporary:
        root = Path(temporary)
        app = root / "Payload" / "LiveContainer.app"
        app.parent.mkdir()
        shutil.copytree(host, app, symlinks=True)
        alt = extract_ipa(altstore, root / "alt", "com.rileytestut.AltStore")
        stik = extract_ipa(stikdebug, root / "stik", "com.stik.stikdebug")
        versions = {}
        for key, source, ipa in [("AltStore", alt, altstore), ("StikDebug", stik, stikdebug)]:
            info = load(source / "Info.plist")
            versions[key] = {"version": info["CFBundleShortVersionString"], "sha256": hashlib.sha256(ipa.read_bytes()).hexdigest()}
        # Keep this internal path for compatibility with LC's existing bootstrap.
        destination = app / "Frameworks" / "SideStoreApp.framework"
        if destination.exists():
            raise ValueError("Use the plain Xcode archive, not a SideStore-packaged app")
        shutil.copytree(alt, destination, symlinks=True)
        info = load(destination / "Info.plist")
        info["UIDeviceFamily"] = [1, 2]
        info["UISupportedInterfaceOrientations~ipad"] = ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationPortraitUpsideDown", "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]
        # Separate virtual groups from the host's real app group.
        info["ALTAppGroups"] = ["group.com.rileytestut.AltStore"]
        save(destination / "Info.plist", info)
        executable = destination / info["CFBundleExecutable"]
        converted = executable.with_suffix(".dylib")
        subprocess.run([str(dylibify.resolve()), str(executable), str(converted)], check=True)
        converted.replace(executable)
        executable.chmod(0o755)
        subprocess.run(["ldid", "-S", str(executable)], check=True)
        config = load(Path(__file__).parents[1] / "sidelc" / "LCAppInfo.plist")
        config["LCSelectedLanguage"] = "ja"
        config["classicMode"] = False
        save(destination / "LCAppInfo.plist", config)
        # Guest extensions cannot run as SpringBoard widgets. Never silently
        # register a widget with an unrelated provisioning profile or database.
        plugins = destination / "PlugIns"
        if plugins.exists():
            shutil.rmtree(plugins)
        resources = app / "BundledApps"
        resources.mkdir()
        localizations = Path(__file__).parent / "localizations"
        stik_translations = localizations / "StikDebug"
        if stik_translations.exists():
            shutil.copytree(stik_translations, stik, dirs_exist_ok=True)
        subprocess.run(["zip", "-qry", str(resources / "StikDebug.ipa"), "Payload"], cwd=root / "stik", check=True)
        save(resources / "Versions.plist", versions)
        host_info = load(app / "Info.plist")
        host_info["LCBuiltInStore"] = "AltStore"
        host_info["CFBundleDisplayName"] = "AltContainer"
        host_info["MinimumOSVersion"] = max(
            (host_info.get("MinimumOSVersion", "17.4"), "17.4"),
            key=lambda value: tuple(map(int, value.split("."))),
        )
        host_info["NSLocalNetworkUsageDescription"] = "AltStoreとStikDebugがデバイスおよびRemote AltServerに接続するためにローカルネットワークを使用します。"
        services = host_info.setdefault("NSBonjourServices", [])
        for service in ["_altserver._tcp", "_remotepairing-pairable-host._tcp"]:
            if service not in services:
                services.append(service)
        add_schemes(host_info, ["altstore", "altstore-classic", "altstore-com.rileytestut.AltStore", "stikdebug", "stikjit"])
        save(app / "Info.plist", host_info)
        if localizations.exists():
            for folder in localizations.iterdir():
                if folder.name == "AltStore":
                    shutil.copytree(folder, destination, dirs_exist_ok=True)
        for signature in app.rglob("_CodeSignature"):
            shutil.rmtree(signature)
        output.parent.mkdir(parents=True, exist_ok=True)
        # zip preserves executable permissions and symlinks on macOS.
        subprocess.run(["zip", "-qry", str(output.resolve()), "Payload", "-x", "*.DS_Store"], cwd=root, check=True)
        print(json.dumps({"output": str(output), "upstream": versions}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ["host", "altstore", "stikdebug", "dylibify", "output"]:
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    package(**vars(args))
