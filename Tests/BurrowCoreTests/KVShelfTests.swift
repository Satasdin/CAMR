@testable import BurrowCore
import XCTest

final class KVShelfTests: XCTestCase {
    func testACacheIsRefusedForAnotherModelOrChangedFiles() throws {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: folder) }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try "# Act\n\nSix years.\n".write(to: folder.appendingPathComponent("act.md"), atomically: true, encoding: .utf8)
        let vault = try Vault(project: folder, everything: true)
        let shelf = KVShelf(vault: vault)

        let prefix = try shelf.prefix(for: ["act.md"])
        XCTAssertTrue(prefix.contains("<excerpt file=\"act.md\">\n1: # Act"))
        XCTAssertTrue(prefix.hasSuffix("\n"), "the prefix ends on a line break, so the question's tokens start cleanly")
        XCTAssertEqual(KVShelf.key(for: ["act.md"]), KVShelf.key(for: ["act.md"]))
        XCTAssertNotEqual(KVShelf.key(for: ["act.md"]), KVShelf.key(for: ["act.md", "b.md"]))

        try FileManager.default.createDirectory(at: shelf.folder, withIntermediateDirectories: true)
        let key = KVShelf.key(for: ["act.md"])
        try Data([1, 2, 3]).write(to: shelf.folder.appendingPathComponent(key + ".bin"))
        let entry = KVShelf.Entry(key: key, model: "qwen3-4b", file: key + ".bin", sources: shelf.hashes(["act.md"]), tokens: 40, bytes: 3, buildSeconds: 0.1, created: Date())
        XCTAssertNil(shelf.stale(entry, model: "qwen3-4b"))
        XCTAssertNotNil(shelf.stale(entry, model: "gemma4"), "a cache only fits the model that built it")
        try "# Act\n\nFive years.\n".write(to: folder.appendingPathComponent("act.md"), atomically: true, encoding: .utf8)
        XCTAssertNotNil(shelf.stale(entry, model: "qwen3-4b"), "a changed file makes the cache stale")
    }
}
