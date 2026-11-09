import BurrowCore
import BurrowTrial
import Foundation

let usage = """
burrow-trial: runs simulated developer agents over a project, session after session

  burrow-trial verify <project-folder> [--scratch DIR]
  burrow-trial run <project-folder> --run-name NAME [--mode none|search|walk|all] [--model NAME] [--scratch DIR] [--results DIR] [--overwrite]
"""

func value(_ name: String, in arguments: [String]) -> String? {
    guard let index = arguments.firstIndex(of: name), index + 1 < arguments.count else { return nil }
    return arguments[index + 1]
}

func say(_ line: String) {
    print(line)
    fflush(stdout)
}

func main() async throws {
    let arguments = Array(CommandLine.arguments.dropFirst())
    guard arguments.count >= 2 else {
        print(usage)
        return
    }
    let project = try TrialProject(root: URL(fileURLWithPath: arguments[1]))
    let scratch = URL(fileURLWithPath: value("--scratch", in: arguments) ?? NSTemporaryDirectory() + "burrow-trial")

    switch arguments[0] {
    case "verify":
        let report = try verify(project: project, scratch: scratch)
        report.lines.forEach(say)
        say("\(report.lines.count) checks, \(report.failures) wrong")
        if report.failures > 0 { exit(1) }

    case "run":
        guard let runName = value("--run-name", in: arguments) else { throw TrialFailure("run needs --run-name") }
        let word = value("--mode", in: arguments) ?? "all"
        let modes: [Mode]
        if word == "all" { modes = Mode.allCases } else {
            guard let mode = Mode(rawValue: word) else { throw TrialFailure("unknown mode \(word)") }
            modes = [mode]
        }
        var options = TrialOptions(modes: modes, runName: runName, scratch: scratch,
                                   results: URL(fileURLWithPath: value("--results", in: arguments) ?? "trials/results"))
        options.overwrite = arguments.contains("--overwrite")
        let ollama = Ollama()
        let answerer: Answerer = ollama.answerer(model: value("--model", in: arguments) ?? Ollama.defaultModel, contextWords: 16_384)
        let embedder: Embedder = ollama.embedder()
        let started = Date()
        let records = try await runTrial(project: project, options: options, answerer: answerer, embedder: embedder, log: say)
        say(summary(records))
        say(String(format: "finished in %.0f s", Date().timeIntervalSince(started)))

    default:
        print(usage)
    }
}

do {
    try await main()
} catch {
    FileHandle.standardError.write(Data("burrow-trial: \(error)\n".utf8))
    exit(1)
}
