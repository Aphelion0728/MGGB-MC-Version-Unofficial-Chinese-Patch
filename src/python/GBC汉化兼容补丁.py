#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MGS Master Collection Vol.2 / Ghost Babel Chinese ROM compatibility patch.

This utility does not include a ROM or game data.  It accepts only the exact
translation ROM analysed for this installation, creates a timestamped backup,
then patches a user's local executable and archive.  Every generated archive
is zlib/XOR round-trip verified before replacing a game file.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import queue
import shutil
import struct
import sys
import threading
import zlib
from difflib import SequenceMatcher
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pefile


STOCK_EXE_SHA256 = "ab2eb668545297e9a00dd048e4a7dc758c4f9f104ba2c37bc77eb0d627fd8fca"
PATCHED_EXE_SHA256 = "2c0459c2b159973de8e003f7d5b65332eeaffb2f778467c45766bf0edac4d8a8"
STOCK_ARCHIVE_SHA256 = "40feb4cb173d6271e29571a3135aaff58755ce7b9cd703bc46c7a95d34256e7b"
PATCHED_ARCHIVE_SHA256 = "9b145882db9c6adef678c4af283d327bf0f32ab6c0375903a5f927ebc3595a19"
CHS_ROM_SHA256 = "ff6950746169ab565d2f852ef699fcf1242e172ab24580ff43eb9aa17cd6a773"
EXE_NAME = "MGS MC2 Bonus Content.exe"
TABLE_VA = 0x1404B85F0
ENTRY_COUNT = 74
ENTRY_SIZE = 24
ROM_BLOCK_OFFSET = 229853184
ROM_BLOCK_SPAN = 1474560
ROM_KEY = bytes.fromhex(
    "1124fa5f5ab36ae83cc359efd477b063"
    "09d5c1c63fdc75ad474fdc5424f753ed"
    "16fa23d1e91eeeb02dac32b6d67cd2b7a"
    "6ff601a53c40a3cc16989ffcfc54643"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def xor_crypt(data: bytes) -> bytes:
    return bytes(value ^ ROM_KEY[index % len(ROM_KEY)] for index, value in enumerate(data))


def file_offset(pe: pefile.PE, va: int) -> int:
    return pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)


def replace_bytes(data: bytearray, offset: int, replacement: bytes) -> None:
    data[offset : offset + len(replacement)] = replacement


def load_bank1_mapping(en: bytes, chs: bytes) -> dict[int, int]:
    """Map unchanged byte positions in the ROM bank used by the verified build."""
    matcher = SequenceMatcher(None, en[0x4000:0x8000], chs[0x4000:0x8000], autojunk=False)
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, _j2 in matcher.get_opcodes():
        if tag != "equal":
            continue
        for rel in range(i1, i2):
            mapping[0x4000 + rel] = 0x4000 + j1 + (rel - i1)
    return mapping


def build_exe(source: Path, en_rom: Path, chs_rom: Path) -> bytes:
    """Build the verified 5-8 mapping image in memory."""
    pe = pefile.PE(str(source), fast_load=True)
    original = source.read_bytes()
    data = bytearray(original)
    en = en_rom.read_bytes()
    chs = chs_rom.read_bytes()
    if len(en) != len(chs) or len(chs) != 4 * 1024 * 1024:
        raise ValueError("ROM 大小必须为 4 MiB")

    compare = file_offset(pe, 0x140046716)
    if original[compare : compare + 5] != b"\xB9\x99\x74\x00\x00":
        raise ValueError("EXE ROM 校验指令不符合官方版本")
    replace_bytes(data, compare + 1, b"\x17\xB7")

    table = file_offset(pe, TABLE_VA)
    entries = [struct.unpack_from("<QQQ", original, table + index * ENTRY_SIZE) for index in range(ENTRY_COUNT)]
    mapping = load_bank1_mapping(en, chs)
    # The large overlay and all unverified hooks must remain disabled. Only
    # entries 5-8 are needed for the translated ROM's verified runtime path.
    for index in list(range(1, 5)) + list(range(9, ENTRY_COUNT)):
        replace_bytes(data, table + index * ENTRY_SIZE + 16, struct.pack("<Q", 0))
    for index in (5, 6, 7, 8):
        target, source_va, length = entries[index]
        if length != 2:
            raise ValueError(f"补丁表第 {index} 项长度异常")
        old_value = struct.unpack_from("<H", original, file_offset(pe, source_va))[0]
        mapped = mapping.get(old_value)
        if mapped is None:
            raise ValueError(f"补丁表第 {index} 项指针无法映射")
        replace_bytes(data, file_offset(pe, source_va), struct.pack("<H", mapped))
    return bytes(data)


