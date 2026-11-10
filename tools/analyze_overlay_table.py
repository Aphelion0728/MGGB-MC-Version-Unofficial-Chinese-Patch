"""Read-only report for the Ghost Babel native ROM overlay table.

The stock executable contains 74 copy records.  Each record copies a payload
from the PE image to a ROM offset before emulation starts.  The CHS release
disabled records 9-73.  This report shows the stock payload, the bytes it
expects in the English ROM, and the bytes currently present in the translated
ROM so the records can be ported by function instead of enabled blindly.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[3]
STOCK_EXE = ROOT / "Buckup" / "20261026_qe_emulator_diag_before" / "MGS MC2 Bonus Content.exe"
RELEASE_EXE = ROOT / "CHS_Project" / "release" / "0.2beta" / "MGS MC2 Bonus Content.exe"
EN_ROM = ROOT / "EN ROM" / "block_230.gbc"
CHS_ROM = ROOT / "CHS ROM" / "block_230.gbc"
OUT = ROOT / "CHS_Project" / "outputs" / "analysis_shortcuts" / "overlay_table_report.json"

TABLE_VA = 0x1404B85F0
ENTRY_COUNT = 74
ENTRY_SIZE = 24


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def read_payload(image: bytes, pe: pefile.PE, va: int, size: int) -> bytes:
    if not size:
        return b""
    try:
        offset = file_offset(pe, va)
    except Exception:
        return bytes(size)
    payload = image[offset : offset + size]
    if len(payload) < size:
        payload += bytes(size - len(payload))
    return payload


def bank(offset: int) -> int:
    return offset // 0x4000


def main() -> None:
    stock = STOCK_EXE.read_bytes()
    release = RELEASE_EXE.read_bytes()
    en = EN_ROM.read_bytes()
    chs = CHS_ROM.read_bytes()
    stock_pe = pefile.PE(data=stock, fast_load=True)
    release_pe = pefile.PE(data=release, fast_load=True)
    stock_table = file_offset(stock_pe, TABLE_VA)
    release_table = file_offset(release_pe, TABLE_VA)

    rows = []
    for index in range(ENTRY_COUNT):
        target, source_va, stock_len = struct.unpack_from(
            "<QQQ", stock, stock_table + index * ENTRY_SIZE
        )
        rel_target, rel_source_va, release_len = struct.unpack_from(
            "<QQQ", release, release_table + index * ENTRY_SIZE
        )
        payload = read_payload(stock, stock_pe, source_va, stock_len)
        en_before = en[target : target + stock_len]
        chs_same = chs[target : target + stock_len]
        rows.append(
            {
                "entry": index,
                "target": f"0x{target:06X}",
                "bank": bank(target),
                "source_va": f"0x{source_va:X}",
                "stock_length": stock_len,
                "release_length": release_len,
                "release_target_same": rel_target == target,
                "release_source_same": rel_source_va == source_va,
                "payload": payload.hex(" "),
                "english_before": en_before.hex(" "),
                "translated_same_offset": chs_same.hex(" "),
                "english_already_payload": en_before == payload,
                "translated_already_payload": chs_same == payload,
            }
        )

    report = {
        "inputs": {
            "stock_exe": str(STOCK_EXE),
            "stock_exe_sha256": sha256(STOCK_EXE),
            "release_exe": str(RELEASE_EXE),
            "release_exe_sha256": sha256(RELEASE_EXE),
            "english_rom_sha256": sha256(EN_ROM),
            "translated_rom_sha256": sha256(CHS_ROM),
        },
        "entries": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("entry target   bank len release payload              EN-before            CHS-same")
    for row in rows:
        if row["entry"] < 9:
            continue
        print(
            f"{row['entry']:>2} {row['target']} {row['bank']:>4} "
            f"{row['stock_length']:>3}/{row['release_length']:<3} "
            f"{row['payload'][:20]:<20} {row['english_before'][:20]:<20} "
            f"{row['translated_same_offset'][:20]}"
        )
    print(f"\nJSON: {OUT}")


if __name__ == "__main__":
    main()
