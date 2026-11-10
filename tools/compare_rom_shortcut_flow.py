"""Compare the Ghost Babel shortcut control flow in the EN and CHS ROMs.

This is a read-only LR35902 diagnostic.  It decodes the first-bank routines
and pointer table touched by stock overlay entries 59-73, following direct
branches/calls so that relocation can be checked by instruction semantics
instead of by a byte offset guess.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROMS = {
    "EN": ROOT / "EN ROM" / "block_230.gbc",
    "CHS": ROOT / "CHS ROM" / "block_230.gbc",
}

REGS = ("b", "c", "d", "e", "h", "l", "[hl]", "a")
CONDS = ("nz", "z", "nc", "c")


def signed(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def decode(data: bytes, pc: int) -> tuple[int, str, int | None]:
    op = data[pc]
    b1 = data[pc + 1] if pc + 1 < len(data) else 0
    word = b1 | ((data[pc + 2] if pc + 2 < len(data) else 0) << 8)
    target = None

    if op == 0xCB:
        group, bit, reg = b1 >> 6, (b1 >> 3) & 7, REGS[b1 & 7]
        if group == 0:
            name = ("rlc", "rrc", "rl", "rr", "sla", "sra", "swap", "srl")[bit]
            return 2, f"{name} {reg}", None
        return 2, f"{('bit', 'res', 'set')[group - 1]} {bit},{reg}", None
    if 0x40 <= op <= 0x7F:
        if op == 0x76:
            return 1, "halt", None
        return 1, f"ld {REGS[(op >> 3) & 7]},{REGS[op & 7]}", None
    if 0x80 <= op <= 0xBF:
        name = ("add a", "adc a", "sub", "sbc a", "and", "xor", "or", "cp")[(op >> 3) & 7]
        return 1, f"{name},{REGS[op & 7]}", None

    one = {
        0x00: "nop", 0x02: "ld [bc],a", 0x03: "inc bc", 0x04: "inc b", 0x05: "dec b",
        0x07: "rlca", 0x09: "add hl,bc", 0x0A: "ld a,[bc]", 0x0B: "dec bc", 0x0C: "inc c",
        0x0D: "dec c", 0x0F: "rrca", 0x12: "ld [de],a", 0x13: "inc de", 0x14: "inc d",
        0x15: "dec d", 0x17: "rla", 0x19: "add hl,de", 0x1A: "ld a,[de]", 0x1B: "dec de",
        0x1C: "inc e", 0x1D: "dec e", 0x1F: "rra", 0x22: "ld [hl+],a", 0x23: "inc hl",
        0x24: "inc h", 0x25: "dec h", 0x27: "daa", 0x29: "add hl,hl", 0x2A: "ld a,[hl+]",
        0x2B: "dec hl", 0x2C: "inc l", 0x2D: "dec l", 0x2F: "cpl", 0x32: "ld [hl-],a",
        0x33: "inc sp", 0x34: "inc [hl]", 0x35: "dec [hl]", 0x37: "scf", 0x39: "add hl,sp",
        0x3A: "ld a,[hl-]", 0x3B: "dec sp", 0x3C: "inc a", 0x3D: "dec a", 0x3F: "ccf",
        0xC1: "pop bc", 0xC5: "push bc", 0xC9: "ret", 0xD1: "pop de", 0xD5: "push de",
        0xD9: "reti", 0xE1: "pop hl", 0xE2: "ld [c],a", 0xE5: "push hl", 0xE9: "jp hl",
        0xF1: "pop af", 0xF2: "ld a,[c]", 0xF3: "di", 0xF5: "push af", 0xF9: "ld sp,hl",
        0xFB: "ei",
    }
    if op in one:
        return 1, one[op], None

    imm8 = {
        0x06: "ld b", 0x0E: "ld c", 0x16: "ld d", 0x1E: "ld e", 0x26: "ld h",
        0x2E: "ld l", 0x36: "ld [hl]", 0x3E: "ld a", 0xC6: "add a", 0xCE: "adc a",
        0xD6: "sub", 0xDE: "sbc a", 0xE0: "ldh [", 0xE6: "and", 0xE8: "add sp",
        0xEE: "xor", 0xF0: "ldh a,[", 0xF6: "or", 0xF8: "ld hl,sp+", 0xFE: "cp",
    }
    if op in imm8:
        suffix = f"${b1:02x}"
        if op in (0xE0, 0xF0):
            suffix += "]"
        return 2, f"{imm8[op]} {suffix}", None

    imm16 = {
        0x01: "ld bc", 0x08: "ld [", 0x11: "ld de", 0x21: "ld hl", 0x31: "ld sp",
        0xEA: "ld [", 0xFA: "ld a,[",
    }
    if op in imm16:
        text = f"{imm16[op]}${word:04x}"
        if op in (0x08, 0xEA, 0xFA):
            text += "]"
        if op in (0x08, 0xEA):
            text += ",sp" if op == 0x08 else ",a"
        return 3, text, None

    if op == 0x18 or op in (0x20, 0x28, 0x30, 0x38):
        target = (pc + 2 + signed(b1)) & 0xFFFF
        cond = "" if op == 0x18 else f" {CONDS[(op - 0x20) // 8]},"
        return 2, f"jr{cond}${target:04x}", target

    if op == 0xC3 or op in (0xC2, 0xCA, 0xD2, 0xDA):
        cond = "" if op == 0xC3 else f" {CONDS[((op & 0x18) >> 3)]},"
        return 3, f"jp{cond}${word:04x}", word
    if op == 0xCD or op in (0xC4, 0xCC, 0xD4, 0xDC):
        cond = "" if op == 0xCD else f" {CONDS[((op & 0x18) >> 3)]},"
        return 3, f"call{cond}${word:04x}", word
    if op in (0xC0, 0xC8, 0xD0, 0xD8):
        return 1, f"ret {CONDS[(op - 0xC0) // 8]}", None
    if op & 0xC7 == 0xC7:
        return 1, f"rst ${op & 0x38:02x}", op & 0x38
    return 1, f"db ${op:02x}", None


def linear(data: bytes, start: int, end: int) -> list[str]:
    rows = []
    pc = start
    while pc < end:
        size, text, _target = decode(data, pc)
        rows.append(f"{pc:04x}  {data[pc:pc + size].hex():<8} {text}")
        pc += size
    return rows


def reachable(data: bytes, starts: list[int], limit: int = 0x4000) -> list[str]:
    queue = deque(starts)
    seen: set[int] = set()
    rows: dict[int, str] = {}
    while queue:
        pc = queue.popleft()
        while 0 <= pc < limit and pc not in seen:
            seen.add(pc)
            size, text, target = decode(data, pc)
            rows[pc] = f"{pc:04x}  {data[pc:pc + size].hex():<8} {text}"
            op = data[pc]
            if target is not None and target < limit:
                queue.append(target)
            pc += size
            if op in (0xC3, 0xC9, 0xD9, 0xE9) or op in (0x18,):
                break
    return [rows[address] for address in sorted(rows)]


def main() -> None:
    for label, path in ROMS.items():
        data = path.read_bytes()
        print(f"\n===== {label}: pointer table 0x01df =====")
        for offset in range(0x1DF, 0x205, 2):
            print(f"{offset:04x}: {int.from_bytes(data[offset:offset + 2], 'little'):04x}")
        print(f"\n===== {label}: shortcut gate 0x09d0-0x0a30 =====")
        print("\n".join(linear(data, 0x09D0 if label == "EN" else 0x09CF,
                               0x0A31 if label == "EN" else 0x0A30)))
        print(f"\n===== {label}: common handler =====")
        start = 0x0A08 if label == "EN" else 0x0A07
        print("\n".join(reachable(data, [start])))
        print(f"\n===== {label}: call site 0x0a90-0x0ad0 =====")
        print("\n".join(linear(data, 0x0A90 if label == "EN" else 0x0A8F,
                               0x0AD0 if label == "EN" else 0x0ACF)))


if __name__ == "__main__":
    main()
