// Renders each text as a picture, then reads it back with the Mac's Vision text recognition, as CAMR for Mac does.
//   swift thesis_photos.swift <in.json: [{id,text}]> <out-dir>   prints [{id,path,read:[{text,labels}]}]
import AppKit
import Vision

let items = try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))) as! [[String: String]]
let dir = URL(fileURLWithPath: CommandLine.arguments[2])
try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
var out: [[String: Any]] = []
for item in items {
    let size = 1100
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: 800, bitsPerSample: 8, samplesPerPixel: 4,
                               hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    NSColor(white: 0.97, alpha: 1).setFill()
    NSRect(x: 0, y: 0, width: size, height: 800).fill()
    (item["text"]! as NSString).draw(in: NSRect(x: 70, y: 60, width: 960, height: 680),
        withAttributes: [.font: NSFont.systemFont(ofSize: 40), .foregroundColor: NSColor.black])
    NSGraphicsContext.restoreGraphicsState()
    let url = dir.appendingPathComponent("\(item["id"]!).png")
    try! rep.representation(using: .png, properties: [:])!.write(to: url)
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.usesLanguageCorrection = true
    let labels = VNClassifyImageRequest()
    try? VNImageRequestHandler(cgImage: rep.cgImage!, options: [:]).perform([text, labels])
    let lines = (text.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    let seen = (labels.results ?? []).filter { $0.confidence > 0.12 }.prefix(12).map { $0.identifier.replacingOccurrences(of: "_", with: " ") }
    out.append(["id": item["id"]!, "path": url.path, "read": [["text": lines.joined(separator: "\n"), "labels": Array(seen)]]])
}
print(String(data: try! JSONSerialization.data(withJSONObject: out), encoding: .utf8)!)
