import AppKit
import SwiftUI
import WebKit

/// The built-in browser: a page the model wrote, beside the chat, with the project's files. The same shut-in browser
/// tests the agent's pages for it (PageTester).
@MainActor
final class PreviewCenter: ObservableObject {
    static let shared = PreviewCenter()
    @Published var code: String?
    @Published var phone = false
    @Published var loads = 0
    @Published var problems: [String] = []
    @Published var scripts = false {  // a page's own scripts: off until the person turns them on, for this exact page
        didSet { if scripts != oldValue { loads += 1 } }
    }
    /// The agent may run its own page's scripts when it tests the page (to press its buttons and see what changes).
    /// Off unless the person turns it on; it stays as they set it, as it is about the agent, not one page.
    @Published var agentScripts = UserDefaults.standard.bool(forKey: "camr.agentScripts") {
        didSet { UserDefaults.standard.set(agentScripts, forKey: "camr.agentScripts") }
    }
    var agentScriptsThisRun = false  // set by a test script: for this launch only, never saved in the person's settings
    @Published var tab = "page"
    @Published var files: [String] = []
    @Published var openPath: String?
    @Published var openText = ""
    var project: String?
    var readFile: ((String) async -> String?)?
    weak var web: WKWebView?

    var hasScripts: Bool { code?.range(of: "<script", options: .caseInsensitive) != nil }

    /// A document the agent made: its PDF (made here) and its Word file, shown in the PDF and Word tabs.
    @Published var pdf: URL?
    @Published var docx: URL?
    @Published var docVersion = 0

    func show(pdf: URL?, docx: URL?, project: String? = nil) {
        self.pdf = pdf
        self.docx = docx
        self.project = project
        docVersion += 1
        tab = pdf != nil ? "pdf" : docx != nil ? "word" : tab
    }

    func show(code: String, project: String? = nil) {
        if code != self.code { scripts = false }  // agreeing to run one page is not agreeing to run the next
        self.project = project
        self.code = code
        problems = []
        loads += 1
    }

    func close() {
        pdf = nil
        docx = nil
        code = nil
        project = nil
        files = []
        openPath = nil
    }

    func open(file: String) {
        openPath = file
        Task { openText = await readFile?(file) ?? "(could not read \(file))" }
    }

    /// The page as drawn now, saved as a PNG (a window's own snapshot leaves web content out).
    func savePage(to url: URL) async {
        guard let web, let image = try? await web.takeSnapshot(configuration: nil),
              let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff) else { return }
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }

    func inspect() async -> String {
        guard let web else { return "{\"error\":\"no page open\"}" }
        return (try? await web.evaluateJavaScript(PageTester.report, contentWorld: .defaultClient) as? String) ?? "{}"
    }
}

struct PreviewDock: View {
    @ObservedObject var center: PreviewCenter

