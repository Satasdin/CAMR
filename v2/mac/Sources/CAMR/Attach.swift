// Adding a photo, PDF or document to memory. The app copies the file into CAMR's own inbox (so the engine never
// needs permission for your folders), reads images itself with Apple's Vision framework (the text in them and
// what they show, all on this Mac), and hands that to the engine, which sorts it onto a shelf.

import AppKit
import UniformTypeIdentifiers
import Vision

enum Attach {
    static let types: [UTType] = [.image, .pdf, .plainText, UTType(filenameExtension: "md") ?? .plainText]

    static func pick() -> URL? {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = types
        panel.allowsMultipleSelection = false
        panel.message = "Choose a photo, PDF or text file for CAMR to remember"
        return panel.runModal() == .OK ? panel.url : nil
    }

    /// A copy in ~/.camr/mac/inbox, where the engine may read it.
    static func intoInbox(_ url: URL) throws -> URL {
        let inbox = Engine.memoryDir.appendingPathComponent("inbox")
        try FileManager.default.createDirectory(at: inbox, withIntermediateDirectories: true)
        let stamp = Int(Date().timeIntervalSince1970)
        let dest = inbox.appendingPathComponent("\(stamp)-\(url.lastPathComponent)")
        try FileManager.default.copyItem(at: url, to: dest)
        return dest
    }

    static func isImage(_ url: URL) -> Bool { UTType(filenameExtension: url.pathExtension)?.conforms(to: .image) ?? false }

    /// What an image holds: its text (Live Text's recognizer) and what it shows (the Mac's own image labels).
    static func read(image url: URL) -> [JSON] {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
              let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { return [] }
        let text = VNRecognizeTextRequest()
        text.recognitionLevel = .accurate
        text.usesLanguageCorrection = true
        let labels = VNClassifyImageRequest()
        try? VNImageRequestHandler(cgImage: img, options: [:]).perform([text, labels])
        let lines = (text.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        let seen = (labels.results ?? []).filter { $0.confidence > 0.12 }.prefix(12)
            .map { $0.identifier.replacingOccurrences(of: "_", with: " ") }
        return [["text": lines.joined(separator: "\n"), "labels": Array(seen)]]
    }
}
