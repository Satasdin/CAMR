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
        // The page is drawn once as one tall PDF, then laid onto real A4 pages here, each page a slice of it cut
        // between blocks (never through a line). WebKit's own print loop ran away once (a 15.7 GB file), so it is
        // not used; at most MAX_PAGES pages and MAX_BYTES are written, and only when whole.
        let pageW: CGFloat = 794  // the page's width in CSS pixels
        let a4 = CGRect(x: 0, y: 0, width: 595.28, height: 841.89), margin: CGFloat = 42
        let scale = (a4.width - 2 * margin) / pageW
        let sliceH = (a4.height - 2 * margin) / scale  // CSS pixels of the page on one A4 page
        web.frame = NSRect(x: 0, y: 0, width: pageW, height: 1123)
        let js = "JSON.stringify({h: document.documentElement.scrollHeight, ends: [...document.querySelectorAll('h1,h2,h3,p,li,tr,.page-break')].map(e => [Math.ceil(e.getBoundingClientRect().bottom + window.scrollY), e.classList.contains('page-break') ? 1 : 0])})"
        var height: CGFloat = 1123
        var ends: [(CGFloat, Bool)] = []
        if let s = try? await web.evaluateJavaScript(js, contentWorld: .defaultClient) as? String,
           let d = s.data(using: .utf8), let got = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            height = CGFloat((got["h"] as? Double) ?? 1123)
            ends = ((got["ends"] as? [[Double]]) ?? []).map { (CGFloat($0[0]), $0.count > 1 && $0[1] == 1) }
        }
        height = min(height, sliceH * CGFloat(MAX_PAGES))
        var cuts: [CGFloat] = [0]
        while let top = cuts.last, top + 1 < height, cuts.count <= MAX_PAGES {
            let limit = top + sliceH
            if limit >= height, !ends.contains(where: { $0.1 && $0.0 > top + 1 && $0.0 < height - 1 }) {
                cuts.append(height)  // the rest fits on this page
                break
            }
            let forced = ends.first { $0.1 && $0.0 > top + 1 && $0.0 <= limit }?.0
            let fit = ends.filter { $0.0 > top + 1 && $0.0 <= limit }.map(\.0).max()
            cuts.append(min(forced ?? fit ?? limit, height))
        }
        web.frame = NSRect(x: 0, y: 0, width: pageW, height: height)
        guard let tall = try? await web.pdf(configuration: WKPDFConfiguration()),
              let provider = CGDataProvider(data: tall as CFData), let src = CGPDFDocument(provider)?.page(at: 1)
        else { return false }
        let srcH = src.getBoxRect(.mediaBox).height
        let data = NSMutableData()
        var box = a4
        guard let consumer = CGDataConsumer(data: data as CFMutableData),
              let ctx = CGContext(consumer: consumer, mediaBox: &box, nil) else { return false }
        for (a, b) in zip(cuts, cuts.dropFirst()).prefix(MAX_PAGES) {
            ctx.beginPDFPage(nil)
            ctx.saveGState()
            let shown = (b - a) * scale
            ctx.clip(to: CGRect(x: margin, y: a4.height - margin - shown, width: a4.width - 2 * margin, height: shown))
            // the slice's top (a pixels down the page, so srcH - a up from the PDF's bottom) at the page's top margin
            ctx.translateBy(x: margin, y: a4.height - margin - (srcH - a) * scale)
            ctx.scaleBy(x: scale, y: scale)
            ctx.drawPDFPage(src)
            ctx.restoreGState()
            ctx.endPDFPage()
        }
        ctx.closePDF()
        guard data.length < MAX_BYTES else { return false }
        return data.write(to: out, atomically: true)
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
