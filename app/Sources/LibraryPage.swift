import AppKit
import BurrowCore
import PDFKit
import SwiftUI

/// Home: everything in the vault as a cover, grouped by the folder it lives in.
struct LibraryPage: View {
    let workspace: Workspace
    let kind: LibraryKind

    private var groups: [(folder: String, files: [MapFile])] {
        let files = workspace.map.files.filter { kind.holds($0.path) }
        let byFolder = Dictionary(grouping: files) { file -> String in
            let parts = file.path.split(separator: "/")
            return parts.count > 1 ? String(parts[0]) : ""
        }
        // Folders that hold pictures and documents come first, so the page opens on covers rather than words.
        func pictures(_ folder: String) -> Int { byFolder[folder]!.filter { [.documents, .images].contains(LibraryKind.of($0.path)) }.count }
        return byFolder.keys.sorted { a, b in
            let (pa, pb) = (pictures(a), pictures(b))
            if (pa > 0) != (pb > 0) { return pa > 0 }
            return a.isEmpty != b.isEmpty ? a.isEmpty : a.localizedStandardCompare(b) == .orderedAscending
        }.map { ($0, byFolder[$0]!.sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }) }
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 26, pinnedViews: []) {
                header
                if groups.isEmpty {
                    ContentUnavailableView(kind == .all ? "Nothing here yet" : "No \(kind.title.lowercased()) yet", systemImage: kind.symbol,
                                           description: Text("Drop files into the vault folder, or link a folder you already have."))
                        .foregroundStyle(Night.dim).frame(maxWidth: .infinity).padding(.top, 60)
                }
                ForEach(groups, id: \.folder) { group in
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Image(systemName: group.folder.isEmpty ? "tray" : workspace.linked.contains { $0.name == group.folder } ? "link" : "folder")
                                .foregroundStyle(Night.faint)
                            Text(group.folder.isEmpty ? "In the vault" : group.folder).font(.system(size: 15, weight: .semibold))
                            Text("\(group.files.count)").font(.system(size: 13)).foregroundStyle(Night.faint).monospacedDigit()
                        }
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 168, maximum: 240), spacing: 16, alignment: .top)], alignment: .leading, spacing: 18) {
                            ForEach(group.files, id: \.path) { file in
                                CoverCard(workspace: workspace, path: file.path, selected: workspace.librarySelection == file.path)
                                    .onTapGesture(count: 2) { workspace.go(.file(file.path), newTab: true) }
                                    .simultaneousGesture(TapGesture().onEnded { workspace.librarySelection = file.path })
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 28).padding(.vertical, 22)
        }
        .background(Night.ground)
        .environment(\.colorScheme, .dark)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(kind == .all ? "Library" : kind.title).font(.system(size: 28, weight: .bold)).tracking(-0.4)
                Text(summary).foregroundStyle(Night.dim).monospacedDigit()
                Spacer()
            }
            // The kinds the sidebar used to list, as filter chips: Obsidian keeps the sidebar for the file tree.
            HStack(spacing: 8) {
                ForEach(LibraryKind.allCases, id: \.self) { each in
                    let count = each == .all ? workspace.map.files.count : workspace.count(each)
                    if each == .all || count > 0 {
                        Chip(title: each.title, count: count, dot: LibraryKind.colour(of: each == .notes ? "x.md" : each == .documents ? "x.pdf" : each == .images ? "x.png" : ""),
                             selected: each == kind) { workspace.go(.library(each)) }
                    }
                }
            }
        }
    }

    private var summary: String {
        if kind != .all { return "\(workspace.count(kind)) files" }
        return [LibraryKind.notes, .documents, .images, .code].compactMap { k in
            let n = workspace.count(k)
            return n == 0 ? nil : "\(n) \(k.title.lowercased())"
        }.joined(separator: " · ")
    }
}

