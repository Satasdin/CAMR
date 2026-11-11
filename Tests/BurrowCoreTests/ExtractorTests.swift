import AppKit
@testable import BurrowCore
import XCTest

final class ExtractorTests: XCTestCase {
    func testWordAndRichTextBecomeMarkdownWithATitle() throws {
        let text = NSAttributedString(string: "Section one\n\nThe term is six years.\n# not a heading\n")
        for (kind, type) in [("docx", NSAttributedString.DocumentType.officeOpenXML), ("rtf", .rtf)] {
            let data = try text.data(from: NSRange(location: 0, length: text.length), documentAttributes: [.documentType: type])
            let markdown = try XCTUnwrap(Extractor.extract(data, path: "Docs/act.\(kind)"), kind)
            XCTAssertTrue(markdown.hasPrefix("---\ntitle: act\nextracted-from: \(kind)\n---\n\n# act\n"), kind)
            XCTAssertTrue(markdown.contains("The term is six years."), kind)
            XCTAssertTrue(markdown.contains("\\# not a heading"), "a line starting with # is not taken for a heading")
        }
    }

    func testAPDFGetsAHeadingPerPage() throws {
        let data = NSMutableData()
        var box = CGRect(x: 0, y: 0, width: 300, height: 300)
        let consumer = CGDataConsumer(data: data as CFMutableData)!
        let context = CGContext(consumer: consumer, mediaBox: &box, nil)!
        for page in 1...2 {
            context.beginPDFPage(nil)
            let line = CTLineCreateWithAttributedString(NSAttributedString(string: "Clause on page \(page) about retention", attributes: [.font: NSFont.systemFont(ofSize: 14)]))
            context.textPosition = CGPoint(x: 20, y: 150)
            CTLineDraw(line, context)
            context.endPDFPage()
        }
        context.closePDF()
        let markdown = try XCTUnwrap(Extractor.extract(data as Data, path: "a.pdf"))
        XCTAssertTrue(markdown.contains("## Page 1"))
        XCTAssertTrue(markdown.contains("## Page 2"))
        XCTAssertTrue(markdown.contains("Clause on page 2"))
        let pieces = Chunker.markdownChunks(of: markdown)
        XCTAssertTrue(pieces.contains { $0.section.contains("Page 2") || $0.section.contains("a") })
    }

    func testOnlyKnownDocumentsAreTaken() {
        XCTAssertTrue(Extractor.handles("x/Report.PDF"))
        XCTAssertTrue(Extractor.handles("scan.heic"))
        XCTAssertFalse(Extractor.handles("main.swift"))
        XCTAssertTrue(Scanner.wanted("Docs/report.docx"))
    }
}
