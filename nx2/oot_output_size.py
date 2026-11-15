"""Output/scene/pool patches from Hookshot PR849 and oot_wide.py (GPL-3.0).

Apply the selected output dimensions in the game before allocating render targets.
"""
from pathlib import Path

OUT_DECL = "uint32_t hos_output_size(int height);\nuint64_t hos_rt_pool_size(uint64_t game);\n"
SIZE_CHANGED = "(hos_output_size(0) != 2560 || hos_output_size(1) != 1440)"
OUTPUT_SITES_STAMP = "akyno-output-sites-v3"
PREVIOUS_OUTPUT_SITES_STAMP = "akyno-output-sites-v2"
DISPLAY_SETTINGS = "void f_83213890(Ctx *__restrict A64_NOESC c) {"
OUT_EDITS = [
    # Initial dimensions for the framework's window textures.
    ("    c->x[8] = 0xa00ULL;\n    c->x[8] = (c->x[8] & ~(0xFFFFULL<<32)) | (0x5a0ULL<<32);\n"
          "    { uint64_t _b=c->x[21]; int64_t _o=20; recomp_store64(c,(_b+_o),c->x[8]); }",
     "    c->x[8] = hos_output_size(0) | ((uint64_t)hos_output_size(1) << 32);\n"
          "    { uint64_t _b=c->x[21]; int64_t _o=20; recomp_store64(c,(_b+_o),c->x[8]); }"),
    ("    { uint64_t _a=c->x[0], _b=724ULL; uint64_t _r=_a+_b; c->x[21]=_r; }\n"
     "    { uint64_t _r = ((uint64_t)0 | ((c->x[1]) << 0)); c->x[20] = _r; }\n",
     "    { uint64_t _a=c->x[0], _b=724ULL; uint64_t _r=_a+_b; c->x[21]=_r; }\n"
     "    { uint64_t _r = ((uint64_t)0 | ((c->x[1]) << 0)); c->x[20] = _r; }\n"
     f"    if ({SIZE_CHANGED} && recomp_load32(c, c->x[20] + 8) == 2560) {{ recomp_store32(c, c->x[20] + 8, hos_output_size(0)); recomp_store32(c, c->x[20] + 12, hos_output_size(1)); }}\n"),
    # - f_80ea2f30: the 3D's largest size, ResolutionParam's BaseResolution (or 1920 x 1080 as constants), 3/4 of 2560 x 1440;
    #   above it the game takes a smaller upscale network (1/3: 1280 x 720 at 4K). Scaled with the output.
    ("c->x[30] = 0x80ea2ffcULL; f_831cca50(c);\n"
     "    { uint64_t _b=c->x[0]; int64_t _o=0; { uint64_t _p0,_p1; recomp_ldp32(c,(_b+_o),&_p0,&_p1); c->x[24]=_p0; c->x[25]=_p1; } }\n",
     "c->x[30] = 0x80ea2ffcULL; f_831cca50(c);\n"
     "    { uint64_t _b=c->x[0]; int64_t _o=0; { uint64_t _p0,_p1; recomp_ldp32(c,(_b+_o),&_p0,&_p1); c->x[24]=_p0; c->x[25]=_p1; } }\n"
     f"    if ({SIZE_CHANGED}) {{ c->x[24] = (uint32_t)c->x[24] * hos_output_size(0) / 2560; c->x[25] = (uint32_t)c->x[25] * hos_output_size(1) / 1440; }}\n"),
    ("    c->x[8] = 0x44f00000ULL;\n    c->x[8] &= 0xFFFFFFFFULL;\n    recomp_store32(c,c->x[19] + 3668,c->x[8]);\n"
     "    c->x[8] = 0x44870000ULL;\n    c->x[8] &= 0xFFFFFFFFULL;\n",
     "    c->x[8] = hos_output_size(0) * 3 / 4;\n    { float _f = (float)c->x[8]; uint32_t _u; memcpy(&_u, &_f, 4); c->x[8] = _u; }\n"
     "    recomp_store32(c,c->x[19] + 3668,c->x[8]);\n"
     "    c->x[8] = hos_output_size(1) * 3 / 4;\n    { float _f = (float)c->x[8]; uint32_t _u; memcpy(&_u, &_f, 4); c->x[8] = _u; }\n"),
    # - The render targets' GPU pool: 0x13100000 bytes (the graphics config's +1464, read in f_836ce9d0, which takes its storage from
    #   the "Graphics" heap and makes a physical pool and a virtual one over it: f_80c4a1c0 -> f_80c49070 -> f_80c49380 -> f_811c9ba0).
    #   Sized for 2560 x 1440: a 3840x2160 3D at the 4K output ran out of it and the next target came back null (crash in f_8005ed00,
    #   the pool's allocator, its +0x28 0x13100000). Scaled with the output's pixels (host/nn_applet.c
    #   hos_rt_pool_size: 687 MB at 3840 x 2160), at the config, so the storage and the pool agree.
    ("L_836cea54:;\n",
     "L_836cea54:;\n"
     "    if (recomp_load64(c, c->x[19] + 1464) == 0x13100000ULL) recomp_store64(c, c->x[19] + 1464, hos_rt_pool_size(0x13100000ULL));\n"),
    # - The "Graphics" heap holds it, made by f_83b7b340 with the other module heaps (twice: 0x34900000 bytes in f_83b7a2c0's first
    #   pass, then the heap kept, 0x348ffe20; it had under 16 MB to spare): grown by as much as the pool.
    ("c->x[30] = 0x83b7b440ULL; f_809df710(c);\n",
     "if (c->x[0] == 0x34900000ULL || c->x[0] == 0x348ffe20ULL) c->x[0] += hos_rt_pool_size(0x13100000ULL) - 0x13100000ULL;\n"
     "c->x[30] = 0x83b7b440ULL; f_809df710(c);\n"),
    # - f_83b7b340 then takes each module heap's use (its vtable +120) off the module's budget (the configured size, a table of slots)
    #   and aborts below zero (f_8351c280): the Graphics heap's use counts as the shipped one.
    ("{ uint64_t _t = c->x[8]; c->x[30] = 0x83b7b4e0ULL; A64_ICALL(c, _t); }\n",
     "{ uint64_t _t = c->x[8]; c->x[30] = 0x83b7b4e0ULL; A64_ICALL(c, _t); }\n"
     "{ const uint64_t _b = recomp_load64(c, c->x[21] + (c->x[22] << 3)), _g = hos_rt_pool_size(0x13100000ULL) - 0x13100000ULL; "
     "if ((_b == 0x34900000ULL || _b == 0x348ffe20ULL) && c->x[0] > _g) c->x[0] -= _g; }\n"),
    # - f_80b72340 (from the graphics init f_836cf4b0) makes a heap of what the Graphics heap can still give, which took the growth as
    #   well (0x1b6cb48 bytes as shipped, 0x1996cb48 grown) and left too little for the pool: it keeps its shipped size.
    ("c->x[30] = 0x80b723acULL; f_809df700(c);\n",
     "if (c->x[0] > hos_rt_pool_size(0x13100000ULL) - 0x13100000ULL) c->x[0] -= hos_rt_pool_size(0x13100000ULL) - 0x13100000ULL;\n"
     "c->x[30] = 0x80b723acULL; f_809df700(c);\n"),
]

