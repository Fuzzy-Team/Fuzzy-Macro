import AppKit
import Foundation
import CoreGraphics
import Darwin

private let statePath = "/tmp/fuzzy_virtual_display_state.json"

private var display: CGVirtualDisplay?
private var mirrorWindow: NSWindow?
private var mirrorView: DisplayMirrorView?

private typealias CGDisplayCreateImageFunction = @convention(c) (CGDirectDisplayID) -> Unmanaged<CGImage>?
private let createDisplayImage: CGDisplayCreateImageFunction? = {
    guard let handle = dlopen("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics", RTLD_LAZY),
          let symbol = dlsym(handle, "CGDisplayCreateImage") else {
        return nil
    }
    return unsafeBitCast(symbol, to: CGDisplayCreateImageFunction.self)
}()

private struct VMState: Codable {
    let active: Bool
    let pid: Int32?
    let display_id: UInt32?
    let x: Int?
    let y: Int?
    let width: Int?
    let height: Int?
    let error: String?
}

private func emit(_ state: VMState, exitCode: Int32 = 0) -> Never {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    if let data = try? encoder.encode(state), let out = String(data: data, encoding: .utf8) {
        print(out)
    } else {
        print("{\"active\":false,\"error\":\"failed to encode state\"}")
    }
    fflush(stdout)
    Foundation.exit(exitCode)
}

private func saveState(_ state: VMState) {
    let encoder = JSONEncoder()
    guard let data = try? encoder.encode(state) else { return }
    try? data.write(to: URL(fileURLWithPath: statePath), options: [.atomic])
}

private func clearState() {
    try? FileManager.default.removeItem(atPath: statePath)
}

private func readState() -> VMState? {
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: statePath)) else { return nil }
    return try? JSONDecoder().decode(VMState.self, from: data)
}

private func isPidAlive(_ pid: Int32) -> Bool {
    if pid <= 0 { return false }
    return kill(pid, 0) == 0
}

private func screenForDisplayID(_ id: UInt32) -> NSScreen? {
    for screen in NSScreen.screens {
        if let value = screen.deviceDescription[NSDeviceDescriptionKey(rawValue: "NSScreenNumber")] as? NSNumber,
           value.uint32Value == id {
            return screen
        }
    }
    return nil
}

private final class DisplayMirrorView: NSView {
    private let displayID: CGDirectDisplayID
    private var timer: Timer?

    init(displayID: CGDirectDisplayID) {
        self.displayID = displayID
        super.init(frame: .zero)
        wantsLayer = true
        layer?.backgroundColor = NSColor.black.cgColor
        layer?.contentsGravity = .resizeAspect
        timer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: true) { [weak self] _ in
            self?.refresh()
        }
        timer?.tolerance = 1.0 / 120.0
        refresh()
    }

    required init?(coder: NSCoder) {
        nil
    }

    private func refresh() {
        guard let image = createDisplayImage?(displayID)?.takeRetainedValue() else { return }
        layer?.contents = image
    }

    deinit {
        timer?.invalidate()
    }
}

private func showMirrorWindow(for displayID: CGDirectDisplayID) {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    app.finishLaunching()

    guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }
    let frame = screen.frame
    let view = DisplayMirrorView(displayID: displayID)
    view.frame = NSRect(origin: .zero, size: frame.size)

    let window = NSWindow(
        contentRect: frame,
        styleMask: [.borderless],
        backing: .buffered,
        defer: false,
        screen: screen
    )
    window.title = "Fuzzy Macro Virtual Monitor"
    window.contentView = view
    window.backgroundColor = .black
    window.isOpaque = true
    window.level = .normal
    window.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
    window.ignoresMouseEvents = true
    window.orderFrontRegardless()

    mirrorView = view
    mirrorWindow = window
}

private func statusCommand() -> Never {
    guard let state = readState() else {
        emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: nil))
    }
    if let pid = state.pid, isPidAlive(pid) {
        emit(state)
    }
    clearState()
    emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: nil))
}

private func stopCommand() -> Never {
    guard let state = readState(), let pid = state.pid else {
        emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: nil))
    }

    _ = kill(pid, SIGTERM)

    let timeout = Date().addingTimeInterval(2.0)
    while Date() < timeout {
        if !isPidAlive(pid) { break }
        usleep(100_000)
    }

    clearState()
    emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: nil))
}

private func handleSignal(_ signal: Int32) {
    mirrorWindow?.close()
    mirrorWindow = nil
    mirrorView = nil
    display = nil
    clearState()
    Foundation.exit(0)
}

private func startCommand(width: Int, height: Int) -> Never {
    if let existing = readState(), let pid = existing.pid, isPidAlive(pid) {
        emit(existing)
    }

    signal(SIGTERM) { sig in handleSignal(sig) }
    signal(SIGINT) { sig in handleSignal(sig) }

    let descriptor = CGVirtualDisplayDescriptor()
    descriptor.setDispatchQueue(DispatchQueue.main)
    descriptor.name = "Fuzzy Macro Virtual Display"
    descriptor.maxPixelsWide = UInt32(width)
    descriptor.maxPixelsHigh = UInt32(height)
    descriptor.sizeInMillimeters = CGSize(width: 509, height: 286)
    descriptor.productID = 0x1234
    descriptor.vendorID = 0x3456
    descriptor.serialNum = UInt32(getpid())

    let virtualDisplay = CGVirtualDisplay(descriptor: descriptor)
    let settings = CGVirtualDisplaySettings()
    settings.hiDPI = 0
    settings.modes = [
        CGVirtualDisplayMode(width: UInt(width), height: UInt(height), refreshRate: 60),
    ]

    if !virtualDisplay.apply(settings) {
        emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: width, height: height, error: "Failed to apply virtual display settings"), exitCode: 2)
    }

    display = virtualDisplay
    usleep(250_000)

    let displayID = virtualDisplay.displayID
    let frame = CGDisplayBounds(displayID)

    let state = VMState(
        active: true,
        pid: getpid(),
        display_id: displayID,
        x: Int(frame.origin.x),
        y: Int(frame.origin.y),
        width: Int(frame.width == 0 ? CGFloat(width) : frame.width),
        height: Int(frame.height == 0 ? CGFloat(height) : frame.height),
        error: nil
    )

    saveState(state)
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.sortedKeys]
    if let data = try? encoder.encode(state), let out = String(data: data, encoding: .utf8) {
        print(out)
        fflush(stdout)
    }

    showMirrorWindow(for: displayID)
    RunLoop.main.run()
    mirrorWindow?.close()
    mirrorWindow = nil
    mirrorView = nil
    display = nil
    clearState()
    Foundation.exit(0)
}

private func parseIntArg(_ name: String, default value: Int) -> Int {
    guard let idx = CommandLine.arguments.firstIndex(of: name), CommandLine.arguments.count > idx + 1 else {
        return value
    }
    return Int(CommandLine.arguments[idx + 1]) ?? value
}

let args = CommandLine.arguments
if args.count < 2 {
    emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: "No command provided"), exitCode: 1)
}

switch args[1] {
case "start":
    let width = parseIntArg("--width", default: 1920)
    let height = parseIntArg("--height", default: 1080)
    startCommand(width: width, height: height)
case "status":
    statusCommand()
case "stop":
    stopCommand()
default:
    emit(VMState(active: false, pid: nil, display_id: nil, x: nil, y: nil, width: nil, height: nil, error: "Unknown command"), exitCode: 1)
}
