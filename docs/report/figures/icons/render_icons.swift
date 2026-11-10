import AppKit
// usage: icons <outdir> name:hex ...
let args = CommandLine.arguments
for spec in args[2...] {
    let parts = spec.split(separator: ":")
    let name = String(parts[0]); let hex = String(parts[1])
    var v: UInt64 = 0; Scanner(string: hex).scanHexInt64(&v)
    let color = NSColor(red: CGFloat((v >> 16) & 255)/255, green: CGFloat((v >> 8) & 255)/255, blue: CGFloat(v & 255)/255, alpha: 1)
    let cfg = NSImage.SymbolConfiguration(pointSize: 200, weight: .medium).applying(.init(paletteColors: [color]))
    guard let img = NSImage(systemSymbolName: name, accessibilityDescription: nil)?.withSymbolConfiguration(cfg) else { print("missing", name); continue }
    let size = img.size
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width), pixelsHigh: Int(size.height), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    img.draw(in: NSRect(origin: .zero, size: size))
    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: "\(args[1])/\(name)-\(hex).png"))
}
