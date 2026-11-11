import AppKit
import BurrowCore
import SwiftUI

struct FilePage: View {
    let workspace: Workspace
    @Bindable var document: Document

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Theme.page
            if document.loaded {
                VStack(spacing: 0) {
                    // Obsidian shows front matter as properties above the page; the page itself is only the note's body.
                    if document.path.isMarkdownPath, !FrontMatter.split(document.text).header.isEmpty {
                        PropertiesPanel(workspace: workspace, document: document, editable: document.editable && !workspace.isReading)
                            .frame(maxWidth: .infinity).padding(.horizontal, 36)
                    }
                    VaultTextView(workspace: workspace, document: document, reading: workspace.isReading || !document.editable)
                }
            }
            if document.loaded, !document.editable {
                Label("Read only", systemImage: "lock").font(.caption).foregroundStyle(Theme.inkSoft).padding(12)
            }
        }
    }
}

extension NSAttributedString.Key {
    static let burrowMark = NSAttributedString.Key("burrowMark")
}

/// The Markdown page. Marks like ** and [[ show only on the line you're on, so a note reads as finished text while you write it.
struct VaultTextView: NSViewRepresentable {
    let workspace: Workspace
    let document: Document
    let reading: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.autohidesScrollers = true
        let storage = NSTextStorage()
        let layout = NSLayoutManager()
        storage.addLayoutManager(layout)
        let container = NSTextContainer(size: NSSize(width: 0, height: CGFloat.greatestFiniteMagnitude))
        container.widthTracksTextView = true
        layout.addTextContainer(container)
        let text = VaultNSTextView(frame: .zero, textContainer: container)
        text.minSize = .zero
        text.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        text.isVerticallyResizable = true
        text.isHorizontallyResizable = false
        text.autoresizingMask = [.width]
        text.delegate = context.coordinator
        text.drawsBackground = false
        text.isRichText = false
        text.importsGraphics = false
        text.allowsUndo = true
        text.usesFindBar = true
        text.isIncrementalSearchingEnabled = true
        text.isAutomaticQuoteSubstitutionEnabled = false
        text.isAutomaticDashSubstitutionEnabled = false
        text.isAutomaticTextReplacementEnabled = false
        text.isContinuousSpellCheckingEnabled = document.path.isMarkdownPath
        text.insertionPointColor = Theme.inkNS
        text.linkTextAttributes = [.foregroundColor: NSColor.controlAccentColor, .cursor: NSCursor.pointingHand]
        text.coordinator = context.coordinator
        scroll.documentView = text
        scroll.contentView.postsFrameChangedNotifications = true
        context.coordinator.attach(text, scroll)
        text.string = context.coordinator.shown(document.text)
        context.coordinator.restyleAll()
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.parent = self
        guard let text = coordinator.text else { return }
        text.isEditable = !reading
        let shown = coordinator.shown(document.text)
        if text.string != shown, !coordinator.isTyping {
            text.string = shown
            coordinator.restyleAll()
        }
        if coordinator.wasReading != reading {
            coordinator.wasReading = reading
            coordinator.restyleAll()
        }
        if let line = document.pendingLine {
            DispatchQueue.main.async {
                coordinator.jump(toLine: line)
                document.pendingLine = nil
            }
        }
    }

    @MainActor
    final class Coordinator: NSObject, NSTextViewDelegate {
        var parent: VaultTextView
        weak var text: VaultNSTextView?
        weak var scroll: NSScrollView?
        var isTyping = false
        var wasReading: Bool
        private var activeLine: NSRange?
        private let styler: Styler

        init(_ parent: VaultTextView) {
            self.parent = parent
            wasReading = parent.reading
            styler = Styler(markdown: parent.document.path.isMarkdownPath, language: (parent.document.path as NSString).pathExtension.lowercased())
        }

        func attach(_ text: VaultNSTextView, _ scroll: NSScrollView) {
            self.text = text
            self.scroll = scroll
            NotificationCenter.default.addObserver(self, selector: #selector(resized), name: NSView.frameDidChangeNotification, object: scroll.contentView)
            resized()
        }

        /// Keeps a comfortable reading measure, centred, at any window width.
        @objc private func resized() {
            guard let text, let scroll else { return }
            let measure: CGFloat = parent.document.path.isMarkdownPath ? 720 : 980
            let side = max(36, (scroll.contentSize.width - measure) / 2)
            text.textContainerInset = NSSize(width: side, height: 44)
        }

        func restyleAll() {
            guard let text, let storage = text.textStorage else { return }
            let selected = text.selectedRange()
            let caretLine = (text.string as NSString).paragraphRange(for: NSRange(location: min(selected.location, (text.string as NSString).length), length: 0))
            activeLine = caretLine
            storage.beginEditing()
            styler.style(storage, in: NSRange(location: 0, length: storage.length), activeLine: parent.reading ? nil : caretLine)
            storage.endEditing()
        }

        func textDidChange(_ notification: Notification) {
            guard let text else { return }
            isTyping = true
            parent.workspace.edited(parent.document, to: whole(text.string))
            restyleAll()
            isTyping = false
            if text.inWikiLink { DispatchQueue.main.async { text.complete(nil) } }
        }

        func textViewDidChangeSelection(_ notification: Notification) {
            guard let text, !parent.reading, let storage = text.textStorage else { return }
            let string = text.string as NSString
            let caretLine = string.paragraphRange(for: NSRange(location: min(text.selectedRange().location, string.length), length: 0))
            guard caretLine != activeLine else { return }
            // Only headings and marks change here, so the two affected lines are enough, and a code fence can't change.
            let old = activeLine.flatMap { NSMaxRange($0) <= string.length ? $0 : nil }
            activeLine = caretLine
            storage.beginEditing()
            if let old { styler.style(storage, in: old, activeLine: caretLine, context: string as String) }
            styler.style(storage, in: caretLine, activeLine: caretLine, context: string as String)
            storage.endEditing()
        }

        func textView(_ textView: NSTextView, clickedOnLink link: Any, at charIndex: Int) -> Bool {
            guard let url = link as? URL, url.scheme == "burrow" else {
                if let url = link as? URL { NSWorkspace.shared.open(url) }
                return true
            }
            let newTab = NSEvent.modifierFlags.contains(.command)
            let target = url.path.removingPercentEncoding.map { String($0.dropFirst()) } ?? ""
            if url.host == "task" {
                toggleTask(at: charIndex)
            } else {
                parent.workspace.follow(target, newTab: newTab)
            }
            return true
        }

        private func toggleTask(at index: Int) {
            guard let text, text.isEditable, let storage = text.textStorage else { return }
            let string = storage.string as NSString
            guard index + 2 < string.length else { return }
            let mark = string.substring(with: NSRange(location: index + 1, length: 1))
            let range = NSRange(location: index + 1, length: 1)
            let new = mark == " " ? "x" : " "
            if text.shouldChangeText(in: range, replacementString: new) {
                storage.replaceCharacters(in: range, with: new)
                text.didChangeText()
            }
        }

        func textView(_ textView: NSTextView, completions words: [String], forPartialWordRange charRange: NSRange, indexOfSelectedItem index: UnsafeMutablePointer<Int>?) -> [String] {
            let typed = (textView.string as NSString).substring(with: charRange).lowercased()
            let titles = parent.workspace.map.files.filter { $0.isNote }.map { $0.path.title }
            let hits = titles.filter { typed.isEmpty || $0.lowercased().contains(typed) }
                .sorted { ($0.lowercased().hasPrefix(typed) ? 0 : 1, $0) < ($1.lowercased().hasPrefix(typed) ? 0 : 1, $1) }
            index?.pointee = hits.isEmpty ? -1 : 0
            return Array(hits.prefix(20))
        }

        /// The page shows a note's body; its front matter lives in the properties panel. Code and other files show whole.
        func shown(_ full: String) -> String {
            parent.document.path.isMarkdownPath ? FrontMatter.split(full).body : full
        }

        /// The edited body put back under the note's current front matter.
        func whole(_ body: String) -> String {
            guard parent.document.path.isMarkdownPath else { return body }
            var parts = FrontMatter.split(parent.document.text)
            parts.body = body
            return FrontMatter.join(parts)
        }

        /// Lines of the file that sit above the page, so a line number in the file lands on the right line of the page.
        private var hiddenLines: Int {
            guard parent.document.path.isMarkdownPath else { return 0 }
            let parts = FrontMatter.split(parent.document.text)
            return parts.header.isEmpty ? 0 : parts.header.components(separatedBy: "\n").count - 1 + parts.gap.count
        }

        func jump(toLine fileLine: Int) {
            guard let text else { return }
            let line = max(1, fileLine - hiddenLines)
            let string = text.string as NSString
            var location = 0
            var current = 1
            while current < line, location < string.length {
                location = NSMaxRange(string.lineRange(for: NSRange(location: location, length: 0)))
                current += 1
            }
            let range = string.lineRange(for: NSRange(location: min(location, string.length), length: 0))
            text.scrollRangeToVisible(range)
            text.setSelectedRange(NSRange(location: range.location, length: 0))
            text.showFindIndicator(for: range)
        }
    }
}

