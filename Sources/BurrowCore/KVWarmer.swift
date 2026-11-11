import Foundation

/// Keeps the shelf warm while a client works (D-60).
///
/// When a client's lookup returns files, the folders they sit in are read into the model's cache on a spare llama.cpp
/// slot, filed on the shelf, and loaded again the next time those folders come up. All of it happens after the client
/// already has its answer, and only while the server has nothing else to do. Nothing here can fail a lookup: the text
/// went to the client first, and every problem is only logged.
public actor KVWarmer {
    public struct Settings: Sendable {
        public var server: URL
        /// The most the shelf may hold. The least recently used caches are cleared past it.
        public var limitBytes: Int = 12 * 1_073_741_824
        /// How many separate lookups have to touch a folder before it is worth reading into the cache.
        public var lookupsBeforeWarming = 2
        /// How long to wait for the server to be idle before giving up on a build.
        public var idleWait: TimeInterval = 600
        public var idlePoll: TimeInterval = 2

        public init(server: URL) { self.server = server }
    }

    public enum State: Sendable, Equatable {
        case unknown
        case ready(model: String, spareSlot: Int, windowTokens: Int)
        case off(String)
    }

    public let settings: Settings
    private let open: @Sendable () throws -> Vault
    private let log: @Sendable (String) -> Void
    private var shelf: KVShelf?
    public private(set) var state: State = .unknown
    private var seen: [String: Int] = [:]
    private var wanted: [(scope: String, parts: Set<Int>?)] = []
    private var working = false
    /// The cache now loaded in the spare slot.
    public private(set) var resident: String?
    /// What has been built or loaded, newest last, for a person or a test to read.
    public private(set) var history: [String] = []

    public init(settings: Settings, open: @escaping @Sendable () throws -> Vault, log: @escaping @Sendable (String) -> Void = { _ in }) {
        self.settings = settings
        self.open = open
        self.log = log
    }

    /// Checks the server once: its model, a slot no client needs, and the window to size packs for.
    @discardableResult
    public func connect() async -> State {
        if case .ready = state { return state }
        let llama = LlamaServer(base: settings.server)
        do {
            let model = try await llama.model()
            let slots = try await llama.slots()
            guard slots.count >= 2, let spare = slots.max(by: { $0.id < $1.id }) else {
                state = .off("llama.cpp has one slot, and Burrow won't build in the slot a client is using. Start it with -np 2 or more")
                log("kv: \(describe(state))")
                return state
            }
            state = .ready(model: model, spareSlot: spare.id, windowTokens: spare.contextTokens)
            log("kv: warming \(model)'s caches on slot \(spare.id), packs sized for \(spare.contextTokens) tokens")
        } catch {
            state = .off("no llama.cpp server at \(settings.server.absoluteString): \(error)")
            log("kv: \(describe(state))")
        }
        return state
    }

    public var windowTokens: Int? {
        if case let .ready(_, _, window) = state { return window }
        return nil
    }

    /// A lookup returned these files. Returns at once; the work happens later.
    public nonisolated func noticed(_ paths: [String]) {
        Task { await self.count(paths) }
    }

    /// A client asked to read a folder whole: that alone makes it worth keeping.
    public nonisolated func asked(scope: String, part: Int?) {
        Task { await self.enqueue(scope, parts: part.map { [$0] }) }
    }

    /// Waits until everything asked for so far is done. For tests and the command line.
    public func settle() async {
        while working || !wanted.isEmpty { try? await Task.sleep(nanoseconds: 100_000_000) }
    }

    private func count(_ paths: [String]) async {
        // The folders this lookup used most, at most two, so one broad search doesn't set off a build of everything.
        var counts: [String: Int] = [:]
        for path in paths { counts[KVShelf.scope(of: path), default: 0] += 1 }
        let top = counts.filter { !$0.key.isEmpty }.sorted { $0.value != $1.value ? $0.value > $1.value : $0.key < $1.key }.prefix(2)
        for (scope, _) in top {
            seen[scope, default: 0] += 1
            if (seen[scope] ?? 0) >= settings.lookupsBeforeWarming {
                // The part each file is in, so a folder bigger than one window is warmed where it is used.
                enqueue(scope, parts: nil, files: Set(paths.filter { KVShelf.scope(of: $0) == scope }))
            }
        }
    }

    private var touchedFiles: [String: Set<String>] = [:]

    private func enqueue(_ scope: String, parts: Set<Int>?, files: Set<String> = []) {
        touchedFiles[scope, default: []].formUnion(files)
        if let index = wanted.firstIndex(where: { $0.scope == scope }) {
            if let parts, let had = wanted[index].parts { wanted[index].parts = had.union(parts) } else { wanted[index].parts = nil }
        } else {
            wanted.append((scope, parts))
        }
        if !working {
            working = true
            Task { await self.drain() }
        }
    }

    private func drain() async {
        defer { working = false }
        guard case let .ready(model, spare, window) = await connect() else {
            wanted.removeAll()
            return
        }
        while !wanted.isEmpty {
            let job = wanted.removeFirst()
            do {
                try await warm(job.scope, parts: job.parts, model: model, spare: spare, window: window)
            } catch {
                log("kv: \(job.scope) was not warmed: \(error)")
            }
        }
    }

    private func openShelf() throws -> KVShelf {
        if let shelf { return shelf }
        let made = KVShelf(vault: try open())
        shelf = made
        return made
    }

    private func warm(_ scope: String, parts asked: Set<Int>?, model: String, spare: Int, window: Int) async throws {
        let shelf = try openShelf()
        let plan = try shelf.plan(scope: scope, budgetCharacters: KVShelf.packCharacters(windowTokens: window))
        // Which parts: the ones asked for, or the ones holding the files that were looked up, or all of a small folder.
        let touched = touchedFiles[scope] ?? []
        // A file in the spine is in every part, so the first part stands for it.
        var parts = asked ?? Set(plan.packs.filter { pack in pack.pieces.contains { touched.contains($0.path) } }.map(\.part))
        if parts.isEmpty { parts = [1] }
        let keys = plan.packs.filter { parts.contains($0.part) }.map { KVShelf.key(for: $0, in: plan) }
        let fresh = keys.allSatisfy { key in shelf.entries().contains { $0.key == key && $0.model == model && shelf.stale($0, model: model) == nil } }

        if !fresh {
            guard await waitForIdle(spare: spare) else {
                log("kv: \(scope) not warmed, the server stayed busy")
                return
            }
            let built = try await shelf.build(plan, server: settings.server, slot: spare, only: parts)
            for item in built where !item.skipped {
                note(String(format: "built %@ part %d of %d: %d tokens read in %.1f s, %d MB", scope, item.entry.part ?? 0, item.entry.parts ?? 0,
                            item.readTokens, item.readSeconds, item.entry.bytes / 1_048_576))
            }
            resident = built.last?.entry.key
        } else if let key = keys.last, resident != key, let entry = shelf.entries().first(where: { $0.key == key && $0.model == model }) {
            // Already on the shelf: load it into the spare slot, so a client that opens with this pack is answered from it.
            guard await waitForIdle(spare: spare) else { return }
            let seconds = try await shelf.load(entry, server: settings.server, slot: spare)
            resident = key
            note(String(format: "loaded %@ part %d (%d tokens) in %.2f s", scope, entry.part ?? 0, entry.tokens, seconds))
        }
        let cleared = try shelf.trim(toBytes: settings.limitBytes, keeping: Set([resident].compactMap { $0 }))
        for entry in cleared { note("cleared \(entry.key) to stay under the shelf's limit") }
    }

    private func note(_ line: String) {
        history.append(line)
        log("kv: " + line)
    }

    /// True once no client slot is working. Burrow's reading would otherwise slow the client's answer down.
    private func waitForIdle(spare: Int) async -> Bool {
        let llama = LlamaServer(base: settings.server)
        let deadline = Date().addingTimeInterval(settings.idleWait)
        while Date() < deadline {
            if let slots = try? await llama.slots(), !slots.contains(where: \.busy) { return true }
            try? await Task.sleep(nanoseconds: UInt64(settings.idlePoll * 1_000_000_000))
        }
        return false
    }

    private func describe(_ state: State) -> String {
        switch state {
        case .unknown: return "not checked yet"
        case let .ready(model, slot, window): return "ready for \(model) on slot \(slot), \(window) tokens"
        case let .off(why): return "off: \(why). Lookups still return text as always"
        }
    }
}
