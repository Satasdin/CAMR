@testable import BurrowCore
import BurrowTools
@testable import BurrowTUI
import XCTest

final class CellsTests: XCTestCase {
    func testWidths() {
        XCTAssertEqual(Cells.width(of: "abc"), 3)
        XCTAssertEqual(Cells.width(of: "漢字"), 4)
        XCTAssertEqual(Cells.width(of: "🌊"), 2)
        XCTAssertEqual(Cells.width(of: "e\u{0301}"), 1, "a combining mark takes no column")
        XCTAssertEqual(Cells.width(of: "🇰🇪"), 2)
        XCTAssertEqual(Cells.width(of: "👩‍💻"), 2)
        XCTAssertEqual(Cells.width(of: "مرحبا"), 5)
    }

    func testTruncateNeverSplitsACharacter() {
        XCTAssertEqual(Cells.truncate("hello world", to: 6), "hello…")
        XCTAssertEqual(Cells.truncate("short", to: 10), "short")
        XCTAssertEqual(Cells.truncate("漢字漢字", to: 4), "漢…")
        XCTAssertEqual(Cells.truncate("👩‍💻👩‍💻", to: 3), "👩‍💻…")
    }

    func testTruncateLeftKeepsTheEnd() {
        XCTAssertEqual(Cells.truncateLeft("alpha/beta/gamma.md", to: 9), "…gamma.md")
    }
}

final class KeyDecoderTests: XCTestCase {
    func testArrowsAndControls() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed(Array("\u{1B}[A\u{1B}[B\u{1B}OC\r\t\u{03}\u{7F}".utf8)), [.up, .down, .right, .enter, .tab, .control("c"), .backspace])
    }

    func testShiftTabAndPageKeys() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed(Array("\u{1B}[Z\u{1B}[5~\u{1B}[6~\u{1B}[3~\u{1B}[1~\u{1B}[4~".utf8)), [.backTab, .pageUp, .pageDown, .delete, .home, .end])
    }

    func testALoneEscapeWaitsThenCounts() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed([0x1B]), [])
        XCTAssertTrue(decoder.waitingOnEscape)
        XCTAssertEqual(decoder.flushEscape(), [.escape])
        XCTAssertFalse(decoder.waitingOnEscape)
    }

    func testASequenceSplitAcrossReads() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed([0x1B]), [])
        XCTAssertEqual(decoder.feed(Array("[B".utf8)), [.down])
    }

    func testUTF8SplitAcrossReads() {
        var decoder = KeyDecoder()
        let bytes = Array("é".utf8)
        XCTAssertEqual(decoder.feed([bytes[0]]), [])
        XCTAssertEqual(decoder.feed([bytes[1]]), [.character("é")])
    }

    func testBracketedPasteIsOneKey() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed(Array("\u{1B}[200~line\none\u{1B}[201~x".utf8)), [.paste("line\none"), .character("x")])
    }

    func testPastedEscapeSequencesAreNotKeys() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed(Array("\u{1B}[200~\u{1B}[A".utf8)), [])
        XCTAssertEqual(decoder.feed(Array("\u{1B}[201~".utf8)), [.paste("\u{1B}[A")])
    }

    func testInvalidBytesAreDropped() {
        var decoder = KeyDecoder()
        XCTAssertEqual(decoder.feed([0xFF, 0x41]), [.character("A")])
    }
}

final class TextFieldTests: XCTestCase {
    func testEditing() {
        var field = TextField()
        for key: Key in [.character("a"), .character("c"), .left, .character("b")] { XCTAssertTrue(field.apply(key)) }
        XCTAssertEqual(field.text, "abc")
        _ = field.apply(.backspace)
        XCTAssertEqual(field.text, "ac")
        _ = field.apply(.control("w"))
        XCTAssertEqual(field.text, "c")
        _ = field.apply(.home)
        _ = field.apply(.delete)
        XCTAssertEqual(field.text, "")
    }

