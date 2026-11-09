@testable import BurrowCore
import XCTest

final class VaultOfEverythingTests: XCTestCase {
    private var top: URL!
    private var vaultFolder: URL { top.appendingPathComponent("vault") }
    private var codeFolder: URL { top.appendingPathComponent("shop") }

    override func setUpWithError() throws {
        top = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        for (path, text) in [
            "vault/Home.md": "Start here. See [[Trips/Lamu]] and [plan](Plan%20B.md). #life",
            "vault/Plan B.md": "Nothing yet about pay_invoice in shop.",
            "vault/Trips/Lamu.md": "A week by the sea. Back to [[Home]]. #travel",
            "vault/Recipes/ugali.txt": "maize flour and water",
            "shop/billing.py": "def pay_invoice(amount):\n    return amount\n",
            "shop/README.md": "The shop service.",
        ] {
            let url = top.appendingPathComponent(path)
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try text.write(to: url, atomically: true, encoding: .utf8)
        }
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: top) }

    private func opened() async throws -> Vault {
        let vault = try Vault(project: vaultFolder, everything: true)
        try vault.linkFolder(codeFolder)
        try await vault.refresh()
        return vault
    }

    func testEveryMarkdownFileIsANoteAndALinkedFolderIsNot() async throws {
        let map = try await opened().projectMap()
        XCTAssertEqual(Set(map.files.filter(\.isNote).map(\.path)), ["Home.md", "Plan B.md", "Trips/Lamu.md"])
        XCTAssertTrue(map.files.contains { $0.path == "shop/billing.py" && !$0.isNote })
    }

    func testWikiAndMarkdownLinksConnectNotes() async throws {
        let vault = try await opened()
        let out = try vault.neighbours(of: "Home.md").filter(\.forward).map(\.path)
        XCTAssertTrue(out.contains("Trips/Lamu.md"))
        XCTAssertTrue(out.contains("Plan B.md"))
        XCTAssertEqual(try vault.mentions(of: "Home.md").first?.path, "Trips/Lamu.md")
    }

    func testANoteCanLinkIntoALinkedFolder() async throws {
        let vault = try await opened()
        XCTAssertTrue(try vault.neighbours(of: "Plan B.md").contains { $0.path == "shop/billing.py" })
    }

    func testScopeStaysInsideTheFolder() async throws {
        let vault = try await opened()
        let found = try await vault.retrieve("service shop week sea", mode: .search, scope: "shop")
        XCTAssertFalse(found.paths.isEmpty)
        XCTAssertTrue(found.paths.allSatisfy { $0.hasPrefix("shop/") })
    }

    func testALinkedFolderCanBeReadButNotChanged() async throws {
        let vault = try await opened()
        XCTAssertTrue(vault.text(of: "shop/billing.py")?.contains("pay_invoice") ?? false)
        XCTAssertFalse(vault.canEdit("shop/README.md"))
        XCTAssertThrowsError(try vault.writeNote("shop/README.md", text: "changed"))
        XCTAssertThrowsError(try vault.trash("shop/billing.py"))
        XCTAssertThrowsError(try vault.move("shop/billing.py", to: ""))
    }

    func testNothingCanLeaveTheVault() async throws {
        let vault = try await opened()
        XCTAssertNil(vault.text(of: "../shop/billing.py"))
        XCTAssertThrowsError(try vault.writeNote("../outside.md", text: "x"))
    }

    func testCreatingRenamingAndMovingNotes() async throws {
        let vault = try await opened()
        let made = try vault.createNote(named: "Ideas", in: "Trips")
        XCTAssertEqual(made, "Trips/Ideas.md")
        XCTAssertEqual(try vault.createNote(named: "Ideas", in: "Trips"), "Trips/Ideas 2.md")
        XCTAssertEqual(try vault.renameNote(made, to: "Better"), "Trips/Better.md")
        XCTAssertEqual(try vault.move("Trips/Better.md", to: "Recipes"), "Recipes/Better.md")
        XCTAssertThrowsError(try vault.move("Trips", to: "Trips/Inner"))
    }

    func testSearchFindsTheLineAndTagsAreCollected() async throws {
        let vault = try await opened()
        let hit = try vault.searchLines("week sea").first
        XCTAssertEqual(hit?.path, "Trips/Lamu.md")
        XCTAssertEqual(hit?.line, 1)
        XCTAssertEqual(try vault.tags()["travel"], ["Trips/Lamu.md"])
    }

    func testAKeptNoteGoesInMemoryWithAReadableName() async throws {
        let vault = try await opened()
        let path = try vault.addNote("We rejected retries on the gateway", kind: .rejected)
        XCTAssertEqual(path, "Memory/Rejected - We rejected retries on the gateway.md")
    }

    func testAFolderPathLinkIsShownAsAMentionOnItsOwnLine() async throws {
        try "---\nkind: note\n---\nFirst.\n\nSee [[Trips/Lamu|the coast]].\n".write(to: vaultFolder.appendingPathComponent("Aside.md"), atomically: true, encoding: .utf8)
        let vault = try await opened()
        let mention = try vault.mentions(of: "Trips/Lamu.md").first { $0.path == "Aside.md" }
        XCTAssertEqual(mention?.line, 6)
    }

    func testAShortcutCannotReadOutsideTheVault() async throws {
        try FileManager.default.createSymbolicLink(at: vaultFolder.appendingPathComponent("leak.md"), withDestinationURL: codeFolder.appendingPathComponent("README.md"))
        let vault = try await opened()
        XCTAssertFalse(try vault.projectMap().files.contains { $0.path == "leak.md" })
        XCTAssertNil(vault.text(of: "leak.md"))
    }

    func testHiddenFoldersAreLeftOut() async throws {
        let secret = vaultFolder.appendingPathComponent(".secret/key.md")
        try FileManager.default.createDirectory(at: secret.deletingLastPathComponent(), withIntermediateDirectories: true)
        try "hidden".write(to: secret, atomically: true, encoding: .utf8)
        let vault = try await opened()
        XCTAssertFalse(try vault.projectMap().files.contains { $0.path.contains(".secret") })
    }

    func testObsidianSettingsAreLeftOut() async throws {
        let settings = vaultFolder.appendingPathComponent(".obsidian/app.json")
        try FileManager.default.createDirectory(at: settings.deletingLastPathComponent(), withIntermediateDirectories: true)
        try "{}".write(to: settings, atomically: true, encoding: .utf8)
        let vault = try await opened()
        XCTAssertFalse(try vault.projectMap().files.contains { $0.path.contains(".obsidian") })
    }
}
