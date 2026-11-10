# 《合金装备大师合集 2》特典包资源解包/打包技术说明

这份说明记录 MGS_BC2 特典包中 GBC《合金装备：幽灵通天塔》资源的实际分析结果，重点说明 `windata\alldata.bin` 和 `windata\alldata.psb.m` 的格式、解包方法、回包方法、已验证数据和当前限制。

可直接将本文提供给其他分析对话。文中“已验证”只表示在本工程当前文件版本上完成了离线回读校验，不代表其他游戏版本也使用完全相同的偏移和密钥。

## 1. 文件职责

游戏根目录中的资源文件位于：

```text
windata\alldata.bin
windata\alldata.psb.m
```

两者职责不同：

| 文件 | 作用 | 当前处理状态 |
|---|---|---|
| `alldata.bin` | 主资源数据卷，包含大量 MDF 分块；第 230 块是内置模拟器读取的 4 MiB GBC ROM | 已完成块级解包、ROM 解码、ROM 替换和无损回包 |
| `alldata.psb.m` | 主资源索引/PSB 卷，保存资源路径和资源定位相关数据 | 已完成原始 MDF 提取和原样回写；尚未完成可安全逐文件编辑的 PSB 重建器 |

重要结论：`alldata.bin` 不是普通文件夹压缩包，而是按 `0x800` 字节对齐的 MDF 分块集合；`alldata.psb.m` 也不是可以直接用文本编辑器打开的普通 PSB 文件。

## 2. MDF 外层格式

每个已确认的 MDF 分块都从如下 8 字节头开始：

```text
偏移 +0x00：ASCII `mdf\0`（末尾为 NUL 字节）
偏移 +0x04：little-endian uint32，解压后的逻辑数据长度
偏移 +0x08：加密/压缩 payload
```

`alldata.bin` 中的分块从 `0x800` 边界开始。单个分块的存储范围不是由头部长度直接决定，而是由“当前 MDF 头到下一个 MDF 头”的跨度决定；最后一块延伸到文件末尾。有效跨度必须是 `0x800` 的整数倍。

扫描规则：

1. 从文件开始按 `0x800` 步长扫描。
2. 找到 `mdf\0` 时记录当前位置。
3. 用下一个 MDF 头的位置减去当前位置得到 `span`。
4. 读取当前头部的 uint32 作为逻辑解压长度。
5. 保留 `span`，回包时不能改变分块大小或后续块的偏移。

当前验证文件的扫描结果：

```text
alldata.bin 文件大小：232,654,848 字节
有效 MDF 分块数：351
对齐单位：0x800（2048）字节
```

## 3. 第 230 块 GBC ROM 的编码链

第 230 块是当前已确认的 GBC ROM 分块：

```text
分块编号：230
文件偏移：229,853,184（十六进制 0x0DB20000）
存储跨度：1,474,560 字节
MDF 头声明逻辑长度：4,194,304 字节（4 MiB）
```

第 230 块 payload 的实际编码顺序是：

```text
原始 4 MiB GBC ROM
    -> zlib 压缩（当前回包使用 compression level 9）
    -> 64 字节循环 XOR
    -> 写入 MDF payload
```

解包时反向执行：

```text
MDF payload
    -> 64 字节循环 XOR
    -> zlib 解压
    -> 4 MiB GBC ROM
```

已确认的 64 字节循环 XOR 密钥为：

```text
1124fa5f5ab36ae83cc359efd477b063
09d5c1c63fdc75ad474fdc5424f753ed
16fa23d1e91eeeb02dac32b6d67cd2b7a
6ff601a53c40a3cc16989ffcfc54643
```

XOR 方式不是以块偏移为起点重新取密钥，而是对 payload 的第一个字节使用密钥第 0 字节，然后每 64 字节循环：

```python
decoded[i] = payload[i] ^ key[i % 64]
```

当前汉化 ROM 的离线校验值：

