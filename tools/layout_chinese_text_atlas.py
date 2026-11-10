from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from psd_tools import PSDImage
from pypinyin import lazy_pinyin
import json


ROOT = Path(__file__).resolve().parents[2]
PSD_PATH = ROOT / "CHS_Project" / "Pic" / "启动器英文文字图集_原始分辨率.psd"
OUTPUT_PATH = ROOT / "CHS_Project" / "Pic" / "启动器中文文字图集_拼音排序_第四十三版.png"
LAYOUT_PATH = ROOT / "CHS_Project" / "Pic" / "启动器文字图集_第四十三版_槽位映射.json"
SPRITE_JSON = ROOT / "CHS_Project" / "outputs" / "launcher_text_all_languages" / "installed_verify" / "txt_en" / "txt_en.psb.m.json"
ENGLISH_REFERENCE_JSON = ROOT / "CHS_Project" / "outputs" / "launcher_text_all_languages" / "original_reference_en" / "txt_en.psb.m.json"
ENGLISH_REFERENCE_TEXTURE = ROOT / "CHS_Project" / "outputs" / "launcher_text_all_languages" / "original_reference_en" / "txt_en.psb" / "tex000.png"
ATLAS_WIDTH = 2048
ATLAS_HEIGHT = 2048
TEXT_X = 64
ROW_GAP = 10
ARROW_TO_TEXT_GAP = 46
# The PSD's actual “开” glyph raster is 21 px high. Use that exact visible
# glyph height as the baseline for every Chinese entry except arrow-label pairs.
TARGET_GLYPH_LINE_HEIGHT = 21
ARROW_TEXT_GLYPH_HEIGHT = 31
# Labels shown in the screenshots supplied on 2026-10-24. For these entries,
# use the corresponding original English sprite's cap-to-lowest-glyph height.
ENGLISH_REFERENCE_LABELS = {
    "游戏选择", "数字原声带", "选项", "法律与隐私", "退出游戏",
    "使用条款", "许可", "许可条款", "控制类型", "恢复默认设置", "主菜单音量",
    "游戏音量", "画面平滑", "游戏画面设置", "显示区域", "壁纸",
    "滤镜", "窗口模式", "简体中文", "法语", "意大利语", "德语",
    "西班牙语", "日语", "语言", "音频", "通知", "按键图标",
    "制作组", "音乐列表", "开始游戏", "说明书", "删除存档数据",
    "国际版", "日版",
}
STYLE_CROP_MARGIN = 12
PACK_MARGIN = 8
ARROW_ICON_IDS = {f"{icon_id:04d}" for icon_id in range(88, 96)}
# User-marked residue left in the erased-English raster layer: two nearly
# empty crops after the language prompt, plus the thin specks after the
# resolution-settings line.
# Residual raster-layer artifacts found during atlas review. Keep the Japanese
# and Spanish entries: the user explicitly requested those three crops.
DIRTY_PIXEL_ICON_IDS = {
    "0027", "0065", "0076", "0085", "0112", "0184",
    "0147", "0149", "0190", "0201",
} | {f"{icon_id:04d}" for icon_id in range(156, 175)}
LABEL_OVERRIDES = {
    "英语": "简体中文", "意语": "意大利语",
    "语言": "语言设置", "音频": "音频设置",
    "通知": "游戏通知", "制作组": "制作人员",
    "数字原声带": "原声音乐", "选项": "游戏选项",
    "法律与隐私": "法律隐私",
    "许可": "许可条款",
    "控制类型": "图标类型",
    "重置游戏。": "重置游戏",
    "返回主菜单。": "返回主菜单",
    "未保存的进度将会丢失": "未保存的进度将会丢失。",
    "游戏画面设置": "画面比例",
    "将设置恢复为默认参数。": "将本页设置全部恢复为默认设置。",
    "已分配的按键": "更改按键分配设置。",
    "更改“向后移动”的键盘按键分配": "更改“向后移动”的键盘按键分配。",
    "武器/道具选择键": "装备栏快捷键",
    "Codec": "通讯快捷键",
    "更改“武器/道具选择键”的键盘按键分配。": "更改“装备栏快捷键”的键盘按键分配。",
    "更改“Codec键”的键盘按键分配。": "更改“通讯快捷键”的键盘按键分配。",
    "更改“武器/道具选择键”的手柄按钮分配。": "更改“装备栏快捷键”的手柄按键分配。",
    "更改“Codec键”的手柄按钮分配。": "更改“通讯快捷键”的手柄按键分配。",
    "拳击/确认的手柄按钮分配。": "拳击/确认键",
    "壁纸": "背景壁纸",
    "滤镜": "游戏滤镜",
    "只有在游戏画面设置为像素适配时才能\n调整画面滤镜设置。": "只有在游戏画面设置为像素适配时才能调整画面滤镜设置。",
    "只有将游戏画面设置为标准或像素适配时，\n才能调整壁纸和显示区域。": "只有将游戏画面设置为标准或像素适配时，才能调整壁纸和显示区域。",
}
GROUP_LABEL_OVERRIDES = {
    ("黑", "画面"): "画面设置",
    ("蓝", "画面"): "画面设置",
    ("蓝", "返回主菜单。"): "退出游戏并返回主菜单。",
}


