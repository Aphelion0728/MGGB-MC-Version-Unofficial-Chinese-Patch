"""Build a stock-ROM diagnostic archive that traces emulator input inside the game.

This never changes the installed game. Run it only against the verified stock
archive and index. The output contains the original ROM plus one instrumented
Squirrel resource: system/script/play_standalone.nut.m.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "CHS_Project" / "analysis" / "candidates" / "qe_emulator_trace"
BIN = ROOT / "windata" / "alldata.bin"
INDEX = ROOT / "windata" / "alldata.psb.m"
STOCK = HERE / "original_play_standalone.nut.m"
REPLACER = ROOT / "CHS_Project" / "source" / "PsbResourceReplace" / "bin" / "Release" / "net48" / "PsbResourceReplace.exe"
PREFIX = "25G/xpvTbsb+6"
NAME = "system/script/play_standalone.nut.m"

EXPECTED_BIN = "40feb4cb173d6271e29571a3135aaff58755ce7b9cd703bc46c7a95d34256e7b"
EXPECTED_INDEX = "caad671e13561d410f7e281cddaeadbe5fcfc880c63c068a5c041ddb3dac5400"
EXPECTED_STOCK_SCRIPT = "a3479681d9b02a68364e7db0928a85169190bae5c025376211067afa32292fd4"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def replace_once(data: bytes, old: bytes, new: bytes) -> bytes:
    if data.count(old) != 1:
        raise RuntimeError(f"Expected exactly one script insertion point; found {data.count(old)}")
    return data.replace(old, new, 1)


def main() -> None:
    for path, expected in ((BIN, EXPECTED_BIN), (INDEX, EXPECTED_INDEX), (STOCK, EXPECTED_STOCK_SCRIPT)):
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"Refusing to build from changed source: {path}: {actual}")

    OUT.mkdir(parents=True, exist_ok=True)
    source = STOCK.read_bytes()
    source = replace_once(
        source,
        b"while ( !game_exit ) {\r\n",
        b'local qe_diag_previous = "";\r\nwhile ( !game_exit ) {\r\n',
    )
    marker = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\nwait(0);\r\n}\r\n::pause_main_close();"
    )
    injected = (
        b"if ( !::isMasterBuild() ) {\r\n"
        b"::_play_standalone_gameloop_nomaster(::g_systemdata, ::g_emu_task, input);\r\n"
        b"}\r\n\r\n"
        b"if (System.getSpec() == \"win\") {\r\n"
        b"local diag_q = ::g_inputKeyboard.checkKeyboard(KEYBOARD.Q) ? 1 : 0;\r\n"
        b"local diag_e = ::g_inputKeyboard.checkKeyboard(KEYBOARD.E) ? 1 : 0;\r\n"
        b"local diag_kbl = ::g_inputKeyboard.key(KEY.L) ? 1 : 0;\r\n"
        b"local diag_kbr = ::g_inputKeyboard.key(KEY.R) ? 1 : 0;\r\n"
        b"local diag_padl = ::g_inputPad.key(KEY.L) ? 1 : 0;\r\n"
        b"local diag_padr = ::g_inputPad.key(KEY.R) ? 1 : 0;\r\n"
        b"local diag_emu = ::g_emu_task.getEmuKeyCurrentOn(0);\r\n"
        b"local diag_line = format(\"Q=%d E=%d keyboardL=%d keyboardR=%d padL=%d padR=%d emu=%08x\", "
        b"diag_q, diag_e, diag_kbl, diag_kbr, diag_padl, diag_padr, diag_emu);\r\n"
        b"if (diag_line != qe_diag_previous) {\r\n"
        b'printf("MGS_QE_DIAG %s\\n", diag_line);\r\n'
        b"qe_diag_previous = diag_line;\r\n"
        b"}\r\n"
        b"}\r\n\r\n"
        b"wait(0);\r\n}\r\n::pause_main_close();"
    )
    source = replace_once(source, marker, injected)
    trace_script = OUT / "play_standalone.trace.nut.m"
    trace_script.write_bytes(source)
    candidate_bin = OUT / "alldata.trace.bin"
    candidate_index = OUT / "alldata.trace.psb.m"
    subprocess.run(
        [str(REPLACER), "replace", str(trace_script), str(BIN), str(INDEX), PREFIX, NAME,
         str(candidate_bin), str(candidate_index)],
        check=True,
    )
    extracted = OUT / "play_standalone.roundtrip.nut.m"
    subprocess.run(
        [str(REPLACER), "extract", str(candidate_bin), str(candidate_index), PREFIX, NAME,
         str(extracted)],
        check=True,
    )
    if extracted.read_bytes() != source:
        raise RuntimeError("Trace script round-trip mismatch")
    print(f"Trace archive: {candidate_bin} ({sha256(candidate_bin)})")
    print(f"Trace index: {candidate_index} ({sha256(candidate_index)})")
    print(f"Instrumented script: {trace_script} ({sha256(trace_script)})")


if __name__ == "__main__":
    main()
