import AppKit
import PDFKit
import Quartz
import SwiftUI
import WebKit

/// A document the agent made: the engine writes its Word file and a page for print; the app prints that page to a PDF
/// with WebKit's own print (A4 pages, the page's styles), and shows the PDF and the Word file beside the chat.
@MainActor
enum DocumentPDF {
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
        // print needs the view in a window; this one is never shown
        let window = NSWindow(contentRect: web.frame, styleMask: .borderless, backing: .buffered, defer: false)
        window.contentView = web
        let info = NSPrintInfo()
        info.paperSize = NSSize(width: 595.28, height: 841.89)  // A4, in points
        info.topMargin = 0; info.bottomMargin = 0; info.leftMargin = 0; info.rightMargin = 0  // the page's @page sets them
        info.horizontalPagination = .fit
        info.verticalPagination = .automatic
        info.jobDisposition = .save
        info.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = out
        try? FileManager.default.removeItem(at: out)
        let op = web.printOperation(with: info)
        op.showsPrintPanel = false
        op.showsProgressPanel = false
        op.view?.frame = web.bounds
        _ = op.run()
        withExtendedLifetime((window, guardian)) {}
        let size = (try? FileManager.default.attributesOfItem(atPath: out.path)[.size] as? Int) ?? 0
        if size > 1000 { return true }
        // a print that came out empty: one long page instead, which is still the whole document
        guard let data = try? await web.pdf(configuration: WKPDFConfiguration()) else { return false }
        return (try? data.write(to: out)) != nil
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