/// One file as a picture with its name under it. The thin edge says what kind of thing it is.
struct CoverCard: View {
    let workspace: Workspace
    let path: String
    let selected: Bool
    @State private var hovering = false

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            CoverImage(workspace: workspace, path: path)
                .aspectRatio(4 / 3, contentMode: .fit)
                .clipShape(.rect(cornerRadius: 8))
                .overlay {
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(selected ? Color.accentColor : (LibraryKind.colour(of: path) ?? Night.line).opacity(selected ? 1 : 0.55),
                                      lineWidth: selected ? 2.5 : 1)
                }
                .shadow(color: (LibraryKind.colour(of: path) ?? .clear).opacity(hovering ? 0.35 : 0), radius: 12)
            VStack(alignment: .leading, spacing: 1) {
                Text(path.title).font(.system(size: 12.5, weight: .medium)).lineLimit(1).truncationMode(.middle)
                Text(detail).font(.system(size: 11)).foregroundStyle(Night.faint).lineLimit(1)
            }
            .padding(.horizontal, 2)
        }
        .contentShape(Rectangle())
        .onHover { hovering = $0 }
        .animation(.easeOut(duration: 0.15), value: hovering)
        .help(path)
        .contextMenu {
            Button("Open") { workspace.go(.file(path)) }
            Button("Open in New Tab") { workspace.go(.file(path), newTab: true) }
            Button("Open to the Right") { workspace.openToTheRight(path) }
            Button(workspace.isBookmarked(path) ? "Remove Bookmark" : "Bookmark") { Task { await workspace.toggleBookmark(path) } }
            Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([workspace.fileURL(path)]) }
        }
    }

    private var detail: String {
        let ext = (path as NSString).pathExtension.uppercased()
        let read = workspace.sessions(reading: path).count
        return read > 0 ? "\(ext) · read in \(read.counted("conversation"))" : ext
    }
}

/// The picture for a file. Notes without a picture show their opening lines on a dark card instead.
struct CoverImage: View {
    let workspace: Workspace
    let path: String
    var size = CGSize(width: 480, height: 360)
    /// Too small for words: a file with no picture shows its kind instead of unreadable text.
    var compact = false
    @State private var image: NSImage?
    @State private var words: (title: String?, body: String)?

    var body: some View {
        // The card's size comes from its parent; the picture fills it and is cut at the edges, never the other way round.
        Night.card.overlay(alignment: .top) {
            if let image {
                GeometryReader { box in
                    Image(nsImage: image).resizable().aspectRatio(contentMode: .fill)
                        .frame(width: box.size.width, height: box.size.height, alignment: .top).clipped()
                }
            } else if compact, words != nil {
                Image(systemName: LibraryKind.of(path).symbol).font(.system(size: 15)).foregroundStyle(LibraryKind.colour(of: path) ?? Night.dim)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let words {
                VStack(alignment: .leading, spacing: 6) {
                    if let title = words.title { Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Night.note).lineLimit(2) }
                    Text(words.body).font(.system(size: 10.5)).foregroundStyle(Night.dim).lineSpacing(2)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading).padding(12).clipped()
            } else {
                Image(systemName: LibraryKind.of(path).symbol).font(.system(size: 26, weight: .light)).foregroundStyle(Night.faint)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .clipped()
        .task(id: path) { await load() }
    }

    private func load() async {
        let kind = LibraryKind.of(path)
        if kind == .notes {
            guard let text = await workspace.text(of: path) else { return }
            if let picture = NoteText.firstPicture(in: text, notePath: path, files: workspace.map.files),
               let found = await Covers.shared.cover(for: workspace.fileURL(picture), size: size) {
                image = found
                return
            }
            words = NoteText.opening(text)
            return
        }
        if kind == .code {
            if let text = await workspace.text(of: path) {
                words = (nil, text.components(separatedBy: "\n").prefix(14).joined(separator: "\n"))
            }
            return
        }
        image = await Covers.shared.cover(for: workspace.fileURL(path), size: size)
    }
}

/// The inspector for a Library selection: a big preview, its pages, and the conversations that read it.
struct LibraryInspector: View {
    let workspace: Workspace
    let path: String?

    var body: some View {
        if let path {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    CoverImage(workspace: workspace, path: path, size: CGSize(width: 900, height: 700))
                        .aspectRatio(4 / 3, contentMode: .fit).clipShape(.rect(cornerRadius: 10))
                        .overlay { RoundedRectangle(cornerRadius: 10).strokeBorder((LibraryKind.colour(of: path) ?? Night.line).opacity(0.6)) }
                        .onTapGesture(count: 2) { workspace.go(.file(path), newTab: true) }
                    VStack(alignment: .leading, spacing: 3) {
                        Text(path.title).font(.system(size: 17, weight: .semibold)).lineLimit(3)
                        Text(path.folderPath.isEmpty ? "In the vault" : path.folderPath).foregroundStyle(Night.dim).font(.system(size: 12))
                    }
                    HStack {
                        Button("Open") { workspace.go(.file(path)) }
                        Button("Show in Finder") { NSWorkspace.shared.activateFileViewerSelecting([workspace.fileURL(path)]) }
                    }
                    .controlSize(.small)
                    if LibraryKind.of(path) == .documents || LibraryKind.of(path) == .images { ReadInFacts(workspace: workspace, path: path) }
                    if (path as NSString).pathExtension.lowercased() == "pdf" { PageStrip(url: workspace.fileURL(path)) }
                    ReadBy(workspace: workspace, path: path)
                    LedgerAboutFile(workspace: workspace, path: path)
                }
                .padding(16)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Night.ground)
            .environment(\.colorScheme, .dark)
        } else {
            ContentUnavailableView("Choose a file", systemImage: "square.grid.2x2", description: Text("Its preview, pages and the conversations that read it show here."))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Night.ground)
                .environment(\.colorScheme, .dark)
        }
    }
}