DISPLAY_EDITS = [
    # Hookshot v2.1.0 nx2/oot_wide.py, main+0x31f39f8 and main+0x31f3a04.
    # The display settings also construct these dimensions after framework init.
    ("    c->x[8] = 0xa00ULL;\n    c->x[8] = (c->x[8] & ~(0xFFFFULL<<32)) | (0x5a0ULL<<32);",
     "    c->x[8] = hos_output_size(0) | ((uint64_t)hos_output_size(1) << 32);"
     " /* display settings: output */"),
    # The game's scaler's reference input is 3/4 of the output. The fixed
    # scene scale still determines the actual 3D extent independently.
    ("    c->x[8] = 0x780ULL;\n    c->x[8] = (c->x[8] & ~(0xFFFFULL<<32)) | (0x438ULL<<32);",
     "    c->x[8] = (hos_output_size(0) * 3 / 4) | ((uint64_t)(hos_output_size(1) * 3 / 4) << 32);"
     " /* display settings: scaler reference */"),
]


def plan(gen, *, legacy_only=False):
    """Locate output/pool sites, accepting at most one exact form of each."""
    found = [0] * len(OUT_EDITS)
    display_found = [0] * len(DISPLAY_EDITS)
    work = []
    for path in sorted(Path(gen).glob("code_*.c")):
        source = path.read_text(encoding="utf-8")
        pending = []
        for i, (old, new) in enumerate(OUT_EDITS):
            applied = source.count(new)
            previous = new.replace(SIZE_CHANGED, "hos_output_size(0) != 2560")
            legacy = source.count(previous) if previous != new else 0
            originals = source.count(old) - applied * new.count(old) - legacy * previous.count(old)
            if legacy_only and originals:
                raise ValueError("output upgrade expected an existing output/pool hook: " + path.name)
            found[i] += applied + originals + legacy
            if originals or legacy:
                pending.append((previous if legacy else old, new))
        # Both MOV pairs are in the display settings initializer.
        start = source.find(DISPLAY_SETTINGS)
        if start >= 0:
            end = source.find("\n}", start)
            if end < 0 or source.count(DISPLAY_SETTINGS) != 1:
                raise ValueError("invalid display settings function: " + path.name)
            body = source[start:end]
            updated = body
            for i, (old, new) in enumerate(DISPLAY_EDITS):
                display_found[i] += body.count(old) + body.count(new)
                updated = updated.replace(old, new, 1)
            if updated != body:
                pending.append((body, updated))
        if pending:
            if source.count('#include "a64.h"\n') != 1:
                raise ValueError("output patch needs one runtime header: " + str(path))
            work.append((path, pending))
    if found + display_found != [1] * (len(OUT_EDITS) + len(DISPLAY_EDITS)):
        raise ValueError("output/pool guards incomplete: %s; expected one of each" % (found + display_found))
    return work


def patched_source(path, replacements):
    original = path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    for old, new in replacements:
        before, after = (s.encode("utf-8").replace(b"\n", newline) for s in (old, new))
        if original.count(before) != 1:
            raise ValueError("output site changed after inspection: " + path.name)
        original = original.replace(before, after, 1)
    decl = OUT_DECL.encode().replace(b"\n", newline)
    if decl not in original:
        header = b'#include "a64.h"' + newline
        original = original.replace(header, header + decl, 1)
    return original


def apply(gen):
    """Validate every expected source anchor before changing any output/pool site."""
    stamp = Path(gen) / OUTPUT_SITES_STAMP
    stamp.unlink(missing_ok=True)
    for path, replacements in plan(gen):
        path.write_bytes(patched_source(path, replacements))
    stamp.touch()
    print("output resolution: %d source and pool guards verified" % (len(OUT_EDITS) + len(DISPLAY_EDITS)))


def extended_output_emitted(gen):
    return any((Path(gen) / stamp).is_file() for stamp in (OUTPUT_SITES_STAMP, PREVIOUS_OUTPUT_SITES_STAMP))

