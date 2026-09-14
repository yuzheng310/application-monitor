首个可独立使用的公开版本。

- 18 家招聘入口、本地投递看板、流程展示、历史变化与失败保留。
- 内置 Python、Node.js、OpenCLI、完整 npm 依赖、Chromium 和 Browser Bridge 扩展。
- 解压后双击启动；首次启动无需安装或下载依赖。首次登录招聘账号仍需本人完成。
- Windows x64、macOS Apple Silicon / Intel、Ubuntu 桌面 x64 四种完整包。
- 个人数据只保存在本机用户目录，升级不会覆盖。

请下载下面对应系统的 `application-monitor-*` 完整包。GitHub 自动附带的 Source code 文件是开发源码，不包含运行时。

macOS / Linux：解压后启动 `Start.command` / `Start.sh`。Windows：解压后双击 `Start.cmd`。
发布包未经商业代码签名，系统可能提示未知开发者；系统支持范围和处理方法见 README。

每个完整包附带 `.sha256` 校验文件。四个平台均经过独立构建、运行时自检和实际浏览器 / 扩展 / OpenCLI 集成测试；未对其他使用者的招聘网站账号进行验证，网站改版或登录失效仍可能导致读取失败。
