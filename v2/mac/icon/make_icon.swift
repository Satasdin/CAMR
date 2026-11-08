// Draws CAMR's app icon: a cube of 27 cells in fine lines on a dark tile, one cell lit green (a memory in use).
//   swift make_icon.swift <out.png> [size]
import AppKit

let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon.png"
let size = CommandLine.arguments.count > 2 ? CGFloat(Double(CommandLine.arguments[2]) ?? 1024) : 1024

let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size), pixelsHigh: Int(size), bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                           bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext

// the tile: macOS icon grid (824 of 1024, corner radius about 185)
let inset = size * 100 / 1024
let tile = CGRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
let r = size * 185 / 1024
ctx.saveGState()
ctx.setShadow(offset: CGSize(width: 0, height: -size * 0.01), blur: size * 0.03, color: NSColor.black.withAlphaComponent(0.5).cgColor)
ctx.addPath(CGPath(roundedRect: tile, cornerWidth: r, cornerHeight: r, transform: nil))
ctx.setFillColor(NSColor(red: 0.05, green: 0.06, blue: 0.07, alpha: 1).cgColor)
ctx.fillPath()
ctx.restoreGState()
// a faint top light
ctx.saveGState()
ctx.addPath(CGPath(roundedRect: tile, cornerWidth: r, cornerHeight: r, transform: nil))
ctx.clip()
let light = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: [NSColor.white.withAlphaComponent(0.07).cgColor,
                       NSColor.white.withAlphaComponent(0).cgColor] as CFArray, locations: [0, 1])!
ctx.drawLinearGradient(light, start: CGPoint(x: size / 2, y: tile.maxY), end: CGPoint(x: size / 2, y: tile.midY), options: [])
ctx.restoreGState()

// the cube, in a 220-unit box (y up in AppKit, so flip the design's y)
let s = size * 0.29 / 100  // design units → pixels
let cx = size / 2, cy = size / 2 + size * 0.01
func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: cx + x * s, y: cy - y * s) }

// the lit cell (top face, centre), glowing
ctx.saveGState()
ctx.setShadow(offset: .zero, blur: size * 0.04, color: NSColor(red: 0.62, green: 1, blue: 0.70, alpha: 0.9).cgColor)
ctx.move(to: p(0, -33.3)); ctx.addLine(to: p(-28.9, -50)); ctx.addLine(to: p(0, -66.7)); ctx.addLine(to: p(28.9, -50)); ctx.closePath()
ctx.setFillColor(NSColor(red: 0.62, green: 1, blue: 0.70, alpha: 1).cgColor)
ctx.fillPath()
ctx.restoreGState()

// the grid lines inside the faces
let grid: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [
    (-28.9, -16.7, 57.7, -66.7), (28.9, -16.7, -57.7, -66.7), (-57.7, -33.3, 28.9, -83.3), (57.7, -33.3, -28.9, -83.3),
    (-28.9, -16.7, -28.9, 83.3), (0, 33.3, -86.6, -16.7), (-57.7, -33.3, -57.7, 66.7), (0, 66.7, -86.6, 16.7),
    (28.9, -16.7, 28.9, 83.3), (0, 33.3, 86.6, -16.7), (57.7, -33.3, 57.7, 66.7), (0, 66.7, 86.6, 16.7)]
ctx.setStrokeColor(NSColor.white.withAlphaComponent(0.38).cgColor)
ctx.setLineWidth(size * 0.006)
ctx.setLineCap(.round)
for (x1, y1, x2, y2) in grid { ctx.move(to: p(x1, y1)); ctx.addLine(to: p(x2, y2)) }
ctx.strokePath()

// the outline
ctx.setStrokeColor(NSColor(white: 0.93, alpha: 1).cgColor)
ctx.setLineWidth(size * 0.012)
ctx.setLineJoin(.round)
ctx.move(to: p(0, -100)); ctx.addLine(to: p(86.6, -50)); ctx.addLine(to: p(86.6, 50)); ctx.addLine(to: p(0, 100))
ctx.addLine(to: p(-86.6, 50)); ctx.addLine(to: p(-86.6, -50)); ctx.closePath()
ctx.move(to: p(0, 0)); ctx.addLine(to: p(-86.6, -50))
ctx.move(to: p(0, 0)); ctx.addLine(to: p(86.6, -50))
ctx.move(to: p(0, 0)); ctx.addLine(to: p(0, 100))
ctx.strokePath()

NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
print("wrote \(out)")
