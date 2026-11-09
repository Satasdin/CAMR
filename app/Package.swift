// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "BurrowApp",
    platforms: [.macOS(.v26)],
    dependencies: [.package(name: "Burrow", path: "..")],
    targets: [
        .executableTarget(
            name: "Burrow",
            dependencies: [.product(name: "BurrowCore", package: "Burrow"), .product(name: "BurrowTrial", package: "Burrow")],
            path: "Sources",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
