import json
from pathlib import Path
import tempfile
import unittest

from usb_tool.__main__ import copy, plan, verify


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        (self.source / "nested").mkdir(parents=True)
        (self.source / "nested" / "example.bin").write_bytes(bytes(range(256)) * 100)

    def test_transfer_and_verify(self):
        self.assertEqual(copy(self.source, self.target), ["nested/example.bin"])
        self.assertEqual(verify(self.source, self.target), [])
        self.assertEqual((self.target / "nested/example.bin").read_bytes(), (self.source / "nested/example.bin").read_bytes())

    def test_corruption_detected(self):
        copy(self.source, self.target)
        (self.target / "nested/example.bin").write_bytes(b"changed")
        self.assertEqual(verify(self.source, self.target), ["nested/example.bin"])

    def test_dry_run_does_not_create_destination(self):
        self.assertEqual(copy(self.source, self.target, True), ["nested/example.bin"])
        self.assertFalse(self.target.exists())

    def test_reject_overlap_and_manifest_traversal(self):
        with self.assertRaises(ValueError):
            plan(self.source, self.source / "backup")
        copy(self.source, self.target)
        manifest = self.target / ".usb-tool-manifest.json"
        data = json.loads(manifest.read_text())
        data["files"][0]["path"] = "../outside"
        manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            verify(self.source, self.target)


if __name__ == "__main__":
    unittest.main()