/// What Burrow did to make a document searchable.
struct ReadInFacts: View {
    let workspace: Workspace
    let path: String
    @State private var pages = 0
    @State private var characters = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Read into the vault", systemImage: "circle.fill").labelStyle(DotLabel(colour: Night.document))
                .font(.system(size: 12, weight: .semibold))
            Text(how).font(.system(size: 12)).foregroundStyle(Night.dim)
            if pages > 0 || characters > 0 {
                Text("\(pages > 0 ? "\(pages) page sections · " : "")\(characters.formatted()) characters of text")
                    .font(.system(size: 12)).foregroundStyle(Night.dim).monospacedDigit()
            }
        }
        .task(id: path) {
            guard let text = await workspace.text(of: path) else { return }
            characters = text.count
            pages = text.components(separatedBy: "\n").filter { $0.hasPrefix("## Page ") }.count
        }
    }

    private var how: String {
        switch (path as NSString).pathExtension.lowercased() {
        case "pdf": return "PDF text, one section per page. Scanned pages are read with text recognition."
        case "docx", "doc", "rtf", "odt", "wordml": return "Word-style document read with the Mac's own text reader."
        default: return "Picture. Any words in it are read with text recognition."
        }
    }
}

struct DotLabel: LabelStyle {
    let colour: Color
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 7) {
            Circle().fill(colour).frame(width: 8, height: 8).shadow(color: colour, radius: 4)
            configuration.title
        }
    }
}

/// The pages of a PDF as small pictures. Each page is one section Burrow can find.
struct PageStrip: View {
    let url: URL
    @State private var pages: [NSImage] = []
    @State private var total = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(total > 0 ? "\(total) pages" : "Pages").font(.system(size: 12, weight: .semibold))
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(pages.enumerated()), id: \.offset) { index, page in
                        VStack(spacing: 3) {
                            Image(nsImage: page).resizable().aspectRatio(contentMode: .fit).frame(height: 96)
                                .clipShape(.rect(cornerRadius: 3)).overlay { RoundedRectangle(cornerRadius: 3).strokeBorder(Night.line) }
                            Text("\(index + 1)").font(.system(size: 10)).foregroundStyle(Night.faint).monospacedDigit()
                        }
                    }
                }
            }
        }
        .task(id: url) {
            guard let document = PDFDocument(url: url) else { return }
            total = document.pageCount
            pages = (0..<min(document.pageCount, 24)).compactMap { document.page(at: $0)?.thumbnail(of: CGSize(width: 140, height: 190), for: .mediaBox) }
        }
    }
}

/// The conversations from other programs that opened this file.
struct ReadBy: View {
    let workspace: Workspace
    let path: String

    var body: some View {
        let found = workspace.sessions(reading: path)
        VStack(alignment: .leading, spacing: 8) {
            Text("Read in conversations").font(.system(size: 12, weight: .semibold))
            if found.isEmpty {
                Text("No program has opened this yet.").font(.system(size: 12)).foregroundStyle(Night.faint)
            }
            ForEach(found.prefix(6), id: \.id) { record in
                Button { workspace.go(.session(record.id)) } label: {
                    HStack(spacing: 8) {
                        Image(systemName: record.program.symbol).foregroundStyle(Night.conversation).frame(width: 18)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(record.program.name).font(.system(size: 12, weight: .medium))
                            Text(record.updated.formatted(date: .abbreviated, time: .shortened)).font(.system(size: 11)).foregroundStyle(Night.faint)
                        }
                        Spacer()
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// A filter chip: a name, a count, and the colour of what it holds.
struct Chip: View {
    let title: String
    var count: Int? = nil
    var dot: Color? = nil
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if let dot { Circle().fill(dot).frame(width: 6, height: 6) }
                Text(title).font(.system(size: 12.5, weight: .medium))
                if let count { Text("\(count)").font(.system(size: 11.5)).foregroundStyle(Night.faint).monospacedDigit() }
            }
            .padding(.horizontal, 11).padding(.vertical, 5)
            .background(selected ? Color.white.opacity(0.16) : Night.card, in: .capsule)
            .overlay { Capsule().strokeBorder(selected ? Color.white.opacity(0.25) : Night.line) }
        }
        .buttonStyle(.plain)
    }
}
