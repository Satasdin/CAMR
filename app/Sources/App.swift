import AppKit
import BurrowCore
import SwiftUI

@main
struct BurrowApp: App {
    @NSApplicationDelegateAdaptor(Delegate.self) private var delegate
    @State private var library = Library()

    private var workspace: Workspace? { library.workspace }

    var body: some Scene {
        WindowGroup("Burrow") {
            Root(library: library).frame(minWidth: 900, minHeight: 560)
        }
        .defaultSize(width: 1400, height: 880)
        .commands { commands }

        Settings { SettingsView(library: library) }
    }

    @CommandsBuilder private var commands: some Commands {
        CommandGroup(replacing: .newItem) {
            Button("New Note") { act { await $0.newNote() } }.keyboardShortcut("n").disabled(workspace == nil)
            Button("New Folder") { act { await $0.newFolder() } }.keyboardShortcut("n", modifiers: [.command, .shift]).disabled(workspace == nil)
            Button("Today's Note") { act { await $0.dailyNote() } }.keyboardShortcut("d", modifiers: [.command, .shift]).disabled(workspace == nil)
            Divider()
            Button("Open Vault…") { pickVault(library) }.keyboardShortcut("o")
            Button("Link a Folder…") { if let workspace { pickLinkedFolder(workspace) } }.disabled(workspace == nil)
        }
        CommandGroup(replacing: .saveItem) {
            Button("Close Tab") { workspace?.closeCurrentTab() }.keyboardShortcut("w").disabled(workspace?.currentTab == nil)
        }
        CommandGroup(after: .toolbar) {
            Button(workspace?.isReading == true ? "Edit Note" : "Read Note") { workspace?.isReading.toggle() }.keyboardShortcut("e").disabled(workspace?.currentPath == nil)
            Divider()
            Button("Library") { workspace?.go(.library(.all)) }.keyboardShortcut("1").disabled(workspace == nil)
            Button("Conversations") { workspace?.go(.conversations(nil)) }.keyboardShortcut("2").disabled(workspace == nil)
            Button("Shelf") { workspace?.go(.shelf) }.keyboardShortcut("3").disabled(workspace == nil)
            Button("Programs") { workspace?.go(.programs) }.keyboardShortcut("4").disabled(workspace == nil)
            Button("Ledger") { workspace?.go(.ledger(nil)) }.keyboardShortcut("5").disabled(workspace == nil)
            Button("Map") { workspace?.go(.graph) }.keyboardShortcut("g", modifiers: [.command, .shift]).disabled(workspace == nil)
            Divider()
        }
        CommandMenu("Go") {
            Button("Quick Open…") { workspace?.paletteOpen = true }.keyboardShortcut("k").disabled(workspace == nil)
            Button("Search Vault") { workspace?.sidebarMode = .search }.keyboardShortcut("f", modifiers: [.command, .shift]).disabled(workspace == nil)
            Divider()
            Button("Back") { workspace?.goBack() }.keyboardShortcut("[").disabled(workspace?.currentTab?.back.isEmpty ?? true)
            Button("Forward") { workspace?.goForward() }.keyboardShortcut("]").disabled(workspace?.currentTab?.forward.isEmpty ?? true)
            Divider()
            Button("Next Tab") { workspace?.cycleTab(by: 1) }.keyboardShortcut("}").disabled(workspace == nil)
            Button("Previous Tab") { workspace?.cycleTab(by: -1) }.keyboardShortcut("{").disabled(workspace == nil)
            Divider()
            Button("Read Vault Again") { act { await $0.readAgain() } }.keyboardShortcut("r").disabled(workspace == nil)
        }
    }

    private func act(_ work: @escaping (Workspace) async -> Void) {
        guard let workspace else { return }
        Task { await work(workspace) }
    }
}

final class Delegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        if ProcessInfo.processInfo.environment["BURROW_SNAPSHOT"] == nil { NSApp.activate(ignoringOtherApps: true) }
        snapshotIfAsked()
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    /// For checking the layout without a person at the screen: BURROW_SNAPSHOT=out.png BURROW_SNAPSHOT_AFTER=seconds.
    private func snapshotIfAsked() {
        let environment = ProcessInfo.processInfo.environment
        guard let path = environment["BURROW_SNAPSHOT"] else { return }
        let wait = Double(environment["BURROW_SNAPSHOT_AFTER"] ?? "") ?? 10
        DispatchQueue.main.asyncAfter(deadline: .now() + wait) {
            if let view = NSApp.windows.first(where: \.isVisible)?.contentView?.superview,
               let picture = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: picture)
                try? picture.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
            }
            NSApp.terminate(nil)
        }
    }
}

@MainActor
func pickVault(_ library: Library) {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.canCreateDirectories = true
    panel.prompt = "Open Vault"
    panel.message = "Choose a folder for your vault. An Obsidian vault works as it is. Nothing leaves this Mac."
    if panel.runModal() == .OK, let url = panel.url { library.open(url) }
}

@MainActor
func pickLinkedFolder(_ workspace: Workspace) {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.prompt = "Link Folder"
    panel.message = "Link a folder, such as a code project. Burrow reads it where it is."
    if panel.runModal() == .OK, let url = panel.url { Task { await workspace.link(url) } }
}

struct Root: View {
    let library: Library

    var body: some View {
        Group {
            if let workspace = library.workspace {
                MainWindow(library: library, workspace: workspace).id(workspace.folder)
            } else {
                Welcome(library: library)
            }
        }
        .onAppear {
            if library.workspace == nil, let path = ProcessInfo.processInfo.environment["BURROW_VAULT"] {
                library.open(URL(fileURLWithPath: path))
            }
        }
    }
}

struct Welcome: View {
    let library: Library

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 18) {
                Text("Burrow").font(.system(size: 46, weight: .semibold)).tracking(-0.8).foregroundStyle(.white)
                Text("A vault for everything you know, read by a model on this Mac.")
                    .font(.title3).foregroundStyle(.white.opacity(0.65))
                Button("Open or Create a Vault…") { pickVault(library) }
                    .buttonStyle(.borderedProminent).controlSize(.extraLarge).padding(.top, 10)
                if !library.recents.isEmpty {
                    VStack(spacing: 8) {
                        ForEach(library.recents, id: \.self) { path in
                            Button(path.fileName) { library.open(URL(fileURLWithPath: path)) }.buttonStyle(.link)
                        }
                    }
                    .padding(.top, 10)
                }
                if let failure = library.failure { Text(failure).foregroundStyle(.red) }
            }
        }
    }
}

struct SettingsView: View {
    let library: Library

    var body: some View {
        Form {
            if let workspace = library.workspace {
                Section("Model") {
                    Picker("Answers with", selection: Binding(get: { workspace.model }, set: { workspace.model = $0 })) {
                        ForEach(workspace.models, id: \.self) { Text($0).tag($0) }
                    }
                }
                Section("Linked folders") {
                    if workspace.linked.isEmpty { Text("None yet").foregroundStyle(.secondary) }
                    ForEach(workspace.linked) { folder in
                        LabeledContent(folder.name) {
                            Button("Unlink") { Task { await workspace.unlink(folder.name) } }
                        }
                        .help(folder.path)
                    }
                    Button("Link a Folder…") { pickLinkedFolder(workspace) }
                }
            } else {
                Text("Open a vault to change its settings.").foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .frame(width: 460, height: 340)
    }
}
