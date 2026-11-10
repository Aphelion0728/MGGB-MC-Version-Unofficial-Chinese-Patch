# MGS_BC2 汉化工具与文本图集

本仓库保存《合金装备 大师合集 Vol.2》特典包汉化项目的工具源码、启动器文本图集 PSD、字体和资源处理说明。完整游戏、原始 ROM、`windata` 数据卷、备份和工作区不进入 Git 仓库。

## 内容

- `src/python`：MDF 解包/回包、逻辑解包和 GBC 汉化兼容补丁源码。
- `src/csharp`：PSB 资源替换、资源添加和启动器图集工具源码。
- `tools`：文本图集、字体、输入诊断和构建脚本，以及构建所需的 FreeMote 运行时。
- `assets/launcher`：启动器英文文本图集 PSD 和槽位映射。
- `docs`：编译说明、发布流程和补丁技术文档。

当前 0.6 补丁 ZIP 不作为普通 Git 文件提交，而作为 GitHub Release 资产发布。这样可以避开 GitHub 普通仓库的单文件大小限制，同时保留可验证的完整补丁包。

## 快速开始

先阅读 [`docs/编译说明与发布流程_v0.6.md`](docs/编译说明与发布流程_v0.6.md)，再阅读 [`docs/补丁技术文档_v0.6.md`](docs/补丁技术文档_v0.6.md)。

本项目不分发完整游戏、原始 ROM 或 Steam 文件。使用补丁前请确认拥有正版游戏和相应汉化 ROM。

## 许可证与权利声明

- `src/` 与 `tools/` 中由本项目原创的程序源码采用 [MIT License](LICENSE)。
- `assets/` 中由本项目原创的 PSD、图集和映射资料，以及 `docs/` 中由本项目原创的文档，采用 [CC BY-NC-SA 4.0](ASSET_LICENSE.md)。
- 游戏本体、原始 ROM、Konami 素材、第三方字体和第三方组件不属于上述授权范围，继续适用各自权利人的条款。
- GitHub Release 中发布的汉化补丁是依赖正版游戏使用的非官方社区补丁，不授予任何原游戏内容的权利。详见 [NOTICE.md](NOTICE.md)。
- `tools/FreeMote` 属于第三方组件，采用其目录内的 `FreeMote.LICENSE.txt`，不属于本项目 MIT 授权。
