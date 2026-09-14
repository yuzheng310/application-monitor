# 投递进度助手 · Application Monitor

把多家公司的招聘官网投递进度汇总到一张本地网页，保留历史、标记变化，查看岗位的当前阶段和官网原始记录。

**[介绍与下载](https://yuzheng310.github.io/application-monitor/) · [下载完整启动包](https://github.com/yuzheng310/application-monitor/releases/latest)**

## 一键启动

1. 下载与你电脑匹配的 **Release 完整包**，解压整个目录。GitHub 自动生成的 Source code 压缩包只有源码。
2. Windows 双击 `Start.cmd`；macOS 双击 `Start.command`；Linux 运行 `./Start.sh`。
3. 软件自动打开内置浏览器和投递管理网页。点击公司的「官网」完成首次登录，再点击「一键查询全部」。

**无需安装 Python、Node.js、npm、Chrome、OpenCLI 或浏览器扩展。** 这些运行依赖已打包；启动时不运行 pip/npm，也不下载依赖。招聘官网查询需要联网，账号登录和验证码由你本人完成。第一次登录后可复用本机登录状态；登录过期需重新登录。

| 下载包 | 适用系统 |
|---|---|
| `application-monitor-windows-x64.zip` | Windows 10/11，Intel/AMD 64 位 |
| `application-monitor-macos-arm64.tar.gz` | macOS 14+，Apple Silicon |
| `application-monitor-macos-x64.tar.gz` | macOS 14+，Intel |
| `application-monitor-linux-x64.tar.gz` | Ubuntu 22.04/24.04 桌面，Intel/AMD 64 位 |

发布包未购买代码签名证书。macOS 如提示开发者无法验证，可在系统「隐私与安全性」中允许本次打开；Windows 可能提示未知发布者。无需关闭系统安全功能。Linux 需要系统桌面库，极简服务器和其他发行版不保证直接运行。

## 支持的入口

内置 18 个校招或应聘记录入口：百度、MiniMax、得物、快手、滴滴、美团、京东、蚂蚁集团、阿里巴巴、小红书、携程、米哈游、库洛游戏、商汤、同花顺、网易游戏、科大讯飞、小米。

这些是基于本地已有页面验证整理的读取规则，不是招聘网站的官方接口。首次查询并不保证所有站点都成功：未登录、无记录、页面改版或额外验证会明确显示失败或待确认。默认同时查询 4 家，网页可选择 1～8 并发；实际耗时由官网响应决定。不会提交、修改或撤回申请。

网页默认展示非实习岗位，保留已结束的非实习记录。流程名称不代表已完成；只有明确的状态、日期或高亮证据才用于判断。失败不会覆盖上一次成功记录，也不会推断为被拒绝。当前不自动翻页或遍历所有招聘年份，最终结果以官网和 HR 通知为准。

## 并行查询与错误处理（v1.1）

- 默认 4 家并行，页面可选择 1 / 2 / 4 / 6 / 8 家。较慢电脑可降至 2 家；`sites.json` 的 `concurrency` 或 CLI `--workers 1..8` 可设置默认值。
- 每家公司的浏览器会话独立；进度显示正在查询、等待查询、已完成数量和耗时。结果由单个协调线程写入，避免并发覆盖历史。
- 每家公司都可单独查询；「仅重试失败公司」保留其他公司的结果，无需每次重跑全部。
- 登录/验证、网络连接、浏览器离线、读取超时、页面结构变化等错误分别给出原因、处理建议和错误代码。登录失败立即返回，不继续等待页面加载超时。
- 批次启动失败和断连提示单独展示，不会被下一轮状态刷新悄悄覆盖。配置损坏也会明确提示。

## 数据与隐私

软件只监听 `127.0.0.1:18765`。公开网站提供介绍和下载，无法读取你的本地投递记录。内置浏览器使用独立用户目录，不复制日常 Chrome 的登录状态。

| 系统 | 数据目录 |
|---|---|
| Windows | `%LOCALAPPDATA%\ApplicationMonitor` |
| macOS | `~/Library/Application Support/ApplicationMonitor` |
| Linux | `~/.local/share/application-monitor`（或 `$XDG_DATA_HOME/application-monitor`） |

目录中 `sites.json` 是你的站点配置；`data/` 保存结果与日志；`browser/` 保存内置浏览器登录状态；`browser-bridge/` 是本机扩展副本。备份投递记录可复制 `sites.json` 和 `data/`。不要分享整个数据目录，其中浏览器配置可能含登录凭据。卸载软件不会删除数据；需要彻底清除时再手动删除此目录。

升级时下载并解压新包，关闭旧版本网页后启动新版，自动复用上述数据。若旧服务仍占用原端口，启动器会自动选择后续空闲端口，避免误打开旧版本。`APPLICATION_MONITOR_HOME` 可指定独立数据目录。关闭网页不会停止进行中的查询；电脑休眠和浏览器退出会影响查询。

## 定时检查（可选）

默认不开启定时任务，不依赖 Codex。在发布包目录运行 `./ApplicationMonitor watch`（Windows：`ApplicationMonitor.exe watch`），并保持内置浏览器和命令窗口打开。每天北京时间 09:00、12:00、19:00 检查，可在用户 `sites.json` 的 `times` 中调整。Ctrl+C 停止。不自动安装开机任务；网页按钮与定时进程共用进程锁，定时进程运行时不能重复启动检查。

## 开发与构建

源码模式要求 Python 3.9+。`python launcher.py --no-browser` 可启动网页；完整自动查询需要已构建的内置运行环境，或已安装的 OpenCLI 并在用户 `sites.json` 中指定对应 `profile`。推荐普通使用者下载 Release。

```sh
python -m venv .venv
# 激活虚拟环境后：
pip install -r requirements-build.txt
python -m unittest discover -v
python scripts/build.py
```

构建机还需要 Node.js/npm。构建阶段联网下载固定版本的 npm 包、官方 Node 二进制与 Chromium；Node 下载校验官方 SHA-256，npm 使用 lockfile 的 integrity 校验。输出在 `releases/`，每个平台独立构建，不能交叉使用可执行文件。Linux 构建机可先用 `python -m playwright install-deps chromium` 安装桌面测试库。

GitHub Actions 构建四个平台，先执行单元测试、完整包自检和实际 HTTP 启动测试；打 `v*` 标签后，所有构建通过才统一发布 Release。完整包包含依赖许可证和 `VERSIONS.json`。

## 排错

- **浏览器连接失败**：重新双击启动软件，保持内置浏览器打开，稍等扩展连接后重试。
- **需要登录 / 页面发生跳转**：在当前内置浏览器打开对应官网，完成登录后重试。
- **投递区域不存在 / 未找到标识**：官网布局可能变化，携带去除个人信息的错误描述提交 Issue。
- **端口占用**：运行 `ApplicationMonitor --port 18766`；不要关闭不认识的服务。
- **数据在哪**：见上表，网页日志为 `data/web-server.log`，查询日志为 `data/web-query.log`。

本项目代码采用 [MIT](LICENSE)；第三方组件见 [许可证说明](THIRD_PARTY_NOTICES.md)。
