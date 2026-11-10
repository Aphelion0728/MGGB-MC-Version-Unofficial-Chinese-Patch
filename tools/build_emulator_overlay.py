"""Build a stock-ROM diagnostic overlay for the emulator input pipeline.

The diagnostic reads Squirrel input objects and EmuTaskBase's virtual-key mask.
It draws the values in-game, avoiding the release build's disabled print sink.
The game installation is not changed by this builder.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_emulator_overlay"
BIN = ROOT / "windata" / "alldata.bin"
INDEX = ROOT / "windata" / "alldata.psb.m"
STOCK = HERE / "original_play_standalone.nut.m"
REPLACER = ROOT / "CHS_Project" / "source" / "PsbResourceReplace" / "bin" / "Release" / "net48" / "PsbResourceReplace.exe"
PREFIX = "25G/xpvTbsb+6"
NAME = "system/script/play_standalone.nut.m"

EXPECTED_BIN = "40feb4cb173d6271e29571a3135aaff58755ce7b9cd703bc46c7a95d34256e7b"
EXPECTED_INDEX = "caad671e13561d410f7e281cddaeadbe5fcfc880c63c068a5c041ddb3dac5400"
EXPECTED_SCRIPT = "a3479681d9b02a68364e7db0928a85169190bae5c025376211067afa32292fd4"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one insertion point, got {count}")
    return source.replace(old, new, 1)


def main() -> None:
    for path, expected in ((BIN, EXPECTED_BIN), (INDEX, EXPECTED_INDEX), (STOCK, EXPECTED_SCRIPT)):
        if sha(path) != expected:
            raise RuntimeError(f"Source hash mismatch: {path}: {sha(path)}")
    OUT.mkdir(parents=True, exist_ok=True)
    source = STOCK.read_bytes()
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
        b"qe_indicator.print(\"EMU DIAG ACTIVE\");\r\n"
    )
    source = replace_once(source, anchor, anchor + setup)
    marker = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\nwait(0);\r\n}\r\n::pause_main_close();"
    )
    injection = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\n"
        b"local qe_q = ::g_inputKeyboard.checkKeyboard(KEYBOARD.Q) ? 1 : 0;\r\n"
        b"local qe_e = ::g_inputKeyboard.checkKeyboard(KEYBOARD.E) ? 1 : 0;\r\n"
        b"local qe_l = (::g_input.key(KEY.L) == KEY.L) ? 1 : 0;\r\n"
        b"local qe_r = (::g_input.key(KEY.R) == KEY.R) ? 1 : 0;\r\n"
        b"local qe_pad_l = (::g_inputPad.key(KEY.L) == KEY.L) ? 1 : 0;\r\n"
        b"local qe_pad_r = (::g_inputPad.key(KEY.R) == KEY.R) ? 1 : 0;\r\n"
        b"local qe_virt = ::g_emu_task.getEmuKeyCurrentOn(0);\r\n"
        b"if (qe_q || qe_e || qe_l || qe_r || qe_pad_l || qe_pad_r || qe_virt) {\r\n"
        b"qe_last = format(\"Q%d E%d L%d R%d PL%d PR%d V%08x\", qe_q, qe_e, qe_l, qe_r, qe_pad_l, qe_pad_r, qe_virt);\r\n"
        b"}\r\n"
        b"qe_indicator.print(format(\"EMU DIAG  Q%d E%d L%d R%d PL%d PR%d V%08x\\nLAST %s\", qe_q, qe_e, qe_l, qe_r, qe_pad_l, qe_pad_r, qe_virt, qe_last));\r\n"
        b"wait(0);\r\n}\r\n::pause_main_close();"
    )
    source = replace_once(source, marker, injection)
    script = OUT / "play_standalone.overlay.nut.m"
    script.write_bytes(source)
    candidate_bin = OUT / "alldata.overlay.bin"
    candidate_index = OUT / "alldata.overlay.psb.m"
    subprocess.run([str(REPLACER), "replace", str(script), str(BIN), str(INDEX), PREFIX, NAME,
                    str(candidate_bin), str(candidate_index)], check=True)
    extracted = OUT / "play_standalone.roundtrip.nut.m"
    subprocess.run([str(REPLACER), "extract", str(candidate_bin), str(candidate_index), PREFIX, NAME,
                    str(extracted)], check=True)
    if extracted.read_bytes() != source:
        raise RuntimeError("Roundtrip verification failed")
    print(f"bin {candidate_bin} {sha(candidate_bin)}")
    print(f"index {candidate_index} {sha(candidate_index)}")
    print(f"script {script} {sha(script)}")


if __name__ == "__main__":
    main()