def build_archive(source: Path, rom_path: Path) -> bytes:
    original = source.read_bytes()
    if len(original) < ROM_BLOCK_OFFSET + ROM_BLOCK_SPAN:
        raise ValueError("alldata.bin 长度异常")
    old_block = original[ROM_BLOCK_OFFSET : ROM_BLOCK_OFFSET + ROM_BLOCK_SPAN]
    if old_block[:4] != b"mdf\0":
        raise ValueError("第 230 资源块不是预期 MDF 格式")
    rom = rom_path.read_bytes()
    compressed = zlib.compress(rom, 9)
    if len(compressed) > ROM_BLOCK_SPAN - 8:
        raise ValueError("汉化 ROM 压缩后超过原资源块容量")
    block = b"mdf\0" + struct.pack("<I", len(rom)) + xor_crypt(compressed)
    block += old_block[8 + len(compressed) :]
    if len(block) != ROM_BLOCK_SPAN:
        raise AssertionError("资源块长度改变")
    recovered = zlib.decompress(xor_crypt(block[8:]))
    if recovered != rom:
        raise ValueError("资源包回读验证失败")
    output = bytearray(original)
    output[ROM_BLOCK_OFFSET : ROM_BLOCK_OFFSET + ROM_BLOCK_SPAN] = block
    return bytes(output)


def paths(root: Path) -> tuple[Path, Path]:
    return root / EXE_NAME, root / "windata" / "alldata.bin"


def state(root: Path, rom: Path | None = None) -> tuple[str, str]:
    exe, archive = paths(root)
    if not exe.is_file() or not archive.is_file():
        return "路径不完整", "未找到游戏 EXE 或 windata\\alldata.bin。"
    exe_hash, archive_hash = sha256(exe), sha256(archive)
    if exe_hash == PATCHED_EXE_SHA256 and archive_hash == PATCHED_ARCHIVE_SHA256:
        text = "已应用本工具的汉化兼容补丁"
    elif exe_hash == STOCK_EXE_SHA256 and archive_hash == STOCK_ARCHIVE_SHA256:
        text = "官方原版文件，可应用补丁"
    else:
        text = "文件版本不匹配，工具不会覆盖"
    details = f"EXE：{exe_hash[:12]}…\nalldata.bin：{archive_hash[:12]}…"
    if rom is not None and rom.is_file():
        details += f"\nROM：{sha256(rom)[:12]}…"
    return text, details


