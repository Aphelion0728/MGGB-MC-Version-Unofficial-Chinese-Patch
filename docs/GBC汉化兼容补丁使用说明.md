# GBC《合金装备：幽灵通天塔》汉化兼容补丁

本工具用于让已分析的 V1.0 汉化 ROM 在《合金装备大师合集 2》特典的内置模拟器中运行。

工具不包含、也不分发 ROM、游戏 EXE 或资源包。使用者需要拥有正版游戏及对应 ROM。

## 使用方法

1. 将 `GBC汉化兼容补丁.exe` 放在游戏根目录。
2. 保留原版对照 ROM：`EN ROM\block_230.gbc`。
3. 将已支持的汉化 ROM 放在 `CHS ROM\block_230.gbc`，或在界面内另行选择。
4. 关闭游戏，运行工具并点击“验证当前状态”。
5. 点击“应用汉化兼容补丁”。工具会备份并替换：
   - `MGS MC2 Bonus Content.exe`
   - `windata\alldata.bin`
6. 若需回退，点击“恢复最近汉化备份”。

备份目录为：`Buckup\CHS_GhostBabel_日期时间\`。

## 支持范围

当前版本严格校验以下文件，避免误写未知版本：

- 官方 EXE SHA-256：`ab2eb668545297e9a00dd048e4a7dc758c4f9f104ba2c37bc77eb0d627fd8fca`
- 官方资源包 SHA-256：`40feb4cb173d6271e29571a3135aaff58755ce7b9cd703bc46c7a95d34256e7b`
- 汉化 ROM SHA-256：`ff6950746169ab565d2f852ef699fcf1242e172ab24580ff43eb9aa17cd6a773`

不匹配时工具会停止，不会强行覆盖。

## 技术说明

汉化 ROM 相比英文 ROM 不只是文本发生变化，首 bank 有代码位移，多处指针也移动了 8 字节。工具会：

- 让内置模拟器把汉化 ROM 识别为 Ghost Babel 专用 Mode1；
- 仅启用已验证的 Mode1 Entry 5～8，并按欧版 ROM 与汉化 ROM 的首个 16 KiB bank 对齐关系映射四个地址；
- 禁用 Entry 1～4 及 Entry 9～73，避免英文大资源覆盖层和未验证钩子覆盖汉化 ROM；
- 将 ROM 写入 MDF 第 230 块，同时保持原块跨度及后续资源偏移不变；
- 写回前进行 ROM 解密、解压和哈希回读验证。