def translated_label(layer, source_label: str) -> str:
    return GROUP_LABEL_OVERRIDES.get(
        (layer.parent.name, source_label),
        LABEL_OVERRIDES.get(source_label, source_label),
    )


FONT_PATH = ROOT / "CHS_Project" / "reference_outputs" / "AlibabaPuHuiTi-3-55-Regular.otf"
CYAN_GLOW_RGB = (0, 155, 156)
CYAN_GLOW_OPACITY = 0.75
CYAN_GLOW_PSD_BLUR = 6
CYAN_GLOW_FILTER_RADIUS = 2
CYAN_GLOW_SPREAD = 1
CYAN_GLOW_CROP_MARGIN = 3
RASTER_TEXT_TRANSLATIONS = {
    "0080": "画面设置",
    "0141": "选择您想要的显示语言。",
    "0155": "更改游戏的分辨率设置。",
}
RASTER_TEXT_GLOW_IDS = {"0155"}
# Menu option labels share the same visible Chinese glyph height. Message and
# body text remain at their original reference sizes.
UNIFORM_MENU_GLYPH_HEIGHT = 24
UNIFORM_MENU_FRAME_HEIGHT = 30
OPTION_MENU_LABELS = {
    "语言设置", "画面设置", "音频设置", "游戏通知", "按键图标", "制作人员",
}
# One-atlas-pixel optical corrections compensate for the per-icon transforms
# visible in the 2560x1439 game captures. The common design size stays 24 px.
MENU_GLYPH_HEIGHT_OVERRIDES = {
    "画面设置": 25,
    "画面平滑": 23, "显示区域": 23, "游戏滤镜": 25,
    "主菜单音量": 25,
    "西班牙语": 25, "日版": 25,
    # Optical sizes measured from the 2560x1439 keyboard-list capture. These
    # render about 1–2 screen pixels taller than the neighboring 24px sprites.
    "向前移动": 23, "向后移动": 23, "向右移动": 23, "向左移动": 23,
    "拳击/确认键": 23, "武器/取消键": 23, "爬行键": 23,
    "恢复默认设置": 23, "装备栏快捷键": 23, "通讯快捷键": 23,
}
# The white "音频设置" sprite (0085) is shared by the launcher and pause
# menus. Its 24px core has visibly lighter/narrower ink than "画面设置" (0080).
# At 25px, both cover almost the same area while retaining a common left edge.
ICON_GLYPH_HEIGHT_OVERRIDES = {"0085": 25}
UNIFORM_MENU_LABELS = {
    "游戏选择", "数字原声带", "选项", "法律与隐私", "退出游戏",
    "原声音乐", "游戏选项", "法律隐私",
    "语言", "语言设置", "画面设置", "音频", "音频设置", "通知",
    "游戏通知", "按键图标", "制作组", "制作人员",
    "画面", "游戏画面", "画面比例", "背景壁纸", "游戏滤镜", "暂停菜单", "控制设置", "键盘设置", "手柄设置", "保存", "读取",
    "画面平滑", "游戏画面设置", "显示区域", "壁纸", "滤镜",
    "窗口模式", "恢复默认设置", "主菜单音量", "游戏音量",
    "控制类型", "图标类型", "国际版", "日版", "开始游戏", "说明书", "删除存档数据",
    "简体中文", "法语", "意大利语", "德语", "西班牙语", "日语", "使用条款", "许可条款", "音乐列表",
    "继续游戏", "重置游戏", "返回主菜单", "向前移动", "向后移动", "向右移动", "向左移动",
    "拳击/确认键", "武器/取消键", "爬行键", "菜单键", "武器/道具选择键", "装备栏快捷键", "Codec", "通讯快捷键",
}
RASTER_TEXT_TARGET_HEIGHTS = {"0080": UNIFORM_MENU_GLYPH_HEIGHT}
MULTILINE_VISIBLE_GAP = 6


def walk_text_layers(layers):
    for layer in layers:
        if not layer.visible:
            continue
        if layer.kind == "type":
            label = (layer.text or "").replace("\r", "\n").strip()
            if label:
                yield layer, label
        elif layer.is_group():
            yield from walk_text_layers(layer)


def pinyin_key(label: str):
    return (" ".join(lazy_pinyin(label)).casefold(), label.casefold())


