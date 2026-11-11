import BurrowCore
import Foundation

extension VaultTools {
    /// `vault_pack`: one part of a folder read whole (D-59). The text is exactly the pack's text, so a client program can
    /// also use it as its system message and be answered from a cache the server saved.
    func pack(_ given: ToolArguments) async throws -> ToolResult {
        let folder: String?
        do { folder = try scope(given.text("folder")) } catch let problem as ToolProblem { return .failure(problem.description) }
        let shelf = KVShelf(vault: vault)
        let plan: KVPackPlan
        do { plan = try shelf.plan(scope: folder ?? "", budgetCharacters: KVShelf.packCharacters(windowTokens: packWindow)) } catch {
            return .failure("\(error)")
        }
        let part = given.number("part") ?? 1
        guard let pack = plan.packs.first(where: { $0.part == part }) else {
            return .failure("\(plan.scope.isEmpty ? "The vault" : plan.scope) has \(plan.packs.count) part\(plan.packs.count == 1 ? "" : "s"), so there is no part \(part).")
        }
        let sources = (plan.spinePaths.map { ToolResult.Source(path: $0, startLine: 1, endLine: 1, reason: "pack spine") })
            + pack.pieces.map { ToolResult.Source(path: $0.path, startLine: $0.first, endLine: $0.last, reason: "pack") }
        return ToolResult(text: shelf.text(of: pack, in: plan), sources: sources,
                          summary: "\(plan.scope.isEmpty ? "vault" : plan.scope) part \(part) of \(plan.packs.count), \(pack.paths.count) files")
    }
}