```text
ROM 大小：4,194,304 字节
ROM SHA-256：FF6950746169AB565D2F852EF699FCF1242E172AB24580FF43EB9AA17CD6A773
```

当前资源包第 230 块的压缩流长度为 `1,074,113` 字节。解压器在 zlib 结束标记处停止，后面的分块填充区不是压缩流的一部分。

## 4. `alldata.bin` 解包流程

工具源码：

```text
CHS_Project\source\MDF资源工具.py
```

按钮“解包 alldata.bin”的实际流程：

1. 检查 `windata\alldata.bin` 是否存在。
2. 在 `Buckup\YYYYMMDD_HHMMSS\` 备份原文件。
3. 扫描 MDF 头并建立分块表。
4. 创建 `Extracted\alldata.bin\`。
5. 第 230 块：读取 8 字节 MDF 头后的 payload，执行 XOR + zlib 解码，输出：

   ```text
   Extracted\alldata.bin\block_230.gbc
   ```

6. 其他分块不强行猜测逻辑格式，按原始存储字节输出：

   ```text
   Extracted\alldata.bin\block_000.mdf
   Extracted\alldata.bin\block_001.mdf
   ...
   ```

7. 写出 `manifest.json`，记录每个分块的编号、偏移、跨度和逻辑大小。

这样做的原因是：绝大多数 MDF 块的内部逻辑格式没有在离线分析中被安全确认。保留原始块比错误解码后重新编码更可靠。

## 5. `alldata.bin` 重打包流程

按钮“重打包并写回资源”不会重新排列全部资源，而是以当前 `windata\alldata.bin` 为模板，在临时文件上修改。

### 5.1 替换第 230 块

如果存在：

```text
Extracted\alldata.bin\block_230.gbc
```

工具会：

1. 读取 ROM。
2. 保留已验证汉化 ROM 自身的识别字段，尤其是全局校验字段 `17 B7`；不要强行改回欧版的 `99 74`。
3. zlib 压缩 ROM。
4. 检查压缩数据是否小于 `第 230 块跨度 - 8`。
5. 对压缩流执行 64 字节循环 XOR。
6. 写入：

   ```text
   mdf\0
   uint32(0x400000)
   encrypted_zlib_stream
   原第 230 块 payload 的剩余填充字节
   ```

7. 通过 XOR 逆运算和 zlib 解压回读，确认解码结果与输入 ROM 完全一致。

### 5.2 其他分块

对 `block_NNN.mdf`：

- 文件存在时，必须与原分块长度完全一致；
- 前 4 字节必须是 `mdf\\0`；
- 通过检查后按原偏移写回；
- 文件不存在时，保留模板中的原分块不动。

最后使用 `os.replace` 替换原文件，避免直接在原文件中间写入导致半成品。工具在操作开始前会先备份原文件。

## 6. `alldata.psb.m` 的确认结果

当前文件实测：

```text
文件大小：20,879 字节
SHA-256：CAAD671E13561D410F7E281CDDAEADBE5FCFC880C63C068A5C041DDB3DAC5400
前 4 字节：mdf\\0
头部声明逻辑长度：28,114 字节
MDF 头后存储 payload：20,871 字节
```

它是一个 MDF 包装的 PSB 索引卷。当前已测试的第 230 块 ROM XOR 密钥不能直接解开它：对其 payload 直接 zlib 解压、先 XOR 再 zlib 解压，都不能得到有效 zlib 流。因此不能把 `alldata.psb.m` 按第 230 块 ROM 的方式处理。

### 6.1 当前安全实现

按钮“解包 alldata.psb.m”执行：

1. 备份原 `windata\alldata.psb.m`。
2. 将完整原始文件复制到：

   ```text
   Extracted\alldata.psb.m\resource.mdf
   ```

3. 写出 `manifest.json`，标记 `mode: raw-preserved`。

按钮“重打包并写回资源”执行：

1. 读取 `resource.mdf`。
2. 检查前 4 字节仍为 `mdf\0`。
3. 检查文件长度仍为 20,879 字节（必须与当前源文件一致）。
4. 写入临时文件后原子替换 `windata\alldata.psb.m`。

这套实现适合做原样备份、对比、验证和保留资源卷，不会误把未知的 PSB/MDF 内部数据重新编码。

### 6.2 尚未完成的部分

目前没有可靠完成以下功能：

- 从 `alldata.psb.m` 中恢复所有逻辑资源路径；
- 将其中的 PSB 节点、图片、字体或脚本逐项导出为普通文件；
- 修改单个 PSB 资源后重新计算其索引、压缩和 MDF 加密并回包。

因此不要把 `resource.mdf` 拆成任意文件后直接回包，也不要用第 230 块 ROM 的 XOR 密钥处理它。

## 7. 逻辑解包工具的作用和边界

工具源码：

```text
CHS_Project\source\MGS逻辑解包工具.py
```

它是在块级解包基础上的侦测工具，不是完整的通用重打包器。流程为：

1. 先按同样的 MDF 扫描规则读取 `alldata.bin`。
2. 第 230 块解码为 `block_230.gbc`，其他块保留为 `.mdf`。
3. 在已提取的 MDF payload 中寻找明文 `PSB\\0` 根节点。
4. 以相邻 `PSB\\0` 位置切出 bundle，输出到：

   ```text
   Extracted\alldata.bin\Logical\PSB\
   ```

5. 提取可识别的 ASCII 资源路径，写入 `.names.txt`。
6. 识别部分 `sound_archive` 固定字段，写入 `.sound.json`。
7. 对能确定位置和长度的独立 `codec=0x20001` 音频流导出 `.m2snd` 原始流。

逻辑解包的结果用于研究和定位，不能据此推断所有 bundle 都能独立回包。未知数据保持原样是设计要求。

## 8. 当前文件验证清单

当前 0.1beta 实装资源：

```text
MGS MC2 Bonus Content.exe
SHA-256: 2C0459C2B159973DE8E003F7D5B65332EEAFFB2F778467C45766BF0EDAC4D8A8

