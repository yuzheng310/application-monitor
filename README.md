<p align="center"><img src="docs/assets/icon.svg" width="88" height="88" alt="投递进度助手图标"></p>
<h1 align="center">投递进度助手</h1>
<p align="center">Application Monitor · 少开几个标签页，不错过下一步。</p>
<p align="center">把分散在招聘官网的投递记录，汇总成一张保存在本机的进度看板。</p>
<p align="center"><a href="https://github.com/yuzheng310/application-monitor/releases/latest">下载完整启动包</a> · <a href="https://yuzheng310.github.io/application-monitor/demo/">体验虚构数据演示</a> · <a href="AI_USAGE.md">让 AI 帮你使用</a></p>

## 一眼看到，下一步在哪里

投了多家公司之后，不必反复打开每个招聘网站。查询完成后，面试、笔试、筛选和已结束的岗位会显示在同一页；有变化的公司自动排到前面，原始记录也保留下来供核对。

![桌面产品展示：公司目录、更新标记和岗位时间线](docs/assets/dashboard.png)

> 展示图片与在线演示全部使用虚构公司、岗位和状态，不包含真实求职者的投递记录、账号或浏览器信息。截图展示当前源码能力，可能领先于已发布安装包。

| 你想做什么 | 软件如何帮助你 |
|---|---|
| 快速查看全部进度 | 默认同时查询 4 家，页面可选 1 / 2 / 4 / 6 / 8 家，逐家显示结果与耗时 |
| 找到某家公司 | 左侧目录平滑跳转，顶部留出阅读空隙并轻微提示目标公司；高亮当前公司，窄屏目录移到顶部 |
| 优先看有变化的记录 | 带“记录有更新”标记的公司优先显示，同组内按岗位进度排序 |
| 看懂当前阶段 | 用时间线区分已完成、当前和后续阶段，不把流程名称当成通过证据 |
| 处理查询失败 | 显示原因与处理建议，可重试单家公司或仅重试失败公司 |
| 核对结果 | 展开官网原始记录与本次变化；失败时保留上次成功结果 |

<table><tr><td width="68%"><img src="docs/assets/error-feedback.png" alt="虚构示例：登录错误的处理建议和单公司重试"></td><td width="32%"><img src="docs/assets/mobile.png" alt="虚构示例：手机窄屏下的公司目录和岗位卡片"></td></tr></table>

## 三步开始

