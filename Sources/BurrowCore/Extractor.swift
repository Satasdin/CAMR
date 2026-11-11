import AppKit
import Foundation
import PDFKit
import Vision

/// Turns documents that are not plain text into Markdown that search, chunking and `vault_read` treat like a note:
/// a title, then a heading per page, so an excerpt can say which page it came from.
/// Everything here is part of macOS (PDFKit, the system's text readers, Vision), so Burrow still needs no dependencies,
/// and nothing leaves the Mac.
public enum Extractor {
    static let pdf: Set<String> = ["pdf"]
    static let richText: [String: NSAttributedString.DocumentType] = [
        "docx": .officeOpenXML, "doc": .docFormat, "rtf": .rtf, "odt": .openDocument, "wordml": .wordML,
    ]
    static let images: Set<String> = ["png", "jpg", "jpeg", "heic", "tif", "tiff", "gif", "bmp", "webp"]
    /// Documents can be much larger than code. Past this, a file is skipped rather than read.
    static let largest = 80_000_000
    /// Scanned pages are read by text recognition, which takes about a second a page. A long scan stops here.
    static let mostRecognisedPages = 120

    public static func handles(_ path: String) -> Bool {
        let kind = (path as NSString).pathExtension.lowercased()
        return pdf.contains(kind) || richText[kind] != nil || images.contains(kind)
    }

    /// Extractions are kept by the file's content, outside any vault, so the same PDF in two vaults is read once.
    static var cache: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("Burrow/extracted", isDirectory: true)
    }

    /// The document as Markdown, from the cache when this exact content was read before.
    static func markdown(of data: Data, path: String, hash: String) -> String? {
        let saved = cache.appendingPathComponent(hash + ".md")
        if let text = try? String(contentsOf: saved, encoding: .utf8) { return text }
        guard let text = extract(data, path: path) else { return nil }
        try? FileManager.default.createDirectory(at: cache, withIntermediateDirectories: true)
        try? text.write(to: saved, atomically: true, encoding: .utf8)
        return text
    }

    static func extract(_ data: Data, path: String) -> String? {
        let kind = (path as NSString).pathExtension.lowercased()
        let title = ((path as NSString).lastPathComponent as NSString).deletingPathExtension
        var body: String?
        if pdf.contains(kind) { body = pdfText(data) }
        else if let type = richText[kind] { body = richTextOf(data, type) }
        else if images.contains(kind) { body = imageText(data).map { "## Text in the image\n\n" + $0 } }
        guard let body, !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
        // The front matter says where the text came from, so a model knows it is read from a document, not written as a note.
        return "---\ntitle: \(title)\nextracted-from: \(kind)\n---\n\n# \(title)\n\n\(body)\n"
    }

    // MARK: PDF

    static func pdfText(_ data: Data) -> String? {
        guard let document = PDFDocument(data: data), document.pageCount > 0 else { return nil }
        var pages: [String] = []
        var recognised = 0
        for index in 0..<document.pageCount {
            guard let page = document.page(at: index) else { continue }
            var text = page.string ?? ""
            // A page with no text layer is a scan: read it the way a person would, from the picture.
            if text.trimmingCharacters(in: .whitespacesAndNewlines).count < 20, recognised < mostRecognisedPages {
                recognised += 1
                let bounds = page.bounds(for: .mediaBox)
                let scale = min(3, 2400 / max(bounds.width, bounds.height))
                let image = page.thumbnail(of: NSSize(width: bounds.width * scale, height: bounds.height * scale), for: .mediaBox)
                if let picture = image.cgImage(forProposedRect: nil, context: nil, hints: nil), let read = recognise(picture) { text = read }
            }
            pages.append("## Page \(index + 1)\n\n" + tidy(text))
        }
        return pages.joined(separator: "\n\n")
    }

    // MARK: Word, RTF, OpenDocument

    static func richTextOf(_ data: Data, _ type: NSAttributedString.DocumentType) -> String? {
        guard let text = try? NSAttributedString(data: data, options: [.documentType: type], documentAttributes: nil) else { return nil }
        return tidy(text.string)
    }

    // MARK: Images

    static func imageText(_ data: Data) -> String? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil), let picture = CGImageSourceCreateImageAtIndex(source, 0, nil) else { return nil }
        return recognise(picture)
    }

    static func recognise(_ picture: CGImage) -> String? {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = true
        try? VNImageRequestHandler(cgImage: picture).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        return lines.isEmpty ? nil : lines.joined(separator: "\n")
    }

    /// Page text arrives with hard line breaks inside sentences and runs of blank lines. Keep paragraphs, drop the noise,
    /// and never let a line start with `#`, which would read as a heading the document does not have.
    static func tidy(_ text: String) -> String {
        var out: [String] = []
        var blank = false
        for raw in text.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\r", with: "\n").components(separatedBy: "\n") {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty {
                if !blank, !out.isEmpty { out.append("") }
                blank = true
                continue
            }
            blank = false
            out.append(line.hasPrefix("#") ? "\\" + line : line)
        }
        return out.joined(separator: "\n")
    }
}
