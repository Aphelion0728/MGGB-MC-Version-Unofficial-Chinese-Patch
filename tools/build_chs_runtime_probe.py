"""Build a reversible in-memory ROM shortcut probe for the CHS release.

The probe displays input state and live ROM bytes. Pressing F8 writes six
verified shortcut sites to the emulator's in-memory ROM through its own
setRomValue API. It never modifies the ROM file and only writes when every
original byte matches the expected CHS image.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_runtime_probe"
RELEASE = ROOT / "CHS_Project" / "release" / "0.2beta" / "windata"
REPLACER = ROOT / "CHS_Project" / "source" / "PsbResourceReplace" / "bin" / "Release" / "net48" / "PsbResourceReplace.exe"
PREFIX = "25G/xpvTbsb+6"
NAME = "system/script/play_standalone.nut.m"
SOURCE = OUT / "play_standalone.release.nut.m"

EXPECTED_SCRIPT = "a3479681d9b02a68364e7db0928a85169190bae5c025376211067afa32292fd4"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one insertion point; found {count}")
    return data.replace(old, new, 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        subprocess.run([str(REPLACER), "extract", str(RELEASE / "alldata.bin"),
                        str(RELEASE / "alldata.psb.m"), PREFIX, NAME, str(SOURCE)], check=True)
    if sha(SOURCE) != EXPECTED_SCRIPT:
        raise RuntimeError("Release script does not match expected original")
    rom = (ROOT / "CHS ROM" / "block_230.gbc").read_bytes()
    sites = [
        (0x09ED, bytes.fromhex("19"), bytes.fromhex("00")),
        (0x09F6, bytes.fromhex("10"), bytes.fromhex("00")),
        (0x0AB3, bytes.fromhex("07 0A"), bytes.fromhex("B5 0A")),
        (0x01E1, bytes.fromhex("84 02"), bytes.fromhex("07 0A")),
        (0x01E7, bytes.fromhex("98 02"), bytes.fromhex("07 0A")),
        (0x01F3, bytes.fromhex("C7 02"), bytes.fromhex("07 0A")),
    ]
    for address, original, _ in sites:
        if rom[address:address + len(original)] != original:
            raise RuntimeError(f"CHS ROM unexpected bytes at {address:#x}")

    source = SOURCE.read_bytes()
    anchor = b"::pause_main_init( session, _play_replay, _replay_mode, disable_state_save, _title_control, pause_pad_id );\r\n"
    setup = (
        b"local qe_font_path = load_font_checkJapanese();\r\n"
        b"local qe_font_resource = Resource();\r\n"
        b"qe_font_resource.load(qe_font_path);\r\n"
        b"while (qe_font_resource.loading) wait(0);\r\n"
        b"local qe_layer = ScaledLayer();\r\n"
        b"qe_layer.priority = PRIORITY_NOTIFY_DIALOG_LAYER + 10;\r\n"
        b"qe_layer.smoothing = true;\r\n"
        b"qe_layer.visible = true;\r\n"
        b"local qe_indicator = Indicator(qe_layer, qe_font_resource.find(qe_font_path));\r\n"
        b"qe_indicator.left = -SCREEN_XSIZE / 2 + 40;\r\n"
        b"qe_indicator.top = -SCREEN_YSIZE / 2 + 40;\r\n"
        b"qe_indicator.visible = true;\r\n"
        b"qe_indicator.fontColor = 0xffffffff;\r\n"
        b"local qe_last = \"none\";\r\n"
        b"local qe_patch = \"OFF (press F8)\";\r\n"
        b"qe_indicator.print(\"CHS ROM PROBE ACTIVE\");\r\n"
    )
    source = replace_once(source, anchor, anchor + setup)
    marker = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\nwait(0);\r\n}\r\n::pause_main_close();"
    )
    lines = [
        "if ( !::isMasterBuild() ) {",
        "::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);",
        "}",
        "",
        "if (::g_inputKeyboard.keyboardPressed() == KEYBOARD.F8 && qe_patch == \"OFF (press F8)\") {",
        "local qe_bytes_ok = true;",
    ]
    for address, original, _ in sites:
        for offset, value in enumerate(original):
            lines.append(f"if (::g_emu_task.getRomValue(8, 0x{address + offset:X}) != 0x{value:02X}) qe_bytes_ok = false;")
    lines += ["if (qe_bytes_ok) {"]
    for address, _, patched in sites:
        for offset, value in enumerate(patched):
            lines.append(f"::g_emu_task.setRomValue(8, 0x{address + offset:X}, 0x{value:02X});")
    lines += [
        "qe_patch = \"APPLIED\";",
        "} else qe_patch = \"MISMATCH - NOT WRITTEN\";",
        "}",
        "local qe_q = ::g_inputKeyboard.checkKeyboard(KEYBOARD.Q) ? 1 : 0;",
        "local qe_e = ::g_inputKeyboard.checkKeyboard(KEYBOARD.E) ? 1 : 0;",
        "local qe_l = (::g_input.key(KEY.L) == KEY.L) ? 1 : 0;",
        "local qe_r = (::g_input.key(KEY.R) == KEY.R) ? 1 : 0;",
        "local qe_virt = ::g_emu_task.getEmuKeyCurrentOn(0);",
        "if (qe_q || qe_e || qe_l || qe_r) qe_last = format(\"Q%d E%d L%d R%d V%08x\", qe_q, qe_e, qe_l, qe_r, qe_virt);",
        "local qe_byte_a = ::g_emu_task.getRomValue(8, 0xAB3);",
        "local qe_byte_b = ::g_emu_task.getRomValue(8, 0x1E1);",
        "local qe_byte_c = ::g_emu_task.getRomValue(8, 0x9ED);",
        "qe_indicator.print(format(\"CHS PROBE Q%d E%d L%d R%d V%08x\\nLAST %s\\nROM AB3=%02x 1E1=%02x 9ED=%02x %s\", qe_q, qe_e, qe_l, qe_r, qe_virt, qe_last, qe_byte_a, qe_byte_b, qe_byte_c, qe_patch));",
        "wait(0);",
        "}",
        "::pause_main_close();",
    ]
    injection = ("\r\n".join(lines)).encode("ascii")
    source = replace_once(source, marker, injection)
    script = OUT / "play_standalone.chs_probe.nut.m"
    script.write_bytes(source)
    candidate_bin = OUT / "alldata.chs_probe.bin"
    candidate_index = OUT / "alldata.chs_probe.psb.m"
    subprocess.run([str(REPLACER), "replace", str(script), str(RELEASE / "alldata.bin"),
                    str(RELEASE / "alldata.psb.m"), PREFIX, NAME,
                    str(candidate_bin), str(candidate_index)], check=True)
    extracted = OUT / "play_standalone.roundtrip.nut.m"
    subprocess.run([str(REPLACER), "extract", str(candidate_bin), str(candidate_index),
                    PREFIX, NAME, str(extracted)], check=True)
    if extracted.read_bytes() != source:
        raise RuntimeError("Probe resource roundtrip failed")
    print(f"bin {candidate_bin} {sha(candidate_bin)}")
    print(f"index {candidate_index} {sha(candidate_index)}")


if __name__ == "__main__":
    main()
