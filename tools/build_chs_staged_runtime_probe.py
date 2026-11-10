"""Build a staged, reversible runtime shortcut overlay experiment."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_staged_runtime_probe"
RELEASE = ROOT / "CHS_Project" / "release" / "0.2beta" / "windata"
REPLACER = ROOT / "CHS_Project" / "source" / "PsbResourceReplace" / "bin" / "Release" / "net48" / "PsbResourceReplace.exe"
PREFIX = "25G/xpvTbsb+6"
NAME = "system/script/play_standalone.nut.m"
SOURCE = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_chs_runtime_probe" / "play_standalone.release.nut.m"
EXPECTED_SCRIPT = "a3479681d9b02a68364e7db0928a85169190bae5c025376211067afa32292fd4"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise RuntimeError(f"Expected one insertion point; found {data.count(old)}")
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
        b"local qe_stage = 0;\r\n"
        b"local qe_last = \"none\";\r\n"
        b"qe_indicator.print(\"CHS STAGED PATCH\");\r\n"
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
        "if (::g_inputKeyboard.keyboardPressed() == KEYBOARD.F8 && qe_stage == 0) {",
        "::g_emu_task.setRomValue(8, 0x9ED, 0x00);",
        "::g_emu_task.setRomValue(8, 0x9F6, 0x00);",
        "::g_emu_task.setRomValue(8, 0xAB3, 0xB5);",
        "::g_emu_task.setRomValue(8, 0xAB4, 0x0A);",
        "qe_stage = 1;",
        "}",
        "if (::g_inputKeyboard.keyboardPressed() == KEYBOARD.F9 && qe_stage == 1) {",
        "::g_emu_task.setRomValue(8, 0x1E1, 0x07);",
        "::g_emu_task.setRomValue(8, 0x1E2, 0x0A);",
        "::g_emu_task.setRomValue(8, 0x1E7, 0x07);",
        "::g_emu_task.setRomValue(8, 0x1E8, 0x0A);",
        "::g_emu_task.setRomValue(8, 0x1F3, 0x07);",
        "::g_emu_task.setRomValue(8, 0x1F4, 0x0A);",
        "qe_stage = 2;",
        "}",
        "if (::g_inputKeyboard.keyboardPressed() == KEYBOARD.F10 && qe_stage == 2) {",
        "::g_emu_task.setRomValue(8, 0x4891, 0x05);",
        "::g_emu_task.setRomValue(8, 0x48A5, 0x05);",
        "::g_emu_task.setRomValue(8, 0x494A, 0x05);",
        "::g_emu_task.setRomValue(8, 0x4984, 0x18);",
        "::g_emu_task.setRomValue(8, 0x6B74, 0x4D);",
        "::g_emu_task.setRomValue(8, 0x48E3, 0x02);",
        "::g_emu_task.setRomValue(8, 0x66E1, 0x02);",
        "::g_emu_task.setRomValue(8, 0x66B7, 0x00);",
        "::g_emu_task.setRomValue(8, 0x4D5C, 0x04);",
        "qe_stage = 3;",
        "}",
        "local q = ::g_inputKeyboard.checkKeyboard(KEYBOARD.Q) ? 1 : 0;",
        "local e = ::g_inputKeyboard.checkKeyboard(KEYBOARD.E) ? 1 : 0;",
        "local l = (::g_input.key(KEY.L) == KEY.L) ? 1 : 0;",
        "local r = (::g_input.key(KEY.R) == KEY.R) ? 1 : 0;",
        "if (q || e || l || r) qe_last = format(\"Q%d E%d L%d R%d\", q, e, l, r);",
        "local a = ::g_emu_task.getRomValue(8, 0xAB3);",
        "local b = ::g_emu_task.getRomValue(8, 0x1E1);",
        "qe_indicator.print(format(\"CHS STAGE %d F8->1 F9->2 F10->3\\nQ%d E%d L%d R%d LAST %s\\nREAD AB3=%02x 1E1=%02x\", qe_stage, q, e, l, r, qe_last, a, b));",
        "wait(0);",
        "}",
        "::pause_main_close();",
    ]
    src = replace_once(src, marker, "\r\n".join(lines).encode("ascii"))
    script = OUT / "play_standalone.staged_probe.nut.m"
    script.write_bytes(src)
    candidate_bin = OUT / "alldata.staged_probe.bin"
    candidate_index = OUT / "alldata.staged_probe.psb.m"
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
