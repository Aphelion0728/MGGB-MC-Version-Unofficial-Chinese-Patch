"""Map the stock Ghost Babel native callback hooks into the translated ROM.

The Bonus Content executable has two different ROM integration mechanisms:

* a copy-overlay table (24-byte records), and
* a native callback table (16-byte records).

For each native callback record the launcher checks one opcode in the ROM and,
when it matches, replaces it with 0x40 and associates the ROM bank/address with
an x64 callback.  This report relocates those hook sites by comparing the stock
English and translated ROM bank-by-bank.  It is deliberately read-only.
"""

from __future__ import annotations

import hashlib
import json
import struct
from difflib import SequenceMatcher
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[3]
STOCK_EXE = ROOT / "Buckup" / "20261026_qe_emulator_diag_before" / "MGS MC2 Bonus Content.exe"
EN_ROM = ROOT / "EN ROM" / "block_230.gbc"
CHS_ROM = ROOT / "CHS ROM" / "block_230.gbc"
OUT_DIR = ROOT / "CHS_Project" / "outputs" / "analysis_shortcuts"
OUT_JSON = OUT_DIR / "native_hook_relocation.json"
OUT_MD = OUT_DIR / "native_hook_relocation.md"

MODE1_HOOK_TABLE_VA = 0x1404B8D00
RECORD_SIZE = 16
BANK_SIZE = 0x4000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def rom_offset(bank: int, address: int) -> int:
    if bank == 0:
        if not 0 <= address < 0x4000:
            raise ValueError(f"invalid bank-0 address: {address:#x}")
        return address
    if not 0x4000 <= address < 0x8000:
        raise ValueError(f"invalid switched-bank address: {bank}:{address:#x}")
    return bank * BANK_SIZE + address - 0x4000


def bank_address(bank: int, offset_in_bank: int) -> int:
    return offset_in_bank if bank == 0 else 0x4000 + offset_in_bank


def matching_map(en_bank: bytes, chs_bank: bytes) -> tuple[dict[int, int], list[tuple[int, int, int]]]:
    matcher = SequenceMatcher(None, en_bank, chs_bank, autojunk=False)
    mapping: dict[int, int] = {}
    blocks = []
    for block in matcher.get_matching_blocks():
        if not block.size:
            continue
        blocks.append((block.a, block.b, block.size))
        for index in range(block.size):
            mapping[block.a + index] = block.b + index
    return mapping, blocks


def context_candidates(en_bank: bytes, chs_bank: bytes, position: int) -> list[dict[str, int]]:
    candidates: list[dict[str, int]] = []
    for radius in (32, 24, 16, 12, 8, 6, 4):
        start = max(0, position - radius)
        end = min(len(en_bank), position + radius + 1)
        needle = en_bank[start:end]
        found = []
        cursor = 0
        while True:
            hit = chs_bank.find(needle, cursor)
            if hit < 0:
                break
            found.append(hit + (position - start))
            cursor = hit + 1
        if found:
            for hit in found:
                candidates.append({"position": hit, "context_bytes": len(needle), "matches": len(found)})
            break
    return candidates