final class VaultNSTextView: NSTextView {
    weak var coordinator: VaultTextView.Coordinator?

    /// The text after an unclosed [[ on this line, if the caret is in one.
    var openLinkRange: NSRange? {
        let string = self.string as NSString
        let caret = selectedRange().location
        guard caret <= string.length else { return nil }
        let line = string.lineRange(for: NSRange(location: caret, length: 0))
        let before = string.substring(with: NSRange(location: line.location, length: caret - line.location)) as NSString
        let open = before.range(of: "[[", options: .backwards)
        guard open.location != NSNotFound, before.range(of: "]]", options: .backwards, range: NSRange(location: open.location, length: before.length - open.location)).location == NSNotFound else { return nil }
        let start = line.location + open.location + 2
        return NSRange(location: start, length: caret - start)
    }

    var inWikiLink: Bool { openLinkRange != nil }

    override var rangeForUserCompletion: NSRange { openLinkRange ?? super.rangeForUserCompletion }

    override func insertCompletion(_ word: String, forPartialWordRange charRange: NSRange, movement: Int, isFinal flag: Bool) {
        super.insertCompletion(word, forPartialWordRange: charRange, movement: movement, isFinal: flag)
        guard flag, movement == NSTextMovement.return.rawValue || movement == NSTextMovement.tab.rawValue else { return }
        let caret = selectedRange().location
        let string = self.string as NSString
        let closed = caret + 2 <= string.length && string.substring(with: NSRange(location: caret, length: 2)) == "]]"
        if closed { setSelectedRange(NSRange(location: caret + 2, length: 0)) } else { insertText("]]", replacementRange: selectedRange()) }
    }
}

