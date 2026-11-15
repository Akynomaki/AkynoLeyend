"""Guarded Ocarina of Time 1.1.1 projection hooks, from Hookshot v2.0.14."""

from pathlib import Path

MAIN = 0x80020000
SITES = (
    (0x6BC708, 0xAD415915, 19, 20),
    (0x6BCF8C, 0x3DC0013A, 26, None),
    (0x6BCF9C, 0x3DC00126, None, 6),
)
FEATURE = "fsr-temporal-jitter-v1"
RECEIPT = "fsr-jitter.txt"


def install(lifter, image):
    """The three sites must match together or the original camera stays intact."""
    for offset, word, _, _ in SITES:
        try:
            actual = image.word(MAIN + offset)
        except (IndexError, ValueError, KeyError):
            actual = None
        if actual != word:
            print(f"FSR jitter: unexpected instruction at main+{offset:#x}; hooks inactive")
            return False
    for offset, _, xreg, yreg in SITES:
        parts = []
        for axis, reg in enumerate((xreg, yreg)):
            if reg is not None:
                lane = f"(uint8_t *)c->vreg[{reg}] + 8"
                parts.append(f"{{ float f; memcpy(&f, {lane}, 4); f += j[{axis}]; memcpy({lane}, &f, 4); }}")
        hook = (
            "{ extern int hos_fsr_jitter_clip(uint64_t projection, float out[2]); float j[2]; "
            "if (hos_fsr_jitter_clip(c->x[28] + 0x1a8, j)) { " + " ".join(parts)
            + f" }} }} /* FSR jitter {offset:x} */"
        )
        pc = MAIN + offset
        lifter.after[pc] = "\n".join(filter(None, (lifter.after.get(pc), hook)))
    return True


def record_emission(gen, files, installed):
    """Publish the capability only after all guarded hooks appear in emitted C."""
    receipt = Path(gen) / RECEIPT
    receipt.unlink(missing_ok=True)
    if not installed:
        return
    missing = {f"/* FSR jitter {offset:x} */" for offset, _, _, _ in SITES}
    for path in files:
        if not missing:
            break
        text = Path(path).read_text(encoding="utf-8")
        missing.difference_update(marker for marker in tuple(missing) if marker in text)
    if not missing:
        receipt.write_text(FEATURE + "\n", encoding="ascii")
    print(f"FSR jitter: {len(SITES) - len(missing)} of {len(SITES)} projection hooks emitted")