    var body: some View {
        if center.code != nil || center.pdf != nil || center.docx != nil {
            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    Picker("", selection: $center.tab) {
                        if center.pdf != nil { Text("PDF").tag("pdf") }
                        if center.docx != nil { Text("Word").tag("word") }
                        if center.code != nil { Text("Page").tag("page") }
                        Text("Files \(center.files.count)").tag("files")
                    }
                    .pickerStyle(.segmented).frame(width: center.pdf != nil ? 230 : 130).labelsHidden()
                    if center.tab == "pdf" || center.tab == "word", let f = center.tab == "pdf" ? center.pdf : center.docx {
                        Button { NSWorkspace.shared.open(f) } label: { Label("Open", systemImage: "arrow.up.forward.app") }
                            .buttonStyle(.plain).font(Theme.mono(10)).foregroundStyle(Theme.dim)
                            .help("Open \(f.lastPathComponent) in its own app")
                    }
                    Spacer()
                    if center.tab == "page" {
                        Picker("", selection: $center.phone) {
                            Text("Desktop").tag(false)
                            Text("Phone").tag(true)
                        }
                        .pickerStyle(.segmented).frame(width: 140).labelsHidden()
                        Toggle("Scripts", isOn: $center.scripts)
                            .toggleStyle(.checkbox).font(Theme.mono(10))
                            .foregroundStyle(center.scripts ? Theme.error : Theme.dim)
                            .help("Run this version of the page's scripts. They are off because a model wrote them, and they go off again when the page changes. With them on, the page is limited but not fully sealed off from the network.")
                        Toggle("Agent tests", isOn: $center.agentScripts)
                            .toggleStyle(.checkbox).font(Theme.mono(10))
                            .foregroundStyle(center.agentScripts ? Theme.error : Theme.dim)
                            .help("Let the agent run its page's scripts when it tests the page, so it can press the buttons and see whether anything changes. The page runs shut in, as with Scripts: limited, but not fully sealed off from the network.")
                        Button { center.loads += 1 } label: { Image(systemName: "arrow.clockwise") }
                            .buttonStyle(.plain).foregroundStyle(Theme.dim).help("Load the page again")
                    }
                    Button { center.close() } label: { Image(systemName: "xmark") }
                        .buttonStyle(.plain).foregroundStyle(Theme.dim).help("Close")
                }
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Theme.panel)
                if center.tab == "pdf", let f = center.pdf {
                    PDFPane(url: f, version: center.docVersion).frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if center.tab == "word", let f = center.docx {
                    QuickLookPane(url: f, version: center.docVersion).frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if center.tab == "page", let code = center.code {
                    if center.hasScripts && !center.scripts {
                        Text("This page has scripts, which are off. Tick Scripts to run them.")
                            .font(Theme.mono(10)).foregroundStyle(Theme.model)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 12).padding(.vertical, 5).background(Theme.panel)
                    }
                    PageView(code: code, loads: center.loads, center: center)
                        .frame(maxWidth: center.phone ? 375 : .infinity)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color.black)
                    if !center.problems.isEmpty {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(center.problems.prefix(4), id: \.self) { p in
                                Text(p).font(Theme.mono(10)).foregroundStyle(Theme.error).lineLimit(2)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(8).background(Theme.panel)
                    }
                } else {
                    filesTab
                }
            }
            .frame(width: 620)
            .frame(maxHeight: .infinity)
            .background(Theme.ink)
            .overlay(alignment: .leading) { Rectangle().fill(Theme.line).frame(width: 1) }
        }
    }

    private var filesTab: some View {
        VStack(alignment: .leading, spacing: 0) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(center.files, id: \.self) { f in
                        Button(f) { center.open(file: f) }
                            .buttonStyle(.plain).font(Theme.mono(11))
                            .foregroundStyle(center.openPath == f ? Theme.memory : Theme.dim)
                            .padding(.horizontal, 8).padding(.vertical, 5)
                            .background(RoundedRectangle(cornerRadius: 6).fill(center.openPath == f ? Theme.panel : .clear))
                    }
                }
                .padding(8)
            }
            Rectangle().fill(Theme.line).frame(height: 1)
            ScrollView([.vertical, .horizontal]) {
                Text(center.openPath == nil ? "Choose a file." : center.openText)
                    .font(Theme.mono(12)).foregroundStyle(Color.white.opacity(0.88))
                    .textSelection(.enabled)
                    .fixedSize(horizontal: true, vertical: true)
                    .padding(12)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }
}

/// A page a model wrote is untrusted. Its scripts are off unless the person turns them on. It also runs behind a
/// content rule list (in place before anything loads; if it cannot be compiled, nothing loads), a content security
/// policy in the page, and no navigating away. With scripts on, WebRTC is also taken off the page, which narrows what
/// a script can do but is not a boundary: the process has network access.
enum ShutIn {
    static let blocked = """
    [{"trigger":{"url-filter":"^https?://"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^wss?://"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^file:"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^ftp://"},"action":{"type":"block"}}]
    """
    static let origin = URL(string: "https://page.camr.invalid/")
    static let policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
        + "font-src data:; media-src data:; base-uri 'none'; form-action 'none'; frame-src 'none'"

    /// The page with the policy as the first thing in its head, so it covers everything after it.
    static func page(_ html: String) -> String {
        let meta = "<meta http-equiv=\"Content-Security-Policy\" content=\"\(policy)\">"
        if let r = html.range(of: #"<head(\s[^>]*)?>"#, options: [.regularExpression, .caseInsensitive]) {
            return html.replacingCharacters(in: r, with: html[r] + meta)
        }
        if let r = html.range(of: #"<html(\s[^>]*)?>"#, options: [.regularExpression, .caseInsensitive]) {
            return html.replacingCharacters(in: r, with: html[r] + "<head>" + meta + "</head>")
        }
        return "<!doctype html><head>" + meta + "</head>" + html
    }

    final class Guard: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var loaded = -1
        var ready = false
        var waiting: String?
        var ownLoad = false  // the one load this app starts; a page's own navigation is not it
        var scripts: @MainActor () -> Bool = { false }
        var problem: @MainActor (String) -> Void = { _ in }
        var finished: (@MainActor () -> Void)?

