import Darwin
import Foundation

// Signal handlers can only touch plain memory and call a few system functions, so the restore state is set up ahead of time here.
private var saved = termios()
private var isRaw: Int32 = 0
private var restoreBytes: UnsafeMutablePointer<UInt8>?
private var restoreLength = 0
private var crashBytes: UnsafeMutablePointer<UInt8>?
private var crashLength = 0
private var wakeDescriptor: Int32 = -1
private var resized: sig_atomic_t = 0
private var resumed: sig_atomic_t = 0

private func restoreInHandler() {
    guard isRaw == 1 else { return }
    isRaw = 0
    _ = tcsetattr(STDIN_FILENO, TCSAFLUSH, &saved)
    if let restoreBytes { _ = write(STDOUT_FILENO, restoreBytes, restoreLength) }
}

private func wake() {
    var byte: UInt8 = 1
    _ = write(wakeDescriptor, &byte, 1)
}

private func onFatalSignal(_ number: Int32) {
    let wasRaw = isRaw == 1
    restoreInHandler()
    if wasRaw, number != SIGINT, number != SIGTERM, number != SIGHUP, let crashBytes { _ = write(STDERR_FILENO, crashBytes, crashLength) }
    signal(number, SIG_DFL)
    raise(number)
}

private func onResize(_: Int32) {
    resized = 1
    wake()
}

private func onSuspend(_ number: Int32) {
    restoreInHandler()
    signal(SIGTSTP, SIG_DFL)
    raise(SIGTSTP)
}

private func onResume(_: Int32) {
    signal(SIGTSTP, onSuspend)
    resumed = 1
    wake()
}

/// Owns the real terminal: raw mode, the alternate screen, signals, and writing frames.
final class TerminalScreen {
    struct NotATerminal: Error, CustomStringConvertible {
        let description: String
    }

    private static let leave = "\u{1B}[?2026l\u{1B}[0m\u{1B}[?2004l\u{1B}[?25h\u{1B}[?1049l"
    private static let enterSequence = "\u{1B}[?1049h\u{1B}[?2004h\u{1B}[?25l\u{1B}[2J\u{1B}[H"
    let depth = ColorDepth.detect()
    let wakeRead: Int32
    static var wakeWriteDescriptor: Int32 { wakeDescriptor }
    private var previous: Frame?
    private let logPath: String
    private var savedError: Int32 = -1

    /// Checks everything a full-screen view needs, before touching the terminal.
    init(logPath: String) throws {
        guard isatty(STDIN_FILENO) == 1, isatty(STDOUT_FILENO) == 1 else {
            throw NotATerminal(description: "the full-screen view needs a terminal. Try burrow chat or burrow find for plain output")
        }
        guard ProcessInfo.processInfo.environment["TERM"] != "dumb" else {
            throw NotATerminal(description: "this terminal can't place text on the screen (TERM=dumb). Try burrow chat")
        }
        var pipeEnds: [Int32] = [0, 0]
        guard pipe(&pipeEnds) == 0 else { throw NotATerminal(description: "could not set up the wake pipe") }
        _ = fcntl(pipeEnds[0], F_SETFL, O_NONBLOCK)
        _ = fcntl(pipeEnds[1], F_SETFL, O_NONBLOCK)
        wakeRead = pipeEnds[0]
        wakeDescriptor = pipeEnds[1]
        self.logPath = logPath

        restoreLength = Self.leave.utf8.count
        restoreBytes = UnsafeMutablePointer<UInt8>.allocate(capacity: restoreLength)
        restoreBytes?.initialize(from: Array(Self.leave.utf8), count: restoreLength)
        let crash = Array("burrow: crashed. Details, if any, are in \(logPath)\n".utf8)
        crashLength = crash.count
        crashBytes = UnsafeMutablePointer<UInt8>.allocate(capacity: crashLength)
        crashBytes?.initialize(from: crash, count: crashLength)
    }

    func enter() {
        tcgetattr(STDIN_FILENO, &saved)
        for number in [SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGSEGV, SIGBUS, SIGILL, SIGABRT, SIGTRAP, SIGFPE] { signal(number, onFatalSignal) }
        signal(SIGWINCH, onResize)
        signal(SIGCONT, onResume)
        signal(SIGTSTP, onSuspend)
        signal(SIGPIPE, SIG_IGN)
        // Something printing to stderr would scribble over the screen, so it goes to a file while the view is up.
        fflush(stderr)
        savedError = dup(STDERR_FILENO)
        let log = open(logPath, O_WRONLY | O_CREAT | O_TRUNC, 0o600)
        if log >= 0 {
            dup2(log, STDERR_FILENO)
            close(log)
        }
        goRaw()
    }

    private func goRaw() {
        var raw = saved
        raw.c_lflag &= ~tcflag_t(ECHO | ICANON | ISIG | IEXTEN)
        raw.c_iflag &= ~tcflag_t(IXON | ICRNL | BRKINT | INPCK | ISTRIP)
        raw.c_cflag |= tcflag_t(CS8)
        withUnsafeMutableBytes(of: &raw.c_cc) { bytes in
            bytes[Int(VMIN)] = 1
            bytes[Int(VTIME)] = 0
        }
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw)
        isRaw = 1
        send(Self.enterSequence)
        previous = nil
    }

    func leave() {
        if isRaw == 1 {
            isRaw = 0
            tcsetattr(STDIN_FILENO, TCSAFLUSH, &saved)
            send(Self.leave)
        }
        if savedError >= 0 {
            dup2(savedError, STDERR_FILENO)
            close(savedError)
            savedError = -1
        }
        // An empty log means nothing went wrong, so there is nothing to keep.
        if let size = try? FileManager.default.attributesOfItem(atPath: logPath)[.size] as? Int, size == 0 { try? FileManager.default.removeItem(atPath: logPath) }
        for number in [SIGINT, SIGTERM, SIGHUP, SIGQUIT, SIGSEGV, SIGBUS, SIGILL, SIGABRT, SIGTRAP, SIGFPE, SIGWINCH, SIGCONT, SIGTSTP] { signal(number, SIG_DFL) }
    }

    func suspend() { raise(SIGTSTP) }

    /// True once after the terminal has changed size.
    func takeResize() -> Bool {
        guard resized == 1 else { return false }
        resized = 0
        return true
    }

    /// True once after coming back from Control-Z. Raw mode has to be set up again.
    func takeResume() -> Bool {
        guard resumed == 1 else { return false }
        resumed = 0
        goRaw()
        return true
    }

    var size: (width: Int, height: Int) {
        var box = winsize()
        guard ioctl(STDOUT_FILENO, TIOCGWINSZ, &box) == 0, box.ws_col > 0, box.ws_row > 0 else { return (80, 24) }
        return (Int(box.ws_col), Int(box.ws_row))
    }

    func present(_ frame: Frame) {
        send(frame.encoded(from: previous, depth: depth))
        previous = frame
    }

    private func send(_ text: String) {
        let bytes = Array(text.utf8)
        var sent = 0
        while sent < bytes.count {
            let wrote = bytes[sent...].withUnsafeBytes { write(STDOUT_FILENO, $0.baseAddress, $0.count) }
            if wrote < 0 {
                if errno == EINTR || errno == EAGAIN { continue }
                return
            }
            sent += wrote
        }
    }
}