def main() -> None:
    exe = STOCK_EXE.read_bytes()
    en = EN_ROM.read_bytes()
    chs = CHS_ROM.read_bytes()
    pe = pefile.PE(data=exe, fast_load=False)
    table_offset = file_offset(pe, MODE1_HOOK_TABLE_VA)

    records = []
    for index in range(256):
        start = table_offset + index * RECORD_SIZE
        bank, address, opcode, callback = struct.unpack_from("<HHB3xQ", exe, start)
        if callback == 0:
            break
        records.append((index, bank, address, opcode, callback, start))

    bank_maps = {}
    bank_blocks = {}
    for bank in sorted({record[1] for record in records}):
        en_bank = en[bank * BANK_SIZE : (bank + 1) * BANK_SIZE]
        chs_bank = chs[bank * BANK_SIZE : (bank + 1) * BANK_SIZE]
        bank_maps[bank], bank_blocks[bank] = matching_map(en_bank, chs_bank)

    rows = []
    for index, bank, address, opcode, callback, record_file_offset in records:
        absolute = rom_offset(bank, address)
        position = absolute - bank * BANK_SIZE
        en_bank = en[bank * BANK_SIZE : (bank + 1) * BANK_SIZE]
        chs_bank = chs[bank * BANK_SIZE : (bank + 1) * BANK_SIZE]
        mapped = bank_maps[bank].get(position)
        method = "matching block"
        confidence = "high"
        context_bytes = 0
        alternatives = 0

        if mapped is None or chs_bank[mapped] != opcode:
            candidates = [
                item for item in context_candidates(en_bank, chs_bank, position)
                if chs_bank[item["position"]] == opcode
            ]
            if candidates:
                candidates.sort(key=lambda item: (item["matches"], -item["context_bytes"], abs(item["position"] - position)))
                chosen = candidates[0]
                mapped = chosen["position"]
                method = "exact context"
                context_bytes = chosen["context_bytes"]
                alternatives = chosen["matches"]
                confidence = "high" if alternatives == 1 else "medium"
            else:
                mapped = None
                method = "unresolved"
                confidence = "none"

        chs_address = bank_address(bank, mapped) if mapped is not None else None
        rows.append(
            {
                "entry": index,
                "bank": bank,
                "stock_address": f"0x{address:04X}",
                "translated_address": f"0x{chs_address:04X}" if chs_address is not None else None,
                "delta": chs_address - address if chs_address is not None else None,
                "expected_opcode": f"0x{opcode:02X}",
                "translated_opcode": f"0x{chs_bank[mapped]:02X}" if mapped is not None else None,
                "callback_va": f"0x{callback:X}",
                "method": method,
                "confidence": confidence,
                "context_bytes": context_bytes,
                "candidate_count": alternatives,
                "record_file_offset": f"0x{record_file_offset:X}",
                "record_address_field_file_offset": f"0x{record_file_offset + 2:X}",
            }
        )

    report = {
        "inputs": {
            "stock_exe": str(STOCK_EXE),
            "stock_exe_sha256": sha256(STOCK_EXE),
            "english_rom": str(EN_ROM),
            "english_rom_sha256": sha256(EN_ROM),
            "translated_rom": str(CHS_ROM),
            "translated_rom_sha256": sha256(CHS_ROM),
        },
        "native_hook_table_va": f"0x{MODE1_HOOK_TABLE_VA:X}",
        "entry_count": len(rows),
        "resolved_count": sum(row["translated_address"] is not None for row in rows),
        "rows": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Ghost Babel native hook relocation",
        "",
        "This is a read-only bank-aware mapping of the stock mode-1 native callback table.",
        "",
        f"- Entries: {report['entry_count']}",
        f"- Resolved: {report['resolved_count']}",
        "",
        "| # | Bank | Stock | CHS | Delta | Opcode | Callback | Method | Confidence |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        delta = "-" if row["delta"] is None else f"{row['delta']:+d}"
        lines.append(
            f"| {row['entry']} | {row['bank']} | {row['stock_address']} | "
            f"{row['translated_address'] or '-'} | {delta} | {row['expected_opcode']} | "
            f"{row['callback_va']} | {row['method']} | {row['confidence']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"entries={report['entry_count']} resolved={report['resolved_count']}")
    for row in rows:
        print(
            f"{row['entry']:02d} bank={row['bank']:03d} {row['stock_address']} -> "
            f"{row['translated_address'] or 'UNRESOLVED':>10} delta={str(row['delta']):>4} "
            f"op={row['expected_opcode']} callback={row['callback_va']} "
            f"{row['method']}/{row['confidence']}"
        )
    print(OUT_JSON)
    print(OUT_MD)


if __name__ == "__main__":
    main()
