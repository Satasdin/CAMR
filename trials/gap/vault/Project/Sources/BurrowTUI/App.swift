import BurrowCore
import BurrowTools
import Darwin
import Foundation

/// What background jobs send to the screen. The vault's single-thread rule means only the main loop touches the model.
private enum Posted {
    case found(VaultTools.Found)
    case word(String)
    case finished(Double)
    case failed(String)
    case indexProgress(String)
    case indexed(message: String?, problem: Bool)
}

private final class Mailbox {
    private let lock = NSLock()
    private var items: [Posted] = []
    private let wakeWrite: Int32

    init(wakeWrite: Int32) { self.wakeWrite = wakeWrite }

    func post(_ item: Posted) {
        lock.lock()
        items.append(item)
        lock.unlock()
        var byte: UInt8 = 1
        _ = write(wakeWrite, &byte, 1)
    }

    func take() -> [Posted] {
        lock.lock()
        defer { lock.unlock() }
        let out = items
        items = []
        return out
    }
}

/// The full-screen view of a vault: reads keys, runs jobs in the background, and draws.
public final class TerminalApp {
    public struct Failure: Error, CustomStringConvertible {
        public let description: String
    }

    private let model: Model
    private let screen: TerminalScreen
    private let tools: VaultTools
    private let backgroundVault: Vault
    private let ollama = Ollama()
    private let mailbox: Mailbox
    private var decoder = KeyDecoder()
    private var job: Task<Void, Never>?
    private var running = true

    public init(vaultFolder: URL, store: URL?, modelName: String) throws {
        // The vault can't be shared between threads, so the screen and the background jobs each open their own.
        let foreground = try Vault(project: vaultFolder, store: store, everything: true)
        backgroundVault = try Vault(project: vaultFolder, store: store, everything: true)
        do {
            screen = try TerminalScreen(logPath: NSTemporaryDirectory() + "burrow-tui-\(getpid()).log")
        } catch let problem as TerminalScreen.NotATerminal {
            throw Failure(description: problem.description)
        }
        mailbox = Mailbox(wakeWrite: TerminalScreen.wakeWriteDescriptor)
        model = Model(vault: foreground, modelName: modelName)
        tools = VaultTools.onThisMac(vault: backgroundVault, model: modelName)
    }

    public func run() {
        screen.enter()
        defer { screen.leave() }
        let size = screen.size
        model.resize(width: size.width, height: size.height)
        model.reload()
        startIndexing(embedAll: false)
        draw()
        loop()
        job?.cancel()
    }

    private func draw() { screen.present(View.render(model)) }

    /// One job at a time, in order. Starts after whatever is already running.
    private func enqueue(_ body: @escaping @Sendable () async -> Void) {
        let previous = job
        job = Task.detached {
            await previous?.value
            await body()
        }
    }

    private func startIndexing(embedAll: Bool) {
        let tools = self.tools
        let vault = backgroundVault
        let mailbox = self.mailbox
        let ollama = self.ollama
        enqueue {
            if embedAll {
                do {
                    let report = try await vault.refresh(embedder: ollama.embedder()) { line in mailbox.post(.indexProgress(line)) }
                    mailbox.post(.indexed(message: "Indexed. \(report.filesChanged) files changed, \(report.embedded) passages embedded.", problem: false))
                } catch {
                    mailbox.post(.indexed(message: "Words are indexed, but Ollama could not embed: \(error)", problem: true))
                }
            } else {
                await tools.freshen(checkNow: true)
                mailbox.post(.indexed(message: nil, problem: false))
            }
        }
    }

    private var askJob: Task<Void, Never>?

    private func perform(_ effect: Effect) {
        switch effect {
        case .quit: running = false
        case .suspend: screen.suspend()
        case .reindex:
            model.indexing = "Indexing…"
            startIndexing(embedAll: true)
        case .cancelAsk:
            askJob?.cancel()
            askJob = nil
            model.askFailed("Stopped.")
        case let .ask(question, folder):
            let tools = self.tools
            let mailbox = self.mailbox
            let name = model.modelName
            let previous = job
            let task = Task.detached {
                await previous?.value
                do {
                    let outcome = try await tools.answer(question, folder: folder, model: name, onFound: { mailbox.post(.found($0)) }, onWord: { mailbox.post(.word($0)) })
                    try Task.checkCancellation()
                    mailbox.post(.finished(outcome.result.totalSeconds))
                } catch is CancellationError {
                    return
                } catch let error as URLError where error.code == .cancelled {
                    return
                } catch where OllamaReach.isUnreachable(error) {
                    mailbox.post(.failed(OllamaReach.message))
                } catch {
                    mailbox.post(.failed("The model could not answer: \(error)"))
                }
            }
            askJob = task
            job = task
        }
    }

    private func apply(_ item: Posted) {
        switch item {
        case let .found(found): if askJob != nil { model.askFound(found) }
        case let .word(word): if askJob != nil { model.askWord(word) }
        case let .finished(seconds):
            if askJob != nil { model.askFinished(seconds: seconds) }
            askJob = nil
        case let .failed(message):
            if askJob != nil { model.askFailed(message) }
            askJob = nil
        case let .indexProgress(line):
            model.indexing = line
        case let .indexed(message, problem):
            model.indexing = nil
            model.reload()
            if let message { model.setStatus(message, problem: problem) }
        }
    }

    private func loop() {
        var descriptors = [pollfd(fd: STDIN_FILENO, events: Int16(POLLIN), revents: 0), pollfd(fd: screen.wakeRead, events: Int16(POLLIN), revents: 0)]
        var buffer = [UInt8](repeating: 0, count: 8192)
        while running {
            // A short wait tells a lone Escape from an escape sequence, and a slow tick keeps the elapsed time moving during Ask.
            let timeout: Int32 = decoder.waitingOnEscape ? 30 : (model.askBusy ? 500 : -1)
            let ready = poll(&descriptors, 2, timeout)
            var needsDraw = false

            if ready > 0, descriptors[0].revents & Int16(POLLIN | POLLHUP) != 0 {
                let count = read(STDIN_FILENO, &buffer, buffer.count)
                if count == 0 { return }
                if count > 0 {
                    for key in decoder.feed(Array(buffer[0..<count])) {
                        for effect in model.handle(key) { perform(effect) }
                        if !running { return }
                    }
                    needsDraw = true
                }
            } else if ready == 0, decoder.waitingOnEscape {
                for key in decoder.flushEscape() {
                    for effect in model.handle(key) { perform(effect) }
                }
                needsDraw = true
            }

            if ready > 0, descriptors[1].revents & Int16(POLLIN) != 0 {
                var drain = [UInt8](repeating: 0, count: 256)
                while read(screen.wakeRead, &drain, drain.count) > 0 {}
                needsDraw = true
            }
            for item in mailbox.take() {
                apply(item)
                needsDraw = true
            }
            if screen.takeResume() { needsDraw = true }
            if screen.takeResize() {
                let size = screen.size
                model.resize(width: size.width, height: size.height)
                needsDraw = true
            }
            if ready == 0, model.askBusy { needsDraw = true }
            if needsDraw { draw() }
        }
    }
}
