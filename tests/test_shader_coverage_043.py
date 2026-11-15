"""Synthetic BAHS/NDSR cases from Hookshot v2.0.6, GPL-3.0; local safety/dedup regressions."""
import collections
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nx2"))
import shader_census as sc
CONTROL_SIZE = 0xD8

def control(stage, end=0x100):
    c = bytearray(CONTROL_SIZE)
    c[0:4] = sc.CONTROL_MAGIC
    struct.pack_into("<I", c, 0x38, 0x40)
    struct.pack_into("<II", c, 0x40, end, end)
    struct.pack_into("<H", c, 0x56, stage)
    return c

def code(seed, end=0x100):
    return bytes((seed + i) & 0xFF for i in range(end))

def sharc():
    """A BAHS blob: a vertex + fragment program and a compute program, each stage pointing at its control section and code"""
    base, blob, size = 0x100, 0x2000, 0x3000
    data = bytearray(size)
    data[0:4] = b"BAHS"
    struct.pack_into("<III", data, 0x14, base, size - blob, blob)
    stages = [(0, 0x1000, 0x000), (1, 0x1100, 0x100), (5, 0x1200, 0x200)]   # (stage, its control section, its code in the blob)
    at = base + 0x158
    for k, (stage, ctl, off) in enumerate(stages):
        struct.pack_into("<IIIIQIi", data, at, 0x30, (0, 1, 3)[k], 0, 0, off, 0xE0, ctl - (at + 16))
        data[ctl:ctl + CONTROL_SIZE] = control(stage)
        data[blob + off:blob + off + 0x100] = code(k)
        at += 0x30
    table = at
    struct.pack_into("<II", data, base + 0x150, table - (base + 0x150), len(stages))
    struct.pack_into("<II", data, table, 0x30, 2)
    struct.pack_into("<IIII", data, table + 8, 0x14, 0, 0b11, 0)    # vertex + fragment, from stage 0
    struct.pack_into("<IIII", data, table + 0x1C, 0x14, 0, 0b1, 2)  # compute, stage 2
    return bytes(data), blob

def check_sharc():
    data, blob = sharc()
    found = [[s[0] for s in p] for p in sc.bahs_programs(data)]
    if found != [[0, 1], [5]]:
        raise SystemExit("expected a vertex + fragment and a compute program, got %r" % found)
    stage, ctl, cs = list(sc.bahs_programs(data))[1][0]
    if ctl != data[0x1200:0x1200 + CONTROL_SIZE] or cs != data[blob + 0x200:blob + 0x300]:
        raise SystemExit("the compute program's control section or code is not the archive's")

def check_ndsr():
    data = bytearray(0x600)
    data[0:4] = b"NDSR"
    struct.pack_into("<I", data, 0x0C, 2)
    struct.pack_into("<IIII", data, 0x14, 0x100, CONTROL_SIZE << 4 | 6, 0x200, 0x100 << 4 | 7)
    data[0x100:0x100 + CONTROL_SIZE] = control(5)
    data[0x200:0x300] = code(9)
    found = list(sc.ndsr_programs(bytes(data), 0))
    if len(found) != 1 or found[0][0][0] != 5 or found[0][0][2] != bytes(data[0x200:0x300]):
        raise SystemExit("expected the network's compute program, got %r" % [[s[0] for s in p] for p in found])

def check_archives():
    with tempfile.TemporaryDirectory() as romfs:
        for folder, name in (("Shader", "Model.Product.bfsha.zs"), ("Shader", "ApplicationPackage.release.sarc.zs"),
                             ("Effect", "Animal_Cow.Nin_Ounce_NVN2.vsetb.byml.zs"), ("Effect", "notes.txt"),
                             ("Lib/agl", "agl_resource.Nin_Ounce_NVN2.release.sarc.zs"), ("Movie/Ndve", "Ndve-Nvn2-vid_seq5.dat.zs"),
                             ("Layout2Shader", "MergeShader.bfsha.zs")):
            os.makedirs(os.path.join(romfs, folder), exist_ok=True)
            open(os.path.join(romfs, folder, name), "wb").close()
        names = sorted(os.path.basename(p) for p in sc.archives(romfs))
    want = sorted(["Model.Product.bfsha.zs", "ApplicationPackage.release.sarc.zs", "Animal_Cow.Nin_Ounce_NVN2.vsetb.byml.zs",
                   "agl_resource.Nin_Ounce_NVN2.release.sarc.zs", "Ndve-Nvn2-vid_seq5.dat.zs", "MergeShader.bfsha.zs"])
    if names != want:
        raise SystemExit("archives: %r, expected %r" % (names, want))

class ShaderCoverageTests(unittest.TestCase):
    def test_real_graphics_group_and_compute_group(self): check_sharc()
    def test_network_compute(self): check_ndsr()
    def test_archive_coverage(self): check_archives()
    def test_corrupt_offsets_fail_before_publication(self):
        data, _ = sharc()
        truncated = data[:0x240]
        with self.assertRaises(ValueError): list(sc.bahs_programs(truncated))
        with self.assertRaises(ValueError): list(sc.bahs_programs(data[:0x2010]))
    def test_embedded_network_and_canonical_dedup(self):
        data = bytearray(0x800)
        data[:4] = b"NDVE"
        base = 0x28
        data[base:base+4] = b"NDSR"
        struct.pack_into("<I", data, base+0x0c, 2)
        struct.pack_into("<IIII", data, base+0x14, 0x100, CONTROL_SIZE<<4|6, 0x200, 0x100<<4|7)
        data[base+0x100:base+0x100+CONTROL_SIZE] = control(5)
        data[base+0x200:base+0x300] = code(19)
        records = list(sc.programs_in(bytes(data), collections.Counter()))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0][0][0], 5)
        with sc.SeedWriter() as writer:
            self.assertTrue(writer.add(records[0]))
            kind, ctl, raw = records[0][0]
            self.assertFalse(writer.add([(kind, bytes(ctl)+b"padding", bytes(raw)+b"trailer")]))
            self.assertEqual(writer.program_count, 1)
    def test_bare_sharcb_is_discovered_recursively(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"Lib/sub/agl.sharcb";p.parent.mkdir(parents=True);p.touch()
            self.assertEqual(list(sc.archives(directory)), [str(p)])
    def test_compute_source_changes_invalidate_preparation(self):
        from akynoleyend.shader_prepare import seed_identity
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dictionary = root / "Pack/ZsDic.pack.zs"
            dictionary.parent.mkdir();dictionary.write_bytes(b"synthetic dictionary")
            shader = root / "Lib/agl/network.pck"
            shader.parent.mkdir(parents=True);shader.write_bytes(b"synthetic compute")
            first = seed_identity(root, "image")
            shader.write_bytes(b"changed synthetic compute, different length")
            self.assertNotEqual(first, seed_identity(root, "image"))

if __name__ == "__main__": unittest.main()
