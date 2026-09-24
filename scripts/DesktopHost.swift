import Cocoa
import WebKit

final class DesktopHost: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var label: NSTextField!
    var attempts = 0
    var launched = false
    var loading = false
    let info = Bundle.main.infoDictionary ?? [:]
    var home: URL { URL(string: info["MonitorURL"] as? String ?? "http://127.0.0.1:18765/")! }
    func command(_ key: String) -> [String] {
        if let custom = info[key] as? [String] { return custom }
        let backend = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("ApplicationMonitor").path
        return key == "MonitorBackend" ? [backend, "--no-browser", "--query-browser"] : [backend, "--open-url"]
    }
    func launch(_ arguments: [String]) throws {
        guard let path = arguments.first else { return }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: path)
        process.arguments = Array(arguments.dropFirst())
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        try process.run()
    }
    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appMenu = NSMenuItem(); menu.addItem(appMenu)
        appMenu.submenu = NSMenu()
        appMenu.submenu?.addItem(withTitle: "退出投递进度助手", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let edit = NSMenuItem(); menu.addItem(edit); edit.submenu = NSMenu(title: "编辑")
        for (title, selector, key) in [("撤销", "undo:", "z"), ("剪切", "cut:", "x"), ("复制", "copy:", "c"), ("粘贴", "paste:", "v"), ("全选", "selectAll:", "a")] {
            edit.submenu?.addItem(withTitle: title, action: Selector(selector), keyEquivalent: key)
        }
        let view = NSMenuItem(); menu.addItem(view); view.submenu = NSMenu(title: "显示")
        view.submenu?.addItem(withTitle: "刷新", action: #selector(reload), keyEquivalent: "r")
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 900), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "投递进度助手"
        window.minSize = NSSize(width: 480, height: 500)
        window.isReleasedWhenClosed = false
        window.center()
        web = WKWebView(frame: window.contentView!.bounds)
        web.autoresizingMask = [.width, .height]
        web.navigationDelegate = self
        web.uiDelegate = self
        window.contentView?.addSubview(web)
        label = NSTextField(labelWithString: "正在启动投递进度助手…")
        label.frame = NSRect(x: 30, y: 40, width: 650, height: 40)
        label.autoresizingMask = [.maxXMargin, .maxYMargin]
        window.contentView?.addSubview(label)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        connect()
    }
    @objc func reload() { if web.url == nil { connect() } else { web.reload() } }
    func connect() {
        guard !loading else { return }
        loading = true
        var request = URLRequest(url: home.appendingPathComponent("api/status"))
        request.timeoutInterval = 2
        URLSession.shared.dataTask(with: request) { data, response, error in
            let status = (response as? HTTPURLResponse)?.statusCode
            let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [String: Any]
            let marker = json?["app"] as? String
            let healthy = status == 200 && ["application-monitor", "application-monitor-public"].contains(marker ?? "")
            DispatchQueue.main.async {
                self.loading = false
                if healthy {
                    self.attempts = 0
                    self.web.load(URLRequest(url: self.home))
                    return
                }
                if response != nil && !healthy {
                    self.showFailure("本地服务没有返回有效的投递看板，请检查端口或服务日志。")
                    return
                }
                if !self.launched {
                    self.launched = true
                    do { try self.launch(self.command("MonitorBackend")) }
                    catch { self.showFailure("无法启动本地服务：\(error.localizedDescription)"); return }
                }
                self.attempts += 1
                if self.attempts >= 30 { self.showFailure("本地服务启动超时，请检查本地服务日志后重试。"); return }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { self.connect() }
            }
        }.resume()
    }
    func showFailure(_ message: String) {
        label.stringValue = "启动未完成，可以重试。"
        label.isHidden = false
        let alert = NSAlert(); alert.messageText = "投递进度助手未能加载"; alert.informativeText = message
        alert.addButton(withTitle: "重试"); alert.addButton(withTitle: "退出")
        alert.beginSheetModal(for: window) { response in
            if response == .alertFirstButtonReturn { self.attempts = 0; self.launched = false; self.connect() }
            else { NSApp.terminate(nil) }
        }
    }
    func external(_ url: URL) {
        guard ["https", "http"].contains(url.scheme ?? "") else { return }
        do { try launch(command("MonitorBrowser") + [url.absoluteString]) }
        catch { showFailure("无法打开官网：\(error.localizedDescription)") }
    }
    func local(_ url: URL) -> Bool { url.scheme == home.scheme && url.host == home.host && url.port == home.port }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if local(url) { decisionHandler(.allow) }
        else { external(url); decisionHandler(.cancel) }
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url { if local(url) { web.load(URLRequest(url: url)) } else { external(url) } }
        return nil
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { label.isHidden = true }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled { showFailure("页面加载失败：\(error.localizedDescription)") }
    }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { webView.reload() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = DesktopHost()
application.delegate = delegate
application.run()
