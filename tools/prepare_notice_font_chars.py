"""Prepare a complete character list for rebuilding the English notice font."""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.ttLib import TTFont


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "working/notice_translation_v1"
BASE_FONT_JSON = WORK / "font_current_decoded/font_current.json"
NOTICE_JSON = WORK / "notice.psb.m.json"
OUT = WORK / "AlibabaPuHuiTi_notice_chars.txt"
NOTICE_KEYS = (
    "NoticeMsg__ASK_CLOSE_SOUNDTRACK",
    "NoticeMsg__COMMON_SL_BACK",
    "NoticeMsg__COMMON_SL_END",
    "NoticeMsg__COMMON_SL_NO",
    "NoticeMsg__COMMON_SL_YES",
    "NoticeMsg__EXIT_APPLICATION",
    "NoticeMsg__EXIT_TITLE",
    "NoticeMsg__SAVE_RESET_CONFIRM",
    "NoticeMsg__SAVE_RESET_CONFIRM_CANCEL",
    "NoticeMsg__SAVE_RESET_CONFIRM_DELETE",
)


def main() -> None:
    font = json.loads(BASE_FONT_JSON.read_text(encoding="utf-8"))
    notice = json.loads(NOTICE_JSON.read_text(encoding="utf-8"))
    otf = TTFont(str(PROJECT / "font/AlibabaPuHuiTi-3-65-Medium.otf"))
    cmap = set().union(*(table.cmap.keys() for table in otf["cmap"].tables))
    seen: set[str] = set()
    chars: list[str] = []
    unsupported = []
    for char in font["code"]:
        if char not in "\r\n\t" and char not in seen and ord(char) in cmap:
            chars.append(char)
            seen.add(char)
        elif char not in "\r\n\t" and ord(char) not in cmap:
            unsupported.append(char)
    for key in NOTICE_KEYS:
        for char in notice["message"][key]["eng"][0]:
            if char not in "\r\n\t" and char not in seen:
                if ord(char) not in cmap:
                    raise RuntimeError(f"Alibaba font lacks required notice glyph U+{ord(char):04X}")
                chars.append(char)
                seen.add(char)
    OUT.write_text("".join(chars), encoding="utf-8")
    print(f"Prepared {len(chars)} glyphs; omitted {len(unsupported)} unsupported legacy glyphs.")


if __name__ == "__main__":
    main()
