// camr-see: read the text of images and PDF pages on this Mac, with Apple's Vision framework (the engine behind
// Live Text; nothing leaves the machine), and write a preview of each page for the app to show.
//
//   camr-see <image or pdf> <output folder> [max pages]
//
// Prints JSON: {"pages": [{"index", "image", "width", "height", "text_layer", "lines": [{"text", "conf", "box"}]}]}
// "box" is [x, y, width, height] as fractions of the page, from the top left. "text_layer" is a PDF page's own text
// (empty for images and scans). Compiled once by camr/app/reader.py with swiftc.

import CoreGraphics
import Foundation
import ImageIO
import PDFKit
import UniformTypeIdentifiers
import Vision

func recognize(_ image: CGImage) -> [[String: Any]] {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    // English, not detected per image: detection read a price as Polish ("980.0ął"); Swahili and other
    // Latin-script text is read by the same model
    request.recognitionLanguages = ["en-US"]
    if #available(macOS 13.0, *) { request.automaticallyDetectsLanguage = false }
    try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    var lines: [[String: Any]] = []
    for observation in request.results ?? [] {
        guard let best = observation.topCandidates(1).first else { continue }
        let b = observation.boundingBox  // fractions, origin bottom left
        lines.append(["text": best.string, "conf": Double(best.confidence),
                      "box": [Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height)]])
    }
    return lines
}

func flatten(_ image: CGImage, maxSide: CGFloat) -> CGImage? {
    // onto white (a transparent screenshot would turn black), at most maxSide pixels on its longer side
    let scale = min(1, maxSide / CGFloat(max(image.width, image.height)))
    let w = Int(CGFloat(image.width) * scale), h = Int(CGFloat(image.height) * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.interpolationQuality = .high
    ctx.draw(image, in: CGRect(x: 0, y: 0, width: w, height: h))
    return ctx.makeImage()
}

func writeJPEG(_ image: CGImage, to url: URL) {
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil)
    else { return }
    CGImageDestinationAddImage(dest, image, [kCGImageDestinationLossyCompressionQuality: 0.85] as CFDictionary)
    CGImageDestinationFinalize(dest)
}

func page(_ index: Int, _ image: CGImage, _ out: URL, textLayer: String = "") -> [String: Any] {
    let read = flatten(image, maxSide: 3000) ?? image  // OCR at up to 3000 px
    let preview = flatten(image, maxSide: 1600) ?? image
    let name = "page-\(index).jpg"
    writeJPEG(preview, to: out.appendingPathComponent(name))
    return ["index": index, "image": name, "width": preview.width, "height": preview.height,
            "text_layer": textLayer, "lines": recognize(read)]
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: camr-see <image or pdf> <output folder> [max pages]\n".data(using: .utf8)!)
    exit(2)
}
let input = URL(fileURLWithPath: args[1])
let out = URL(fileURLWithPath: args[2], isDirectory: true)
let maxPages = args.count > 3 ? Int(args[3]) ?? 40 : 40
try? FileManager.default.createDirectory(at: out, withIntermediateDirectories: true)

var pages: [[String: Any]] = []
var total = 0
if input.pathExtension.lowercased() == "pdf", let pdf = PDFDocument(url: input) {
    total = pdf.pageCount
    for i in 0..<min(pdf.pageCount, maxPages) {
        guard let p = pdf.page(at: i) else { continue }
        let box = p.bounds(for: .mediaBox)
        let scale: CGFloat = 2.5  // about 180 dpi: enough for OCR of body text
        let w = Int(box.width * scale), h = Int(box.height * scale)
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                                  space: CGColorSpaceCreateDeviceRGB(),
                                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { continue }
        ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
        ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
        ctx.scaleBy(x: scale, y: scale)
        p.draw(with: .mediaBox, to: ctx)
        if let image = ctx.makeImage() {
            pages.append(page(i, image, out, textLayer: p.string ?? ""))
        }
    }
} else if let src = CGImageSourceCreateWithURL(input as CFURL, nil) {
    total = 1
    // the photo the right way up (a phone stores its orientation separately)
    let opts: [CFString: Any] = [kCGImageSourceCreateThumbnailFromImageAlways: true,
                                 kCGImageSourceCreateThumbnailWithTransform: true,
                                 kCGImageSourceThumbnailMaxPixelSize: 4000]
    if let image = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) {
        pages.append(page(0, image, out))
    }
}
if pages.isEmpty {
    FileHandle.standardError.write("camr-see: cannot read \(input.path)\n".data(using: .utf8)!)
    exit(1)
}
let json = try JSONSerialization.data(withJSONObject: ["pages": pages, "page_count": total], options: [])
FileHandle.standardOutput.write(json)