windata\alldata.bin
SHA-256: 9B145882DB9C6ADEF678C4AF283D327BF0F32AB6C0375903A5F927EBC3595A19

windata\alldata.psb.m
SHA-256: CAAD671E13561D410F7E281CDDAEADBE5FCFC880C63C068A5C041DDB3DAC5400
```

当前 EXE 的 ROM 兼容补丁与资源包解码是两个层次：

- 资源层：把汉化 ROM 放进 MDF 第 230 块；
- 模拟器层：让内置模拟器识别汉化 ROM，并只启用已验证的 Entry 0、5、6、7、8，关闭 Entry 1～4 和 Entry 9～73。

如果资源包回读正确但进入游戏白屏，优先检查 EXE 是否仍是上述 `2C0459...` 哈希，而不是重新压缩 ROM。

## 9. 推荐的复现顺序

```text
1. 退出游戏和启动器。
2. 备份 windata\alldata.bin / alldata.psb.m。
3. 扫描 MDF 分块并生成 manifest.json。
4. 只解码第 230 块，确认输出大小为 4 MiB。
5. 替换 block_230.gbc。
6. zlib 压缩 + 64 字节循环 XOR，保持第 230 块跨度不变。
7. XOR 解码 + zlib 解压回读，确认 ROM SHA-256 一致。
8. 保持 alldata.psb.m 原样，除非已经掌握其独立的运行时解码和 PSB 重建算法。
9. 使用已验证的 5-8 映射 EXE，不要启用未经验证的全量补丁表。
```

## 10. 相关工程文件

```text
CHS_Project\source\MDF资源工具.py
CHS_Project\source\MGS逻辑解包工具.py
CHS_Project\analysis\verified_algorithm\repack_rom_block230.py
CHS_Project\analysis\verified_algorithm\logical_unpack_probe.py
CHS_Project\analysis\verified_algorithm\build_verified_mode1.py
CHS_Project\release\0.1beta\
```
