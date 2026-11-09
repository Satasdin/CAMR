// The built-in browser: for code previews and for research helpers that need to see a page. A WKWebView with an
// address field, back and forward. It keeps its own website data, apart from Safari's.

import SwiftUI
import WebKit

@MainActor
final class BrowserModel: ObservableObject {
    @Published var address = "https://en.wikipedia.org/wiki/Mount_Kenya"
    @Published var title = ""
    @Published var canGoBack = false
    @Published var canGoForward = false
    @Published var loading = false
    @Published var progress = 0.0
    let web: WKWebView
    private var watching: NSKeyValueObservation?

    init() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        web = WKWebView(frame: .zero, configuration: config)
        web.allowsBackForwardNavigationGestures = true
        watching = web.observe(\.estimatedProgress) { [weak self] view, _ in
            let done = view.estimatedProgress
            Task { @MainActor in self?.progress = done }
        }
    }

    func go(_ text: String) {
        var s = text.trimmingCharacters(in: .whitespaces)
        if s.isEmpty { return }
        if !s.contains("://") {
            if s.contains(".") && !s.contains(" ") {
                s = (s.hasPrefix("localhost") || s.hasPrefix("127.0.0.1") ? "http://" : "https://") + s
            } else {
                s = "https://duckduckgo.com/?q=" + (s.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? s)
            }
        }
        guard let url = URL(string: s) else { return }
        web.load(URLRequest(url: url))
    }

    func sync() {
        title = web.title ?? ""
        address = web.url?.absoluteString ?? address
        canGoBack = web.canGoBack
        canGoForward = web.canGoForward
        loading = web.isLoading
    }
}

struct WebView: NSViewRepresentable {
    let model: BrowserModel

    func makeCoordinator() -> Coordinator { Coordinator(model: model) }

    func makeNSView(context: Context) -> WKWebView {
        model.web.navigationDelegate = context.coordinator
        return model.web
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let model: BrowserModel
        init(model: BrowserModel) { self.model = model }
        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            Task { @MainActor in model.sync() }
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            Task { @MainActor in model.sync() }
        }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            Task { @MainActor in model.sync() }
        }
    }
}

struct BrowserView: View {
    @ObservedObject var model: BrowserModel
    @State private var typed = ""

    var body: some View {
        WebView(model: model)
            .overlay(alignment: .top) {  // how much of the page has arrived
                if model.loading {
                    GeometryReader { g in
                        Rectangle().fill(Color.white.opacity(0.85)).frame(width: g.size.width * model.progress, height: 2)
                            .animation(.easeOut(duration: 0.2), value: model.progress)
                    }
                    .frame(height: 2)
                    .transition(.opacity)
                }
            }
            .navigationTitle(model.title.isEmpty ? "Browser" : model.title)
            .toolbar {
                ToolbarItemGroup(placement: .navigation) {
                    Button { model.web.goBack() } label: { Image(systemName: "chevron.left") }
                        .disabled(!model.canGoBack).help("Back")
                    Button { model.web.goForward() } label: { Image(systemName: "chevron.right") }
                        .disabled(!model.canGoForward).help("Forward")
                }
                ToolbarItem(placement: .principal) {
                    TextField("Search or enter an address", text: $typed)
                        .textFieldStyle(.roundedBorder)
                        .frame(minWidth: 320, idealWidth: 520)
                        .onSubmit { model.go(typed) }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button { if model.loading { model.web.stopLoading() } else { model.web.reload() } } label: {
                        Image(systemName: model.loading ? "xmark" : "arrow.clockwise")
                    }
                    .help(model.loading ? "Stop" : "Reload")
                }
            }
            .onAppear {
                typed = model.address
                if model.web.url == nil { model.go(model.address) }
            }
            .onChange(of: model.address) { _, a in typed = a }
    }
}