    func testPastedLinesBecomeOneLine() {
        var field = TextField()
        _ = field.apply(.paste("one\ntwo\r\nthree\rfour\u{1B}[A"))
        XCTAssertEqual(field.text, "one two three four[A")
    }

    func testALongLineScrollsToTheCursor() {
        var field = TextField(String(repeating: "x", count: 50))
        let view = field.visible(width: 10)
        XCTAssertEqual(view.cursorColumn, 9)
        _ = field.apply(.home)
        XCTAssertEqual(field.visible(width: 10).cursorColumn, 0)
    }
}

final class FrameTests: XCTestCase {
    func testWideCharactersTakeTwoColumns() {
        var frame = Frame(width: 6, height: 1)
        XCTAssertEqual(frame.put(0, 0, "漢a"), 3)
        XCTAssertEqual(frame.row(0), "漢a   ")
    }

    func testAWideCharacterThatDoesNotFitLeavesABlank() {
        var frame = Frame(width: 3, height: 1)
        frame.put(2, 0, "漢")
        XCTAssertEqual(frame.row(0), "   ")
    }

    func testControlCharactersNeverReachTheTerminal() {
        var frame = Frame(width: 20, height: 1)
        frame.put(0, 0, "a\u{1B}[2Jb\u{07}")
        let sent = frame.encoded(from: nil, depth: .none)
        XCTAssertFalse(sent.contains("\u{1B}[2Jb"))
        XCTAssertEqual(frame.row(0).trimmingCharacters(in: .whitespaces), "a[2Jb")
    }

    func testOnlyChangesAreSent() {
        var first = Frame(width: 20, height: 3)
        first.put(0, 0, "unchanged line")
        var second = first
        second.put(0, 2, "new")
        let sent = second.encoded(from: first, depth: .none)
        XCTAssertFalse(sent.contains("unchanged"))
        XCTAssertTrue(sent.contains("new"))
    }

    func testNoColorStillShowsEmphasis() {
        var frame = Frame(width: 10, height: 1)
        frame.put(0, 0, "x", Style(ink: .note, bold: true))
        let mono = frame.encoded(from: nil, depth: .none)
        XCTAssertTrue(mono.contains("\u{1B}[0;1m"))
        XCTAssertFalse(mono.contains("38;5"))
        XCTAssertTrue(frame.encoded(from: nil, depth: .full).contains("38;5;178"))
    }

    func testColorDepth() {
        XCTAssertEqual(ColorDepth.detect(environment: ["NO_COLOR": "1", "TERM": "xterm-256color"]), .none)
        XCTAssertEqual(ColorDepth.detect(environment: ["TERM": "dumb"]), .none)
        XCTAssertEqual(ColorDepth.detect(environment: ["TERM": "screen-256color"]), .full)
        XCTAssertEqual(ColorDepth.detect(environment: ["TERM": "xterm"]), .sixteen)
    }
}

final class LayoutTests: XCTestCase {
    func testWideWindowsShowThreePanes() {
        let layout = Layout.vault(width: 130, height: 40, focus: .tree, showSide: true)
        XCTAssertNotNil(layout.tree)
        XCTAssertNotNil(layout.reader)
        XCTAssertNotNil(layout.side)
        XCTAssertLessThanOrEqual(layout.readerTextWidth, Layout.readingMeasure)
    }

    func testMiddleWindowsDropTheSidePanel() {
        let layout = Layout.vault(width: 90, height: 30, focus: .reader, showSide: true)
        XCTAssertNotNil(layout.tree)
        XCTAssertNil(layout.side)
    }

    func testNarrowWindowsShowOnlyTheFocusedPane() {
        let tree = Layout.vault(width: 60, height: 24, focus: .tree, showSide: true)
        XCTAssertNotNil(tree.tree)
        XCTAssertNil(tree.reader)
        let reader = Layout.vault(width: 60, height: 24, focus: .reader, showSide: true)
        XCTAssertNil(reader.tree)
        XCTAssertNotNil(reader.reader)
    }

