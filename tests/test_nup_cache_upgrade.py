"""The real extractor upgrades private legacy inputs without discarding the workspace."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from akynoleyend.build import prepare_inputs
from akynoleyend.config import ROOT, BuildRequest
from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json, sha256, write_json
from test_nup_packed import make_archive


class NupCacheUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nup-upgrade-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "cópia do jogo.nup"
        self.header = bytearray(0x100)
        self.header[:4] = b"NSO0"
        self.header[0x40:0x44] = bytes.fromhex("e0f3ccfa")
        self.asset = b"correct extracted asset" * 100
        make_archive(
            self.source,
            [
                ("exefs", "main", bytes(self.header), "packed"),
                ("romfs", "asset.bin", self.asset, "packed"),
            ],
        )
        self.request = BuildRequest(
            self.root / "out", self.root / "work", self.root / "tools", nup=self.source
        )
        self.identity = sha256(self.source)
        self.inputs = self.request.work / "inputs" / self.identity

    def legacy_cache(self):
        (self.inputs / "exefs").mkdir(parents=True)
        (self.inputs / "romfs").mkdir()
        (self.inputs / "exefs/main").write_bytes(self.header)
        (self.inputs / "romfs/asset.bin").write_bytes(b"x" * len(self.asset))
        write_json(
            self.inputs / "input.json", {"sha256": self.identity, "source": str(self.source)}
        )
        (self.request.work / "keep.txt").write_text("keep other work")

    def test_fresh_packed_archive_is_extracted_and_marked_with_reader_identity(self):
        exefs, romfs = prepare_inputs(self.request, dict(os.environ), lambda _: None)
        self.assertEqual((exefs / "main").read_bytes(), self.header)
        self.assertEqual((romfs / "asset.bin").read_bytes(), self.asset)
        self.assertEqual(
            read_json(self.inputs / "input.json")["reader_sha256"], sha256(ROOT / "nx2/nup.py")
        )
        with patch(
            "akynoleyend.build.run", side_effect=AssertionError("Should reuse verified extraction")
        ):
            prepare_inputs(self.request, dict(os.environ), lambda _: None)

    def test_legacy_cache_is_repaired_in_place_without_removing_other_work(self):
        self.legacy_cache()
        source_bytes = self.source.read_bytes()
        exefs, romfs = prepare_inputs(self.request, dict(os.environ), lambda _: None)
        self.assertEqual(exefs, self.inputs / "exefs")
        self.assertEqual((romfs / "asset.bin").read_bytes(), self.asset)
        self.assertEqual((self.request.work / "keep.txt").read_text(), "keep other work")
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertIn("reader_sha256", read_json(self.inputs / "input.json"))

    def test_failed_repair_does_not_mark_cache_as_upgraded(self):
        self.legacy_cache()
        with patch(
            "akynoleyend.build.run", side_effect=ProjectError("synthetic interrupted extraction")
        ):
            with self.assertRaises(ProjectError):
                prepare_inputs(self.request, dict(os.environ), lambda _: None)
        self.assertNotIn("reader_sha256", read_json(self.inputs / "input.json"))
        prepare_inputs(self.request, dict(os.environ), lambda _: None)
        self.assertEqual((self.inputs / "romfs/asset.bin").read_bytes(), self.asset)
