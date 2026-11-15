"""BAHS/NDSR/NDVE layouts from Hookshot v2.0.6 (GPL-3.0), adapted to checked spans.

The seed writer remains disk-backed; these readers return real stage groups only.
"""
import os
import re
import struct

CONTROL_MAGIC = b"\x34\x12\x76\x98"
CONTROL_BYTES = 0xD8
MAX_RECORDS = 262144


def checked(data, offset, size):
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise ValueError("shader container span outside file: %#x + %#x" % (offset, size))
    return memoryview(data)[offset:offset + size]


def fields(fmt, data, offset):
    return struct.unpack(fmt, checked(data, offset, struct.calcsize(fmt)))


def control_at(data, offset):
    control = checked(data, offset, CONTROL_BYTES)
    if control[:4] != CONTROL_MAGIC or fields("<H", control, 0x56)[0] > 7:
        raise ValueError("invalid NVN2 control section")
    size = fields("<I", control, 0x44)[0]
    if not 0 < size <= 16 << 20 or fields("<I", control, 0x38)[0] > size or fields("<I", control, 0x40)[0] > size:
        raise ValueError("shader code size outside seed bounds")
    return control, size


def stage(control, code):
    return fields("<H", control, 0x56)[0], control, code


def bahs_programs(data):
    base, blob_size, blob = fields("<III", data, 0x14)
    checked(data, blob, blob_size)
    table, count = fields("<II", data, base + 0x150)
    if count > MAX_RECORDS:
        raise ValueError("BAHS stage count outside seed bounds")
    at, stages = base + 0x158, []
    for _ in range(count):
        step = fields("<I", data, at)[0]
        if step < 32:
            raise ValueError("invalid BAHS stage stride")
        checked(data, at, step)
        offset, _, relative = fields("<QIi", data, at + 16)
        control, size = control_at(data, at + 16 + relative)
        if offset > blob_size or size > blob_size - offset:
            raise ValueError("BAHS code outside blob")
        stages.append(stage(control, checked(data, blob + offset, size)))
        at += step
    table += base + 0x150
    table_size, programs = fields("<II", data, table)
    checked(data, table, table_size)
    if programs > MAX_RECORDS:
        raise ValueError("BAHS program count outside seed bounds")
    at, heads = table + 8, []
    for _ in range(programs):
        size, _, kinds, first = fields("<4I", data, at)
        width = kinds.bit_count()
        if size < 16 or not 0 < width <= 8 or first >= count or at + size > table + table_size:
            raise ValueError("invalid BAHS program record")
        heads.append((first, width))
        at += size
    heads.sort()
    if len({first for first, _ in heads}) != len(heads):
        raise ValueError("duplicate BAHS program start")
    for i, (first, width) in enumerate(heads):
        last = heads[i + 1][0] if i + 1 < len(heads) else count
        if (last - first) % width:
            raise ValueError("incomplete BAHS stage group")
        for start in range(first, last, width):
            yield stages[start:start + width]


def ndsr_programs(data, base=0):
    count = fields("<I", data, base + 0x0C)[0]
    if count > MAX_RECORDS:
        raise ValueError("NDSR item count outside seed bounds")
    checked(data, base + 0x14, count * 8)
    items = [fields("<II", data, base + 0x14 + i * 8) for i in range(count)]
    graphics = []
    for (control_offset, ct), (code_offset, code_type) in zip(items, items[1:]):
        kind = ct & 15
        if kind not in (0, 3, 6) or code_type & 15 != kind + 1:
            continue
        control, size = control_at(data, base + control_offset)
        part = stage(control, checked(data, base + code_offset, size))
        if kind == 6:
            yield [part]
        elif kind == 0:
            if graphics:
                yield graphics
            graphics = [part]
        elif graphics:
            graphics.append(part)
    if graphics:
        yield graphics


def ndve_programs(data):
    if data[0x28:0x2C] == b"NDSR":
        yield from ndsr_programs(data, 0x28)
    for match in re.finditer(re.escape(CONTROL_MAGIC), data):
        control_offset = match.start()
        try:
            control, size = control_at(data, control_offset)
        except ValueError:
            continue
        for entry_match in re.finditer(re.escape(struct.pack("<II", size, 0)), data):
            entry = entry_match.start() - 8
            if entry < 0 or entry % 4:
                continue
            to_control, to_code = fields("<II", data, entry)
            table = control_offset - to_control
            if not to_control or table < 0 or table % 4 or control_offset + to_code + size > len(data):
                continue
            count, blobs = fields("<II", data, table)
            first = table + 8 + blobs * 8
            if 0 < count < 256 and blobs < 16 and (entry - first) % 16 == 0 and 0 <= (entry - first) // 16 < count:
                yield [stage(control, checked(data, control_offset + to_code, size))]
                break


def archives(romfs):
    for folder in ("Shader", "Layout2Shader", "Lib", "Movie", "Effect"):
        for top, dirs, names in os.walk(os.path.join(romfs, folder)):
            dirs.sort()
            for name in sorted(names):
                if name.endswith(".zs") or any(x in name for x in (".bfsha", ".sarc", ".pck", ".sharcb")):
                    yield os.path.join(top, name)
