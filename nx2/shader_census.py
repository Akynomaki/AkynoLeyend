"""Every shader program in the game's archives, for the precompile before the first start.

    python -I nx2/shader_census.py <romfs> [--out <file>]

Walks BNSH, BAHS, NDSR and NDVE containers in Shader, Layout2Shader, Lib, Movie and Effect. A BNSH's variations
are programs: which stages go together, so what comes out are real pairs, not a heap of stages. --out writes them for the back
end to translate (gpu/vk/vk_shader.cpp); nothing here goes into the repository: the file is made from the player's own game.

After tools/shader_census.py of TotK Recomp (github.com/valentderah/totk-pc-recomp, MIT), itself after MacNativeGames'
prepare_shader_seed.py (MIT): the BNSH layout and the walk of its variations.

    <out>:  "HKSEED01", u32 programs, u32 stages; then the stages, each once:
            u64 key, u32 stage, u32 control bytes, u32 code bytes, control, code
            then the programs: u32 count, u32 stage indices
"""
import argparse
import collections
import hashlib
import os
import re
import struct
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shader_containers import archives, bahs_programs, ndsr_programs, ndve_programs, checked, fields

CONTROL_MAGIC = b"\x34\x12\x76\x98"
ZSTD = b"\x28\xb5\x2f\xfd"
# the stages a variation's program points at (a 0 offset: none), as far as the structure reaches
SLOTS = (8, 16, 24, 32, 40, 48, 56, 64, 72)
IO_CHUNK = 64 << 10
MAX_RECORDS = 262144


def write_chunks(file, data):
    view = memoryview(data)
    for at in range(0, len(view), IO_CHUNK):
        file.write(view[at:at + IO_CHUNK])


class SeedWriter:
    """Spool packages to disk; the in-memory index contains hashes and IDs only."""
    def __init__(self, directory=None):
        self.directory = tempfile.TemporaryDirectory(prefix="shader-seed-", dir=directory)
        self.stages = open(Path(self.directory.name) / "stages", "w+b")
        self.programs = open(Path(self.directory.name) / "programs", "w+b")
        self.stage_index, self.seen = {}, set()
        self.program_count = 0
        self.kinds = collections.Counter()

    def add(self, stages):
        ids = []
        kinds = []
        if not stages or len(stages) > 16:
            raise ValueError("unsupported shader program size")
        for stage, control, code in stages:
            if not 0 <= stage <= 7 or not 0x60 <= len(control) <= 4096 or not 0 < len(code) <= 16 << 20:
                raise ValueError("shader package outside seed bounds")
            if len(control) >= 0xD8:
                end = struct.unpack_from("<I", control, 0x44)[0]
                if 0 < end <= len(code):
                    control, code = control[:0xD8], code[:end]
            digest = hashlib.sha1(); digest.update(control); digest.update(code)
            key = digest.digest()
            if key not in self.stage_index:
                if len(self.stage_index) >= MAX_RECORDS:
                    raise ValueError("shader stage index limit exceeded")
                self.stage_index[key] = len(self.stage_index)
                self.stages.write(struct.pack("<QIII", int.from_bytes(key[:8], "little"), stage, len(control), len(code)))
                write_chunks(self.stages, control); write_chunks(self.stages, code)
            ids.append(self.stage_index[key]); kinds.append(stage)
        record = struct.pack("<I%dI" % len(ids), len(ids), *ids)
        if record in self.seen:
            return False
        if len(self.seen) >= MAX_RECORDS:
            raise ValueError("shader program index limit exceeded")
        self.seen.add(record)
        self.programs.write(record)
        self.program_count += 1
        self.kinds[tuple(sorted(kinds))] += 1
        return True

    def publish(self, destination):
        if not self.program_count:
            raise ValueError("no shader programs found; the previous bank was preserved")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(b"HKSEED01" + struct.pack("<II", self.program_count, len(self.stage_index)))
                for source in (self.stages, self.programs):
                    source.flush(); source.seek(0)
                    while block := source.read(IO_CHUNK):
                        output.write(block)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        self.stages.close(); self.programs.close(); self.directory.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def dictionaries(romfs, zs):
    """The game's zstd dictionaries: the files of a SARC, Pack/ZsDic.pack.zs"""
    raw = zs.ZstdDecompressor().decompress(open(os.path.join(romfs, "Pack", "ZsDic.pack.zs"), "rb").read(), max_output_size=1 << 28)
    start = struct.unpack_from("<I", raw, 0x0c)[0]
    out = []
    for k in range(struct.unpack_from("<H", raw, 0x1a)[0]):
        _, _, st, end = struct.unpack_from("<IIII", raw, 0x20 + k * 16)
        out.append(raw[start + st:start + end])
    return out


