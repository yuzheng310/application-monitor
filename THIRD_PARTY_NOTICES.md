# 第三方软件

本项目自身代码使用 MIT 许可证。以下依赖保留各自的许可证，并不改为 MIT。

| 组件 | 固定版本 | 来源及许可 |
|---|---|---|
| OpenCLI | 1.8.6 | https://github.com/jackwener/opencli · Apache-2.0 |
| OpenCLI Browser Bridge | 1.0.24 | 同上，`vendor/browser-bridge/LICENSE` |
| Node.js | 24.21.0 | https://nodejs.org/ · MIT 及其第三方许可，包内 `runtime/NODE-LICENSE` |
| Chromium | Playwright 1.62.0 固定的构建 | https://www.chromium.org/ · BSD 及第三方许可，包内 `runtime/CHROMIUM-CREDITS.html` |
| Python | 以包内 VERSIONS.json 为准 | https://www.python.org/ · PSF，随 PyInstaller 运行环境分发 |
| PyInstaller | 6.16.0 | GPL-2.0-or-later，含允许分发生成程序的 bootloader 例外 |
| Playwright | 1.62.0，仅构建及测试时使用 | Apache-2.0 |

OpenCLI 的全部运行时 npm 依赖通过 `package-lock.json` 固定，构建时使用 `npm ci --ignore-scripts`，完整目录和许可证一起收入 `runtime/node_modules`。不运行安装后脚本，也不下载额外站点适配器。

Browser Bridge 来自官方 Chrome 扩展 1.0.24 的已安装静态资源，未包含浏览历史、Cookie、扩展存储或账号数据。排除 Chrome 商店校验元数据和 sourcemap；安装时只修改 `getCurrentContextId()` 的返回值，为独立浏览器指定本机随机身份，防止路由到使用者的其他浏览器。修改逻辑见 `runtime.prepare_extension()`，原始 vendored 文件保持不变。

完整发布包包含 Chromium、Node、Python 运行环境、OpenCLI、递归 npm 依赖和浏览器扩展。首次运行不会安装包或下载运行环境。操作系统自身的图形界面、系统库和驱动由操作系统提供；Linux 面向 Ubuntu 22.04/24.04 桌面环境。
