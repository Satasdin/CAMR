// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "Burrow",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "BurrowCore", targets: ["BurrowCore"]),
        .library(name: "BurrowTrial", targets: ["BurrowTrial"]),
        .library(name: "BurrowTools", targets: ["BurrowTools"]),
        .executable(name: "burrow", targets: ["burrow"]),
        .executable(name: "burrow-trial", targets: ["burrow-trial"]),
    ],
    targets: [
        .target(name: "BurrowCore", swiftSettings: [.swiftLanguageMode(.v5)]),
        .target(name: "BurrowTrial", dependencies: ["BurrowCore"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .target(name: "BurrowTools", dependencies: ["BurrowCore"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .target(name: "BurrowMCP", dependencies: ["BurrowCore", "BurrowTools"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .target(name: "BurrowChat", dependencies: ["BurrowCore", "BurrowTools"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .target(name: "BurrowTUI", dependencies: ["BurrowCore", "BurrowTools"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .executableTarget(name: "burrow", dependencies: ["BurrowCore", "BurrowTools", "BurrowMCP", "BurrowChat", "BurrowTUI"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .executableTarget(name: "burrow-trial", dependencies: ["BurrowCore", "BurrowTrial"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .testTarget(name: "BurrowCoreTests", dependencies: ["BurrowCore"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .testTarget(name: "BurrowTrialTests", dependencies: ["BurrowCore", "BurrowTrial"], swiftSettings: [.swiftLanguageMode(.v5)]),
        .testTarget(name: "BurrowTerminalTests", dependencies: ["BurrowCore", "BurrowTools", "BurrowMCP", "BurrowChat", "BurrowTUI"], swiftSettings: [.swiftLanguageMode(.v5)]),
    ]
)
