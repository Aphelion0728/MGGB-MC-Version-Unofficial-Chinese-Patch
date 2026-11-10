"""Build a read-only emulator ROM address probe for the CHS release."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_rom_read_probe"
RELEASE = ROOT / "CHS_Project" / "release" / "0.2beta" / "windata"
REPLACER = ROOT / "CHS_Project" / "source" / "PsbResourceReplace" / "bin" / "Release" / "net48" / "PsbResourceReplace.exe"
PREFIX = "25G/xpvTbsb+6"
NAME = "system/script/play_standalone.nut.m"
SOURCE = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_runtime_probe" / "play_standalone.release.nut.m"
EXPECTED_SCRIPT = "a3479681d9b02a68364e7db0928a85169190bae5c025376211067afa32292fd4"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one insertion point, found {count}")
    return data.replace(old, new, 1)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if sha(SOURCE) != EXPECTED_SCRIPT:
        raise RuntimeError("Release script source differs from verified original")
    src = SOURCE.read_bytes()
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
        b"qe_indicator.print(\"ROM READ PROBE\");\r\n"
    )
    src = replace_once(src, anchor, anchor + setup)
    marker = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\nwait(0);\r\n}\r\n::pause_main_close();"
    )
    lines = [
        "if ( !::isMasterBuild() ) {",
        "::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);",
        "}",
        "local q = ::g_inputKeyboard.checkKeyboard(KEYBOARD.Q) ? 1 : 0;",
        "local e = ::g_inputKeyboard.checkKeyboard(KEYBOARD.E) ? 1 : 0;",
        "local l = (::g_input.key(KEY.L) == KEY.L) ? 1 : 0;",
        "local r = (::g_input.key(KEY.R) == KEY.R) ? 1 : 0;",
        "local a100 = ::g_emu_task.getRomValue(8, 0x100);",
        "local a101 = ::g_emu_task.getRomValue(8, 0x101);",
        "local a102 = ::g_emu_task.getRomValue(8, 0x102);",
        "local a134 = ::g_emu_task.getRomValue(8, 0x134);",
        "local a135 = ::g_emu_task.getRomValue(8, 0x135);",
        "local a1e1 = ::g_emu_task.getRomValue(8, 0x1E1);",
        "local a9ed = ::g_emu_task.getRomValue(8, 0x9ED);",
        "local aab3 = ::g_emu_task.getRomValue(8, 0xAB3);",
        "local b1e1 = ::g_emu_task.getRomValue(8, 0x101E1);",
        "local b9ed = ::g_emu_task.getRomValue(8, 0x109ED);",
        "local bab3 = ::g_emu_task.getRomValue(8, 0x10AB3);",
        "qe_indicator.print(format(\"ROM READ Q%d E%d L%d R%d\\n0100 %02x %02x %02x 0134 %02x %02x\\n01E1 %02x 09ED %02x 0AB3 %02x\\n101E1 %02x 109ED %02x 10AB3 %02x\", q, e, l, r, a100, a101, a102, a134, a135, a1e1, a9ed, aab3, b1e1, b9ed, bab3));",
        "wait(0);",
        "}",
        "::pause_main_close();",
    ]
    src = replace_once(src, marker, "\r\n".join(lines).encode("ascii"))
    script = OUT / "play_standalone.rom_read.nut.m"
    script.write_bytes(src)
    candidate_bin = OUT / "alldata.rom_read.bin"
    candidate_index = OUT / "alldata.rom_read.psb.m"
    subprocess.run([str(REPLACER), "replace", str(script), str(RELEASE / "alldata.bin"),
                    str(RELEASE / "alldata.psb.m"), PREFIX, NAME,
                    str(candidate_bin), str(candidate_index)], check=True)
    roundtrip = OUT / "play_standalone.roundtrip.nut.m"
    subprocess.run([str(REPLACER), "extract", str(candidate_bin), str(candidate_index),
                    PREFIX, NAME, str(roundtrip)], check=True)
    if roundtrip.read_bytes() != src:
        raise RuntimeError("Resource roundtrip differs")
    print(f"bin {sha(candidate_bin)}")
    print(f"index {sha(candidate_index)}")


if __name__ == "__main__":
    main()
