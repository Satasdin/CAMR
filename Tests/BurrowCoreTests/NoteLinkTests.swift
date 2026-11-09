@testable import BurrowCore
import XCTest

final class NoteLinkTests: XCTestCase {
    private let code = "def amount(x):\n    return x\n\nclass Quote:\n    pass\n\ndef charge_card():\n    pass\n"

    private func linked(_ note: String) -> Bool {
        LinkFinder.links(files: ["price.py": code, "notes/a.md": note], notes: ["notes/a.md"])
            .contains { $0.from == "notes/a.md" && $0.to == "price.py" }
    }

    func testEverydayWordsDoNotLinkANoteToCode() {
        XCTAssertFalse(linked("Every mode gets the same amount of text."))
    }

    func testCodeNamesDoLinkANoteToCode() {
        XCTAssertTrue(linked("Never retry charge_card, it charged a customer twice."))
        XCTAssertTrue(linked("Quote is frozen once sent."))
        XCTAssertTrue(linked("Don't round inside `amount`."))
        XCTAssertTrue(linked("amount() must stay exact."))
        XCTAssertTrue(linked("The function amount must stay exact."))
    }

    func testAPathStillLinks() {
        XCTAssertTrue(linked("See price.py for how this is done."))
    }
}
