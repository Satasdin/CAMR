import Foundation

public enum TerminalText {
    /// Removes control characters, so a file or a model can't send escape codes to the terminal. Newlines and tabs stay.
    public static func clean(_ text: String) -> String {
        guard text.unicodeScalars.contains(where: isControl) else { return text }
        var out = String.UnicodeScalarView()
        for scalar in text.unicodeScalars where !isControl(scalar) { out.append(scalar) }
        return String(out)
    }

    private static func isControl(_ scalar: Unicode.Scalar) -> Bool {
        (scalar.value < 0x20 && scalar != "\n" && scalar != "\t") || (0x7F...0x9F).contains(scalar.value)
    }
}