    func testPanesStayInsideTheWindow() {
        for width in stride(from: 40, through: 220, by: 7) {
            for focus in [Focus.tree, .reader, .links] {
                let layout = Layout.vault(width: width, height: 30, focus: focus, showSide: true)
                for rect in [layout.tree, layout.reader, layout.side].compactMap({ $0 }) {
                    XCTAssertGreaterThanOrEqual(rect.x, 0)
                    XCTAssertLessThanOrEqual(rect.right, width, "\(width) \(focus)")
                    XCTAssertGreaterThan(rect.width, 0, "\(width) \(focus)")
                }
            }
        }
    }
}

final class MarkdownTests: XCTestCase {
    private func render(_ text: String, width: Int = 40, known: [String] = ["Other.md", "src/a.py"]) -> RenderedDocument {
        DocumentRenderer(width: width, isNote: { $0.hasSuffix(".md") }, resolve: { target in
            known.first { $0 == target || $0 == target + ".md" }
        }).renderNote(text)
    }

    private func plain(_ document: RenderedDocument) -> [String] { document.lines.map(\.plain) }

    func testHeadingsLoseTheirMarks() {
        let lines = render("# Title\n\nbody").lines
        XCTAssertEqual(lines[0].plain, "Title")
        XCTAssertTrue(lines[0].spans[0].style.bold)
    }

    func testFrontMatterBecomesAQuietLine() {
        XCTAssertEqual(plain(render("---\nkind: bug\ndate: 2026-01-02\n---\n\nHello")), ["kind  bug", "date  2026-01-02", "", "Hello"])
        XCTAssertEqual(plain(render("---\ntags:\n  - a\n  - b\nsource: https://x.org\n---\nHi")), ["tags    #a  #b", "source  https://x.org", "", "Hi"])
    }

    func testSourceLinesCountFromTheFile() {
        let lines = render("---\nkind: bug\n---\n\nline five\n\nline seven").lines
        XCTAssertEqual(lines.first { $0.plain == "line seven" }?.source, 7)
    }

    func testWikiLinksShowTheirNameAndResolve() {
        let document = render("See [[Other]] and [[Other|that one]].")
        XCTAssertEqual(plain(document), ["See Other and that one."])
        XCTAssertEqual(document.links.map(\.resolved), ["Other.md", "Other.md"])
        XCTAssertEqual(document.links.map(\.label), ["Other", "that one"])
    }

    func testAMissingWikiLinkStaysFaint() {
        let document = render("[[Nope]]")
        XCTAssertNil(document.links[0].resolved)
        XCTAssertTrue(document.lines[0].spans[0].style.dim)
    }

    func testMarkdownLinksAndWebAddresses() {
        let document = render("[a](Other.md) and [b](https://example.com/x)")
        XCTAssertEqual(document.links[0].resolved, "Other.md")
        XCTAssertTrue(document.links[1].isExternal)
        XCTAssertEqual(plain(document), ["a and b"])
    }

    func testAPathInBackticksIsFollowable() {
        XCTAssertEqual(render("see `src/a.py` here").links[0].resolved, "src/a.py")
    }

    func testBoldItalicAndCode() {
        let line = render("**bold** and *it* and `code`").lines[0]
        XCTAssertEqual(line.plain, "bold and it and code")
        XCTAssertTrue(line.spans.first { $0.text == "bold" }!.style.bold)
        XCTAssertTrue(line.spans.first { $0.text == "it" }!.style.italic)
        XCTAssertEqual(line.spans.first { $0.text == "code" }!.style.ink, .code)
    }

    func testUnderscoresInNamesAreNotItalic() {
        XCTAssertEqual(plain(render("call pay_invoice and retry_charge now")), ["call pay_invoice and retry_charge now"])
    }

