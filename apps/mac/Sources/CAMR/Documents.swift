import AppKit
import PDFKit
import Quartz
import SwiftUI
import WebKit

/// A document the agent made: the engine writes its Word file and a page for print; the app prints that page to a PDF
/// with WebKit's own print (A4 pages, the page's styles), and shows the PDF and the Word file beside the chat.
@MainActor
enum DocumentPDF {
    static let MAX_PAGES = 40
    static let MAX_BYTES = 50_000_000
    /// The PDF of a print page, written to `out`. The page is the engine's, made by rule from the model's Markdown
    /// (escaped, no scripts); it is still loaded with scripts off and nothing allowed to load.
    static func make(html: String, out: URL) async -> Bool {
        // the same shut-in browser as every page a model wrote: the rule list, the policy, no navigating, scripts off
        let guardian = ShutIn.Guard()
        guardian.scripts = { false }
        var done = false
        guardian.finished = { done = true }
        let web = ShutIn.web(guardian, frame: NSRect(x: 0, y: 0, width: 794, height: 1123))
        guardian.open(html, in: web)
        for _ in 0..<80 where !done { try? await Task.sleep(nanoseconds: 100_000_000) }
        guard done else { return false }
        // WebKit's print loop ran away once (a 15.7 GB file): the page is cut into A4-shaped slices instead, each made
        // with WebKit's own PDF, at most MAX_PAGES of them, and the file is checked before it is kept
        let pageH: CGFloat = 1123, pageW: CGFloat = 794  // A4 at 96 dpi
        web.frame = NSRect(x: 0, y: 0, width: pageW, height: pageH)
        // where each block ends (headings, paragraphs, list items, table rows), so no page cuts through one
        let js = "JSON.stringify({h: document.documentElement.scrollHeight, ends: [...document.querySelectorAll('h1,h2,h3,p,li,tr,.page-break')].map(e => [Math.ceil(e.getBoundingClientRect().bottom + window.scrollY), e.classList.contains('page-break') ? 1 : 0])})"
        var height = pageH
        var ends: [(CGFloat, Bool)] = []
        if let s = try? await web.evaluateJavaScript(js, contentWorld: .defaultClient) as? String,
           let d = s.data(using: .utf8), let got = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            height = CGFloat((got["h"] as? Double) ?? Double(pageH))
            ends = ((got["ends"] as? [[Double]]) ?? []).map { (CGFloat($0[0]), $0.count > 1 && $0[1] == 1) }
        }
        var cuts: [CGFloat] = [0]
        while let top = cuts.last, top + 1 < height, cuts.count <= MAX_PAGES {
            let limit = top + pageH - 60  // a margin at the foot of each page
            let forced = ends.first { $0.1 && $0.0 > top + 1 && $0.0 <= limit }?.0
            let fit = ends.filter { $0.0 > top + 1 && $0.0 <= limit }.map(\.0).max()
            cuts.append(forced ?? fit ?? min(limit, height))
        }
        if cuts.last! < height { cuts.append(height) }
        web.frame = NSRect(x: 0, y: 0, width: pageW, height: max(height, pageH))
        let doc = PDFDocument()
        for (a, b) in zip(cuts, cuts.dropFirst()).prefix(MAX_PAGES) {
            let c = WKPDFConfiguration()
            c.rect = CGRect(x: 0, y: a, width: pageW, height: b - a)
            guard let data = try? await web.pdf(configuration: c), let one = PDFDocument(data: data),
                  let page = one.page(at: 0) else { return false }
            // every page A4-shaped at this width, the slice at its top below a small margin; printing scales it to A4
            let h = page.bounds(for: .mediaBox).height
            page.setBounds(CGRect(x: 0, y: h + 48 - pageH, width: pageW, height: pageH), for: .mediaBox)
            doc.insert(page, at: doc.pageCount)
        }
        guard let data = doc.dataRepresentation(), data.count < MAX_BYTES else { return false }
        return (try? data.write(to: out, options: .atomic)) != nil
    }

}

/// A PDF, as Preview shows one.
struct PDFPane: NSViewRepresentable {
    let url: URL
    let version: Int

    func makeNSView(context: Context) -> PDFView {
        let v = PDFView()
        v.autoScales = true
        v.displayMode = .singlePageContinuous
        v.backgroundColor = NSColor(white: 0.12, alpha: 1)
        v.document = PDFDocument(url: url)
        return v
    }

    func updateNSView(_ v: PDFView, context: Context) {
        if context.coordinator.shown != version {
            context.coordinator.shown = version
            v.document = PDFDocument(url: url)
        }
    }

    func makeCoordinator() -> Shown { Shown() }
    final class Shown { var shown = -1 }
}

/// Any file Quick Look can show (a Word file here), as Finder's preview shows it.
struct QuickLookPane: NSViewRepresentable {
    let url: URL
    let version: Int

    func makeNSView(context: Context) -> QLPreviewView {
        let v = QLPreviewView(frame: .zero, style: .normal)!
        v.autostarts = true
        v.previewItem = url as NSURL
        return v
    }

    func updateNSView(_ v: QLPreviewView, context: Context) {
        v.previewItem = nil
        v.previewItem = url as NSURL
    }
}
