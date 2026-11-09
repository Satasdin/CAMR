// swift-tools-version:6.2
// CAMR for Mac: the native app. It starts the Python engine (camr_engine.app) as a child process and talks to it
// over 127.0.0.1 with a launch token. Build with mac/build.sh, which makes CAMR.app.
import PackageDescription

let package = Package(
    name: "CAMR",
    platforms: [.macOS(.v26)],
    targets: [
        .executableTarget(name: "CAMR", path: "Sources/CAMR")
    ],
    swiftLanguageModes: [.v5]
)