    func testListsAndTasks() {
        XCTAssertEqual(plain(render("- one\n- [ ] two\n- [x] three\n1. first")), ["• one", "☐ two", "☑ three", "1. first"])
    }

    func testAWrappedListItemHangsUnderItsText() {
        let lines = plain(render("- " + String(repeating: "word ", count: 12), width: 20))
        XCTAssertTrue(lines[1].hasPrefix("  "))
        XCTAssertFalse(lines[1].hasPrefix("   "))
    }

    func testCodeFencesKeepTheirText() {
        XCTAssertEqual(plain(render("```python\n**not bold**\n```")).prefix(2), ["python", "  **not bold**"])
    }

    func testTablesLineUp() {
        let lines = plain(render("| A | Bee |\n|---|---|\n| one | 2 |"))
        XCTAssertEqual(lines[0], "A   │ Bee")
        XCTAssertEqual(lines[1], "one │ 2  ")
    }

    func testATableTooWideBecomesLines() {
        let lines = plain(render("| aaaaaaaaaaaaaa | bbbbbbbbbbbbbbb |\n|---|---|\n| c | d |", width: 12))
        XCTAssertTrue(lines.contains { $0.contains("·") })
    }

    func testALinkKeepsItsIdentityAcrossAWrap() {
        let document = render("start [[Other|a long label that wraps over lines]]", width: 16)
        let carrying = document.lines.filter { $0.spans.contains { $0.link == 0 } }
        XCTAssertGreaterThan(carrying.count, 1)
    }

    func testNoLineIsWiderThanAsked() {
        let text = "# A heading that goes on\n\nParagraph 漢字漢字 with **bold** and [[Other]] and 🌊 waves and a verylongwordthatcannotfitonasinglelineatall.\n\n- list item that also wraps around\n\n> quoted text that is long enough to wrap"
        for width in [12, 20, 37] {
            for line in render(text, width: width).lines { XCTAssertLessThanOrEqual(Cells.width(of: line.plain), width, line.plain) }
        }
    }

    func testCommentsAreHidden() {
        XCTAssertEqual(plain(render("a<!-- hidden -->b")), ["ab"])
    }

    func testCodeFilesGetLineNumbers() {
        let document = DocumentRenderer(width: 30, isNote: { _ in false }, resolve: { _ in nil }).renderCode("first\n\tsecond\n")
        XCTAssertEqual(document.lines.map(\.plain), ["  1  first", "  2      second"])
    }
}

final class ModelTests: XCTestCase {
    private var fixture: VaultFixture!
    private var model: Model!

    override func setUp() async throws {
        fixture = try VaultFixture()
        let vault = try await fixture.opened()
        model = Model(vault: vault, modelName: "stand-in")
        model.resize(width: 120, height: 34)
        model.reload()
    }

    private func press(_ keys: Key...) { for key in keys { _ = model.handle(key) } }
    private func type(_ text: String) { for character in text { _ = model.handle(.character(character)) } }
    private func screen() -> String { View.render(model).plainText }

    func testTheTreeListsFoldersFirstAndMarksLinkedOnes() {
        XCTAssertEqual(model.rows.first?.name, "Decisions")
        XCTAssertTrue(model.rows.contains { $0.name == "shop" && $0.isLinked })
        XCTAssertTrue(screen().contains("Files"))
    }

    func testFoldersFoldAndUnfold() {
        let before = model.rows.count
        press(.left)
        XCTAssertLessThan(model.rows.count, before)
        press(.right)
        XCTAssertEqual(model.rows.count, before)
    }

    func testOpeningFromTheTree() {
        model.treeSelected = model.rows.firstIndex { $0.path == "Home.md" }!
        press(.enter)
        XCTAssertEqual(model.document?.path, "Home.md")
        XCTAssertEqual(model.focus, .reader)
        XCTAssertTrue(screen().contains("Start with Decisions/Retry".prefix(10)))
    }

