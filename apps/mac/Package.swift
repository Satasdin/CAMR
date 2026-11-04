// swift-tools-version:5.10
// CAMR for the Mac: Chat and Code on a local model, with the memory engine beside it. Built with the command-line
// tools alone (`swift build`); build.sh wraps the binary as CAMR.app.
import PackageDescription

let package = Package(
    name: "CAMR",
    platforms: [.macOS(.v14)],
    targets: [.executableTarget(name: "CAMR", path: "Sources/CAMR")]
)