def unpack(data, dicts, zs):
    if data[:4] != ZSTD:
        return data
    try:
        return zs.ZstdDecompressor().decompress(data, max_output_size=1 << 31)
    except zs.ZstdError:
        pass
    for d in dicts:
        try:
            return zs.ZstdDecompressor(dict_data=zs.ZstdCompressionDict(d, dict_type=zs.DICT_TYPE_FULLDICT)).decompress(
                data, max_output_size=1 << 31)
        except zs.ZstdError:
            continue
    raise ValueError("no dictionary fits")


def bnsh_programs(data, stats):
    """Each variation of a BNSH (its offsets are its own) as [(stage, control, code)...]"""
    if data[:4] != b"BNSH" or data[12:14] != b"\xff\xfe" or data[96:100] != b"grsc":
        raise ValueError("unsupported BNSH header")
    size = struct.unpack_from("<I", data, 28)[0]
    if size > len(data) or size < 136:
        raise ValueError("truncated BNSH")
    data = data[:size]
    count, variations = struct.unpack_from("<IQ", data, 124)
    if count > MAX_RECORDS or variations > size or count * 64 > size - variations:
        raise ValueError("invalid BNSH variations")
    for i in range(count):
        program = struct.unpack_from("<Q", data, variations + i * 64 + 16)[0]
        if not program or program + 80 > size:
            stats["no program"] += 1
            continue
        stages = []
        for rel in SLOTS:
            offset = struct.unpack_from("<Q", data, program + rel)[0]
            if not offset or offset + 32 > size:
                continue
            control_off, code_off, code_size, control_size = struct.unpack_from("<QQII", data, offset + 8)
            if not 0x60 <= control_size <= 0x1000 or control_off + control_size > size or code_off + code_size > size:
                continue
            control = data[control_off:control_off + control_size]
            if control[:4] != CONTROL_MAGIC:
                continue
            stage = struct.unpack_from("<H", control, 0x56)[0]
            stats["slot %d, stage %d" % (rel, stage)] += 1
            stages.append((stage, control, data[code_off:code_off + code_size]))
        if stages:
            yield stages


def programs_in(data, stats):
    if data[:4] == b"BAHS":
        yield from bahs_programs(data)
    elif data[:4] == b"NDSR":
        yield from ndsr_programs(data)
    elif data[:4] == b"NDVE":
        yield from ndve_programs(data)
    else:
        for match in re.finditer(b"BNSH", data):
            start = match.start()
            if start + 136 <= len(data) and data[start + 96:start + 100] == b"grsc":
                size = fields("<I", data, start + 28)[0]
                yield from bnsh_programs(checked(data, start, size), stats)


def sarc_files(data):
    start = fields("<I", data, 0x0c)[0]
    count = fields("<H", data, 0x1a)[0]
    checked(data, 0x20, count * 16)
    for k in range(count):
        _, _, st, end = fields("<IIII", data, 0x20 + k * 16)
        yield checked(data, start + st, end - st)


def blobs(data, dicts, zs, depth=0):
    """The data itself, or each file when it is an archive"""
    if data[:4] == b"SARC":
        if depth >= 16:
            raise ValueError("shader archive nesting limit exceeded")
        for inner in sarc_files(data):
            yield from blobs(unpack(inner, dicts, zs), dicts, zs, depth + 1)
    else:
        yield data


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("romfs")
    p.add_argument("--out")
    a = p.parse_args()
    import zstandard as zs
    dicts = dictionaries(a.romfs, zs)
    stats = collections.Counter()
    with SeedWriter(Path(a.out).parent if a.out else None) as writer:
        for path in archives(a.romfs):
            made = 0
            with open(path, "rb") as source:
                archive = source.read()
            for data in blobs(unpack(archive, dicts, zs), dicts, zs):
                stats["container " + bytes(data[:4]).hex()] += 1
                for stages in programs_in(data, stats):
                    made += writer.add(stages)
            print("%-64s %6d programs" % (os.path.basename(path)[:64], made), flush=True)
        print("%d programs from %d stages" % (writer.program_count, len(writer.stage_index)))
        print("by stages:", writer.kinds.most_common(12))
        print("slots:", sorted(stats.items()))
        if a.out:
            writer.publish(a.out)
            print("wrote", a.out, os.path.getsize(a.out) >> 20, "MB")


if __name__ == "__main__":
    sys.exit(main())