    func testFollowingALinkAndComingBack() {
        model.open("Home.md")
        press(.tab)
        XCTAssertEqual(model.document?.activeLink, 0)
        press(.enter)
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
        press(.character("["))
        XCTAssertEqual(model.document?.path, "Home.md")
        press(.character("]"))
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
    }

    func testABrokenLinkSaysSoAndStaysPut() {
        model.open("Decisions/Retry.md")
        press(.tab, .tab, .enter)
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
        XCTAssertTrue(model.status?.contains("Missing note") ?? false)
        XCTAssertTrue(model.statusIsProblem)
    }

    func testBacklinksAreListed() {
        model.open("Decisions/Retry.md")
        XCTAssertTrue(model.sideRows.contains { $0.path == "Home.md" && !$0.forward })
        XCTAssertTrue(screen().contains("Linked from"))
    }

    func testQuickOpenFindsByScatteredLetters() {
        press(.character("o"))
        XCTAssertEqual(model.overlay, .quickOpen)
        type("lmu")
        XCTAssertEqual(model.quick.results.first?.path, "Trips/Lamu.md")
        press(.enter)
        XCTAssertEqual(model.document?.path, "Trips/Lamu.md")
        XCTAssertEqual(model.overlay, .none)
    }

    func testSearchOpensAtTheLine() {
        press(.character("/"))
        type("failed charge")
        XCTAssertEqual(model.search.results.first?.path, "Decisions/Retry.md")
        press(.enter)
        XCTAssertEqual(model.document?.path, "Decisions/Retry.md")
        XCTAssertEqual(model.document?.markedLine, 3)
    }

    func testSearchScopeNarrowsResults() {
        press(.character("/"))
        type("service")
        XCTAssertTrue(model.search.results.contains { $0.path.hasPrefix("shop/") })
        model.ask.scope = "Trips"
        model.updateSearchResults()
        XCTAssertTrue(model.search.results.isEmpty)
    }

    func testAQuoteOnlySearchIsNotACrash() {
        press(.character("/"))
        type("\"")
        XCTAssertNotNil(View.render(model))
    }

    func testEscapeClosesAnOverlay() {
        press(.character("?"))
        XCTAssertEqual(model.overlay, .help)
        press(.escape)
        XCTAssertEqual(model.overlay, .none)
    }

    func testTheStarCentresAndRecentres() {
        model.open("Home.md")
        press(.character("s"))
        XCTAssertEqual(model.page, .star)
        XCTAssertFalse(model.star.neighbours.isEmpty)
        let next = model.star.neighbours[0].path
        press(.enter)
        XCTAssertEqual(model.star.center, next)
        press(.escape)
        XCTAssertEqual(model.page, .vault)
    }

    func testStarsDoNotShareARowOnOneSide() {
        let placed = StarMap.place(count: 20, in: Rect(x: 0, y: 2, width: 120, height: 28))
        for side in [true, false] {
            let rows = placed.filter { $0.labelOnRight == side }.map(\.y)
            XCTAssertEqual(Set(rows).count, rows.count)
        }
    }

    func testAskSendsTheQuestionWithItsScope() {
        press(.character("a"))
        type("hello?")
        model.ask.scope = "shop"
        let effects = model.handle(.enter)
        XCTAssertEqual(effects, [.ask(question: "hello?", folder: "shop")])
        XCTAssertEqual(model.ask.status, .searching)
        XCTAssertTrue(screen().contains("Looking through the vault"))
    }

    func testTypingInAskDoesNotTriggerShortcuts() {
        press(.character("a"))
        type("q/o")
        XCTAssertEqual(model.ask.field.text, "q/o")
        XCTAssertEqual(model.page, .ask)
    }

