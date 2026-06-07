import Cocoa
import FlutterMacOS
import ServiceManagement
import Sparkle

@main
class AppDelegate: FlutterAppDelegate {
  private var backend: Process?
  private var restartAttempts = 0
  private let maxRestartAttempts = 3
  private let restartDelay: UInt32 = 2
  private var updaterController: SPUStandardUpdaterController?

  override func applicationDidFinishLaunching(_ notification: Notification) {
    super.applicationDidFinishLaunching(notification)
    launchBackend()
    registerLoginItem()
    setupSparkle()
  }

  // ─── Auto-update (Sparkle) ───

  private func setupSparkle() {
    updaterController = SPUStandardUpdaterController(
      startingUpdater: true,
      updaterDelegate: nil,
      userDriverDelegate: nil
    )
    // Check for updates after 5 second delay, then every 24 hours
    DispatchQueue.main.asyncAfter(deadline: .now() + 5) { [weak self] in
      self?.updaterController?.updater.checkForUpdatesInBackground()
    }
    NSLog("[EA] Sparkle auto-updater initialized")
  }

  @objc func checkForUpdates(_ sender: Any) {
    updaterController?.checkForUpdates(sender)
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

  // ─── Backend lifecycle ───

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

    proc.terminationHandler = { [weak self] process in
      let status = process.terminationStatus
      NSLog("[EA] Backend exited with status \(status)")
      DispatchQueue.main.async {
        self?.handleBackendExit(status: status)
      }
    }

    do {
      try proc.run()
      self.backend = proc
      self.restartAttempts = 0
      NSLog("[EA] Backend started at \(backendURL.path)")
    } catch {
      NSLog("[EA] ERROR: Failed to launch backend: \(error)")
      self.showBackendErrorAlert(error: error)
    }
  }

  private func stopBackend() {
    guard let proc = self.backend, proc.isRunning else { return }
    proc.terminate()
    proc.waitUntilExit()
    self.backend = nil
    NSLog("[EA] Backend stopped")
  }

  private func handleBackendExit(status: Int32) {
    self.backend = nil

    if status == 0 {
      // Normal exit — don't restart
      NSLog("[EA] Backend exited cleanly")
      return
    }

    if status == 15 {
      // SIGTERM from us — intentional stop
      NSLog("[EA] Backend received SIGTERM (intentional)")
      return
    }

    guard restartAttempts < maxRestartAttempts else {
      NSLog("[EA] Backend crashed \(maxRestartAttempts) times — giving up")
      showBackendErrorAlert(exitCode: status)
      return
    }

    restartAttempts += 1
    NSLog("[EA] Restarting backend (attempt \(restartAttempts)/\(maxRestartAttempts))...")
    sleep(restartDelay)
    launchBackend()
  }

  // ─── Login Item ───

  private func registerLoginItem() {
    if #available(macOS 13.0, *) {
      do {
        try SMAppService.mainApp.register()
        NSLog("[EA] Registered as Login Item")
      } catch {
        // Already registered or not supported — not critical
        NSLog("[EA] Login Item registration skipped: \(error.localizedDescription)")
      }
    }
  }

  // ─── Error alert ───

  private func showBackendErrorAlert(exitCode: Int32? = nil, error: Error? = nil) {
    let alert = NSAlert()
    alert.alertStyle = .critical
    alert.messageText = "Something went wrong"
    if let code = exitCode {
      alert.informativeText = "Executive Assistant encountered an unexpected error and needs to restart. If this keeps happening, click \"Report Issue\" in the app settings to let us know."
    } else if let err = error {
      alert.informativeText = "Could not start Executive Assistant. Please try restarting the app. If the issue persists, click \"Report Issue\" in settings."
    }
    alert.addButton(withTitle: "OK")
    alert.runModal()
  }
}