def backup(root: Path) -> Path:
    destination = root / "Buckup" / ("CHS_GhostBabel_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    destination.mkdir(parents=True, exist_ok=False)
    exe, archive = paths(root)
    shutil.copy2(exe, destination / EXE_NAME)
    shutil.copy2(archive, destination / "alldata.bin")
    return destination


def install_verified(temporary: Path, destination: Path) -> None:
    """Install a fully verified temporary file, even where EXE rename is blocked."""
    try:
        os.replace(temporary, destination)
    except PermissionError:
        # Some endpoint products deny renaming over an EXE but permit an
        # in-place overwrite. The backup is already complete and the temporary
        # file was hash-verified immediately before this fallback.
        shutil.copyfile(temporary, destination)
        temporary.unlink(missing_ok=True)


def apply(root: Path, rom_path: Path, progress) -> Path:
    exe, archive = paths(root)
    en_rom = root / "EN ROM" / "block_230.gbc"
    if not en_rom.is_file():
        raise FileNotFoundError("需要 EN ROM\\block_230.gbc 作为原版对照 ROM")
    if not rom_path.is_file():
        raise FileNotFoundError("未找到汉化 ROM")
    if sha256(rom_path) != CHS_ROM_SHA256:
        raise ValueError("此工具仅支持已验证的 V1.0 汉化 ROM（SHA-256 不匹配）")
    if sha256(exe) != STOCK_EXE_SHA256 or sha256(archive) != STOCK_ARCHIVE_SHA256:
        raise ValueError("EXE 或 alldata.bin 不是本工具支持的官方原版；请先恢复备份")
    progress(5, "正在创建可恢复备份…")
    saved = backup(root)
    try:
        progress(20, "正在构建 EXE 兼容补丁…")
        patched_exe = build_exe(exe, en_rom, rom_path)
        progress(55, "正在写入并验证汉化 ROM 资源包…")
        patched_archive = build_archive(archive, rom_path)
        exe_tmp = exe.with_suffix(".exe.chs_tmp")
        archive_tmp = archive.with_suffix(".bin.chs_tmp")
        exe_tmp.write_bytes(patched_exe)
        archive_tmp.write_bytes(patched_archive)
        if sha256(exe_tmp) != PATCHED_EXE_SHA256 or sha256(archive_tmp) != PATCHED_ARCHIVE_SHA256:
            raise ValueError("生成结果与已验证版本不一致，已停止")
        progress(90, "正在原子替换游戏文件…")
        install_verified(exe_tmp, exe)
        install_verified(archive_tmp, archive)
        progress(100, "完成")
        return saved
    except Exception:
        for temporary in (exe.with_suffix(".exe.chs_tmp"), archive.with_suffix(".bin.chs_tmp")):
            temporary.unlink(missing_ok=True)
        # If an endpoint product interrupted installation between the two
        # replacements, best-effort rollback keeps EXE and archive paired.
        try:
            shutil.copy2(saved / EXE_NAME, exe)
            shutil.copy2(saved / "alldata.bin", archive)
        except Exception:
            pass
        raise


def restore(root: Path) -> Path:
    folder = root / "Buckup"
    backups = sorted((entry for entry in folder.glob("CHS_GhostBabel_*") if entry.is_dir()), reverse=True)
    if not backups:
        raise FileNotFoundError("Buckup 中没有本工具创建的汉化备份")
    latest = backups[0]
    exe, archive = paths(root)
    shutil.copy2(latest / EXE_NAME, exe)
    shutil.copy2(latest / "alldata.bin", archive)
    return latest


class App:
    def __init__(self, window: tk.Tk) -> None:
        self.window = window
        window.title("MGS_BC2《幽灵通天塔》汉化兼容补丁")
        window.geometry("780x355")
        base = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        self.root_dir = tk.StringVar(value=str(base))
        self.rom_path = tk.StringVar(value=str(base / "CHS ROM" / "block_230.gbc"))
        self.status = tk.StringVar(value="请选择游戏根目录与已支持的汉化 ROM")
        self.jobs: queue.Queue = queue.Queue()
        self.make_ui()
        window.after(100, self.poll)

    def make_ui(self) -> None:
        outer = ttk.Frame(self.window, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)
        ttk.Label(outer, text="游戏根目录：").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.root_dir).grid(row=0, column=1, sticky="ew", padx=7)
        ttk.Button(outer, text="浏览…", command=self.choose_root).grid(row=0, column=2)
        ttk.Label(outer, text="汉化 ROM：").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.rom_path).grid(row=1, column=1, sticky="ew", padx=7)
        ttk.Button(outer, text="浏览…", command=self.choose_rom).grid(row=1, column=2)
        action = ttk.LabelFrame(outer, text="操作", padding=10)
        action.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 10))
        ttk.Button(action, text="验证当前状态", command=self.validate).pack(side="left", padx=8)
        ttk.Button(action, text="应用汉化兼容补丁", command=self.start_apply).pack(side="left", padx=8)
        ttk.Button(action, text="恢复最近汉化备份", command=self.start_restore).pack(side="left", padx=8)
        self.bar = ttk.Progressbar(outer, maximum=100)
        self.bar.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(outer, textvariable=self.status, relief="sunken", anchor="w", justify="left").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=4
        )
        ttk.Label(
            outer,
            text="不包含 ROM 或游戏文件。应用前备份 EXE 与 alldata.bin 至 Buckup\\CHS_GhostBabel_时间戳。",
            foreground="#555",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=7)

    def choose_root(self) -> None:
        selected = filedialog.askdirectory(title="选择 MGS_BC2 游戏根目录")
        if selected:
            self.root_dir.set(selected)

    def choose_rom(self) -> None:
        selected = filedialog.askopenfilename(title="选择汉化 GBC ROM", filetypes=[("GBC ROM", "*.gbc"), ("所有文件", "*.*")])
        if selected:
            self.rom_path.set(selected)

    def validate(self) -> None:
        title, details = state(Path(self.root_dir.get()), Path(self.rom_path.get()))
        self.status.set(title)
        messagebox.showinfo("状态验证", title + "\n\n" + details)

    def start_apply(self) -> None:
        root, rom = Path(self.root_dir.get()), Path(self.rom_path.get())
        title, _ = state(root, rom)
        if title != "官方原版文件，可应用补丁":
            messagebox.showerror("无法应用", title)
            return
        if not messagebox.askyesno("确认应用", "将备份并替换该游戏目录的 EXE 与 alldata.bin。是否继续？"):
            return
        self.bar["value"] = 0
        threading.Thread(target=self.apply_worker, args=(root, rom), daemon=True).start()

    def start_restore(self) -> None:
        root = Path(self.root_dir.get())
        if not messagebox.askyesno("确认恢复", "将从最近一次汉化备份恢复 EXE 与 alldata.bin。是否继续？"):
            return
        threading.Thread(target=self.restore_worker, args=(root,), daemon=True).start()

    def apply_worker(self, root: Path, rom: Path) -> None:
        try:
            saved = apply(root, rom, lambda value, text: self.jobs.put(("progress", value, text)))
            self.jobs.put(("done", f"汉化兼容补丁已应用。\n备份：{saved}"))
        except Exception as exc:
            self.jobs.put(("error", str(exc)))

    def restore_worker(self, root: Path) -> None:
        try:
            saved = restore(root)
            self.jobs.put(("done", f"已恢复：{saved}"))
        except Exception as exc:
            self.jobs.put(("error", str(exc)))

    def poll(self) -> None:
        try:
            while True:
                kind, *payload = self.jobs.get_nowait()
                if kind == "progress":
                    value, text = payload
                    self.bar["value"] = value
                    self.status.set(text)
                elif kind == "done":
                    self.status.set("完成")
                    messagebox.showinfo("完成", payload[0])
                else:
                    self.status.set("失败")
                    messagebox.showerror("操作失败", payload[0])
        except queue.Empty:
            pass
        self.window.after(100, self.poll)


if __name__ == "__main__":
    app_window = tk.Tk()
    App(app_window)
    app_window.mainloop()
