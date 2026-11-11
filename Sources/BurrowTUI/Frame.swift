import Foundation

/// What a colour means. There are only a few: gold for notes, blue for code, red for trouble.
/// Colour means one thing each, as in the Mac app: gold for Burrow's own marks, blue for code, amber for documents read
/// into the vault, cyan for conversations, violet for saved model memory, red for what is wrong or stale.
enum Ink: Equatable { case plain, note, code, alert, doc, talk, cache }

struct Style: Equatable {
    var ink: Ink = .plain
    var bold = false
    var dim = false
    var italic = false
    var underline = false
    var reverse = false

    static let plain = Style()
    static let quiet = Style(dim: true)
    static let strong = Style(bold: true)
    static let note = Style(ink: .note)
    static let code = Style(ink: .code)
    static let alert = Style(ink: .alert)
}

enum ColorDepth {
    case none, sixteen, full

    static func detect(environment: [String: String] = ProcessInfo.processInfo.environment) -> ColorDepth {
        if environment["NO_COLOR"] != nil || environment["TERM"] == "dumb" { return .none }
        if environment["COLORTERM"] != nil || (environment["TERM"] ?? "").contains("256") { return .full }
        return .sixteen
    }
}

struct Cell: Equatable {
    var character: Character = " "
    var style: Style = .plain
    /// The second half of a double-width character.
    var continuation = false
}

/// One whole screen as a grid of cells. Views draw into it, and only what changed is sent to the terminal.
struct Frame {
    let width: Int
    let height: Int
    private(set) var cells: [Cell]
    var cursor: (x: Int, y: Int)?

    init(width: Int, height: Int) {
        self.width = max(0, width)
        self.height = max(0, height)
        cells = Array(repeating: Cell(), count: self.width * self.height)
    }

    /// Writes text left to right, cut at `limit`, and returns the column after it. Anything the terminal could act on is dropped.
    @discardableResult
    mutating func put(_ x: Int, _ y: Int, _ text: String, _ style: Style = .plain, limit: Int? = nil) -> Int {
        guard y >= 0, y < height else { return x }
        let edge = min(width, limit ?? width)
        var column = x
        for character in text {
            let cost = Cells.width(of: character)
            if cost == 0 { continue }
            if column + cost > edge {
                // A wide character that won't fit leaves a blank rather than half a glyph.
                if column >= 0, column < edge { cells[y * width + column] = Cell(character: " ", style: style) }
                column += cost
                break
            }
            if column >= 0 {
                cells[y * width + column] = Cell(character: character, style: style)
                if cost == 2 { cells[y * width + column + 1] = Cell(character: " ", style: style, continuation: true) }
            }
            column += cost
        }
        return min(column, edge)
    }

    mutating func clear(_ x: Int, _ y: Int, width clearWidth: Int, height clearHeight: Int) {
        for row in max(0, y)..<min(height, y + clearHeight) where row >= 0 {
            for column in max(0, x)..<min(width, x + clearWidth) where column >= 0 { cells[row * width + column] = Cell() }
        }
    }

    /// Flips one row's cells, for a highlighted range.
    mutating func restyle(_ x: Int, _ y: Int, width restyleWidth: Int, _ change: (inout Style) -> Void) {
        guard y >= 0, y < height else { return }
        for column in max(0, x)..<max(max(0, x), min(width, x + restyleWidth)) { change(&cells[y * width + column].style) }
    }

    func row(_ y: Int) -> String {
        var out = ""
        for column in 0..<width where !cells[y * width + column].continuation { out.append(cells[y * width + column].character) }
        return out
    }

    /// The screen as plain text, for tests.
    var plainText: String { (0..<height).map { row($0).replacingOccurrences(of: " +$", with: "", options: .regularExpression) }.joined(separator: "\n") }

    func style(atColumn x: Int, row y: Int) -> Style { cells[y * width + x].style }

    private static func code(_ style: Style, depth: ColorDepth) -> String {
        var parts = ["0"]
        if style.bold { parts.append("1") }
        if style.dim { parts.append("2") }
        if style.italic { parts.append("3") }
        if style.underline { parts.append("4") }
        if style.reverse { parts.append("7") }
        switch (style.ink, depth) {
        case (.note, .full): parts.append("38;5;178")
        case (.code, .full): parts.append("38;5;74")
        case (.alert, .full): parts.append("38;5;167")
        case (.doc, .full): parts.append("38;5;214")
        case (.talk, .full): parts.append("38;5;81")
        case (.cache, .full): parts.append("38;5;141")
        case (.doc, .sixteen): parts.append("33")
        case (.talk, .sixteen): parts.append("36")
        case (.cache, .sixteen): parts.append("35")
        case (.note, .sixteen): parts.append("33")
        case (.code, .sixteen): parts.append("36")
        case (.alert, .sixteen): parts.append("31")
        default: break
        }
        return "\u{1B}[" + parts.joined(separator: ";") + "m"
    }

    /// The escape codes that turn the screen from `old` into this frame. With no old frame, every cell is sent.
    func encoded(from old: Frame?, depth: ColorDepth) -> String {
        var out = "\u{1B}[?2026h"
        let previous = (old?.width == width && old?.height == height) ? old : nil
        if previous == nil { out += "\u{1B}[0m\u{1B}[2J" }
        var current: Style?
        for y in 0..<height {
            var x = 0
            while x < width {
                let cell = cells[y * width + x]
                if let previous, previous.cells[y * width + x] == cell {
                    x += 1
                    continue
                }
                if previous == nil, cell == Cell() {
                    x += 1
                    continue
                }
                out += "\u{1B}[\(y + 1);\(x + 1)H"
                while x < width {
                    let run = cells[y * width + x]
                    if let previous, previous.cells[y * width + x] == run { break }
                    if run.continuation {
                        x += 1
                        continue
                    }
                    if run.style != current {
                        out += Self.code(run.style, depth: depth)
                        current = run.style
                    }
                    out.append(run.character)
                    x += 1
                }
            }
        }
        out += "\u{1B}[0m"
        if let cursor {
            out += "\u{1B}[\(cursor.y + 1);\(cursor.x + 1)H\u{1B}[?25h"
        } else {
            out += "\u{1B}[?25l"
        }
        return out + "\u{1B}[?2026l"
    }
}