        func open(_ code: String, in web: WKWebView) {
            guard ready else {
                waiting = code
                return
            }
            ownLoad = true
            // a fixed address that never resolves (.invalid), so the page has an origin of its own: with none, WebKit
            // hides every script error as "Script error." and nothing can be fixed from it. The policy still lets
            // nothing load, and navigating away is still refused
            web.loadHTMLString(ShutIn.page(code), baseURL: ShutIn.origin)
        }

        private func sansFragment(_ url: URL?) -> String? {
            guard let url, var c = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return nil }
            c.fragment = nil
            return c.string
        }

        func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, preferences: WKWebpagePreferences,
                     decisionHandler: @escaping @MainActor (WKNavigationActionPolicy, WKWebpagePreferences) -> Void) {
            preferences.allowsContentJavaScript = MainActor.assumeIsolated { scripts() }
            guard a.targetFrame?.isMainFrame == true else {  // frames, and new windows
                decisionHandler(.cancel, preferences)
                return
            }
            if ownLoad {
                ownLoad = false
                decisionHandler(.allow, preferences)
                return
            }
            // a jump inside this same page; a fragment alone proves nothing, as any address can carry one
            let same = a.request.url?.fragment != nil && sansFragment(a.request.url) == sansFragment(w.url)
            decisionHandler(same ? .allow : .cancel, preferences)
        }

        func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
            MainActor.assumeIsolated { finished?() }
        }

        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
            guard let text = m.body as? String else { return }  // the page writes this: kept short
            let line = String(text.prefix(200))
            MainActor.assumeIsolated { problem(line) }
        }
    }

    static func web(_ guardian: Guard, frame: NSRect = .zero) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()
        // errors in the page are reported, as a browser's console would
        let watch = """
        window.addEventListener('error', function (e) {
          window.webkit.messageHandlers.page.postMessage('error: ' + (e.message || (e.target && (e.target.src || e.target.href)) || 'a resource failed'));
        }, true);
        """
        cfg.userContentController.addUserScript(WKUserScript(source: watch, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        // WebRTC opens connections that neither the rule list nor the page's policy can see. Taken off the page before
        // its script runs; that does not reach every way a script could get at it, which is why scripts start off
        let noPeers = """
        for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'RTCSessionDescription',
                            'RTCIceCandidate', 'WebTransport']) {
          try { Object.defineProperty(window, name, {value: undefined, writable: false, configurable: false}); } catch (e) {}
        }
        """
        cfg.userContentController.addUserScript(WKUserScript(source: noPeers, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        cfg.userContentController.add(guardian, name: "page")
        let web = WKWebView(frame: frame, configuration: cfg)
        web.navigationDelegate = guardian
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "camr-preview-shut-in",
                                                                 encodedContentRuleList: blocked) { list, error in
            guard let list, error == nil else {
                MainActor.assumeIsolated { guardian.problem("The page could not be shut off from the network, so nothing was loaded.") }
                return
            }
            web.configuration.userContentController.add(list)
            guardian.ready = true
            if let code = guardian.waiting {
                guardian.waiting = nil
                guardian.open(code, in: web)
            }
        }
        return web
    }
}

struct PageView: NSViewRepresentable {
    let code: String
    let loads: Int
    let center: PreviewCenter

    func makeCoordinator() -> ShutIn.Guard { ShutIn.Guard() }

    func makeNSView(context: Context) -> WKWebView {
        let guardian = context.coordinator
        guardian.scripts = { [weak center] in center?.scripts ?? false }
        guardian.problem = { [weak center] line in
            guard let center, center.problems.count < 20 else { return }
            center.problems.append(line)
        }
        let web = ShutIn.web(guardian)
        center.web = web
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {
        guard context.coordinator.loaded != loads else { return }
        context.coordinator.loaded = loads
        context.coordinator.open(code, in: web)
    }
}

/// The agent's browser: opens a page shut in, at a phone's width, and reports what it finds, so the model can read it.
@MainActor
final class PageTester {
    static let report = """
    JSON.stringify({title: document.title, text: (document.body ? document.body.innerText.slice(0, 8000) : ''),
      truncated: !!document.body && document.body.innerText.length > 8000,
      hasScripts: document.scripts.length > 0,
      width: window.innerWidth, runsOff: document.documentElement.scrollWidth > window.innerWidth + 1,
      brokenImages: [...document.images].filter(i => i.complete && !i.naturalWidth).map(i => i.getAttribute('src')).slice(0, 8),
      deadLinks: [...document.querySelectorAll('a[href^="#"]')].filter(a => a.getAttribute('href').length > 1 && !document.getElementById(a.getAttribute('href').slice(1))).map(a => a.getAttribute('href')).slice(0, 8)})
    """
    private var keep: [AnyObject] = []

    func test(html: String, scripts: Bool) async -> [String: Any] {
        let guardian = ShutIn.Guard()
        var errors: [String] = []
        guardian.scripts = { scripts }
        guardian.problem = { line in if errors.count < 10 { errors.append(line) } }
        let web = ShutIn.web(guardian, frame: NSRect(x: 0, y: 0, width: 375, height: 800))
        keep = [guardian, web]
        defer { keep = [] }
        var done = false
        guardian.finished = { done = true }
        guardian.open(html, in: web)
        for _ in 0..<80 where !done { try? await Task.sleep(nanoseconds: 100_000_000) }
        try? await Task.sleep(nanoseconds: 800_000_000)  // the page's own start-up
        // read from the source: with scripts off, a page has no script elements to count
        var out: [String: Any] = ["loaded": done, "scriptsRan": scripts,
                                  "hasScripts": html.range(of: "<script", options: .caseInsensitive) != nil]
        // in a world of its own, so a page's scripts cannot replace what the report uses to read the page
        if let s = try? await web.evaluateJavaScript(PageTester.report, contentWorld: .defaultClient) as? String, let d = s.data(using: .utf8),
           let got = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            out.merge(got) { a, _ in a }
            if scripts { out["failed"] = await clickEverything(web) }
        }
        out["errors"] = errors
        return out
    }
}

extension PageTester {
    /// With scripts allowed, it presses each button, as a person would, and notes any that changes nothing on the page.
    private func clickEverything(_ web: WKWebView) async -> [String] {
        let js = """
        JSON.stringify([...document.querySelectorAll('button')].slice(0, 12).map(b => {
          const before = document.body.innerText; b.click();
          return {label: (b.innerText || b.id || 'a button').slice(0, 40), changed: document.body.innerText !== before};
        }))
        """
        guard let s = try? await web.evaluateJavaScript(js, contentWorld: .defaultClient) as? String, let d = s.data(using: .utf8),
              let rows = try? JSONSerialization.jsonObject(with: d) as? [[String: Any]] else { return [] }
        return rows.filter { ($0["changed"] as? Bool) == false }.map { "pressing \"\($0.str("label") ?? "a button")\" changed nothing" }
    }
}

/// A project's page as one document: the browser is shut off from the disk, so its stylesheets and scripts go inside.
enum ProjectPage {
    static func inline(_ html: String, read: (String) async -> String?) async -> (page: String, missing: [String]) {
        var page = html
        var missing: [String] = []
        var deferred: [String] = []
        for (pattern, open, close, end) in [
            (#"<link\b[^>]*href=["']([^"':]+\.css)["'][^>]*>"#, "<style>", "</style>", "</style"),
            (#"<script\b[^>]*src=["']([^"':]+\.js)["'][^>]*>\s*</script>"#, "<script>", "</script>", "</script")] {
            guard let re = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else { continue }
            let found = re.matches(in: page, range: NSRange(page.startIndex..., in: page)).reversed()
            for m in found {
                guard let whole = Range(m.range, in: page), let name = Range(m.range(at: 1), in: page) else { continue }
                let path = String(page[name])
                if let text = await read(path) {
                    let safe = text.replacingOccurrences(of: end, with: "<\\/" + end.dropFirst(2), options: .caseInsensitive)
                    let tag = page[whole].lowercased()
                    if open == "<script>", tag.contains("defer") || tag.contains("type=\"module\"") || tag.contains("type='module'") {
                        // a deferred script runs once the page is read: inlined where it stood (often the head), it
                        // would run before the elements it looks for exist, so it goes at the end of the body instead
                        page.replaceSubrange(whole, with: "")
                        deferred.insert(open + safe + close, at: 0)  // matches come last first; deferred ones run in order
                    } else {
                        page.replaceSubrange(whole, with: open + safe + close)
                    }
                } else {
                    missing.append(path)
                }
            }
        }
        if !deferred.isEmpty {
            if let body = page.range(of: "</body>", options: [.caseInsensitive, .backwards]) {
                page.insert(contentsOf: deferred.joined(), at: body.lowerBound)
            } else {
                page += deferred.joined()
            }
        }
        return (page, missing)
    }
}