    func testAnAnswerShowsWithItsSources() {
        press(.character("a"))
        type("hello")
        _ = model.handle(.enter)
        model.askWord("The answer.")
        model.ask.entries[0].sources = [ToolResult.Source(path: "Home.md", startLine: 1, endLine: 8, reason: "search")]
        model.askFinished(seconds: 1.5)
        let text = screen()
        XCTAssertTrue(text.contains("The answer."))
        XCTAssertTrue(text.contains("Sources  1"))
        XCTAssertTrue(text.contains("Home.md:1"))
        press(.control("o"))
        XCTAssertEqual(model.document?.path, "Home.md")
    }

    func testAFailedAnswerIsShownNotFatal() {
        press(.character("a"))
        type("hello")
        _ = model.handle(.enter)
        model.askFailed("Ollama isn't answering.")
        XCTAssertEqual(model.ask.status, .idle)
        XCTAssertTrue(screen().contains("Ollama isn't answering"))
    }

    func testAModelsEscapeCodesAreRemoved() {
        press(.character("a"))
        type("x")
        _ = model.handle(.enter)
        model.askWord("safe\u{1B}[2Jtext")
        XCTAssertEqual(model.ask.entries[0].answer, "safe[2Jtext")
    }

    func testControlCAlwaysQuitsEvenWhileTyping() {
        press(.character("a"))
        XCTAssertEqual(model.handle(.control("c")), [.quit])
    }

    func testResizingKeepsTheReadersPlace() async throws {
        let long = (1...400).map { "Line number \($0) of a long note." }.joined(separator: "\n\n")
        try long.write(to: fixture.vaultFolder.appendingPathComponent("Long.md"), atomically: true, encoding: .utf8)
        try await model.vault.refresh()
        model.reload()
        model.open("Long.md")
        model.document?.scroll = 300
        let source = model.document!.rendered.lines[300].source
        model.resize(width: 64, height: 20)
        model.resize(width: 150, height: 44)
        XCTAssertEqual(model.document!.rendered.lines[model.document!.scroll].source, source)
    }

    func testEveryPageDrawsAtEverySize() {
        model.open("Home.md")
        let keys: [[Key]] = [[], [.character("/")], [.escape, .character("o")], [.escape, .character("?")], [.escape, .character("s")], [.escape, .character("a")]]
        for size in [(40, 12), (41, 13), (60, 20), (71, 24), (72, 24), (80, 24), (109, 30), (110, 30), (200, 60), (39, 11), (10, 3), (1, 1)] {
            model.resize(width: size.0, height: size.1)
            for sequence in keys {
                for key in sequence { _ = model.handle(key) }
                _ = View.render(model)
            }
            _ = model.handle(.escape)
            model.page = .vault
        }
    }

    func testTooSmallSaysSo() {
        model.resize(width: 30, height: 8)
        XCTAssertTrue(screen().contains("Burrow needs"))
    }

    func testHintsAreVisible() {
        model.resize(width: 120, height: 30)
        XCTAssertTrue(screen().contains("search"))
        XCTAssertTrue(screen().contains("quit"))
    }

    func testEscapesInAFileCannotReachTheScreen() {
        model.open("Bad.md")
        let sent = View.render(model).encoded(from: nil, depth: .none)
        XCTAssertFalse(sent.contains("\u{1B}[2J escape"))
    }

    func testAnEmptyVaultHasAPlainMessage() throws {
        let empty = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: empty, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: empty) }
        let blank = Model(vault: try Vault(project: empty, everything: true), modelName: "x")
        blank.indexing = nil
        blank.resize(width: 100, height: 30)
        blank.reload()
        XCTAssertTrue(View.render(blank).plainText.contains("Nothing here yet"))
    }

    func testFuzzyPrefersTheFileName() {
        XCTAssertGreaterThan(Fuzzy.score("lamu", in: "Trips/Lamu.md")!, Fuzzy.score("lamu", in: "Lamu stuff/other.md") ?? 0)
        XCTAssertNil(Fuzzy.score("zzz", in: "Home.md"))
    }
}
