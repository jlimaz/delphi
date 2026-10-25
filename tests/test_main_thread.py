"""Main-thread regressions with fake capture/apps and temporary files only."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'darwin', 'macOS Swift regression')
class MainThreadTests(unittest.TestCase):
    def swift(self, body):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'check.swift'
            binary = Path(root) / 'check'
            source.write_text(body)
            result = subprocess.run(['swiftc', str(source), '-o', str(binary)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_permission_refresh_deduplicates_pending_probes(self):
        source = (ROOT / 'Delphi.swift').read_text()
        statuses = source[source.index('    static let probeLock'):source.index('    static func sync()')]
        self.swift('''import Foundation
typealias OSStatus = Int32
let noErr: OSStatus = 0, errAEEventNotPermitted: OSStatus = -1743
let gate = DispatchSemaphore(value: 0), started = DispatchSemaphore(value: 0)
let callsLock = NSLock()
var calls = 0
enum Apps {
 static var allowed = Set<String>()
 static func check(_ id: String, ask: Bool) -> OSStatus {
  callsLock.lock(); calls += 1; callsLock.unlock(); started.signal()
  gate.wait(); return noErr
 }
''' + statuses + '''
}
_ = Apps.statuses(["frozen", "frozen"])
precondition(started.wait(timeout: .now() + 1) == .success)
for _ in 0..<4 { _ = Apps.statuses(["frozen"]) }
callsLock.lock(); precondition(calls == 1, "refresh leaked another blocked probe"); callsLock.unlock()
gate.signal()
let deadline = Date().addingTimeInterval(2)
while Date() < deadline {
 Apps.probeLock.lock(); let empty = Apps.pendingProbes.isEmpty; Apps.probeLock.unlock()
 if empty { break }; Thread.sleep(forTimeInterval: 0.01)
}
gate.signal()
precondition(Apps.statuses(["frozen"])["frozen"] == "allowed", "completed probe prevented future refresh")
''')

    def test_activation_returns_without_waiting_and_times_out(self):
        source = (ROOT / 'Delphi.swift').read_text()
        activate = source[source.index('    static func activate(_ pid:'):source.index('    static var workInFront')]
        self.swift('''import Foundation
final class NSRunningApplication {
 init?(processIdentifier: Int32) {}
 func activate() -> Bool { true }
}
final class Process {
 static var launched: [Process] = []
 var executableURL: URL?, arguments: [String]?, standardOutput: Any?, standardError: Any?
 var terminationHandler: ((Process) -> Void)?
 var isRunning = false, terminated = false
 func run() throws { isRunning = true; Self.launched.append(self) }
 func terminate() { precondition(!Thread.isMainThread); terminated = true; isRunning = false; terminationHandler?(self) }
}
enum MiniScreen {
''' + activate + '''
}
let began = Date()
MiniScreen.activate(42)
precondition(Date().timeIntervalSince(began) < 0.3, "activation blocked UI")
MiniScreen.activate(43)
let completed = Process.launched[1]
completed.isRunning = false; completed.terminationHandler?(completed)
RunLoop.current.run(until: Date().addingTimeInterval(2.3))
precondition(Process.launched[0].terminated, "stalled activation was not terminated")
precondition(!completed.terminated && completed.terminationHandler == nil, "completed activation retained its timeout")
''')

    def test_mic_serializes_sessions_and_ignores_cancelled_starts(self):
        source = (ROOT / 'Delphi.swift').read_text()
        mic = source[source.index('final class Mic:'):source.index('    func captureOutput(', source.index('final class Mic:'))] + '}\n'
        self.swift('''import Foundation
protocol AVCaptureAudioDataOutputSampleBufferDelegate {}
final class AVAudioPCMBuffer {}
let AVFormatIDKey = "format", AVSampleRateKey = "rate", AVNumberOfChannelsKey = "channels"
let AVLinearPCMBitDepthKey = "bits", AVLinearPCMIsFloatKey = "float", AVLinearPCMIsNonInterleaved = "interleaved"
let kAudioFormatLinearPCM = 1
final class AVCaptureDevice { var localizedName = "Fake"; var fail = false }
final class AVCaptureDeviceInput {
 init(device: AVCaptureDevice) throws { precondition(!Thread.isMainThread); if device.fail { throw CocoaError(.fileReadUnknown) } }
}
final class AVCaptureAudioDataOutput {
 var audioSettings: [String: Any] = [:]
 func setSampleBufferDelegate(_ delegate: Any, queue: DispatchQueue) {}
}
final class AVCaptureSession {
 static let lock = NSLock()
 static var active = 0, starts = 0, stops = 0
 var isRunning = false
 func canAddInput(_ input: AVCaptureDeviceInput) -> Bool { true }
 func canAddOutput(_ output: AVCaptureAudioDataOutput) -> Bool { true }
 func addInput(_ input: AVCaptureDeviceInput) {}
 func addOutput(_ output: AVCaptureAudioDataOutput) {}
 func startRunning() {
  precondition(!Thread.isMainThread); Thread.sleep(forTimeInterval: 0.2)
  Self.lock.lock(); Self.active += 1; Self.starts += 1; precondition(Self.active == 1); Self.lock.unlock(); isRunning = true
 }
 func stopRunning() {
  precondition(!Thread.isMainThread); Thread.sleep(forTimeInterval: 0.1)
  Self.lock.lock(); Self.active -= 1; Self.stops += 1; Self.lock.unlock(); isRunning = false
 }
}
''' + mic + '''
let mic = Mic(), device = AVCaptureDevice()
var stale = 0, ready = 0, errors = 0, drained = 0
let began = Date()
mic.start(device, sampleRate: 16000, { _ in }) { _ in stale += 1 }
precondition(mic.isRunning)
mic.stop(); precondition(!mic.isRunning)
mic.start(device, sampleRate: 16000, { _ in }) { result in
 precondition(Thread.isMainThread); if case .success = result { ready += 1 }
 mic.stop { precondition(Thread.isMainThread); drained += 1 }
}
precondition(Date().timeIntervalSince(began) < 0.1, "mic start/stop blocked UI")
RunLoop.current.run(until: Date().addingTimeInterval(1))
precondition(stale == 0 && ready == 1 && drained == 1 && !mic.isRunning)
AVCaptureSession.lock.lock(); precondition(AVCaptureSession.starts == 2 && AVCaptureSession.stops == 2 && AVCaptureSession.active == 0); AVCaptureSession.lock.unlock()
device.fail = true
mic.start(device, sampleRate: 16000, { _ in }) { result in
 precondition(Thread.isMainThread && !mic.isRunning); if case .failure = result { errors += 1 }
}
RunLoop.current.run(until: Date().addingTimeInterval(0.3))
precondition(errors == 1)
''')
        start = source[source.index('        engine.start(device,'):source.index('    func heard(')]
        self.assertIn('listenID == listeningID', start)
        self.assertLess(start.index('if case .failure'), start.index('began = Date()'))
