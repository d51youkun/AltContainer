import importlib.util
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
import zipfile

def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

package = module("package")
upstream = module("upstream")

class PackageTests(unittest.TestCase):
    def test_schemes_are_idempotent(self):
        info = {}
        package.add_schemes(info, ["altstore", "stikdebug"])
        package.add_schemes(info, ["altstore", "stikdebug"])
        self.assertEqual(len(info["CFBundleURLTypes"]), 1)

    def test_rejects_encrypted_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "App"
            header = struct.pack("<8I", 0xFEEDFACF, 0x100000C, 0, 2, 1, 24, 0, 0)
            for encrypted in [0, 1]:
                path.write_bytes(header + struct.pack("<6I", 0x2C, 24, 0, 0, encrypted, 0))
                if encrypted:
                    with self.assertRaisesRegex(ValueError, "Encrypted"):
                        package.validate_executable(path)
                else:
                    package.validate_executable(path)

    def test_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ipa = root / "test.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("../outside", "bad")
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                package.extract_ipa(ipa, root / "extract", "test")

    def test_rejects_wrong_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            ipa = root / "test.ipa"
            with zipfile.ZipFile(ipa, "w") as archive:
                archive.writestr("Payload/App.app/Info.plist", plistlib.dumps({"CFBundleIdentifier": "wrong"}))
            with self.assertRaisesRegex(ValueError, "Unexpected bundle"):
                package.extract_ipa(ipa, root / "extract", "expected")

    def test_official_repositories(self):
        self.assertEqual(upstream.APPS["stikdebug"][0], "StikDebug/StikDebug")
        self.assertEqual(upstream.APPS["altstore"][0], "altstoreio/AltStore")

if __name__ == "__main__":
    unittest.main()
