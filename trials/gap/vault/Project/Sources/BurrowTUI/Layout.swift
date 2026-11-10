import Foundation

struct Rect: Equatable {
    var x: Int
    var y: Int
    var width: Int
    var height: Int
    var right: Int { x + width }
    var bottom: Int { y + height }
}

/// Where each pane goes for a window of a given size. A pure function of the size, so it can be tested.
struct Layout: Equatable {
    var tree: Rect?
    var reader: Rect?
    var side: Rect?
    var readerTextWidth = 40

    static let minimumWidth = 40
    static let minimumHeight = 12
    static let readingMeasure = 80

    static func bodyTop(height: Int) -> Int { height >= 16 ? 2 : 1 }
    static func bodyHeight(height: Int) -> Int { max(1, height - bodyTop(height: height) - 2) }

    static func vault(width: Int, height: Int, focus: Focus, showSide: Bool) -> Layout {
        let top = bodyTop(height: height)
        let rows = bodyHeight(height: height)
        var out = Layout()
        let treeWidth = min(34, max(22, width * 26 / 100))
        let sideWidth = min(36, max(26, width * 24 / 100))
        let gap = 3

        if width >= 110, showSide {
            out.tree = Rect(x: 1, y: top, width: treeWidth, height: rows)
            out.side = Rect(x: width - sideWidth - 1, y: top, width: sideWidth, height: rows)
            let readerX = 1 + treeWidth + gap
            out.reader = Rect(x: readerX, y: top, width: width - sideWidth - 1 - gap - readerX, height: rows)
        } else if width >= 72 {
            if focus == .links, showSide {
                out.side = Rect(x: width - sideWidth - 1, y: top, width: sideWidth, height: rows)
                out.reader = Rect(x: 2, y: top, width: width - sideWidth - 2 - gap - 1, height: rows)
            } else {
                out.tree = Rect(x: 1, y: top, width: treeWidth, height: rows)
                let readerX = 1 + treeWidth + gap
                out.reader = Rect(x: readerX, y: top, width: width - readerX - 2, height: rows)
            }
        } else {
            let whole = Rect(x: 1, y: top, width: width - 2, height: rows)
            switch focus {
            case .tree: out.tree = whole
            case .reader: out.reader = whole
            case .links: if showSide { out.side = whole } else { out.reader = whole }
            }
        }
        // Narrow panes hide the reader, but the document still has to be laid out for when it comes back.
        out.readerTextWidth = min(readingMeasure, max(10, (out.reader?.width ?? (width - 2)) - 2))
        return out
    }
}
