"""Apply only the stock L/R shortcut control-flow overlays to the translated ROM.

The release EXE has the stock ROM overlay table disabled. Entries 59-61 gate
the L/R shortcut path, while entries 71-73 redirect three dispatch-table
slots to the common input handler. Entries 62-70 are deliberately excluded:
testing proved that copying those menu/tile values directly into the
translated ROM corrupts the in-game option screen. This builder does not
modify installed files.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import pefile


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_raw_shortcuts_dispatch"
RELEASE = ROOT / "CHS_Project" / "release" / "0.2beta"
STOCK_EXE = ROOT / "Buckup" / "20261026_qe_emulator_diag_before" / "MGS MC2 Bonus Content.exe"
CHS_ROM = ROOT / "CHS ROM" / "block_230.gbc"
EN_ROM = ROOT / "EN ROM" / "block_230.gbc"
ROM_KEY = bytes.fromhex(
    "1124fa5f5ab36ae83cc359efd477b06309d5c1c63fdc75ad"
    "474fdc5424f753ed16fa23d1e91eeeb02dac32b6d67cd2b7a"
    "6ff601a53c40a3cc16989ffcfc54643"
)
EXPECTED = {
    "stock_exe": "ab2eb668545297e9a00dd048e4a7dc758c4f9f104ba2c37bc77eb0d627fd8fca",
    "release_exe": "2c0459c2b159973de8e003f7d5b65332eeaffb2f778467c45766bf0edac4d8a8",
    "chs_rom": "ff6950746169ab565d2f852ef699fcf1242e172ab24580ff43eb9aa17cd6a773",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_sha(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if sha(data) != expected:
        raise RuntimeError(f"Unexpected source hash: {path}")
    return data


def xor_cycle(data: bytes) -> bytes:
    return bytes(value ^ ROM_KEY[index % len(ROM_KEY)] for index, value in enumerate(data))


def block230(archive: bytes) -> tuple[int, int]:
    align = 0x800
    offsets = [i for i in range(0, len(archive) - 7, align) if archive[i:i + 4] == b"mdf\0"]
    if len(offsets) <= 230:
        raise RuntimeError("Release archive has no MDF block 230")
    start = offsets[230]
    end = offsets[231] if len(offsets) > 231 else len(archive)
    if struct.unpack_from("<I", archive, start + 4)[0] != 0x400000:
        raise RuntimeError("Block 230 is not a 4 MiB ROM")
    return start, end


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stock = require_sha(STOCK_EXE, EXPECTED["stock_exe"])
    require_sha(RELEASE / "MGS MC2 Bonus Content.exe", EXPECTED["release_exe"])
    original = require_sha(CHS_ROM, EXPECTED["chs_rom"])
    english = EN_ROM.read_bytes()
    pe = pefile.PE(data=stock, fast_load=True)
    file_offset = lambda va: pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
    table = file_offset(0x1404B85F0)
    rom = bytearray(original)
    changes = []
    for entry in (59, 60, 61, 71, 72, 73):
        target, source_va, length = struct.unpack_from("<QQQ", stock, table + entry * 24)
        if entry == 59:
            if (target, length, stock[file_offset(source_va):file_offset(source_va) + length]) != (0xAB4, 2, bytes.fromhex("b6 0a")):
                raise RuntimeError("Stock entry 59 differs")
            target, payload, expected = 0xAB3, bytes.fromhex("b5 0a"), bytes.fromhex("07 0a")
        elif entry in (60, 61):
            if (entry, target, length) not in ((60, 0x9EE, 1), (61, 0x9F7, 1)):
                raise RuntimeError(f"Stock entry {entry} differs")
            target = {60: 0x9ED, 61: 0x9F6}[entry]
            payload = b"\0"
            expected = {60: b"\x19", 61: b"\x10"}[entry]
        elif entry in (71, 72, 73):
            expected_stock = {71: 0x1E1, 72: 0x1E7, 73: 0x1F3}[entry]
            stock_payload = stock[file_offset(source_va):file_offset(source_va) + length]
            if (target, length, stock_payload) != (expected_stock, 2, bytes.fromhex("08 0a")):
                raise RuntimeError(f"Stock entry {entry} differs")
            target = expected_stock
            payload = bytes.fromhex("07 0a")
            expected = {
                71: bytes.fromhex("84 02"),
                72: bytes.fromhex("98 02"),
                73: bytes.fromhex("c7 02"),
            }[entry]
        else:
            raise RuntimeError(f"Unexpected entry {entry}")
        if bytes(rom[target:target + len(expected)]) != expected:
            raise RuntimeError(f"CHS entry {entry} differs at {target:#x}")
        rom[target:target + len(payload)] = payload
        changes.append({"entry": entry, "target": f"0x{target:04X}",
                        "before": expected.hex(), "after": payload.hex()})

    # Keep the translated ROM's 0x17B7 identity bytes unchanged. The launcher
    # selects its compatibility path using this header, so recomputing the GB
    # checksum would change the ROM identity before any game code executes.
    checksum = struct.unpack_from(">H", rom, 0x14E)[0]
    changed = [i for i, (before, after) in enumerate(zip(original, rom)) if before != after]
    allowed = set()
    for change in changes:
        offset = int(change["target"], 16)
        allowed.update(range(offset, offset + len(bytes.fromhex(change["after"]))))
    if not set(changed) <= allowed:
        raise RuntimeError("Unexpected ROM changes")

    archive_path = RELEASE / "windata" / "alldata.bin"
    archive = bytearray(archive_path.read_bytes())
    start, end = block230(archive)
    recovered = zlib.decompress(xor_cycle(archive[start + 8:end]))
    if recovered != original:
        raise RuntimeError("Release ROM does not match CHS source")
    encoded = xor_cycle(zlib.compress(bytes(rom), 9))
    if len(encoded) > end - start - 8:
        raise RuntimeError("Patched ROM exceeds MDF block")
    struct.pack_into("<I", archive, start + 4, len(rom))
    archive[start + 8:start + 8 + len(encoded)] = encoded
    if zlib.decompress(xor_cycle(archive[start + 8:end])) != bytes(rom):
        raise RuntimeError("Patched ROM archive roundtrip failed")
    out_bin = OUT / "alldata.dispatch_shortcuts.bin"
    out_bin.write_bytes(archive)
    (OUT / "alldata.dispatch_shortcuts.psb.m").write_bytes((RELEASE / "windata" / "alldata.psb.m").read_bytes())
    (OUT / "block_230.dispatch_shortcuts.gbc").write_bytes(rom)
    report = {
        "purpose": "Test candidate: embed relocated stock L/R branch and dispatch overlays 59-61 plus 71-73 into CHS ROM",
        "changes": changes,
        "rom_checksum": f"0x{checksum:04X}",
        "rom_sha256": sha(rom),
        "archive_sha256": sha(archive),
        "source_archive_sha256": sha(archive_path.read_bytes()),
        "release_exe_sha256": EXPECTED["release_exe"],
        "status": "Static roundtrip verified; game test pending",
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
