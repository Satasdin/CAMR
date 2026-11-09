import Foundation

enum Key: Equatable {
    case character(Character)
    case control(Character)
    case enter, tab, backTab, escape, backspace, delete
    case up, down, left, right, home, end, pageUp, pageDown
    case paste(String)
}

/// Turns the bytes a terminal sends into keys. Pure, so it can be tested without a terminal.
struct KeyDecoder {
    private var buffer: [UInt8] = []
    private var pasting = false
    private var pasted: [UInt8] = []
    private static let pasteEnd: [UInt8] = Array("\u{1B}[201~".utf8)
    private static let mostPasted = 1_000_000

    /// True when a lone Escape is waiting to be told apart from the start of a sequence.
    var waitingOnEscape: Bool { !pasting && buffer == [0x1B] }

    mutating func feed(_ bytes: [UInt8]) -> [Key] {
        buffer += bytes
        var keys: [Key] = []
        while !buffer.isEmpty {
            if pasting {
                guard let end = pasteEnd(in: buffer) else {
                    // Hold back anything that could be the start of the end marker.
                    let keep = min(buffer.count, Self.pasteEnd.count - 1)
                    let safe = buffer.count - keep
                    if pasted.count < Self.mostPasted { pasted += buffer[0..<safe] }
                    buffer.removeFirst(safe)
                    return keys
                }
                if pasted.count < Self.mostPasted { pasted += buffer[0..<end] }
                buffer.removeFirst(end + Self.pasteEnd.count)
                pasting = false
                keys.append(.paste(String(decoding: pasted, as: UTF8.self)))
                pasted = []
                continue
            }
            guard let (key, used) = next() else { break }
            buffer.removeFirst(used)
            if let key { keys.append(key) }
        }
        return keys
    }

    /// Called after a short wait: an Escape with nothing behind it was the Escape key.
    mutating func flushEscape() -> [Key] {
        guard waitingOnEscape else { return [] }
        buffer = []
        return [.escape]
    }

    private func pasteEnd(in bytes: [UInt8]) -> Int? {
        guard bytes.count >= Self.pasteEnd.count else { return nil }
        return (0...(bytes.count - Self.pasteEnd.count)).first { Array(bytes[$0..<($0 + Self.pasteEnd.count)]) == Self.pasteEnd }
    }

    /// The next key and how many bytes it took. Nil means more bytes are needed.
    private mutating func next() -> (Key?, Int)? {
        let first = buffer[0]
        switch first {
        case 0x1B: return escapeSequence()
        case 0x0D, 0x0A: return (.enter, 1)
        case 0x09: return (.tab, 1)
        case 0x7F, 0x08: return (.backspace, 1)
        case 0x01...0x1A: return (.control(Character(UnicodeScalar(first + 0x60))), 1)
        case 0x00, 0x1C...0x1F: return (nil, 1)
        default: return utf8Character()
        }
    }

    private func utf8Character() -> (Key?, Int)? {
        let first = buffer[0]
        let length: Int
        switch first {
        case 0x20...0x7E: return (.character(Character(UnicodeScalar(first))), 1)
        case 0xC0...0xDF: length = 2
        case 0xE0...0xEF: length = 3
        case 0xF0...0xF7: length = 4
        default: return (nil, 1)  // not the start of a character
        }
        guard buffer.count >= length else { return nil }
        guard let text = String(bytes: buffer[0..<length], encoding: .utf8), let character = text.first else { return (nil, 1) }
        return (.character(character), length)
    }

    private mutating func escapeSequence() -> (Key?, Int)? {
        guard buffer.count > 1 else { return nil }
        switch buffer[1] {
        case UInt8(ascii: "["):
            var end = 2
            while end < buffer.count, !(0x40...0x7E).contains(buffer[end]) { end += 1 }
            guard end < buffer.count else { return nil }
            let body = String(decoding: buffer[2..<end], as: UTF8.self)
            let used = end + 1
            let final = Character(UnicodeScalar(buffer[end]))
            if final == "~", body.split(separator: ";").first == "200" {
                pasting = true
                return (nil, used)
            }
            return (Self.csi(body, final), used)
        case UInt8(ascii: "O"):
            guard buffer.count > 2 else { return nil }
            switch buffer[2] {
            case UInt8(ascii: "A"): return (.up, 3)
            case UInt8(ascii: "B"): return (.down, 3)
            case UInt8(ascii: "C"): return (.right, 3)
            case UInt8(ascii: "D"): return (.left, 3)
            case UInt8(ascii: "H"): return (.home, 3)
            case UInt8(ascii: "F"): return (.end, 3)
            default: return (nil, 3)
            }
        case 0x1B: return (.escape, 1)
        default: return (nil, 2)  // Alt with a key, which Burrow doesn't use
        }
    }

    private static func csi(_ body: String, _ final: Character) -> Key? {
        switch final {
        case "A": return .up
        case "B": return .down
        case "C": return .right
        case "D": return .left
        case "H": return .home
        case "F": return .end
        case "Z": return .backTab
        case "~":
            switch body.split(separator: ";").first {
            case "1", "7": return .home
            case "4", "8": return .end
            case "3": return .delete
            case "5": return .pageUp
            case "6": return .pageDown
            default: return nil
            }
        default: return nil
        }
    }
}

/// A line of text being typed.
struct TextField: Equatable {
    private(set) var characters: [Character] = []
    private(set) var cursor = 0
    var text: String { String(characters) }

    init(_ text: String = "") {
        characters = Array(text)
        cursor = characters.count
    }

    /// Applies an editing key. Returns true if the key was one.
    mutating func apply(_ key: Key) -> Bool {
        switch key {
        case let .character(character):
            characters.insert(character, at: cursor)
            cursor += 1
        case let .paste(text):
            let flat = Array(text.replacingOccurrences(of: "\r\n", with: " ").replacingOccurrences(of: "\n", with: " ").replacingOccurrences(of: "\r", with: " ").filter { Cells.width(of: $0) > 0 })
            characters.insert(contentsOf: flat, at: cursor)
            cursor += flat.count
        case .backspace:
            guard cursor > 0 else { return true }
            characters.remove(at: cursor - 1)
            cursor -= 1
        case .delete, .control("d"):
            if cursor < characters.count { characters.remove(at: cursor) }
        case .left, .control("b"): cursor = max(0, cursor - 1)
        case .right, .control("f"): cursor = min(characters.count, cursor + 1)
        case .home, .control("a"): cursor = 0
        case .end, .control("e"): cursor = characters.count
        case .control("u"):
            characters.removeFirst(cursor)
            cursor = 0
        case .control("k"): characters.removeLast(characters.count - cursor)
        case .control("w"):
            var start = cursor
            while start > 0, characters[start - 1] == " " { start -= 1 }
            while start > 0, characters[start - 1] != " " { start -= 1 }
            characters.removeSubrange(start..<cursor)
            cursor = start
        default: return false
        }
        return true
    }

    /// What to show in a space this wide, and where the cursor lands in it.
    func visible(width: Int) -> (text: String, cursorColumn: Int) {
        guard width > 0 else { return ("", 0) }
        var start = 0
        var used = characters[0..<cursor].reduce(0) { $0 + Cells.width(of: $1) }
        while used >= width, start < cursor {
            used -= Cells.width(of: characters[start])
            start += 1
        }
        var shown = ""
        var total = 0
        for character in characters[start...] {
            let cost = Cells.width(of: character)
            if total + cost > width { break }
            shown.append(character)
            total += cost
        }
        return (shown, used)
    }
}