1. **下载并完整解压**与你电脑匹配的 [Release 启动包](https://github.com/yuzheng310/application-monitor/releases/latest)。GitHub 的 `Source code` 压缩包仅含源码，不是一键启动包。
2. **打开启动文件**：Windows 双击 `Start.cmd`；macOS 双击 `Start.command`；Linux 运行 `./Start.sh`。
3. **登录后查询**：软件打开内置浏览器。在看板中点击各公司的“官网”，自行完成登录，再回到看板点击“一键查询全部”。

完整包已包含 Python 运行时、Node.js、Chromium、OpenCLI 和浏览器扩展。无需另外安装这些依赖；启动时不运行 pip/npm 或下载依赖。招聘官网查询需要联网，登录与验证码由使用者本人完成。请保持内置浏览器打开。

| 系统 | 下载文件 |
|---|---|
| Windows 10/11 · Intel/AMD 64 位 | `application-monitor-windows-x64.zip` |
| macOS 14+ · Apple Silicon | `application-monitor-macos-arm64.tar.gz` |
| macOS 14+ · Intel | `application-monitor-macos-x64.tar.gz` |
| Ubuntu 22.04/24.04 桌面 · Intel/AMD 64 位 | `application-monitor-linux-x64.tar.gz` |

安装包未购买代码签名证书。macOS 如提示开发者无法验证，可在“隐私与安全性”中允许本次打开；Windows 可能显示未知发布者。无需关闭系统安全功能。Linux 依赖系统桌面库，极简服务器及其他发行版不保证直接运行。

## 已经 clone？让 AI 帮你

把下面这句话交给你常用的 AI 编程助手：

> 请先阅读仓库根目录的 AI_USAGE.md，检查我的系统和现有环境，帮我启动投递进度助手；保留已有配置和记录，告诉我哪些登录步骤需要本人完成，并验证能否查询。

[AI_USAGE.md](AI_USAGE.md) 包含环境判断、源码与安装包启动、配置位置、查询接口、添加公司和排错流程。源码可以直接预览看板，但完整查询仍需要浏览器与 OpenCLI 环境；指南会明确区分“页面能打开”和“查询可用”。

## 支持哪些公司

当前源码提供 **21 个**校招或应聘记录入口：

百度 · MiniMax · 得物 · 快手 · 滴滴 · 美团 · 京东 · 蚂蚁集团 · 阿里巴巴 · 小红书 · 携程 · 米哈游 · 库洛游戏 · 商汤 · 同花顺 · 网易游戏 · 科大讯飞 · 小米 · 小鹏汽车 · Momenta · Shopee。

**版本差异：**v1.1.0 安装包已包含并行查询与错误反馈；小鹏汽车、Momenta、Shopee、更新优先排序、公司目录及本次视觉更新仍属于后续源码更新。现有用户配置不会被新版示例配置自动覆盖，新增公司需合并到自己的 `sites.json`，可让 AI 按指南完成。

读取规则基于招聘网页，不是官方接口。页面改版、登录失效、空记录或额外验证都可能导致查询失败。软件不提交、修改或撤回申请；当前只展示非实习岗位，不自动翻页或遍历所有招聘年份。状态以招聘官网和 HR 通知为准。

## 数据留在哪里

看板只监听本机 `127.0.0.1`，默认端口 `18765`。公开网站只提供介绍、演示和下载，无法读取本地看板的数据。内置浏览器使用独立用户目录，不复制日常 Chrome 的登录状态。

| 系统 | 默认用户数据目录 |
|---|---|
| Windows | `%LOCALAPPDATA%\ApplicationMonitor` |
| macOS | `~/Library/Application Support/ApplicationMonitor` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/application-monitor` |

- `sites.json`：公司入口、并发数、检查时间等配置。
- `data/`：查询结果、变化历史与运行日志。备份记录时复制此目录和 `sites.json`。
- `browser/`：内置浏览器的账号登录状态。不要分享整个用户数据目录。

可用 `APPLICATION_MONITOR_HOME` 指定独立目录。升级时保留用户数据，解压新安装包并启动；关闭网页不等于停止后台服务。卸载程序不会自动删除记录。不要将真实记录、完整日志、Cookie、验证码或带个人参数的链接提交到仓库或 Issue。

## 常见问题

| 现象 | 怎么处理 |
|---|---|
| 需要登录或验证 | 在软件内置浏览器打开该官网，完成登录/验证码，再重试此公司 |
| 未连接到查询浏览器 | 重新启动软件，保持内置浏览器打开，等待扩展连接后重试 |
| 读取超时 / 网络错误 | 确认官网可访问；可降低并发数，仅重试失败公司 |
| 无法识别投递区域 | 确认招聘类别与页面正确；持续失败可能需更新规则，反馈公司名和错误代码即可 |
| 启动包缺少运行文件 | 完整重新解压，不要只移动可执行文件；保留用户数据目录 |
| 端口被占用 | 使用 `ApplicationMonitor --port 18766`，不要关闭不认识的服务 |

查询失败不会覆盖成功记录，也不表示被拒绝。日志位于 `data/web-server.log` 和 `data/web-query.log`，公开反馈前需脱敏。

## 可选：定时检查

启动完整包并保留内置浏览器，然后在包目录运行 `./ApplicationMonitor watch`；Windows 使用 `ApplicationMonitor.exe watch`。默认每天北京时间 09:00、12:00、19:00 检查，时间可在用户配置的 `times` 中调整。

`watch` 会先检查一次，再等待下次时间；Ctrl+C 停止。默认不启用定时任务，也不自动安装开机任务。定时进程持有查询锁，运行时不能同时发起网页或 CLI 查询。电脑休眠、浏览器退出会影响检查。

## 开发与构建

源码看板需要 Python 3.9+：

```sh
python launcher.py --no-browser
```

按命令输出的地址打开网页。这个命令仅启动网页服务，不自动补齐浏览器依赖。需要从源码构建完整包时，在对应目标系统上准备 Python、Node.js/npm，并运行：

```sh
python -m venv .venv
# 先激活虚拟环境，再执行：
python -m pip install -r requirements-build.txt
python -m unittest discover -v
python scripts/build.py
```

构建阶段需要联网获取固定版本依赖，Node 下载检查官方 SHA-256，npm 使用 lockfile 校验。产物位于 `releases/`，不可跨平台使用。Linux 构建机可能需要 `python -m playwright install-deps chromium` 安装桌面库。

GitHub Actions 验证四个平台的构建、自检与启动；推送 `v*` 标签会在构建通过后发布 Release。完整包包含依赖许可证与 `VERSIONS.json`，AI 指南和展示资源也会随下次构建打包。

## 许可证

项目代码与原创图标采用 [MIT](LICENSE)。第三方组件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
