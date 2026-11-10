import Foundation

/// A map of one file and what it connects to: a star at the centre with its neighbours around it.
/// It shows what a list can't: how much hangs off each neighbour, at a glance.
enum StarMap {
    struct Placed: Equatable {
        let index: Int
        let x: Int
        let y: Int
        let labelOnRight: Bool
    }

    /// Spreads the neighbours round an oval, then moves any that would share a row on one side, so no label sits on another.
    static func place(count: Int, in area: Rect) -> [Placed] {
        guard count > 0 else { return [] }
        let centerX = area.x + area.width / 2
        let centerY = area.y + area.height / 2
        let radiusX = Double(max(6, min(area.width / 2 - 18, area.width * 30 / 100)))
        let radiusY = Double(max(2, area.height / 2 - 1))
        var points: [Placed] = []
        for index in 0..<count {
            let angle = -Double.pi / 2 + 2 * Double.pi * Double(index) / Double(count)
            let x = centerX + Int((radiusX * cos(angle)).rounded())
            let y = centerY + Int((radiusY * sin(angle)).rounded())
            points.append(Placed(index: index, x: x, y: y, labelOnRight: x >= centerX))
        }
        var out: [Placed] = []
        for side in [true, false] {
            let group = points.filter { $0.labelOnRight == side }.sorted { $0.y < $1.y }
            var ys = group.map(\.y)
            for position in ys.indices.dropFirst() where ys[position] <= ys[position - 1] { ys[position] = ys[position - 1] + 1 }
            if let last = ys.last, last > area.bottom - 1 {
                ys[ys.count - 1] = area.bottom - 1
                for position in ys.indices.dropLast().reversed() where ys[position] >= ys[position + 1] { ys[position] = ys[position + 1] - 1 }
            }
            for (point, y) in zip(group, ys) { out.append(Placed(index: point.index, x: point.x, y: max(area.y, y), labelOnRight: side)) }
        }
        return out.sorted { $0.index < $1.index }
    }

    private static func label(_ path: String, isNote: Bool) -> String {
        let name = (path as NSString).lastPathComponent
        return isNote ? (name as NSString).deletingPathExtension : name
    }

    static func draw(_ frame: inout Frame, _ model: Model, in area: Rect) {
        guard let center = model.star.center else {
            frame.put(area.x + 2, area.y, "There is nothing to map yet. Add a note, then press R.", .quiet)
            return
        }
        let map = Rect(x: area.x, y: area.y, width: area.width, height: max(3, area.height - 2))
        let centerX = map.x + map.width / 2
        let centerY = map.y + map.height / 2
        let placed = place(count: model.star.neighbours.count, in: map)

        // The lines, faint first and the picked one last.
        for point in placed where point.index != model.star.selected {
            line(&frame, from: (centerX, centerY), to: (point.x, point.y), Style(dim: true))
        }
        if let picked = placed.first(where: { $0.index == model.star.selected }) {
            let neighbour = model.star.neighbours[picked.index]
            line(&frame, from: (centerX, centerY), to: (picked.x, picked.y), neighbour.isNote ? .note : .code)
        }

        // Faint specks beyond each star show how much more hangs off it.
        for point in placed {
            let neighbour = model.star.neighbours[point.index]
            let specks = min(3, neighbour.further)
            for speck in 0..<specks {
                let lift = speck == 0 ? -1 : (speck == 1 ? 1 : 0)
                let reach = (point.labelOnRight ? -1 : 1) * (3 + speck * 2)
                frame.put(point.x + reach, point.y + lift, "·", Style(ink: neighbour.isNote ? .note : .code, dim: true))
            }
        }

        for point in placed {
            let neighbour = model.star.neighbours[point.index]
            let selected = point.index == model.star.selected
            let ink: Ink = neighbour.isNote ? .note : .code
            frame.put(point.x, point.y, neighbour.isNote ? "●" : "◆", Style(ink: ink, bold: selected))
            let arrow = neighbour.forward ? "→ " : "← "
            let room = point.labelOnRight ? map.right - point.x - 2 : point.x - map.x - 2
            let text = arrow + Cells.truncate(label(neighbour.path, isNote: neighbour.isNote), to: max(4, room - 2))
            let column = point.labelOnRight ? point.x + 2 : point.x - 1 - Cells.width(of: text)
            frame.put(column, point.y, text, Style(ink: selected ? ink : .plain, bold: selected, reverse: selected))
        }

        let title = "✦ " + label(center, isNote: model.starCenterIsNote)
        frame.put(centerX - Cells.width(of: title) / 2, centerY, title, Style(ink: model.starCenterIsNote ? .note : .code, bold: true))

        let info = area.y + area.height - 1
        if model.star.neighbours.isEmpty {
            frame.put(area.x + 2, info, "Nothing links to or from this file yet.", .quiet)
        } else if model.star.neighbours.indices.contains(model.star.selected) {
            let picked = model.star.neighbours[model.star.selected]
            var words = "\(picked.forward ? "links to" : "linked from")  \(picked.path)  \(picked.kind)"
            if let via = picked.via { words += " via \(via)" }
            if picked.further > 0 { words += "  ·  \(picked.further) more beyond" }
            if model.star.hidden > 0 { words += "  ·  \(model.star.hidden) not shown" }
            frame.put(area.x + 2, info, Cells.truncate(words, to: area.width - 4), .quiet)
        }
    }

    private static func line(_ frame: inout Frame, from start: (Int, Int), to end: (Int, Int), _ style: Style) {
        let dx = end.0 - start.0
        let dy = end.1 - start.1
        let steps = max(abs(dx), abs(dy))
        guard steps > 5 else { return }
        for step in 3..<(steps - 1) where step % 2 == 1 {
            let x = start.0 + dx * step / steps
            let y = start.1 + dy * step / steps
            frame.put(x, y, "·", style)
        }
    }
}
