// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "RegulatorCompanion",
    platforms: [
        .macOS(.v11)
    ],
    products: [
        .executable(name: "RegulatorCompanion", targets: ["RegulatorCompanion"])
    ],
    targets: [
        .executableTarget(
            name: "RegulatorCompanion",
            path: "Sources/RegulatorCompanion"
        )
    ]
)
