#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MGS_BC2 MDF 资源包 GUI 工具：自动备份、解包、重打包和恢复。"""
from __future__ import annotations
import datetime, json, mmap, os, queue, shutil, struct, sys, threading, zlib
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ALIGN = 0x800
ROM_KEY = bytes.fromhex('1124fa5f5ab36ae83cc359efd477b06309d5c1c63fdc75ad474fdc5424f753ed16fa23d1e91eeeb02dac32b6d67cd2b7a6ff601a53c40a3cc16989ffcfc54643')

class Entry:
    def __init__(self, index, offset, span, size): self.index, self.offset, self.span, self.size = index, offset, span, size
    def as_dict(self): return {'index': self.index, 'offset': self.offset, 'span': self.span, 'size': self.size}

def scan_mdf(path):
    result=[]; length=os.path.getsize(path)
    with open(path,'rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
        offsets=[o for o in range(0,length-7,ALIGN) if mm[o:o+4]==b'mdf\0']
        for n,off in enumerate(offsets):
            end=offsets[n+1] if n+1<len(offsets) else length; span=end-off
            if span>=8 and span%ALIGN==0: result.append(Entry(len(result),off,span,struct.unpack_from('<I',mm,off+4)[0]))
    return result

def xor_cycle(data,key): return bytes(b^key[i%len(key)] for i,b in enumerate(data))

def normalize_gbc_for_mgs(data):
    """恢复 MGS_BC2 内置模拟器需要的原版识别头。

    该模拟器会根据标题、头部校验和及全局校验和选择专用兼容参数。汉化
    ROM 的正文保持不变，只替换这些识别字段；不会修改用户保存的原始 ROM。
    """
    if len(data) >= 0x150 and data[0x147] == 0x1B and data[0x148] == 0x07:
        # 汉化版的代码/指针布局与官方 ROM 不同。EXE 会依据全局校验值
        # 选择专用 ROM 补丁表；强行改成官方校验值会套用错误的补丁，
        # 导致进入游戏后白屏。因此保留汉化 ROM 自身的识别字段，
        # 让模拟器走通用路径。
        title = data[0x134:0x144].rstrip(b'\0')
        if title.startswith(b'METALGEARGBBMGE') or data[0x14E:0x150] == b'\x17\xB7':
            return data
        # 原版标题字段（16 字节，末尾包含 CGB 标记字节）。
        title = b'METALGEARGBBMSP\xC0'
        out = bytearray(data)
        out[0x134:0x144] = title
        out[0x14D] = 0x0D       # header checksum
        out[0x14E:0x150] = b'\x99\x74'  # global checksum used by MGS build
        return bytes(out)
    return data

def decode_payload(payload,key,expected=None):
    obj=zlib.decompressobj()
    try: data=obj.decompress(xor_cycle(payload,key))
    except zlib.error as e: raise ValueError('解码失败：密钥不匹配或资源不是此密钥保护的 MDF') from e
    if not obj.eof: raise ValueError('zlib 数据不完整')
    if expected is not None and len(data)!=expected: raise ValueError(f'解码大小异常：应为 {expected}，实际为 {len(data)}')
    return data

def backup_files(root,names):
    folder=Path(root)/'Buckup'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S'); folder.mkdir(parents=True,exist_ok=True)
    for name in names:
        src=Path(root)/'windata'/name
        if src.is_file(): shutil.copy2(src,folder/name)
    return folder

def unpack_bin(root,progress):
    root=Path(root); src=root/'windata'/'alldata.bin'
    if not src.is_file(): raise FileNotFoundError(src)
    entries=scan_mdf(src); out=root/'Extracted'/'alldata.bin'; out.mkdir(parents=True,exist_ok=True); decoded=[]
    with open(src,'rb') as f:
        for pos,e in enumerate(entries,1):
            f.seek(e.offset); block=f.read(e.span)
            if e.index==230 and e.size==0x400000:
                (out/'block_230.gbc').write_bytes(decode_payload(block[8:],ROM_KEY,e.size)); decoded.append(230)
            else: (out/f'block_{e.index:03d}.mdf').write_bytes(block)
            progress(pos,len(entries),f'解包 alldata.bin：{pos}/{len(entries)}')
    (out/'manifest.json').write_text(json.dumps({'format':'MDF','source':'alldata.bin','entries':[e.as_dict() for e in entries],'decoded':decoded},ensure_ascii=False,indent=2),encoding='utf-8')
    return f'完成：{len(entries)} 个分块\n可修改：{out / "block_230.gbc"}'

def repack_bin(root,progress):
    root=Path(root); src=root/'windata'/'alldata.bin'; folder=root/'Extracted'/'alldata.bin'
    if not src.is_file() or not folder.is_dir(): raise FileNotFoundError('请先解包 alldata.bin')
    entries=scan_mdf(src); tmp=src.with_suffix('.bin.tmp'); shutil.copy2(src,tmp)
    try:
        replacement=folder/'block_230.gbc'; e=entries[230]
        if replacement.is_file():
            data=normalize_gbc_for_mgs(replacement.read_bytes()); comp=zlib.compress(data,9)
            if len(comp)>e.span-8: raise ValueError('汉化 ROM 压缩后超过第 230 块容量')
            with open(src,'rb') as f:
                f.seek(e.offset+8); old=f.read(e.span-8)
            block=b'mdf\0'+struct.pack('<I',len(data))+xor_cycle(comp,ROM_KEY)+old[len(comp):]
            with open(tmp,'r+b') as f: f.seek(e.offset); f.write(block)
        with open(tmp,'r+b') as out:
            for pos,e in enumerate(entries,1):
                raw=folder/f'block_{e.index:03d}.mdf'
                if raw.is_file() and e.index!=230:
                    b=raw.read_bytes()
                    if len(b)!=e.span or b[:4]!=b'mdf\0': raise ValueError(f'{raw.name} 长度或头部错误')
                    out.seek(e.offset); out.write(b)
                progress(pos,len(entries),f'重打包 alldata.bin：{pos}/{len(entries)}')
        os.replace(tmp,src)
    finally:
        if tmp.exists(): tmp.unlink()
    return f'已写回：{src}'

def unpack_psb(root,progress):
    root=Path(root); src=root/'windata'/'alldata.psb.m'
    if not src.is_file(): raise FileNotFoundError(src)
    out=root/'Extracted'/'alldata.psb.m'; out.mkdir(parents=True,exist_ok=True); (out/'resource.mdf').write_bytes(src.read_bytes())
    (out/'manifest.json').write_text(json.dumps({'format':'MDF','source':'alldata.psb.m','mode':'raw-preserved'},ensure_ascii=False,indent=2),encoding='utf-8'); progress(1,1,'解包 alldata.psb.m：完成')
    return f'完成：{out / "resource.mdf"}\nPSB 卷已以原始 MDF 形式保存，可无损回写。'

def repack_psb(root,progress):
    root=Path(root); src=root/'windata'/'alldata.psb.m'; loose=root/'Extracted'/'alldata.psb.m'/'resource.mdf'
    if not src.is_file() or not loose.is_file(): return '未找到 PSB 松散文件，跳过。'
    data=loose.read_bytes()
    if data[:4]!=b'mdf\0' or len(data)!=src.stat().st_size: raise ValueError('resource.mdf 必须保持原始长度和 MDF 头')
    tmp=src.with_suffix('.m.tmp'); shutil.copy2(src,tmp)
    with open(tmp,'r+b') as f: f.write(data)
    os.replace(tmp,src); progress(1,1,'重打包 alldata.psb.m：完成'); return f'已写回：{src}'

class App:
    def __init__(self,root):
        self.root=root; root.title('MGS_BC2 MDF 资源工具'); root.geometry('760x340'); self.jobs=queue.Queue(); base=Path(sys.executable if getattr(sys,'frozen',False) else __file__).resolve().parent; self.address=tk.StringVar(value=str(base)); self.status=tk.StringVar(value='请选择游戏根目录'); self.ui(); root.after(100,self.poll)
    def ui(self):
        box=ttk.LabelFrame(self.root,text='游戏根目录'); box.pack(fill='x',padx=12,pady=12); ttk.Entry(box,textvariable=self.address).pack(side='left',fill='x',expand=True,padx=7,pady=8); ttk.Button(box,text='浏览…',command=self.browse).pack(side='left',padx=4)
        actions=ttk.LabelFrame(self.root,text='资源操作'); actions.pack(fill='x',padx=12,pady=5)
        ttk.Button(actions,text='解包 alldata.bin',command=lambda:self.start(unpack_bin,['alldata.bin'])).grid(row=0,column=0,padx=8,pady=15,ipadx=10,ipady=8)
        ttk.Button(actions,text='解包 alldata.psb.m',command=lambda:self.start(unpack_psb,['alldata.psb.m'])).grid(row=0,column=1,padx=8,pady=15,ipadx=10,ipady=8)
        ttk.Button(actions,text='重打包并写回资源',command=self.repack).grid(row=0,column=2,padx=8,pady=15,ipadx=10,ipady=8)
        ttk.Button(actions,text='恢复备份',command=self.restore).grid(row=0,column=3,padx=8,pady=15,ipadx=10,ipady=8)
        self.progress=ttk.Progressbar(self.root,mode='determinate'); self.progress.pack(fill='x',padx=12,pady=(22,5)); ttk.Label(self.root,textvariable=self.status,relief='sunken',anchor='w').pack(fill='x',padx=12,pady=5); ttk.Label(self.root,text='操作前自动备份到 Buckup\\时间戳；松散文件位于 Extracted\\文件名。',foreground='#555').pack(anchor='w',padx=12)
    def browse(self):
        p=filedialog.askdirectory(title='选择游戏根目录');
        if p:self.address.set(p)
    def start(self,func,names):
        root=self.address.get().strip()
        if not root or not (Path(root)/'windata').is_dir(): return messagebox.showerror('目录错误','目录中未找到 windata 文件夹')
        try: b=backup_files(root,names); self.status.set(f'已备份到 {b}')
        except Exception as e: return messagebox.showerror('备份失败',str(e))
        self.progress['value']=0; threading.Thread(target=self.worker,args=(func,root),daemon=True).start()
    def repack(self):
        root=self.address.get().strip()
        if not (Path(root)/'windata').is_dir(): return messagebox.showerror('目录错误','目录中未找到 windata 文件夹')
        try: b=backup_files(root,['alldata.bin','alldata.psb.m']); self.status.set(f'已备份到 {b}')
        except Exception as e: return messagebox.showerror('备份失败',str(e))
        self.progress['value']=0; threading.Thread(target=self.repack_worker,args=(root,),daemon=True).start()
    def worker(self,func,root):
        try:self.jobs.put(('done',func(root,lambda a,b,s:self.jobs.put(('progress',(a,b,s))))))
        except Exception as e:self.jobs.put(('error',str(e)))
    def repack_worker(self,root):
        try:self.jobs.put(('done',repack_bin(root,lambda a,b,s:self.jobs.put(('progress',(a,b,s))))+'\n'+repack_psb(root,lambda a,b,s:self.jobs.put(('progress',(a,b,s))))))
        except Exception as e:self.jobs.put(('error',str(e)))
    def restore(self):
        root=Path(self.address.get().strip()); backup=root/'Buckup'; folders=sorted([p for p in backup.iterdir() if p.is_dir()],reverse=True) if backup.is_dir() else []
        if not folders:return messagebox.showerror('恢复失败','Buckup 文件夹中没有备份')
        latest=folders[0]; restored=[]
        for name in ('alldata.bin','alldata.psb.m'):
            p=latest/name
            if p.is_file():shutil.copy2(p,root/'windata'/name); restored.append(name)
        messagebox.showinfo('恢复完成',f'已从 {latest.name} 恢复：{", ".join(restored)}')
    def poll(self):
        try:
            while True:
                kind,val=self.jobs.get_nowait()
                if kind=='progress':a,b,s=val; self.progress['maximum']=max(1,b); self.progress['value']=a; self.status.set(s)
                elif kind=='done':messagebox.showinfo('完成',val); self.status.set('完成')
                else:messagebox.showerror('操作失败',val); self.status.set('操作失败')
        except queue.Empty:pass
        self.root.after(100,self.poll)

if __name__=='__main__':
    r=tk.Tk(); App(r); r.mainloop()
