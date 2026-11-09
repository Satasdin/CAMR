import AppKit
import BurrowCore
import SwiftUI

extension NSColor {
    static func burrow(light: NSColor, dark: NSColor) -> NSColor {
        NSColor(name: nil) { $0.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? dark : light }
    }
    convenience init(hex: UInt32) {
        self.init(srgbRed: CGFloat(hex >> 16 & 255) / 255, green: CGFloat(hex >> 8 & 255) / 255, blue: CGFloat(hex & 255) / 255, alpha: 1)
    }
}

enum Theme {
    /// The page follows the Mac's appearance: warm paper by day, warm dark by night.
    static let pageNS = NSColor.burrow(light: NSColor(hex: 0xFAF6EE), dark: NSColor(hex: 0x1C1B19))
    static let inkNS = NSColor.burrow(light: NSColor(hex: 0x2B2620), dark: NSColor(hex: 0xE9E4DA))
    static let inkSoftNS = NSColor.burrow(light: NSColor(hex: 0x6F675C), dark: NSColor(hex: 0x9D968A))
    static let inkFaintNS = NSColor.burrow(light: NSColor(hex: 0xB5AC9E), dark: NSColor(hex: 0x5E5951))
    static let wellNS = NSColor.burrow(light: NSColor(hex: 0xEFE9DC), dark: NSColor(hex: 0x2A2825))
    static let tagNS = NSColor.burrow(light: NSColor(hex: 0x8A5A12), dark: NSColor(hex: 0xE3B66A))

    static let page = Color(nsColor: pageNS)
    static let ink = Color(nsColor: inkNS)
    static let inkSoft = Color(nsColor: inkSoftNS)
    static let well = Color(nsColor: wellNS)

    /// Gold is what the model has read, or where you are. Nothing else uses it.
    static let gold = Color(red: 1, green: 0.84, blue: 0.52)

    /// One colour per top-level folder, so colour always answers "which part of the vault is this".
    static let clusters: [Color] = [
        Color(red: 0.50, green: 0.70, blue: 1.00), Color(red: 0.49, green: 0.89, blue: 0.76), Color(red: 1.00, green: 0.60, blue: 0.64),
        Color(red: 0.78, green: 0.65, blue: 1.00), Color(red: 0.56, green: 0.89, blue: 0.53), Color(red: 1.00, green: 0.69, blue: 0.44),
        Color(red: 0.44, green: 0.85, blue: 0.95), Color(red: 0.95, green: 0.65, blue: 0.88), Color(red: 0.85, green: 0.88, blue: 0.44),
    ]
    static let otherCluster = Color(red: 0.62, green: 0.65, blue: 0.74)

    static func colour(for kind: NoteKind) -> Color {
        switch kind {
        case .decision: return .blue
        case .rejected: return .red
        case .bug: return .orange
        case .convention: return .green
        case .note: return .secondary
        }
    }
}

extension NoteKind {
    var label: String {
        switch self {
        case .decision: return "Decision"
        case .rejected: return "Rejected"
        case .bug: return "Bug"
        case .convention: return "Convention"
        case .note: return "Note"
        }
    }
}

extension String {
    var fileName: String { (self as NSString).lastPathComponent }
    var folderPath: String { (self as NSString).deletingLastPathComponent }
    var title: String {
        let name = fileName
        return ["md", "markdown"].contains((name as NSString).pathExtension.lowercased()) ? (name as NSString).deletingPathExtension : name
    }
    var isMarkdownPath: Bool { ["md", "markdown"].contains((self as NSString).pathExtension.lowercased()) }
}
