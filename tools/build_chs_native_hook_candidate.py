"""Build a minimal CHS executable with the native ROM hooks relocated.

The translated release already selects the stock Ghost Babel integration
profile by recognizing the translated ROM checksum.  Its native callback table
still points at stock-ROM addresses, however.  This builder changes only the
two-byte address field of callback records whose instruction moved in the CHS
ROM.  It deliberately leaves the ROM and the copy-overlay table untouched.
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
MAPPING_JSON = ROOT / "CHS_Project" / "outputs" / "analysis_shortcuts" / "native_hook_relocation.json"
OUT_DIR = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_native_hook_relocation"
OUT_EXE = OUT_DIR / "MGS MC2 Bonus Content.exe"
OUT_MANIFEST = OUT_DIR / "manifest.json"

EXPECTED_HASHES = {
    STOCK_EXE: "ab2eb668545297e9a00dd048e4a7dc758c4f9f104ba2c37bc77eb0d627fd8fca",
    RELEASE_EXE: "2c0459c2b159973de8e003f7d5b65332eeaffb2f778467c45766bf0edac4d8a8",
    EN_ROM: "90d3bb23de52e642ce361f9688910f3dc3669427452de6290589e72b1f22311f",
    CHS_ROM: "ff6950746169ab565d2f852ef699fcf1242e172ab24580ff43eb9aa17cd6a773",
}

MODE1_HOOK_TABLE_VA = 0x1404B8D00
RECORD_SIZE = 16
BANK_SIZE = 0x4000
TRANSLATED_CHECKSUM_FILE_OFFSET = 0x45B17
TRANSLATED_CHECKSUM_BYTES = bytes.fromhex("17 b7")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_hash(path: Path) -> None:
    actual = sha256(path)
    expected = EXPECTED_HASHES[path]
    if actual != expected:
        raise RuntimeError(f"unexpected hash for {path}: {actual} != {expected}")


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


def parse_record(data: bytes, offset: int) -> tuple[int, int, int, int]:
    return struct.unpack_from("<HHB3xQ", data, offset)


def main() -> None:
    for path in EXPECTED_HASHES:
        require_hash(path)

    stock = STOCK_EXE.read_bytes()
    release = RELEASE_EXE.read_bytes()
    translated_rom = CHS_ROM.read_bytes()
    mapping = json.loads(MAPPING_JSON.read_text(encoding="utf-8"))

    if mapping["entry_count"] != 52 or mapping["resolved_count"] != 52:
        raise RuntimeError("native hook mapping is incomplete")
    if mapping["inputs"]["stock_exe_sha256"] != EXPECTED_HASHES[STOCK_EXE]:
        raise RuntimeError("mapping was not generated from the required stock executable")
    if mapping["inputs"]["translated_rom_sha256"] != EXPECTED_HASHES[CHS_ROM]:
        raise RuntimeError("mapping was not generated from the required translated ROM")
    if release[TRANSLATED_CHECKSUM_FILE_OFFSET:TRANSLATED_CHECKSUM_FILE_OFFSET + 2] != TRANSLATED_CHECKSUM_BYTES:
        raise RuntimeError("release no longer contains the translated ROM checksum selector")

    stock_pe = pefile.PE(data=stock, fast_load=False)
    release_pe = pefile.PE(data=release, fast_load=False)
    stock_table = file_offset(stock_pe, MODE1_HOOK_TABLE_VA)
    release_table = file_offset(release_pe, MODE1_HOOK_TABLE_VA)

    candidate = bytearray(release)
    patched_records = []
    allowed_changed_offsets: set[int] = set()

    for row in mapping["rows"]:
        index = row["entry"]
        stock_offset = stock_table + index * RECORD_SIZE
        release_offset = release_table + index * RECORD_SIZE
        stock_record = parse_record(stock, stock_offset)
        release_record = parse_record(release, release_offset)
        if release_record != stock_record:
            raise RuntimeError(f"release native hook record {index} already differs from stock")

        bank, old_address, opcode, callback = release_record
        if bank != row["bank"] or old_address != int(row["stock_address"], 16):
            raise RuntimeError(f"mapping/table identity mismatch at record {index}")
        if opcode != int(row["expected_opcode"], 16) or callback != int(row["callback_va"], 16):
            raise RuntimeError(f"mapping/table payload mismatch at record {index}")
        if row["confidence"] != "high" or row["translated_address"] is None:
            raise RuntimeError(f"record {index} is not a high-confidence relocation")

        new_address = int(row["translated_address"], 16)
        translated_offset = rom_offset(bank, new_address)
        if translated_rom[translated_offset] != opcode:
            raise RuntimeError(f"translated opcode mismatch at record {index}")

        if new_address != old_address:
            address_offset = release_offset + 2
            new_bytes = struct.pack("<H", new_address)
            for byte_index, new_byte in enumerate(new_bytes):
                if release[address_offset + byte_index] != new_byte:
                    allowed_changed_offsets.add(address_offset + byte_index)
            candidate[address_offset:address_offset + 2] = new_bytes
            patched_records.append(
                {
                    "entry": index,
                    "bank": bank,
                    "old_address": f"0x{old_address:04X}",
                    "new_address": f"0x{new_address:04X}",
                    "delta": new_address - old_address,
                    "opcode": f"0x{opcode:02X}",
                    "callback_va": f"0x{callback:X}",
                    "address_field_file_offset": f"0x{address_offset:X}",
                }
            )

    changed_offsets = {index for index, (before, after) in enumerate(zip(release, candidate)) if before != after}
    if changed_offsets != allowed_changed_offsets:
        extra = sorted(changed_offsets - allowed_changed_offsets)
        missing = sorted(allowed_changed_offsets - changed_offsets)
        raise RuntimeError(f"unexpected candidate diff: extra={extra} missing={missing}")

    # Reparse every output record and prove that only its address field changed.
    for row in mapping["rows"]:
        index = row["entry"]
        offset = release_table + index * RECORD_SIZE
        before = parse_record(release, offset)
        after = parse_record(candidate, offset)
        expected_address = int(row["translated_address"], 16)
        if after != (before[0], expected_address, before[2], before[3]):
            raise RuntimeError(f"output record validation failed at {index}")

    if candidate[TRANSLATED_CHECKSUM_FILE_OFFSET:TRANSLATED_CHECKSUM_FILE_OFFSET + 2] != TRANSLATED_CHECKSUM_BYTES:
        raise RuntimeError("translated checksum selector was disturbed")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_EXE.write_bytes(candidate)
    manifest = {
        "purpose": "Relocate the stock mode-1 native callback table to the translated ROM instruction addresses.",
        "scope": "Executable only; ROM and copy-overlay table are unchanged.",
        "inputs": {str(path): sha256(path) for path in EXPECTED_HASHES},
        "mapping": str(MAPPING_JSON),
        "output": str(OUT_EXE),
        "output_sha256": sha256_bytes(candidate),
        "native_hook_table_va": f"0x{MODE1_HOOK_TABLE_VA:X}",
        "records_total": len(mapping["rows"]),
        "records_relocated": len(patched_records),
        "changed_byte_count": len(changed_offsets),
        "patched_records": patched_records,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"records_total={manifest['records_total']}")
    print(f"records_relocated={manifest['records_relocated']}")
    print(f"changed_byte_count={manifest['changed_byte_count']}")
    print(f"output_sha256={manifest['output_sha256']}")
    for record in patched_records:
        print(
            f"{record['entry']:02d} bank={record['bank']:03d} "
            f"{record['old_address']} -> {record['new_address']} ({record['delta']:+d})"
        )
    print(OUT_EXE)
    print(OUT_MANIFEST)


if __name__ == "__main__":
    main()