def alpha_trim(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    return image.crop(bbox) if bbox else image


def center_in_fixed_height(image: Image.Image, target_height: int, label: str = "") -> Image.Image:
    """Center solid glyph ink with equal margins in an exact menu frame."""
    image = image.convert("RGBA")
    alpha = np.asarray(image.getchannel("A"))
    solid_rows = np.flatnonzero(np.any(alpha >= 128, axis=1))
    if not len(solid_rows):
        raise RuntimeError(f"Menu sprite has no visible ink: {label!r}")
    core_height = int(solid_rows[-1] - solid_rows[0] + 1)
    if core_height > target_height:
        raise RuntimeError(f"Menu glyph exceeds fixed frame for {label!r}: {core_height} > {target_height}")
    desired_top = int(solid_rows[0]) - (target_height - core_height) // 2
    source_top = max(0, desired_top)
    source_bottom = min(image.height, desired_top + target_height)
    dest_top = max(0, -desired_top)
    canvas = Image.new("RGBA", (image.width, target_height), (0, 0, 0, 0))
    canvas.alpha_composite(image.crop((0, source_top, image.width, source_bottom)), (0, dest_top))
    return canvas


def menu_frame_height(label: str) -> int:
    return UNIFORM_MENU_FRAME_HEIGHT


def target_glyph_height(record: dict) -> int:
    if record.get("label") in UNIFORM_MENU_LABELS:
        if record.get("reference_icon_id") in ICON_GLYPH_HEIGHT_OVERRIDES:
            return ICON_GLYPH_HEIGHT_OVERRIDES[record["reference_icon_id"]]
        return MENU_GLYPH_HEIGHT_OVERRIDES.get(record.get("label"), UNIFORM_MENU_GLYPH_HEIGHT)
    return int(record.get("english_reference_glyph_height") or TARGET_GLYPH_LINE_HEIGHT)


def render_replacement_text(label: str, target_height: int, color=(255, 255, 255)) -> Image.Image:
    """Render changed language labels with the font used by the PSD text layers."""
    font = ImageFont.truetype(str(FONT_PATH), 24)
    bbox = font.getbbox(label)
    mask = Image.new("L", (max(1, bbox[2] - bbox[0]), max(1, bbox[3] - bbox[1])), 0)
    ImageDraw.Draw(mask).text((-bbox[0], -bbox[1]), label, font=font, fill=255)
    mask = mask.crop(mask.getbbox()) if mask.getbbox() else mask
    result = Image.new("RGBA", mask.size, (*color, 0))
    result.putalpha(mask)
    return alpha_trim(resize_to_visible_height(result, target_height))


def add_cyan_outer_glow(image: Image.Image) -> Image.Image:
    """Recreate the PSD blue-group OuterGlow (75%, 6 px blur, ~1 px spread)."""
    image = image.convert("RGBA")
    # Pillow's GaussianBlur radius behaves like a sigma (about 3x the visual
    # falloff), so a 6 px Photoshop blur corresponds to roughly radius 2 here.
    padding = CYAN_GLOW_PSD_BLUR + CYAN_GLOW_SPREAD
    padded = Image.new("RGBA", (image.width + padding * 2, image.height + padding * 2), (0, 0, 0, 0))
    padded.alpha_composite(image, (padding, padding))
    alpha = padded.getchannel("A")
    if CYAN_GLOW_SPREAD:
        alpha = alpha.filter(ImageFilter.MaxFilter(CYAN_GLOW_SPREAD * 2 + 1))
    alpha = alpha.filter(ImageFilter.GaussianBlur(CYAN_GLOW_FILTER_RADIUS))
    glow_alpha = np.clip(np.rint(np.asarray(alpha, dtype=np.float32) * CYAN_GLOW_OPACITY), 0, 255).astype(np.uint8)
    glow = np.empty((padded.height, padded.width, 4), dtype=np.uint8)
    glow[:, :, :3] = CYAN_GLOW_RGB
    glow[:, :, 3] = glow_alpha
    result = Image.fromarray(glow, "RGBA")
    result.alpha_composite(padded)
    return result


def crop_glow_to_glyph_margin(glow: Image.Image, glyph: Image.Image, margin: int) -> Image.Image:
    """Keep exactly `margin` pixels of glow around the tight glyph bounds."""
    bbox = glyph.convert("RGBA").getchannel("A").getbbox()
    if not bbox:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    padding = CYAN_GLOW_PSD_BLUR + CYAN_GLOW_SPREAD
    x0 = max(0, padding + bbox[0] - margin)
    y0 = max(0, padding + bbox[1] - margin)
    x1 = min(glow.width, padding + bbox[2] + margin)
    y1 = min(glow.height, padding + bbox[3] + margin)
    return glow.crop((x0, y0, x1, y1))


def resize_alpha_preserving_source_colors(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize without pulling hidden white RGB from transparent pixels into edges."""
    image = image.convert("RGBA")
    if image.size == size:
        return image
    rgba = np.asarray(image)
    alpha_src = rgba[:, :, 3]
    visible = alpha_src > 0
    colors = np.unique(rgba[:, :, :3][visible], axis=0)
    alpha = Image.fromarray(alpha_src, "L").resize(size, Image.Resampling.LANCZOS)
    alpha_out = np.asarray(alpha)

    # PSD color-overlay text (including the black subgroup) has one visible
    # RGB color and alpha-only antialiasing. Keeping that RGB constant removes
    # the white fringe that nearest-neighbor RGB sampling introduced.
    if len(colors) == 1:
        out = np.empty((size[1], size[0], 4), dtype=np.uint8)
        out[:, :, :3] = colors[0]
        out[:, :, 3] = alpha_out
        return Image.fromarray(out, "RGBA")

    # For genuinely multicolored artwork, resample premultiplied channels so
    # transparent pixels cannot contribute their hidden RGB values.
    alpha_f = alpha_src.astype(np.float32) / 255.0
    channels = []
    for channel in range(3):
        premultiplied = rgba[:, :, channel].astype(np.float32) * alpha_f
        plane = Image.fromarray(premultiplied, "F").resize(size, Image.Resampling.LANCZOS)
        channels.append(np.asarray(plane, dtype=np.float32))
    alpha_resized = alpha_out.astype(np.float32)
    rgb_out = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    nonzero = alpha_resized > 0
    for channel, plane in enumerate(channels):
        unpremultiplied = np.zeros_like(plane)
        unpremultiplied[nonzero] = plane[nonzero] * 255.0 / alpha_resized[nonzero]
        rgb_out[:, :, channel] = np.clip(np.rint(unpremultiplied), 0, 255).astype(np.uint8)
    out = np.dstack((rgb_out, alpha_out))
    return Image.fromarray(out, "RGBA")


def visible_alpha_height(image: Image.Image, threshold: int = 128) -> int:
    """Measure the solid glyph core, excluding faint antialiasing fringes."""
    alpha = np.asarray(image.convert("RGBA").getchannel("A"))
    ys = np.flatnonzero(np.any(alpha >= threshold, axis=1))
    return int(ys[-1] - ys[0] + 1) if len(ys) else 0


def english_reference_metrics(layer_bbox, icons, english_atlas: Image.Image) -> tuple[str, int]:
    """Match a Chinese PSD layer to its original English sprite and measure its visible glyph span."""
    x0, y0, x1, y1 = layer_bbox
    layer_area = max(1, (x1 - x0) * (y1 - y0))
    scores = []
    for icon_id, info in icons.items():
        box = (
            round(info["left"]), round(info["top"]),
            round(info["left"] + info["width"]), round(info["top"] + info["height"]),
        )
        overlap = max(0, min(x1, box[2]) - max(x0, box[0])) * max(0, min(y1, box[3]) - max(y0, box[1]))
        scores.append((overlap, str(icon_id).zfill(4)))
    scores.sort(reverse=True)
    best_area = scores[0][0]
    if best_area / layer_area < 0.50:
        raise RuntimeError(f"Weak English-sprite match for PSD layer {layer_bbox}: {best_area / layer_area:.3f}")
    tied = [icon_id for overlap, icon_id in scores if overlap == best_area]
    if len(tied) != 1:
        raise RuntimeError(f"Ambiguous English-sprite match for PSD layer {layer_bbox}: {tied}")
    icon_id = tied[0]
    info = icons[icon_id]
    sprite = english_atlas.crop((
        round(info["left"]), round(info["top"]),
        round(info["left"] + info["width"]), round(info["top"] + info["height"]),
    ))
    glyph_height = visible_alpha_height(sprite)
    if glyph_height <= 0:
        raise RuntimeError(f"Original English sprite has no visible glyphs: icon {icon_id}")
    return icon_id, glyph_height


def english_reference_color(icon_id, icons, english_atlas: Image.Image):
    """Preserve the original sprite's ink color when replacing a PSD label."""
    if not icon_id or icon_id not in icons:
        return (255, 255, 255)
    info = icons[icon_id]
    sprite = english_atlas.crop((
        round(info["left"]), round(info["top"]),
        round(info["left"] + info["width"]), round(info["top"] + info["height"]),
    )).convert("RGBA")
    pixels = np.asarray(sprite)
    visible = pixels[pixels[:, :, 3] >= 128, :3]
    if not len(visible):
        return (255, 255, 255)
    median = np.median(visible, axis=0)
    return tuple(int(value) for value in median)


def resize_to_visible_height(image: Image.Image, target_height: int) -> Image.Image:
    """Choose the closest proportional raster whose solid glyph core is exact."""
    source = image.convert("RGBA")
    current = visible_alpha_height(source)
    if current <= 0 or current == target_height:
        return source
    ideal_scale = target_height / current
    center_height = round(source.height * ideal_scale)
    center_width = round(source.width * ideal_scale)
    candidates = []
    for output_height in range(max(1, center_height - 4), center_height + 5):
        scale = output_height / source.height
        proportional_width = round(source.width * scale)
        for output_width in range(max(1, min(center_width, proportional_width) - 4), max(center_width, proportional_width) + 5):
            result = resize_alpha_preserving_source_colors(source, (output_width, output_height))
            actual = visible_alpha_height(result)
            width_scale = output_width / source.width
            candidates.append((actual != target_height, abs(actual - target_height), abs(scale - ideal_scale), abs(width_scale - ideal_scale), result))
    return min(candidates, key=lambda item: item[:4])[4]


def normalize_text_lines(image: Image.Image, label: str, target_height: int) -> Image.Image:
    """Normalize each newline-delimited text line independently, retaining leading."""
    image = image.convert("RGBA")
    line_count = max(1, label.count("\n") + 1)
    if line_count == 1:
        result = resize_to_visible_height(image, target_height)
        if visible_alpha_height(result) != target_height:
            raise RuntimeError(f"Visible glyph height did not normalize: {label!r}")
        return result

    alpha = np.asarray(image.getchannel("A"))
    active_rows = np.flatnonzero(np.any(alpha >= 128, axis=1))
    if len(active_rows) < line_count:
        raise RuntimeError(f"Could not separate {line_count} text lines: {label!r}")

    # Split at the largest horizontal blank bands, which separate wrapped lines
    # while leaving disconnected strokes within each line together.
    gaps = [(int(active_rows[i + 1] - active_rows[i] - 1), i) for i in range(len(active_rows) - 1)]
    split_indices = sorted(i for _, i in sorted(gaps, reverse=True)[: line_count - 1])
    split_rows = sorted((int(active_rows[i]) + int(active_rows[i + 1])) // 2 + 1 for i in split_indices)
    boundaries = [0, *split_rows, image.height]

    line_images = []
    source_lefts = []
    source_heights = []
    for y0, y1 in zip(boundaries, boundaries[1:]):
        region = image.crop((0, y0, image.width, y1))
        bbox = region.getchannel("A").getbbox()
        if not bbox:
            continue
        region = region.crop(bbox)
        core = np.asarray(region.getchannel("A")) >= 128
        ys, xs = np.where(core)
        if not len(ys):
            continue
        source_lefts.append(bbox[0] + int(xs.min()))
        source_heights.append(int(ys.max() - ys.min() + 1))
        line_images.append(resize_to_visible_height(region, target_height))

    if len(line_images) != line_count:
        raise RuntimeError(f"Could not isolate all {line_count} text lines: {label!r}")

    average_scale = target_height / max(1, round(float(np.median(source_heights))))
    first_left = min(source_lefts)
    placements = []
    min_y = min_x = 0
    max_x = max_y = 0
    for index, line_image in enumerate(line_images):
        core = np.asarray(line_image.getchannel("A")) >= 128
        ys, xs = np.where(core)
        core_center = (int(ys.min()) + int(ys.max())) / 2
        # All multiline labels use the same visible interline gap. Preserve
        # their original horizontal alignment, but no longer inherit uneven
        # line leading from differently-sized PSD text layers.
        desired_center = target_height / 2 + index * (target_height + MULTILINE_VISIBLE_GAP)
        x = round((source_lefts[index] - first_left) * average_scale)
        y = round(desired_center - core_center)
        placements.append((line_image, x, y))
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x = max(max_x, x + line_image.width)
        max_y = max(max_y, y + line_image.height)

    canvas = Image.new("RGBA", (max(1, max_x - min_x), max(1, max_y - min_y)), (0, 0, 0, 0))
    for line_image, x, y in placements:
        canvas.alpha_composite(line_image, (x - min_x, y - min_y))
    result = alpha_trim(canvas)
    active = np.flatnonzero(np.any(np.asarray(result.getchannel("A")) >= 128, axis=1))
    gaps = np.diff(active) - 1
    split_indices = sorted(range(len(gaps)), key=lambda i: gaps[i], reverse=True)[: line_count - 1]
    split_rows = sorted((int(active[i]) + int(active[i + 1])) // 2 + 1 for i in split_indices)
    bounds = [0, *split_rows, result.height]
    measured = []
    result_alpha = np.asarray(result.getchannel("A"))
    for y0, y1 in zip(bounds, bounds[1:]):
        rows = np.flatnonzero(np.any(result_alpha[y0:y1] >= 128, axis=1))
        if len(rows):
            measured.append(len(rows))
    if measured != [target_height] * line_count:
        raise RuntimeError(f"Visible line heights {measured} != {[target_height] * line_count}: {label!r}")
    return result


def all_layers(psd: PSDImage):
    def visit(layers):
        for layer in layers:
            yield layer
            if layer.is_group():
                yield from visit(layer)
    return list(visit(psd))


def render_isolated(psd: PSDImage, layers, selected, include_visible_subtree=False):
    states = {id(layer): layer.visible for layer in layers}
    try:
        for layer in layers:
            layer.visible = False

        # Show only the selected layer and its ancestor groups.
        current = selected
        while current is not None and current is not psd:
            current.visible = True
            current = getattr(current, "parent", None)

        if include_visible_subtree:
            descendants = set()
            stack = [selected]
            while stack:
                item = stack.pop()
                descendants.add(id(item))
                if item.is_group():
                    stack.extend(list(item))
            for layer in layers:
                if id(layer) in descendants and states[id(layer)]:
                    layer.visible = True
        return psd.composite().convert("RGBA")
    finally:
        for layer in layers:
            layer.visible = states[id(layer)]


def expanded_bbox(bbox, margin, canvas_size):
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - margin),
        max(0, y0 - margin),
        min(canvas_size[0], x1 + margin),
        min(canvas_size[1], y1 + margin),
    )


def overlaps_with_margin(a, b, margin):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return (
        max(ax0 - margin, bx0 - margin) < min(ax1 + margin, bx1 + margin)
        and max(ay0 - margin, by0 - margin) < min(ay1 + margin, by1 + margin)
    )


def extract_styled_texts(psd: PSDImage, records, english_icons, english_atlas: Image.Image):
    """Render each color subgroup once, isolating only nearby overlapping labels."""
    layers = all_layers(psd)
    records_by_parent = {}
    for record in records:
        records_by_parent.setdefault(id(record["layer"].parent), []).append(record)

    for parent_id, group_records in records_by_parent.items():
        group = group_records[0]["layer"].parent
        # Only the cyan subgroup has an outer glow that extends beyond the
        # type-layer bounds. Other groups have no such effect, so avoid needlessly
        # isolating labels that merely sit near each other.
        style_margin = STYLE_CROP_MARGIN if group.name == "蓝" else 0
        rendered_group = render_isolated(psd, layers, group, include_visible_subtree=True)
        isolated_needed = set()
        for i, first in enumerate(group_records):
            for second in group_records[i + 1 :]:
                if overlaps_with_margin(first["bbox"], second["bbox"], style_margin):
                    isolated_needed.add(id(first))
                    isolated_needed.add(id(second))

        for record in group_records:
            target_height = target_glyph_height(record)
            if record["label"] != record["source_label"]:
                if group.name == "蓝":
                    color = (11, 211, 211)
                elif group.name == "黑":
                    color = (0, 0, 0)
                else:
                    color = english_reference_color(record.get("reference_icon_id"), english_icons, english_atlas)
                image = render_replacement_text(record["label"], target_height, color=color)
                if group.name == "蓝":
                    image = crop_glow_to_glyph_margin(
                        add_cyan_outer_glow(image), image, CYAN_GLOW_CROP_MARGIN
                    )
                record["image"] = image
                record["glyph_height_before"] = target_height
                record["glyph_height_after"] = target_height
                record["glyph_core_height_before"] = visible_alpha_height(record["image"])
                record["glyph_core_height_after"] = target_height
                continue
            if id(record) in isolated_needed:
                rendered = render_isolated(psd, layers, record["layer"])
            else:
                rendered = rendered_group
            crop_box = expanded_bbox(record["bbox"], style_margin, rendered.size)
            image = alpha_trim(rendered.crop(crop_box))

            # Measure the actual text raster, not its styled parent/group bounds.
            # This makes Chinese glyph size uniform even when PSD font sizes or
            # outer effects differ between entries.
            glyph = record["layer"].topil().convert("RGBA")
            glyph_bbox = glyph.getchannel("A").getbbox()
            glyph_height = (glyph_bbox[3] - glyph_bbox[1]) if glyph_bbox else image.height
            line_count = max(1, record["label"].count("\n") + 1)
            target_total_height = target_height * line_count
            source_core_height = visible_alpha_height(image)
            if source_core_height:
                image = normalize_text_lines(image, record["label"], target_height)
            if group.name == "蓝":
                glyph_image = image
                image = crop_glow_to_glyph_margin(
                    add_cyan_outer_glow(glyph_image), glyph_image, CYAN_GLOW_CROP_MARGIN
                )
            else:
                # Non-glow crops end exactly at the antialiased glyph alpha bbox.
                image = alpha_trim(image)
            record["glyph_height_before"] = glyph_height
            record["glyph_height_after"] = target_height
            record["glyph_core_height_before"] = source_core_height
            record["glyph_core_height_after"] = target_total_height
            record["image"] = image
        print(f"Rendered PSD styles: {group.name} ({len(group_records)} text layers)")


def run_components(mask: np.ndarray):
    """Return 8-connected component bounds using row runs (no OpenCV needed)."""
    parent: list[int] = []
    runs: list[tuple[int, int, int]] = []
    previous: list[int] = []

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a: int, b: int) -> None:
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a

    for y, row in enumerate(mask):
        xs = np.flatnonzero(row)
        if not len(xs):
            previous = []
            continue
        groups = np.split(xs, np.where(np.diff(xs) > 1)[0] + 1)
        current = []
        for group in groups:
            start, stop = int(group[0]), int(group[-1]) + 1
            idx = len(runs)
            runs.append((y, start, stop))
            parent.append(idx)
            current.append(idx)
            for prev_idx in previous:
                _, prev_start, prev_stop = runs[prev_idx]
                if prev_start <= stop and prev_stop >= start:
                    union(idx, prev_idx)
        previous = current

    components: dict[int, list[int]] = {}
    for idx, (y, x0, x1) in enumerate(runs):
        root = find(idx)
        comp = components.setdefault(root, [y, x0, y + 1, x1, 0])
        comp[0] = min(comp[0], y)
        comp[1] = min(comp[1], x0)
        comp[2] = max(comp[2], y + 1)
        comp[3] = max(comp[3], x1)
        comp[4] += x1 - x0
    return components.values()


def extract_arrow_components(psd: PSDImage):
    # The chevron is part of the original raster layer. Use a color-connected
    # component mask only to locate its bounds, then copy untouched source pixels.
    source_layer = next(layer for layer in psd if layer.name == "英文 删除")
    source = source_layer.topil().convert("RGBA")
    pixels = np.asarray(source)
    teal = (
        (pixels[:, :, 0] < 80)
        & (pixels[:, :, 1] > 80)
        & (pixels[:, :, 2] > 80)
        & (pixels[:, :, 3] > 40)
    )
    arrows = []
    y_offset = source_layer.bbox[1]
    for y0, x0, y1, x1, area in run_components(teal):
        width, height = x1 - x0, y1 - y0
        if 17 <= width <= 25 and 27 <= height <= 36 and 260 <= area <= 450:
            # Retain a 2 px transparent safety margin around antialiased edges.
            left, top = max(0, x0 - 2), max(0, y0 - 2)
            right, bottom = min(source.width, x1 + 2), min(source.height, y1 + 2)
            arrows.append(
                {
                    "canvas_bbox": (x0, y0 + y_offset, x1, y1 + y_offset),
                    "image": alpha_trim(source.crop((left, top, right, bottom))),
                }
            )
    return arrows


def extract_english_tiles(psd: PSDImage):
    """Extract untouched residual English/icon crops using the game's crop table."""
    crop_data = json.loads(SPRITE_JSON.read_text(encoding="utf-8"))
    icons = crop_data["source"]["tex"]["icon"]
    source_layer = next(layer for layer in psd if layer.name == "英文 删除")
    source = source_layer.topil().convert("RGBA")
    y_offset = source_layer.bbox[1]
    tiles = []
    for icon_id, info in sorted(icons.items(), key=lambda pair: int(pair[0])):
        # Exclude paired chevron duplicates and the user-marked residual pixels.
        if str(icon_id).zfill(4) in ARROW_ICON_IDS | DIRTY_PIXEL_ICON_IDS:
            continue
        x = round(info["left"])
        y = round(info["top"]) - y_offset
        width = round(info["width"])
        height = round(info["height"])
        crop = source.crop((x, y, x + width, y + height))
        bbox = crop.getchannel("A").getbbox()
        if bbox:
            crop = crop.crop(bbox)
            label = None
            if str(icon_id).zfill(4) == "0072":
                label = "通讯快捷键"
                glyph_height = MENU_GLYPH_HEIGHT_OVERRIDES[label]
                crop = center_in_fixed_height(
                    resize_to_visible_height(crop, glyph_height),
                    UNIFORM_MENU_FRAME_HEIGHT,
                    label,
                )
            if str(icon_id).zfill(4) in RASTER_TEXT_TRANSLATIONS:
                label = RASTER_TEXT_TRANSLATIONS[str(icon_id).zfill(4)]
                reference_crop = Image.open(ENGLISH_REFERENCE_TEXTURE).convert("RGBA").crop((
                    round(info["left"]), round(info["top"]),
                    round(info["left"] + info["width"]), round(info["top"] + info["height"]),
                ))
                reference_crop = alpha_trim(reference_crop)
                glyph_height = RASTER_TEXT_TARGET_HEIGHTS.get(
                    str(icon_id).zfill(4), visible_alpha_height(reference_crop)
                )
                opaque = np.asarray(reference_crop.convert("RGBA"))
                visible_colors = opaque[:, :, :3][opaque[:, :, 3] > 0]
                color = tuple(int(value) for value in np.median(visible_colors, axis=0)) if len(visible_colors) else (255, 255, 255)
                crop = render_replacement_text(label, glyph_height, color=color)
                if str(icon_id).zfill(4) in RASTER_TEXT_GLOW_IDS:
                    crop = crop_glow_to_glyph_margin(
                        add_cyan_outer_glow(crop), crop, CYAN_GLOW_CROP_MARGIN
                    )
                if label in UNIFORM_MENU_LABELS:
                    crop = center_in_fixed_height(crop, menu_frame_height(label), label)
            tiles.append(
                {
                    "kind": "english_raster",
                    "source_icon_id": icon_id,
                    "source_bbox": [x + bbox[0], y + y_offset + bbox[1], x + bbox[2], y + y_offset + bbox[3]],
                    "label": label,
                    "english_reference_glyph_height": glyph_height if label else None,
                    "image": crop,
                }
            )
    return tiles


def overlap_ratio(a, b):
    overlap = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return overlap / max(1, min(a[3] - a[1], b[3] - b[1]))


def pair_arrows(arrows, records):
    paired: dict[int, Image.Image] = {}
    for arrow in arrows:
        ax0, ay0, ax1, ay1 = arrow["canvas_bbox"]
        candidates = []
        for index, record in enumerate(records):
            x0, y0, x1, y1 = record["bbox"]
            gap = x0 - ax1
            vertical_match = overlap_ratio((ax0, ay0, ax1, ay1), (x0, y0, x1, y1))
            if 0 <= gap <= 60 and vertical_match >= 0.70:
                vertical_delta = abs((ay0 + ay1) / 2 - (y0 + y1) / 2)
                candidates.append((gap + vertical_delta * 0.25, index))
        if candidates:
            _, index = min(candidates)
            paired[index] = arrow["image"]
    return paired


def main():
    psd = PSDImage.open(PSD_PATH)
    english_json = json.loads(ENGLISH_REFERENCE_JSON.read_text(encoding="utf-8"))
    english_icons = english_json["source"]["tex"]["icon"]
    english_atlas = Image.open(ENGLISH_REFERENCE_TEXTURE).convert("RGBA")
    records = []
    for source_order, (layer, label) in enumerate(walk_text_layers(psd)):
        records.append(
            {
                "label": label,
                "source_label": label,
                "layer": layer,
                "bbox": tuple(layer.bbox),
                "source_order": source_order,
            }
        )

    for record in records:
        record["label"] = translated_label(record["layer"], record["source_label"])
        # Match using the original PSD label before any Chinese wording override;
        # e.g. “语言” must still resolve to its black English header sprite.
        if (record["source_label"] in ENGLISH_REFERENCE_LABELS
                or record["label"] in ENGLISH_REFERENCE_LABELS):
            icon_id, height = english_reference_metrics(record["bbox"], english_icons, english_atlas)
            record["reference_icon_id"] = icon_id
            record["english_reference_glyph_height"] = height
        else:
            record["reference_icon_id"] = None
            record["english_reference_glyph_height"] = TARGET_GLYPH_LINE_HEIGHT

    extract_styled_texts(psd, records, english_icons, english_atlas)
    arrows = extract_arrow_components(psd)
    paired = pair_arrows(arrows, records)

    # Stable pinyin ordering; duplicate labels retain their original order.
    order = sorted(range(len(records)), key=lambda i: (*pinyin_key(records[i]["label"]), records[i]["source_order"]))
    items = []
    for index in order:
        record = records[index]
        text_image = record["image"]
        arrow = paired.get(index)
        if arrow:
            # Keep the old chevron-height treatment for other entries, but let
            # screenshot labels follow their measured English glyph height.
            arrow_text_height = target_glyph_height(record)
            if record["label"] in UNIFORM_MENU_LABELS:
                arrow = resize_to_visible_height(arrow, UNIFORM_MENU_GLYPH_HEIGHT)
            if (record["label"] not in ENGLISH_REFERENCE_LABELS
                    and record["label"] not in UNIFORM_MENU_LABELS):
                factor = ARROW_TEXT_GLYPH_HEIGHT / max(1, arrow_text_height)
                target_size = (
                    max(1, round(text_image.width * factor)),
                    max(1, round(text_image.height * factor)),
                )
                text_image = resize_alpha_preserving_source_colors(text_image, target_size)
                arrow_text_height = ARROW_TEXT_GLYPH_HEIGHT
            combined = Image.new(
                "RGBA",
                (arrow.width + ARROW_TO_TEXT_GAP + text_image.width, max(arrow.height, text_image.height)),
                (0, 0, 0, 0),
            )
            arrow_y = (combined.height - arrow.height) // 2
            text_x = arrow.width + ARROW_TO_TEXT_GAP
            text_y = (combined.height - text_image.height) // 2
            combined.alpha_composite(arrow, (0, arrow_y))
            combined.alpha_composite(text_image, (text_x, text_y))
            text_image = alpha_trim(combined)
        if record["label"] in UNIFORM_MENU_LABELS:
            # The arrow/text composite can gain 1–2 solid rows even when each
            # component was normalized separately. Normalize the final sprite
            # to its screenshot-calibrated target, including optical overrides.
            optical_height = target_glyph_height(record)
            if visible_alpha_height(text_image) != optical_height:
                text_image = resize_to_visible_height(text_image, optical_height)
            if visible_alpha_height(text_image) != optical_height:
                raise RuntimeError(f"Menu glyph height did not normalize: {record['label']!r}")
            text_image = center_in_fixed_height(text_image, menu_frame_height(record["label"]), record["label"])
        items.append(
            {
                "kind": "chinese_text",
                "label": record["label"],
                "source_layer": record["layer"].name,
                "reference_icon_id": record.get("reference_icon_id"),
                "english_reference_glyph_height": record.get("english_reference_glyph_height"),
                "glyph_height_before": record["glyph_height_before"],
                "glyph_height_after": arrow_text_height if arrow else target_glyph_height(record),
                "glyph_core_height_before": record["glyph_core_height_before"],
                "glyph_core_height_after": (
                    arrow_text_height * max(1, record["label"].count("\n") + 1)
                    if arrow else record["glyph_core_height_after"]
                ),
                "image": text_image,
            }
        )

    english_tiles = extract_english_tiles(psd)
    items.extend(english_tiles)
    atlas = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    mapping = []
    x = PACK_MARGIN
    y = PACK_MARGIN
    row_height = 0
    for item in items:
        image = item["image"]
        if image.width + PACK_MARGIN * 2 > ATLAS_WIDTH or image.height + PACK_MARGIN * 2 > ATLAS_HEIGHT:
            raise RuntimeError(f"Sprite does not fit 2048x2048 slot: {item.get('label', item.get('source_icon_id'))} {image.size}")
        if x + image.width + PACK_MARGIN > ATLAS_WIDTH:
            x = PACK_MARGIN
            y += row_height + ROW_GAP
            row_height = 0
        if y + image.height + PACK_MARGIN > ATLAS_HEIGHT:
            raise RuntimeError(
                f"2048x2048 packing overflow at item {len(mapping) + 1}/{len(items)}; "
                f"last item={item.get('label', item.get('source_icon_id'))}, y={y}, height={image.height}"
            )
        atlas.alpha_composite(image, (x, y))
        mapping.append(
            {
                "kind": item["kind"],
                "label": item.get("label"),
                "source_layer": item.get("source_layer"),
                "source_group": item.get("source_group"),
                "source_icon_id": item.get("source_icon_id"),
                "source_bbox": item.get("source_bbox"),
                "destination_bbox": [x, y, x + image.width, y + image.height],
                "size": [image.width, image.height],
                "reference_icon_id": item.get("reference_icon_id"),
                "english_reference_glyph_height": item.get("english_reference_glyph_height"),
                "glyph_height_before": item.get("glyph_height_before"),
                "glyph_height_after": item.get("glyph_height_after"),
                "glyph_core_height_before": item.get("glyph_core_height_before"),
                "glyph_core_height_after": item.get("glyph_core_height_after"),
            }
        )
        x += image.width + PACK_MARGIN
        row_height = max(row_height, image.height)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUTPUT_PATH, optimize=True)
    LAYOUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {OUTPUT_PATH}")
    print(f"canvas: {atlas.width}x{atlas.height}")
    print(f"text entries: {len(records)}")
    print(f"arrow-text pairs: {len(paired)}")
    print(f"retained English raster crops: {len(english_tiles)} (unaltered pixels)")
    print(f"packed items: {len(mapping)}/{len(items)}")
    print(f"mapping: {LAYOUT_PATH}")
    for index in sorted(paired, key=lambda i: pinyin_key(records[i]["label"])):
        print(f"arrow: {records[index]['label']}")


if __name__ == "__main__":
    main()

