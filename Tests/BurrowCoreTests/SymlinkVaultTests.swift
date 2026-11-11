@testable import BurrowCore
import XCTest

/// A vault opened through a symbolic link is read at the link's target, so it is not empty.
final class SymlinkVaultTests: XCTestCase {
    func testAVaultOpenedThroughALinkFindsItsFiles() async throws {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent("symlink-vault-\(UUID().uuidString)")
        let real = base.appendingPathComponent("real")
        try FileManager.default.createDirectory(at: real.appendingPathComponent("Notes"), withIntermediateDirectories: true)
        try "# Hello\n\nThe shelf keeps 12 GB.\n".write(to: real.appendingPathComponent("Notes/a.md"), atomically: true, encoding: .utf8)
        let link = base.appendingPathComponent("link")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: real)
        defer { try? FileManager.default.removeItem(at: base) }

        let vault = try Vault(project: link, everything: true)
        _ = try await vault.refresh(embedder: nil)
        XCTAssertEqual(try vault.stats().notes, 1)
        XCTAssertEqual(try vault.projectMap().files.map(\.path), ["Notes/a.md"])
        XCTAssertNotNil(vault.text(of: "Notes/a.md"))
    }

    func testALinkInsideTheVaultStillCannotReachOutside() async throws {
        let base = FileManager.default.temporaryDirectory.appendingPathComponent("symlink-vault-\(UUID().uuidString)")
        let vaultFolder = base.appendingPathComponent("vault")
        try FileManager.default.createDirectory(at: vaultFolder, withIntermediateDirectories: true)
        try "secret\n".write(to: base.appendingPathComponent("outside.md"), atomically: true, encoding: .utf8)
        try "inside\n".write(to: vaultFolder.appendingPathComponent("inside.md"), atomically: true, encoding: .utf8)
        try FileManager.default.createSymbolicLink(at: vaultFolder.appendingPathComponent("shortcut.md"), withDestinationURL: base.appendingPathComponent("outside.md"))
        defer { try? FileManager.default.removeItem(at: base) }

        let vault = try Vault(project: vaultFolder, everything: true)
        _ = try await vault.refresh(embedder: nil)
        XCTAssertEqual(try vault.projectMap().files.map(\.path), ["inside.md"])
    }
}
