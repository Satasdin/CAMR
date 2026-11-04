import SwiftUI

/// Crisp glow on black. Colour means something and nothing else: memory is cyan, the model's own weights are amber,
/// the person is white, and red is only ever an error.
enum Theme {
    static let ink = Color(red: 0.02, green: 0.02, blue: 0.03)
    static let panel = Color(red: 0.06, green: 0.06, blue: 0.075)
    static let line = Color.white.opacity(0.08)
    static let text = Color.white.opacity(0.92)
    static let dim = Color.white.opacity(0.5)
    static let faint = Color.white.opacity(0.28)
    static let memory = Color(red: 0.25, green: 0.86, blue: 1.0)
    static let model = Color(red: 1.0, green: 0.66, blue: 0.22)
    static let error = Color(red: 1.0, green: 0.36, blue: 0.36)

    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }

    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .default)
    }
}

extension View {
    /// A soft glow of ``color`` behind the view.
    func glow(_ color: Color, radius: CGFloat = 8, opacity: Double = 0.6) -> some View {
        shadow(color: color.opacity(opacity), radius: radius)
    }
}

/// Bytes in the units a person reads.
func bytesText(_ b: Double?) -> String {
    guard let b, b > 0 else { return "—" }
    if b >= 1e9 { return String(format: "%.1f GB", b / 1e9) }
    if b >= 1e6 { return String(format: "%.1f MB", b / 1e6) }
    if b >= 1e3 { return String(format: "%.0f KB", b / 1e3) }
    return String(format: "%.0f B", b)
}

func secondsText(_ s: Double?) -> String {
    guard let s else { return "—" }
    return s < 1 ? String(format: "%.0f ms", s * 1000) : String(format: "%.2f s", s)
}
