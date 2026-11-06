import AppKit
import SwiftUI
import WebKit

/// The built-in browser: a page the model wrote, opened beside the chat. It runs in a private web view with no saved
/// data and no way out: only the page itself loads; a link it holds is not followed.
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

struct PageView: NSViewRepresentable {
    let code: String
    let loads: Int
    let center: PreviewCenter

    final class Guard: NSObject, WKNavigationDelegate, WKScriptMessageHandler {
        var loaded = -1
        weak var center: PreviewCenter?

        func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction,
                     decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void) {
            // the page itself, and jumps inside it; nothing the page links to is opened
            let inside = a.navigationType == .other || a.request.url?.fragment != nil
            decisionHandler(inside ? .allow : .cancel)
        }

        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
            guard let text = m.body as? String else { return }
            let center = center
            Task { @MainActor in center?.problems.append(text) }
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
        cfg.userContentController.add(context.coordinator, name: "page")
        let web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = context.coordinator
        context.coordinator.center = center
        center.web = web
        return web
    }

    func updateNSView(_ web: WKWebView, context: Context) {
        guard context.coordinator.loaded != loads else { return }
        context.coordinator.loaded = loads
        web.loadHTMLString(code, baseURL: nil)
    }
}
