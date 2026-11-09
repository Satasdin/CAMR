import Foundation

/// How wide text is on a terminal grid, which is not its byte or character count.
enum Cells {
    private static let wideRanges: [ClosedRange<UInt32>] = [
        0x1100...0x115F, 0x2E80...0x303E, 0x3041...0x33FF, 0x3400...0x4DBF, 0x4E00...0x9FFF, 0xA000...0xA4CF, 0xA960...0xA97F,
        0xAC00...0xD7A3, 0xF900...0xFAFF, 0xFE10...0xFE19, 0xFE30...0xFE6F, 0xFF00...0xFF60, 0xFFE0...0xFFE6, 0x20000...0x3FFFD,
    ]

    static func width(of character: Character) -> Int {
        if let ascii = character.asciiValue { return ascii < 0x20 || ascii == 0x7F ? 0 : 1 }
        let scalars = character.unicodeScalars
        guard let first = scalars.first else { return 0 }
        if first.properties.isEmojiPresentation || scalars.contains("\u{FE0F}") || (0x1F1E6...0x1F1FF).contains(first.value) { return 2 }
        if scalars.contains("\u{200D}"), first.properties.isEmoji { return 2 }
        if wideRanges.contains(where: { $0.contains(first.value) }) { return 2 }
        switch first.properties.generalCategory {
        case .nonspacingMark, .enclosingMark, .format, .control: return 0
        default: return 1
        }
    }

    static func width(of text: String) -> Int { text.reduce(0) { $0 + width(of: $1) } }

    /// Cuts text to fit, on a character boundary, with an ellipsis if anything was lost.
    static func truncate(_ text: String, to limit: Int) -> String {
        guard limit > 0 else { return "" }
        guard width(of: text) > limit else { return text }
        var out = ""
        var used = 0
        for character in text {
            let cost = width(of: character)
            if used + cost > limit - 1 { break }
            out.append(character)
            used += cost
        }
        return out + "…"
    }

    static func pad(_ text: String, to size: Int) -> String {
        text + String(repeating: " ", count: max(0, size - width(of: text)))
    }

    /// Keeps the end of a path, where the useful part is.
    static func truncateLeft(_ text: String, to limit: Int) -> String {
        guard limit > 0 else { return "" }
        guard width(of: text) > limit else { return text }
        var out = ""
        var used = 0
        for character in text.reversed() {
            let cost = width(of: character)
            if used + cost > limit - 1 { break }
            out.insert(character, at: out.startIndex)
            used += cost
        }
        return "…" + out
    }
}
