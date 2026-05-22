import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  private var backend: Process?

  override func applicationDidFinishLaunching(_ notification: Notification) {
    super.applicationDidFinishLaunching(notification)
    launchBackend()
  }

  override func applicationWillTerminate(_ notification: Notification) {
    stopBackend()
    super.applicationWillTerminate(notification)
  }

  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    return false
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }

  private func launchBackend() {
    guard let resources = Bundle.main.resourceURL else {
      NSLog("[EA] ERROR: No Resources URL — bundle broken")
      return
    }

    let backendURL = resources.appendingPathComponent("ea")
    guard FileManager.default.fileExists(atPath: backendURL.path) else {
      NSLog("[EA] ERROR: Backend binary not found at \(backendURL.path)")
      return
    }

    let dataDir = FileManager.default.homeDirectoryForCurrentUser
      .appendingPathComponent("Executive Assistant")

    do {
      try FileManager.default.createDirectory(at: dataDir, withIntermediateDirectories: true)
    } catch {
      NSLog("[EA] ERROR: Could not create data directory: \(error)")
      return
    }

    let proc = Process()
    proc.executableURL = backendURL
    proc.arguments = ["http"]
    proc.currentDirectoryURL = dataDir

    let pipe = Pipe()
    proc.standardOutput = pipe
    proc.standardError = pipe

    pipe.fileHandleForReading.readabilityHandler = { handle in
      let data = handle.availableData
      if let line = String(data: data, encoding: .utf8), !line.isEmpty {
        NSLog("[EA-backend] \(line.trimmingCharacters(in: .whitespacesAndNewlines))")
      }
    }

    proc.terminationHandler = { process in
      let status = process.terminationStatus
      NSLog("[EA] Backend exited with status \(status)")
      if status != 0 {
        DispatchQueue.main.async {
          self.showBackendErrorAlert(exitCode: status)
        }
      }
    }

    do {
      try proc.run()
      self.backend = proc
      NSLog("[EA] Backend started at \(backendURL.path)")
    } catch {
      NSLog("[EA] ERROR: Failed to launch backend: \(error)")
      self.showBackendErrorAlert(error: error)
    }
  }

  private func stopBackend() {
    guard let proc = self.backend, proc.isRunning else { return }
    proc.terminate()
    self.backend = nil
    NSLog("[EA] Backend stopped")
  }

  private func showBackendErrorAlert(exitCode: Int32? = nil, error: Error? = nil) {
    let alert = NSAlert()
    alert.alertStyle = .critical
    alert.messageText = "Backend Failed to Start"
    if let code = exitCode {
      alert.informativeText = "The Executive Assistant backend exited unexpectedly (code \(code)). Please check ~/Executive Assistant/.env for valid API keys."
    } else if let err = error {
      alert.informativeText = "Could not launch the backend: \(err.localizedDescription)"
    }
    alert.runModal()
  }
}
