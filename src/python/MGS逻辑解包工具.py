#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MGS_BC2 逻辑资源解包工具（独立 GUI）。"""
from __future__ import annotations

import datetime
import json
import mmap
import os
import shutil
import struct
import sys
import threading
import tkinter as tk
import zlib
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ALIGN = 0x800
ROM_KEY = bytes.fromhex(
    "1124fa5f5ab36ae83cc359efd477b06309d5c1c63fdc75ad474fdc5424f753ed"
    "16fa23d1e91eeeb02dac32b6d67cd2b7a6ff601a53c40a3cc16989ffcfc54643"
)
MAGICS = {
    b"PSB\0": "PSB",
    b"RIFF": "RIFF/WAV",
    b"OggS": "Ogg",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"DDS ": "DDS",
}


def scan_mdf(path: Path):
    entries = []
    with path.open("rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        offsets = [o for o in range(0, len(mm) - 7, ALIGN) if mm[o:o + 4] == b"mdf\0"]
        for n, off in enumerate(offsets):
            end = offsets[n + 1] if n + 1 < len(offsets) else len(mm)
            span = end - off
            if span >= 8 and span % ALIGN == 0:
                size = struct.unpack_from("<I", mm, off + 4)[0]
                entries.append((len(entries), off, span, size))
    return entries


def xor_cycle(data: bytes, key: bytes) -> bytes:
    return bytes(v ^ key[i % len(key)] for i, v in enumerate(data))


def decode_rom(payload: bytes, expected: int) -> bytes:
    obj = zlib.decompressobj()
    out = obj.decompress(xor_cycle(payload, ROM_KEY))
    if not obj.eof or len(out) != expected:
        raise ValueError("第 230 块 GBC ROM 解码失败")
    return out


def resource_names(data: bytes) -> list[str]:
    result = []
    for raw in data.split(b"\0"):
        if not 3 <= len(raw) <= 260 or not all(32 <= c < 127 for c in raw):
            continue
        text = raw.decode("ascii")
        if ("/" in text or "\\" in text or ".wav" in text.lower()
                or text in {"sound_archive", "none", "win"}) and text not in result:
            result.append(text)
    return result


def sound_descriptors(data: bytes) -> list[dict]:
    result = []
    for off in range(0, min(len(data), 0x10000) - 16, 4):
        codec, rate, size, location = struct.unpack_from("<4I", data, off)
        if codec not in (0x20001, 0x20002) or not (8000 <= rate <= 96000):
            continue
        if not (4096 < size < len(data)):
            continue
        base = location & 0xFFFF0000
        if base >= len(data):
            continue
        result.append({"record_offset": off, "codec": codec,
                       "sample_rate": rate, "size": size,
                       "location": location, "data_offset": base})
    return result


def logical_unpack(root: Path, progress):
    src = root / "windata" / "alldata.bin"
    if not src.is_file():
        raise FileNotFoundError(src)
    out = root / "Extracted" / "alldata.bin"
    out.mkdir(parents=True, exist_ok=True)
    entries = scan_mdf(src)
    # 确保逻辑解包可以独立运行：先生成块级文件和 GBC ROM。
    with src.open("rb") as f:
        for pos, (idx, off, span, size) in enumerate(entries, 1):
            f.seek(off)
            block = f.read(span)
            if idx == 230 and size == 0x400000:
                (out / "block_230.gbc").write_bytes(decode_rom(block[8:], size))
            else:
                (out / f"block_{idx:03d}.mdf").write_bytes(block)
            progress(25 * pos / len(entries), f"读取 MDF 块：{pos}/{len(entries)}")

    logical = out / "Logical"
    psb_dir = logical / "PSB"
    sound_dir = logical / "Sound"
    psb_dir.mkdir(parents=True, exist_ok=True)
    sound_dir.mkdir(parents=True, exist_ok=True)
    bundles = []
    raw_blocks = sorted(out.glob("block_*.mdf"))
    for bi, block_path in enumerate(raw_blocks, 1):
        data = block_path.read_bytes()
        positions = []
        cursor = 0
        while True:
            cursor = data.find(b"PSB\0", cursor)
            if cursor < 0:
                break
            positions.append(cursor)
            cursor += 1
        for n, start in enumerate(positions):
            end = positions[n + 1] if n + 1 < len(positions) else len(data)
            bundle = data[start:end]
            out_path = psb_dir / f"{block_path.stem}_psb_{n:03d}.bundle"
            out_path.write_bytes(bundle)
            names = resource_names(bundle)
            out_path.with_suffix(".names.txt").write_text("\n".join(names), encoding="utf-8")
            desc = sound_descriptors(bundle)
            out_path.with_suffix(".sound.json").write_text(
                json.dumps(desc, ensure_ascii=False, indent=2), encoding="utf-8")
            # codec=0x20001 的独立音频流可安全切出，但不冒充标准 WAV。
            independent = [d for d in desc if d["codec"] == 0x20001]
            wav_names = [x for x in names if x.lower().endswith(".wav")]
            named = len(independent) == len(wav_names)
            for si, item in enumerate(independent):
                begin = item["data_offset"]
                finish = begin + item["size"]
                if finish > len(bundle):
                    continue
                label = Path(wav_names[si]).name if named else f"stream_{si:02d}"
                (sound_dir / f"{block_path.stem}_psb_{n:03d}_{label}.m2snd").write_bytes(
                    bundle[begin:finish])
            bundles.append({"source": block_path.name, "offset": start,
                            "length": len(bundle),
                            "output": str(out_path.relative_to(out)),
                            "names": names, "sound_descriptors": desc})
        progress(25 + 75 * bi / max(1, len(raw_blocks)), f"解析 PSB：{bi}/{len(raw_blocks)}")

    report = {"format": "MGS_BC2 logical resources", "block_count": len(entries),
              "rom": "block_230.gbc", "psb_bundles": bundles}
    (out / "logical_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out / "block_230.gbc", len(bundles)


class App:
    def __init__(self, window):
        self.window = window
        window.title("MGS_BC2 逻辑解包工具")
        window.geometry("760x360")
        base = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        self.address = tk.StringVar(value=str(base))
        self.status = tk.StringVar(value="请选择游戏根目录")
        self.progress = tk.DoubleVar(value=0)
        self.build_ui()

    def build_ui(self):
        frm = ttk.Frame(self.window, padding=16)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="游戏根目录：").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.address).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(frm, text="浏览…", command=self.browse).grid(row=0, column=2)
        ttk.Button(frm, text="开始逻辑解包", command=self.start).grid(row=1, column=0, columnspan=3, pady=20)
        ttk.Progressbar(frm, variable=self.progress, maximum=100).grid(row=2, column=0, columnspan=3, sticky="ew")
        ttk.Label(frm, textvariable=self.status, wraplength=700).grid(row=3, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Label(frm, text="ROM 输出：Extracted\\alldata.bin\\block_230.gbc\nPSB/音频：Extracted\\alldata.bin\\Logical\\").grid(row=4, column=0, columnspan=3, sticky="w")
        frm.columnconfigure(1, weight=1)

    def browse(self):
        chosen = filedialog.askdirectory(title="选择 MGS_BC2 游戏根目录")
        if chosen:
            self.address.set(chosen)

    def start(self):
        root = Path(self.address.get()).expanduser()
        if not (root / "windata" / "alldata.bin").is_file():
            messagebox.showerror("路径错误", "所选目录中没有 windata\\alldata.bin")
            return
        self.progress.set(0)
        self.status.set("正在解包，请稍候…")
        threading.Thread(target=self.worker, args=(root,), daemon=True).start()

    def worker(self, root):
        try:
            def update(value, text):
                self.window.after(0, lambda: (self.progress.set(value), self.status.set(text)))
            rom, count = logical_unpack(root, update)
            self.window.after(0, lambda: messagebox.showinfo(
                "完成", f"逻辑解包完成，识别 PSB 包：{count} 个\nROM：{rom}"))
            self.window.after(0, lambda: self.status.set("完成"))
        except Exception as exc:
            self.window.after(0, lambda: messagebox.showerror("解包失败", str(exc)))
            self.window.after(0, lambda: self.status.set("失败"))


if __name__ == "__main__":
    root_window = tk.Tk()
    App(root_window)
    root_window.mainloop()
