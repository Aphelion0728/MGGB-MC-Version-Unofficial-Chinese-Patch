"""Append only the Chinese glyphs needed by the translated notice dialogs.

The English notice renderer loads title_sansserif_medium65_24pt.psb. Its original
bitmap font has no simplified-Chinese coverage. Preserve all existing glyphs
and pixels; extend only its second A8 page into unused rows.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "working/notice_translation_v1"
BASE = WORK / "font_current_decoded"
OUT = WORK / "font_extended"
FONT = Path("C:/Windows/Fonts/NotoSansSC-VF.ttf")
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


def render_glyph(char: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    scratch = Image.new("L", (64, 64), 0)
    draw = ImageDraw.Draw(scratch)
    box = draw.textbbox((0, 0), char, font=font)
    draw.text((-box[0], -box[1]), char, fill=255, font=font)
    ink = scratch.crop(scratch.getbbox())
    # The existing CJK ink occupies 13x17 inside a 23x17 advance cell.
    ink = ink.resize((13, 17), Image.Resampling.LANCZOS)
    return Image.merge("RGBA", (Image.new("L", ink.size, 255),) * 3 + (ink,))


def main() -> None:
    notice = json.loads((WORK / "notice.psb.m.json").read_text(encoding="utf-8"))
    data = json.loads((BASE / "font_current.json").read_text(encoding="utf-8"))
    code = data["code"]
    wanted = {c for key in NOTICE_KEYS for c in notice["message"][key]["eng"][0]
              if not c.isspace()}
    missing = sorted(wanted - code.keys())
    if len(missing) != 26 or not FONT.is_file():
        raise RuntimeError(f"Unexpected missing glyph set or font: {missing}")

    sprite_dir = OUT / "font_extended.psb.m"
    sprite_dir.mkdir(parents=True, exist_ok=True)
    first = Image.open(BASE / "font_current/[0]-[0].png").convert("RGBA")
    second = Image.open(BASE / "font_current/[1]-[1].png").convert("RGBA")
    if first.size != (512, 512) or second.size != (512, 256):
        raise RuntimeError("Unexpected source font atlas dimensions")
    extended = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    extended.alpha_composite(second, (0, 0))
    font = ImageFont.truetype(str(FONT), 22)
    template = copy.deepcopy(code["定"])
    if (template["id"], template["w"], template["h"]) != (1, 23.0, 17):
        raise RuntimeError("Unexpected font metrics")

    for n, char in enumerate(missing):
        x, y = 1 + n % 20 * 25, 234 + n // 20 * 20
        extended.alpha_composite(render_glyph(char, font), (x, y))
        item = copy.deepcopy(template)
        item.update(x=float(x), y=y)
        code[char] = item

    data["source"][1]["height"] = 512
    data["source"][1]["truncated_height"] = 512
    (sprite_dir / "[0]-[0].png").write_bytes((BASE / "font_current/[0]-[0].png").read_bytes())
    extended.save(sprite_dir / "[1]-[1].png")
    (OUT / "font_extended.psb.m.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resx = json.loads((BASE / "font_current.resx.json").read_text(encoding="utf-8"))
    resx["Resources"] = {
        "0": "font_extended.psb.m/[1]-[1].png",
        "1": "font_extended.psb.m/[0]-[0].png",
    }
    (OUT / "font_extended.psb.m.resx.json").write_text(
        json.dumps(resx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Added {len(missing)} glyphs: {''.join(missing)}")


if __name__ == "__main__":
    main()
