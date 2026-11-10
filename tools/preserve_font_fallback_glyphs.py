"""Keep legacy-only glyphs alongside the Alibaba bitmap font atlas."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / "working/notice_translation_v1"
NEW = WORK / "AlibabaPuHuiTi_font_verify"
OLD = WORK / "font_current_decoded"
OUT = WORK / "AlibabaPuHuiTi_complete"


def main() -> None:
    data = json.loads((NEW / "AlibabaPuHuiTi_notice_font.json").read_text(encoding="utf-8"))
    old = json.loads((OLD / "font_current.json").read_text(encoding="utf-8"))
    old_resx = json.loads((OLD / "font_current.resx.json").read_text(encoding="utf-8"))
    code = data["code"]
    fallback = sorted(set(old["code"]) - set(code))
    if len(fallback) != 14:
        raise RuntimeError(f"Unexpected legacy glyph fallback count: {len(fallback)}")

    out_sprite = OUT / "AlibabaPuHuiTi_complete.psb.m"
    out_sprite.mkdir(parents=True, exist_ok=True)
    new_resx = json.loads((NEW / "AlibabaPuHuiTi_notice_font.resx.json").read_text(encoding="utf-8"))
    new_atlas = NEW / new_resx["Resources"]["0"]
    shutil.copyfile(new_atlas, out_sprite / "[0]-[0].png")

    for source_index, old_source in enumerate(old["source"]):
        old_resource_index = int(old_source["pixel"].removeprefix("#resource#"))
        new_resource_index = source_index + 1
        data["source"].append({**old_source, "pixel": f"#resource#{new_resource_index}"})
        original_name = old_resx["Resources"][str(old_resource_index)]
        original_path = OLD / original_name
        dest_name = f"legacy_{source_index}.png"
        shutil.copyfile(original_path, out_sprite / dest_name)
        for char, entry in old["code"].items():
            if entry["id"] == source_index and char in fallback:
                fallback_entry = copy.deepcopy(entry)
                fallback_entry["id"] = source_index + 1
                code[char] = fallback_entry

    new_resx["Resources"] = {
        "0": "AlibabaPuHuiTi_complete.psb.m/[0]-[0].png",
        "1": "AlibabaPuHuiTi_complete.psb.m/legacy_0.png",
        "2": "AlibabaPuHuiTi_complete.psb.m/legacy_1.png",
    }
    (OUT / "AlibabaPuHuiTi_complete.psb.m.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "AlibabaPuHuiTi_complete.psb.m.resx.json").write_text(
        json.dumps(new_resx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if len(code) != len(old["code"]) + len(set(code) - set(old["code"])):
        raise RuntimeError("Unexpected merged font code map")
    print(f"Preserved {len(fallback)} legacy glyphs in two fallback atlas pages.")


if __name__ == "__main__":
    main()
