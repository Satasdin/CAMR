import AVFoundation
import AppKit
import ImageIO
import PDFKit
import Vision

/// Images, a video's frames and a PDF's scanned pages read on this Mac with Apple's own text recognition (the Vision
/// framework): no vision model is loaded. What is written is read line by line (accurate, with language correction),
/// and a few labels say what a picture shows, so a photo with no text in it still says something ("receipt, paper").
/// The engine keeps the words as moments from the file, as it keeps a PDF's text (camr_engine.media.read_given).
enum OCR {
    static let images: Set<String> = ["png", "jpg", "jpeg", "webp", "heic", "heif", "tif", "tiff", "gif", "bmp"]
    static let videos: Set<String> = ["mp4", "mov", "m4v"]
    static let everyS = 2.0  // a video frame every this many seconds…
    static let maxFrames = 30  // …at most this many
    static let maxPages = 40  // scanned PDF pages read, at most
    static let labelConfidence: Float = 0.3

    struct Seen {
        var text: String
        var labels: [String]
    }

    /// What the engine is sent for a file: nil when the app has nothing to read in it (text, Markdown, a PDF whose
    /// pages all have text).
    static func read(_ url: URL) async -> [[String: Any]]? {
        let ext = url.pathExtension.lowercased()
        if images.contains(ext) {
            guard let img = cgImage(url) else { return [] }
            let s = see(img)
            return [["text": s.text, "labels": s.labels]]
        }
        if videos.contains(ext) { return await video(url) }
        if ext == "pdf" { return scannedPages(url) }
        return nil
    }

    /// An image file, turned upright by its EXIF orientation, at most 3000 pixels a side.
    static func cgImage(_ url: URL) -> CGImage? {
        guard let src = CGImageSourceCreateWithURL(url as CFURL, nil) else { return nil }
        let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
                                     kCGImageSourceCreateThumbnailWithTransform: true,
                                     kCGImageSourceThumbnailMaxPixelSize: 3000]
        return CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary)
    }

    /// The text in an image, row by row as a person reads it (pieces at the same height joined left to right, so a
    /// receipt's item and its price stay on one line), and what it shows.
    static func see(_ image: CGImage) -> Seen {
        let text = VNRecognizeTextRequest()
        text.recognitionLevel = .accurate
        text.usesLanguageCorrection = true
        text.automaticallyDetectsLanguage = true
        let classify = VNClassifyImageRequest()
        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        try? handler.perform([text, classify])
        let found = (text.results ?? []).compactMap { o -> (CGRect, String)? in
            guard let s = o.topCandidates(1).first?.string else { return nil }
            return (o.boundingBox, s)
        }
        let labels = (classify.results ?? []).filter { $0.confidence >= labelConfidence }.prefix(5)
            .map { $0.identifier.replacingOccurrences(of: "_", with: " ") }
        return Seen(text: rows(found), labels: Array(labels))
    }

    /// Pieces of text grouped into rows: a piece joins a row when its middle is within half its height of the row's.
    static func rows(_ found: [(CGRect, String)]) -> String {
        var rows: [(mid: CGFloat, h: CGFloat, items: [(CGFloat, String)])] = []
        for (box, s) in found.sorted(by: { $0.0.midY > $1.0.midY }) {  // Vision's origin is bottom-left
            if let i = rows.firstIndex(where: { abs($0.mid - box.midY) < max($0.h, box.height) * 0.5 }) {
                rows[i].items.append((box.minX, s))
            } else {
                rows.append((box.midY, box.height, [(box.minX, s)]))
            }
        }
        return rows.map { $0.items.sorted { $0.0 < $1.0 }.map(\.1).joined(separator: "  ") }.joined(separator: "\n")
    }

    /// A frame every two seconds (at most 30), each read; a frame whose text is the one before it again is left out.
    static func video(_ url: URL) async -> [[String: Any]] {
        let asset = AVURLAsset(url: url)
        guard let duration = try? await asset.load(.duration) else { return [] }
        let gen = AVAssetImageGenerator(asset: asset)
        gen.appliesPreferredTrackTransform = true
        gen.maximumSize = CGSize(width: 1920, height: 1920)
        let tolerance = CMTime(seconds: 0.5, preferredTimescale: 600)
        gen.requestedTimeToleranceBefore = tolerance
        gen.requestedTimeToleranceAfter = tolerance
        var out: [[String: Any]] = []
        var last: String?
        var at = 0.0
        while at < max(duration.seconds, 0.01), out.count < maxFrames {
            if let (img, _) = try? await gen.image(at: CMTime(seconds: at, preferredTimescale: 600)) {
                let s = see(img)
                let key = s.text.isEmpty ? s.labels.joined(separator: ",") : s.text
                if key != last, !(s.text.isEmpty && s.labels.isEmpty) {
                    out.append(["text": s.text, "labels": s.labels, "at_s": at])
                    last = key
                }
            }
            at += everyS
        }
        return out
    }

    /// A PDF's pages that carry no text (scans), rendered and read; nil when every page has text.
    static func scannedPages(_ url: URL) -> [[String: Any]]? {
        guard let doc = PDFDocument(url: url) else { return nil }
        var out: [[String: Any]] = []
        for i in 0..<doc.pageCount where out.count < maxPages {
            guard let page = doc.page(at: i),
                  (page.string ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { continue }
            let box = page.bounds(for: .mediaBox)
            let scale = min(3.0, 2400 / max(box.width, box.height, 1))
            let pic = page.thumbnail(of: CGSize(width: box.width * scale, height: box.height * scale), for: .mediaBox)
            guard let img = pic.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
            let s = see(img)
            out.append(["text": s.text, "labels": s.labels, "page": i + 1, "pages": doc.pageCount])
        }
        return out.isEmpty ? nil : out
    }
}
