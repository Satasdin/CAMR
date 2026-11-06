import AppKit
import SwiftUI
import WebKit

/// The built-in browser: a page the model wrote, opened beside the chat, in a private web view with no saved data and
/// no way out (see PageView).
@MainActor
final class PreviewCenter: ObservableObject {
    static let shared = PreviewCenter()
    @Published var code: String?
    @Published var phone = false
    @Published var loads = 0
    @Published var problems: [String] = []

    func show(code: String) {
        self.code = code
        problems = []
        loads += 1
    }

    func close() { code = nil }

    weak var web: WKWebView?

    /// The page as drawn now, saved as a PNG (a window's own snapshot leaves web content out).
    func savePage(to url: URL) async {
        guard let web, let image = try? await web.takeSnapshot(configuration: nil),
              let tiff = image.tiffRepresentation, let rep = NSBitmapImageRep(data: tiff) else { return }
        try? rep.representation(using: .png, properties: [:])?.write(to: url)
    }

    /// What the browser holds now, read from the page itself: its title, how much text it shows, its size, whether it
    /// runs off the side, and the images and links that lead nowhere.
    func inspect() async -> String {
        guard let web else { return "{\"error\":\"no page open\"}" }
        let js = """
        JSON.stringify({title: document.title, text: (document.body ? document.body.innerText.length : -1),
          width: window.innerWidth, height: window.innerHeight,
          runsOff: document.documentElement.scrollWidth > window.innerWidth,
          brokenImages: [...document.images].filter(i => i.complete && !i.naturalWidth).map(i => i.src).slice(0, 8),
          deadLinks: [...document.querySelectorAll('a[href^="#"]')].filter(a => a.getAttribute('href').length > 1 && !document.querySelector(a.getAttribute('href'))).map(a => a.getAttribute('href')).slice(0, 8)})
        """
        do {
            return (try await web.evaluateJavaScript(js) as? String) ?? "{}"
        } catch {
            return "{\"error\":\"\(error.localizedDescription)\"}"
        }
    }
}

struct PreviewDock: View {
    @ObservedObject var center: PreviewCenter

    var body: some View {
        if let code = center.code {
            VStack(spacing: 0) {
                HStack(spacing: 10) {
                    Text("PREVIEW").font(Theme.mono(10, .semibold)).foregroundStyle(Theme.memory)
                    Spacer()
                    Picker("", selection: $center.phone) {
                        Text("Desktop").tag(false)
                        Text("Phone").tag(true)
                    }
                    .pickerStyle(.segmented).frame(width: 150).labelsHidden()
                    Button { center.loads += 1 } label: { Image(systemName: "arrow.clockwise") }
                        .buttonStyle(.plain).foregroundStyle(Theme.dim).help("Load the page again")
                    Button { center.close() } label: { Image(systemName: "xmark") }
                        .buttonStyle(.plain).foregroundStyle(Theme.dim).help("Close the preview")
                }
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Theme.panel)
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
            }
            .frame(width: 620)
            .frame(maxHeight: .infinity)
            .background(Theme.ink)
            .overlay(alignment: .leading) { Rectangle().fill(Theme.line).frame(width: 1) }
        }
    }
}

/// A page a model wrote is untrusted, and it may run scripts. So it runs shut in: a content rule list (in place before
/// anything loads; if it cannot be compiled, nothing loads), a content security policy in the page, WebRTC removed
/// before the page's script runs, and no navigating away. These are layers inside a process that does have network
/// access, not a boundary around it: what they stop is what was tried against them.
struct PageView: NSViewRepresentable {
    let code: String
    let loads: Int
    let center: PreviewCenter

    static let blocked = """
    [{"trigger":{"url-filter":"^https?://"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^wss?://"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^file:"},"action":{"type":"block"}},
     {"trigger":{"url-filter":"^ftp://"},"action":{"type":"block"}}]
    """
    static let policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
        + "font-src data:; media-src data:; base-uri 'none'; form-action 'none'; frame-src 'none'"

    /// The page with the policy as the first thing in its head, so it covers everything after it.
    static func shutIn(_ html: String) -> String {
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
        var failed = false
        var waiting: String?
        var ownLoad = false  // the one load this app starts; a page's own navigation is not it
        weak var center: PreviewCenter?

        func open(_ code: String, in web: WKWebView) {
            guard ready else {
                waiting = code
                return
            }
            ownLoad = true
            web.loadHTMLString(PageView.shutIn(code), baseURL: nil)
        }

        private func sansFragment(_ url: URL?) -> String? {
            guard let url, var c = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return nil }
            c.fragment = nil
            return c.string
        }

        func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction,
                     decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
            guard a.targetFrame?.isMainFrame == true else {  // frames, and new windows
                decisionHandler(.cancel)
                return
            }
            if ownLoad {
                ownLoad = false
                decisionHandler(.allow)
                return
            }
            // a jump inside this same page; a fragment alone proves nothing, as any address can carry one
            let same = a.request.url?.fragment != nil && sansFragment(a.request.url) == sansFragment(w.url)
            decisionHandler(same ? .allow : .cancel)
        }

        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
            guard let text = m.body as? String else { return }  // the page writes this: kept short, and few
            let center = center
            let line = String(text.prefix(200))
            Task { @MainActor in
                guard let center, center.problems.count < 20 else { return }
                center.problems.append(line)
            }
        }
    }

    func makeCoordinator() -> Guard { Guard() }

    func makeNSView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.websiteDataStore = .nonPersistent()
        // errors in the page are shown under it, as a browser's console would
        let watch = """
        window.addEventListener('error', function (e) {
          window.webkit.messageHandlers.page.postMessage('error: ' + (e.message || (e.target && (e.target.src || e.target.href)) || 'a resource failed'));
        }, true);
        """
        cfg.userContentController.addUserScript(WKUserScript(source: watch, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        // WebRTC opens connections that neither the rule list nor the page's policy can see: it is gone before any of
        // the page's own script runs, and cannot be put back
        let noPeers = """
        for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection', 'RTCDataChannel', 'RTCSessionDescription',
                            'RTCIceCandidate', 'WebTransport']) {
          try { Object.defineProperty(window, name, {value: undefined, writable: false, configurable: false}); } catch (e) {}
        }
        """
        cfg.userContentController.addUserScript(WKUserScript(source: noPeers, injectionTime: .atDocumentStart, forMainFrameOnly: false))
        cfg.userContentController.add(context.coordinator, name: "page")
        let web = WKWebView(frame: .zero, configuration: cfg)
        let guardian = context.coordinator
        web.navigationDelegate = guardian
        guardian.center = center
        center.web = web
        WKContentRuleListStore.default().compileContentRuleList(forIdentifier: "camr-preview-shut-in",
                                                                 encodedContentRuleList: PageView.blocked) { list, error in
            guard let list, error == nil else {
                guardian.failed = true
                guardian.center?.problems.append("The preview could not be shut off from the network, so nothing was loaded.")
                return
            }
            cfg.userContentController.add(list)
            web.configuration.userContentController.add(list)
            guardian.ready = true
            if let code = guardian.waiting {
                guardian.waiting = nil
                guardian.open(code, in: web)
            }
        }
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {
        guard context.coordinator.loaded != loads else { return }
        context.coordinator.loaded = loads
        context.coordinator.open(code, in: web)
    }
}