/// Dresses plain text as a page. Attributes only: the words in the file are never touched.
@MainActor
final class Styler {
    private let markdown: Bool
    private let language: String

    init(markdown: Bool, language: String) {
        self.markdown = markdown
        self.language = language
    }

    private static func regex(_ pattern: String, _ options: NSRegularExpression.Options = []) -> NSRegularExpression { try! NSRegularExpression(pattern: pattern, options: options) }
    private static let bold = regex(#"(\*\*|__)(?=\S)(.+?)(?<=\S)\1"#)
    private static let italic = regex(#"(?<![\*\w])(\*|_)(?=[^\s\*_])(.+?)(?<=[^\s\*_])\1(?![\*\w])"#)
    private static let code = regex(#"(`)([^`\n]+)(`)"#)
    private static let wiki = regex(#"(\[\[)([^\]|]+)(?:(\|)([^\]]+))?(\]\])"#)
    private static let link = regex(#"(\[)([^\]\n]+)(\]\()([^)\s]+)(\))"#)
    private static let tag = regex(#"(?:^|(?<=\s))#[A-Za-z][\w/\-]*"#)
    private static let strike = regex(#"(~~)(.+?)(~~)"#)

    private static let keywords: [String: Set<String>] = [
        "py": ["def", "class", "return", "import", "from", "if", "elif", "else", "for", "while", "try", "except", "with", "as", "in", "not", "and", "or", "None", "True", "False", "raise", "async", "await", "lambda", "yield", "pass"],
        "swift": ["func", "class", "struct", "enum", "protocol", "extension", "let", "var", "return", "import", "if", "else", "guard", "for", "while", "switch", "case", "try", "throw", "throws", "async", "await", "self", "nil", "true", "false", "public", "private", "static", "final", "init"],
        "js": ["function", "class", "return", "import", "from", "export", "default", "if", "else", "for", "while", "const", "let", "var", "try", "catch", "throw", "async", "await", "new", "null", "true", "false", "this"],
    ]
    private static let codeWord = regex(#"\b[A-Za-z_][A-Za-z0-9_]*\b"#)
    private static let codeString = regex(#""(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'"#)
    private static let codeComment = regex(#"(#|//).*$"#, [.anchorsMatchLines])

    private func paragraph(_ size: CGFloat, spacingBefore: CGFloat = 0, after: CGFloat = 4, indent: CGFloat = 0) -> NSParagraphStyle {
        let style = NSMutableParagraphStyle()
        style.lineHeightMultiple = size > 20 ? 1.12 : 1.34
        style.paragraphSpacingBefore = spacingBefore
        style.paragraphSpacing = after
        style.firstLineHeadIndent = indent
        style.headIndent = indent
        return style
    }

    private let body = NSFont.systemFont(ofSize: 16)
    private let mono = NSFont.monospacedSystemFont(ofSize: 13.5, weight: .regular)

    func style(_ storage: NSTextStorage, in range: NSRange, activeLine: NSRange?, context: String? = nil) {
        let string = (context ?? storage.string) as NSString
        guard range.length > 0 || string.length == 0, NSMaxRange(range) <= string.length else { return }
        guard markdown else { return styleCode(storage, in: range, string) }

        let reading = activeLine == nil
        // A fence can open before the range, so the state is worked out from the top of the file.
        var inFence = false
        var inFrontMatter = string.hasPrefix("---\n")
        var location = 0
        var isFirst = true
        while location < string.length {
            let line = string.lineRange(for: NSRange(location: location, length: 0))
            let raw = string.substring(with: line).trimmingCharacters(in: .newlines)
            let trimmed = raw.trimmingCharacters(in: .whitespaces)
            let inRange = NSIntersectionRange(line, range).length > 0
            let isActive = activeLine.map { NSIntersectionRange($0, line).length > 0 || $0.location == line.location } ?? false
            if inFrontMatter {
                if inRange {
                    if reading { vanish(storage, line) } else { apply(storage, line, font: NSFont.monospacedSystemFont(ofSize: 12, weight: .regular), colour: Theme.inkFaintNS, paragraph(12, after: 0)) }
                }
                if !isFirst, trimmed == "---" { inFrontMatter = false }
            } else if trimmed.hasPrefix("```") {
                if inRange {
                    if reading { vanish(storage, line) } else {
                        apply(storage, line, font: mono, colour: Theme.inkFaintNS, paragraph(13.5, after: 0))
                        storage.addAttribute(.backgroundColor, value: Theme.wellNS, range: line)
                    }
                }
                inFence.toggle()
            } else if inFence {
                if inRange {
                    apply(storage, line, font: mono, colour: Theme.inkNS, paragraph(13.5, after: 0))
                    storage.addAttribute(.backgroundColor, value: Theme.wellNS, range: line)
                }
            } else if inRange {
                styleLine(storage, line, raw, showMarks: isActive)
            }
            location = NSMaxRange(line)
            isFirst = false
            if location > NSMaxRange(range), !inRange, !inFence, !inFrontMatter { break }
        }
    }

    /// Reading view keeps the words of the page and hides the machinery around them. The properties are in the side panel.
    private func vanish(_ storage: NSTextStorage, _ range: NSRange) {
        let style = NSMutableParagraphStyle()
        style.maximumLineHeight = 0.1
        storage.setAttributes([.font: NSFont.systemFont(ofSize: 0.01), .foregroundColor: NSColor.clear, .paragraphStyle: style], range: range)
    }

    private func apply(_ storage: NSTextStorage, _ range: NSRange, font: NSFont, colour: NSColor, _ style: NSParagraphStyle) {
        storage.setAttributes([.font: font, .foregroundColor: colour, .paragraphStyle: style], range: range)
    }

    private func mark(_ storage: NSTextStorage, _ range: NSRange, show: Bool) {
        guard range.location != NSNotFound, range.length > 0 else { return }
        if show {
            storage.addAttribute(.foregroundColor, value: Theme.inkFaintNS, range: range)
        } else {
            // Not removed, just given no width, so the file keeps every character.
            storage.addAttributes([.font: NSFont.systemFont(ofSize: 0.01), .foregroundColor: NSColor.clear], range: range)
        }
    }

    private func styleLine(_ storage: NSTextStorage, _ line: NSRange, _ raw: String, showMarks: Bool) {
        let text = raw as NSString
        if raw.trimmingCharacters(in: .whitespaces).isEmpty {
            // A blank line separates paragraphs. At full height it would leave a chasm.
            apply(storage, line, font: NSFont.systemFont(ofSize: 7), colour: Theme.inkNS, paragraph(7, after: 0))
            return
        }
        apply(storage, line, font: body, colour: Theme.inkNS, paragraph(16))
        var inlineStart = 0

        if let level = headingLevel(raw) {
            let sizes: [CGFloat] = [30, 24, 20, 17, 16, 16]
            let size = sizes[level - 1]
            let font = NSFont.systemFont(ofSize: size, weight: level == 1 ? .bold : .semibold)
            apply(storage, line, font: font, colour: Theme.inkNS, paragraph(size, spacingBefore: level <= 2 ? 16 : 10, after: 6))
            mark(storage, NSRange(location: line.location, length: level + 1), show: showMarks)
            inlineStart = level + 1
        } else if raw.hasPrefix("> ") {
            apply(storage, line, font: NSFont.systemFont(ofSize: 16), colour: Theme.inkSoftNS, paragraph(16, indent: 18))
            mark(storage, NSRange(location: line.location, length: 2), show: showMarks)
            inlineStart = 2
        } else if let bullet = bulletRange(raw) {
            let indent = CGFloat(bullet.location) * 8 + 18
            storage.addAttribute(.paragraphStyle, value: paragraph(16, after: 3, indent: indent), range: line)
            storage.addAttribute(.foregroundColor, value: Theme.inkSoftNS, range: NSRange(location: line.location + bullet.location, length: bullet.length))
            inlineStart = bullet.location + bullet.length
            if text.length >= inlineStart + 4, text.substring(with: NSRange(location: inlineStart, length: 1)) == "[", text.substring(with: NSRange(location: inlineStart + 2, length: 2)) == "] " {
                let checked = text.substring(with: NSRange(location: inlineStart + 1, length: 1)) != " "
                let box = NSRange(location: line.location + inlineStart, length: 3)
                storage.addAttributes([.link: URL(string: "burrow://task/x")!, .foregroundColor: NSColor.controlAccentColor, .font: NSFont.monospacedSystemFont(ofSize: 15, weight: .medium)], range: box)
                if checked {
                    storage.addAttributes([.foregroundColor: Theme.inkFaintNS, .strikethroughStyle: NSUnderlineStyle.single.rawValue], range: NSRange(location: line.location + inlineStart + 4, length: text.length - inlineStart - 4))
                }
                inlineStart += 4
            }
        } else if raw == "---" || raw == "***" {
            storage.addAttribute(.foregroundColor, value: Theme.inkFaintNS, range: line)
            return
        }

        let scope = NSRange(location: inlineStart, length: text.length - inlineStart)
        guard scope.length > 0 else { return }
        func at(_ range: NSRange) -> NSRange { NSRange(location: line.location + range.location, length: range.length) }

        for match in Self.bold.matches(in: raw, range: scope) {
            let font = (storage.attribute(.font, at: line.location + match.range(at: 2).location, effectiveRange: nil) as? NSFont) ?? body
            storage.addAttribute(.font, value: NSFontManager.shared.convert(font, toHaveTrait: .boldFontMask), range: at(match.range(at: 2)))
            mark(storage, at(NSRange(location: match.range.location, length: 2)), show: showMarks)
            mark(storage, at(NSRange(location: NSMaxRange(match.range) - 2, length: 2)), show: showMarks)
        }
        for match in Self.italic.matches(in: raw, range: scope) {
            let font = (storage.attribute(.font, at: line.location + match.range(at: 2).location, effectiveRange: nil) as? NSFont) ?? body
            storage.addAttribute(.font, value: NSFontManager.shared.convert(font, toHaveTrait: .italicFontMask), range: at(match.range(at: 2)))
            mark(storage, at(NSRange(location: match.range.location, length: 1)), show: showMarks)
            mark(storage, at(NSRange(location: NSMaxRange(match.range) - 1, length: 1)), show: showMarks)
        }
        for match in Self.strike.matches(in: raw, range: scope) {
            storage.addAttributes([.strikethroughStyle: NSUnderlineStyle.single.rawValue, .foregroundColor: Theme.inkSoftNS], range: at(match.range(at: 2)))
            mark(storage, at(match.range(at: 1)), show: showMarks)
            mark(storage, at(match.range(at: 3)), show: showMarks)
        }
        for match in Self.code.matches(in: raw, range: scope) {
            storage.addAttributes([.font: NSFont.monospacedSystemFont(ofSize: 14, weight: .regular), .backgroundColor: Theme.wellNS], range: at(match.range(at: 2)))
            mark(storage, at(match.range(at: 1)), show: showMarks)
            mark(storage, at(match.range(at: 3)), show: showMarks)
        }
        for match in Self.wiki.matches(in: raw, range: scope) {
            let target = text.substring(with: match.range(at: 2))
            let label = match.range(at: 4).location != NSNotFound ? match.range(at: 4) : match.range(at: 2)
            storage.addAttribute(.link, value: Self.linkURL(target), range: at(label))
            mark(storage, at(match.range(at: 1)), show: showMarks)
            mark(storage, at(match.range(at: 5)), show: showMarks)
            if match.range(at: 4).location != NSNotFound {
                mark(storage, at(NSRange(location: match.range(at: 2).location, length: NSMaxRange(match.range(at: 3)) - match.range(at: 2).location)), show: showMarks)
            }
        }
        for match in Self.link.matches(in: raw, range: scope) {
            let target = text.substring(with: match.range(at: 4))
            let value: Any = target.contains("://") ? (URL(string: target) ?? Self.linkURL(target)) : Self.linkURL(target.removingPercentEncoding ?? target)
            storage.addAttribute(.link, value: value, range: at(match.range(at: 2)))
            mark(storage, at(match.range(at: 1)), show: showMarks)
            mark(storage, at(NSRange(location: match.range(at: 3).location, length: NSMaxRange(match.range(at: 5)) - match.range(at: 3).location)), show: showMarks)
        }
        for match in Self.tag.matches(in: raw, range: scope) {
            storage.addAttribute(.foregroundColor, value: Theme.tagNS, range: at(match.range))
        }
    }

    private static func linkURL(_ target: String) -> URL {
        var parts = URLComponents()
        parts.scheme = "burrow"
        parts.host = "note"
        parts.path = "/" + target
        return parts.url ?? URL(string: "burrow://note/")!
    }

    private func headingLevel(_ raw: String) -> Int? {
        let hashes = raw.prefix { $0 == "#" }.count
        guard (1...6).contains(hashes), raw.dropFirst(hashes).first == " " else { return nil }
        return hashes
    }

    private func bulletRange(_ raw: String) -> (location: Int, length: Int)? {
        let spaces = raw.prefix { $0 == " " || $0 == "\t" }.count
        let rest = raw.dropFirst(spaces)
        if rest.hasPrefix("- ") || rest.hasPrefix("* ") || rest.hasPrefix("+ ") { return (spaces, 2) }
        let digits = rest.prefix { $0.isNumber }.count
        if digits > 0, rest.dropFirst(digits).hasPrefix(". ") { return (spaces, digits + 2) }
        return nil
    }

    private func styleCode(_ storage: NSTextStorage, in range: NSRange, _ string: NSString) {
        let whole = NSRange(location: 0, length: string.length)
        let style = NSMutableParagraphStyle()
        style.lineHeightMultiple = 1.25
        storage.setAttributes([.font: mono, .foregroundColor: Theme.inkNS, .paragraphStyle: style], range: whole)
        let family = ["ts", "tsx", "jsx", "mjs"].contains(language) ? "js" : language
        guard string.length < 200_000 else { return }
        let text = string as String
        if let words = Self.keywords[family] {
            for match in Self.codeWord.matches(in: text, range: whole) where words.contains(string.substring(with: match.range)) {
                storage.addAttribute(.foregroundColor, value: NSColor.systemPurple, range: match.range)
            }
        }
        for match in Self.codeString.matches(in: text, range: whole) { storage.addAttribute(.foregroundColor, value: NSColor.systemGreen, range: match.range) }
        for match in Self.codeComment.matches(in: text, range: whole) where family != "js" || string.substring(with: NSRange(location: match.range.location, length: 1)) == "/" {
            storage.addAttribute(.foregroundColor, value: Theme.inkFaintNS, range: match.range)
        }
    }
}
