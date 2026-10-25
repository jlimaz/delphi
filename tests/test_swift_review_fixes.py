"""Regressions from the 1.3.1 Swift/UI review; source-only except for the shortcut matcher harness."""
from pathlib import Path
import shutil
import subprocess
import unittest

from tests import run_swift


ROOT = Path(__file__).resolve().parents[1]


class SwiftReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.swift = (ROOT / "Delphi.swift").read_text()
        self.overlay = (ROOT / "ui/ui.html").read_text()
        self.settings = (ROOT / "ui/settings.html").read_text()

    def test_fn_key_match_is_exact_and_modifier_prefixes_conflict(self):
        helpers = self.swift[self.swift.index("let delphiFnKey"):self.swift.index("func configuredHotkey")]
        matcher = self.swift[self.swift.index("func specialHotkey"):self.swift.index("func handleSpecialHotkeys")]
        self.assertIn("func hotkeysConflict", matcher)
        recorder = self.swift[self.swift.index("    func done("):self.swift.index("    func say(", self.swift.index("    func done("))]
        self.assertIn("hotkeysConflict(hotkey(),dictateHotkey())", recorder)
        harness = "import Cocoa\nimport Carbon\n" + helpers + "\nvar specialGlobalHotkeys: Any?, specialLocalHotkeys: Any?, specialMainDown = false, specialDictateDown = false\n" + matcher + r'''
let fnD = (code: 2, mods: delphiFnKey, flags: NSEvent.ModifierFlags.function)
let fnShiftD = (code: 2, mods: delphiFnKey | shiftKey, flags: NSEvent.ModifierFlags([.function, .shift]))
let fnOnly = (code: -2, mods: delphiFnKey, flags: NSEvent.ModifierFlags.function)
precondition(!hotkeysConflict(fnD, fnShiftD))
precondition(hotkeysConflict(fnOnly, fnD))
var down = false, fired: [Bool] = []
let extra = NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: [.function, .shift],
    timestamp: 0, windowNumber: 0, context: nil, characters: "d", charactersIgnoringModifiers: "d",
    isARepeat: false, keyCode: 2)!
updateSpecialHotkey(extra, fnD, &down) { fired.append($0) }
precondition(fired.isEmpty)
let exact = NSEvent.keyEvent(with: .keyDown, location: .zero, modifierFlags: [.function],
    timestamp: 0, windowNumber: 0, context: nil, characters: "d", charactersIgnoringModifiers: "d",
    isARepeat: false, keyCode: 2)!
updateSpecialHotkey(exact, fnD, &down) { fired.append($0) }
precondition(fired == [true])
print("special shortcuts stay distinct")
'''
        self.assertIn("special shortcuts stay distinct", run_swift(self, harness))

    def test_special_shortcut_registration_is_reported_as_available(self):
        registration = self.swift[self.swift.index("var ref: EventHotKeyRef?"):self.swift.index("let settings = SettingsWindow()")]
        push = self.swift[self.swift.index("    func push()"):self.swift.index("    func refresh()")]
        self.assertIn("var hotkeyRegistered = false", registration)
        self.assertIn("var dictateHotkeyRegistered = false", registration)
        self.assertIn('"hotkeyTaken": !hotkeyRegistered', push)
        self.assertIn('"dictateHotkeyTaken": !Prefs.str("dictateHotkeyLabel").isEmpty && !dictateHotkeyRegistered', push)

    def test_long_step_callout_starts_at_its_first_words(self):
        callout = self.swift[self.swift.index("final class DrawingCalloutView"):self.swift.index("final class ScreenDrawing")]
        self.assertIn("NSScrollView", callout)
        self.assertNotIn("scrollToEndOfDocument", callout)   # one step per callout: read it from the top
        harness = "import Cocoa\n" + callout + r'''
let words = String(repeating: "A readable instruction needs enough words to wrap. ", count: 20)
let size = DrawingCalloutView.size(words, total: 12)
let view = DrawingCalloutView(frame: CGRect(x: 0, y: 0, width: size.width + 24, height: size.height + 24),
                              card: CGRect(x: 12, y: 12, width: size.width, height: size.height), side: nil, tip: 0, text: words, step: 12, total: 12)
RunLoop.current.run(until: Date().addingTimeInterval(0.05))
let scroll = view.subviews.compactMap { $0 as? NSScrollView }.first!
let body = scroll.documentView as! NSTextView
precondition(body.frame.height > scroll.contentSize.height)
precondition(scroll.documentVisibleRect.minY <= 1)
print("long step stays reachable")
'''
        self.assertIn("long step stays reachable", run_swift(self, harness))

    def test_retry_voice_hint_only_names_visible_answers(self):
        respond = self.overlay[self.overlay.index("    respond(text)"):self.overlay.index("    ask([")]
        self.assertNotIn("Sonnet", respond)
        if not shutil.which("node"):
            self.skipTest("Node runs the retry-card behavior check")
        script = r'''
let heard = '', clicked = '';
const buttons = {n:{click(){clicked='n'}}, r:{click(){clicked='r'}}};
const d = {querySelector(s){const m=s.match(/data-answer="(.)"/);return m ? buttons[m[1]] || null : null;}};
const thread = {querySelector(s){return s.startsWith('.pk') ? null : d;}};
const ask = {value:''}, $ = id => id === 'thread' ? thread : ask, status = s => {heard=s};
const ui = {
''' + respond + r'''
};
if (!ui.respond('try sonnet') || clicked || heard !== 'Say “Retry” or “Not now”') process.exit(1);
console.log(heard);
'''
        result = subprocess.run(["node", "--input-type=module"], input=script, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_point_capture_failure_preserves_answer(self):
        finish = self.swift[self.swift.index("    func finishPoint("):self.swift.index("    func pointThumb")]
        self.assertIn('js("notice","Couldn’t capture that mark.")', finish)
        self.assertNotIn('js("msg","Couldn’t capture that mark.")', finish)
        self.assertIn("notice(s)", self.overlay)

    def test_hidden_rewrite_keeps_its_target(self):
        close = self.swift[self.swift.index("    func close(clear: Bool)"):self.swift.index("    func shortcut(", self.swift.index("    func close(clear: Bool)"))]
        harness = r'''import Foundation
final class NSAnimationContext {
    var duration = 0.0
    static func runAnimationGroup(_ changes: (NSAnimationContext) -> Void, completionHandler: () -> Void) {
        changes(NSAnimationContext()); completionHandler()
    }
}
final class Panel { var alphaValue = 1.0; func animator() -> Panel { self } }
final class Drawing { func clear() {} }
func unpoint() {}
final class Harness {
    var replacement: String? = "draft", selection: Int? = 7, lastDone = Date()
    var recent = "/missing", gen = 0
    let panel = Panel(), drawing = Drawing()
    func shush() {}
    func hush() { replacement = nil; selection = nil }
    func gone() {}
''' + close + r'''}
let hidden = Harness(); hidden.close(clear: false)
precondition(hidden.replacement == "draft" && hidden.selection == 7)
let ended = Harness(); ended.close(clear: true)
precondition(ended.replacement == nil && ended.selection == nil)
print("hidden rewrite target kept")
'''
        self.assertIn("hidden rewrite target kept", run_swift(self, harness))

    def test_pointer_respects_reduce_motion(self):
        pointer = self.swift[self.swift.index("func pointAt("):self.swift.index("// Restart Delphi", self.swift.index("func pointAt("))]
        self.assertIn("let still = NSWorkspace.shared.accessibilityDisplayShouldReduceMotion\n    if !still {", pointer)
        self.assertLess(pointer.index("accessibilityDisplayShouldReduceMotion"), pointer.index("l.add(pulse"))
        self.assertIn("if let box, lead(from: box, to: w.frame.insetBy(dx: 8, dy: 8)) {", pointer)
        lead = pointer[pointer.index("func lead("):]   # Reduce Motion: a still leader line, no running head
        self.assertLess(lead.index("if !still {"), lead.index('line.add(head'))

    def test_new_ask_clears_a_held_ring_without_hiding_the_new_answer(self):
        start = self.swift[self.swift.index("    func start(dictate: Bool)"):self.swift.index("    func heard(")]
        run = self.swift[self.swift.index("    func run(_ t: String"):self.swift.index("\n}\n\n// First-run window")]
        unpoint = self.swift[self.swift.index("func unpoint("):self.swift.index("// A line from the box")]
        self.assertIn("unpoint(false)", start)
        self.assertIn("pointContext = nil; unpoint(false)", run)
        self.assertIn("if notify { gone?() }", unpoint)

    def test_released_dictation_drops_queued_level_updates(self):
        start = self.swift[self.swift.index("    func start(dictate: Bool)"):self.swift.index("    func heard(")]
        level = start[start.index('js("level", v)') - 160:start.index('js("level", v)') + 20]
        self.assertIn("listenID == listeningID, self?.engine.isRunning == true", level)

    def test_talking_about_a_drawing_shows_the_listening_orb(self):
        self.assertIn('if replying && !drawingReply { js("draft", "") } else { js("listen")', self.swift)
        self.assertIn('js(drawingReply ? "words" : "draft", now)', self.swift)
        self.assertIn('typed(response, heard: true)', self.swift)

    def test_voice_ask_that_heard_nothing_ends_quietly(self):
        # Oct 20, 2026: a tap, or clicking in to type after letting go, ended in "Didn't catch that." / an empty review.
        finish = self.swift[self.swift.index("    func finish() {"):self.swift.index("    // delphi.py --wait, started")]
        self.assertNotIn("Didn't catch that", finish)
        self.assertIn('if did.isEmpty { js("msg", ""); return hide(after: 0.2) }', finish)
        stop = self.swift[self.swift.index("    func stop() {"):self.swift.index("    func applyReplacement()")]
        quiet = 'if text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { hush(); js("msg", ""); return hide(after: 0.2) }'
        self.assertLess(stop.index(quiet), stop.index("review(\"Couldn’t confirm your words."))
        typing = self.swift[self.swift.index('if b["type"] != nil {'):self.swift.index('if let s = b["link"]')]
        self.assertIn('else if busy && proc == nil && offerText == nil && !dictating && text.isEmpty { hush(); js("msg", "") }', typing)
        start = self.swift[self.swift.index("    func start(dictate: Bool)"):self.swift.index("    func heard(")]
        self.assertLess(start.index("began = Date()   // key-down"), start.index("engine.start(device"))
        msg = self.overlay[self.overlay.index("    msg(s) {"):self.overlay.index("    stopped(s) {")]
        self.assertIn("document.body.classList.remove('hearing')", msg)   # a tap's quiet end comes straight from listening
        self.assertIn('if (part(\'q\')?.classList.contains(\'empty\')) { turn().remove(); status(s); }', msg)   # "" leaves no line

    def test_hidden_box_forgets_hover(self):
        gone = self.swift[self.swift.index("    func gone()"):self.swift.index("    func pill(")]
        self.assertIn("hovering = false", gone)   # else hide() waits on a mouse that left with the panel
        self.assertIn('js("hover", false)', gone)

    def test_unconfirmed_drawing_reply_does_not_leave_the_box_busy(self):
        stop = self.swift[self.swift.index("    func stop() {"):self.swift.index("    func applyReplacement()")]
        branch = stop[stop.index("if let old = offerText"):stop.index("return }", stop.index("if let old = offerText"))]
        self.assertIn("busy = proc?.isRunning == true", branch)

    def test_moved_guide_explains_why_it_closed(self):
        drawing = self.swift[self.swift.index("final class ScreenDrawing"):self.swift.index("// The box can take typing")]
        tick = drawing[drawing.index("    func tick()"):]
        stale = tick[tick.index("guard Self.current(target)"):]
        self.assertLess(stale.index('status?("The screen changed. Ask again to continue.")'), stale.index("clear()"))

    def test_in_app_accessibility_calls_are_bounded(self):
        init = self.swift[self.swift.index("    override init() {\n        let cfg = WKWebViewConfiguration()"):self.swift.index("    func userContentController(_ c: WKUserContentController")]
        self.assertIn("AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 0.5)", init)
        menu = self.swift[self.swift.index("    static func menuShortcut("):self.swift.index("    static func sendKeys(")]
        self.assertIn("AXUIElementSetMessagingTimeout(application, 0.15)", menu)
        web = self.swift[self.swift.index("    static func webFocused("):self.swift.index("    // An app sends keys")]
        self.assertIn("AXUIElementSetMessagingTimeout(application, 0.15)", web)

    def test_sleep_or_lock_releases_recording_and_shortcut_state(self):
        prepare = self.swift[self.swift.index("    func prepareForInactiveSession()"):self.swift.index("    func dictateShortcut(", self.swift.index("    func prepareForInactiveSession()"))]
        self.assertIn("shortcutDown = false; dictateShortcutDown = false", prepare)
        self.assertIn("quietAudio.end(immediate: true)", prepare)
        observers = self.swift[self.swift.index("var specialGlobalHotkeys"):self.swift.index("func specialHotkey(")]
        self.assertIn("NSWorkspace.willSleepNotification", observers)
        self.assertIn("NSWorkspace.didWakeNotification", observers)
        self.assertIn("NSWorkspace.sessionDidResignActiveNotification", observers)
        self.assertIn("specialMainDown = false; specialDictateDown = false", observers)

    def test_display_changes_clear_stale_drawings(self):
        app_init = self.swift[self.swift.index("    override init() {\n        let cfg = WKWebViewConfiguration()"):self.swift.index("    func userContentController(_ c: WKUserContentController")]
        screen = app_init[app_init.index("NSApplication.didChangeScreenParametersNotification"):]
        self.assertIn("drawing.clear()", screen)
        self.assertIn("The screen changed. Ask again to continue.", screen)
        self.assertIn("interrupted = hadDrawing && (engine.isRunning || dictating || busy)", screen)
        self.assertLess(screen.index("if interrupted { hush() }"), screen.index("drawing.clear()"))
        self.assertIn('js("stopped", message)', screen)
        self.assertIn('js("dictated", ["text": message, "ok": false])', screen)

    def test_visible_box_follows_the_pointer_display_without_interrupting_interaction(self):
        follow = self.swift[self.swift.index("    func followPointerScreen()"):self.swift.index("    func pointElement(")]
        self.assertIn("panel.isVisible, !dragging, !hovering, let f = pointerFollow(panel.frame)", follow)
        self.assertNotIn("composing", follow)   # the typing box follows too
        self.assertIn("frame(f)", follow)
        show = self.swift[self.swift.index("    func show()"):self.swift.index("    func hide(")]
        self.assertIn("startFollowingPointerScreen()", show)
        gone = self.swift[self.swift.index("    func gone()"):self.swift.index("    func pill(")]
        self.assertIn("followTimer?.invalidate()", gone)
        self.assertIn("if !dictate && !drawingReply { targetScreen = currentRequestScreen(panel) }", self.swift)
        self.assertIn("if !drawing.active { targetScreen = currentRequestScreen(panel) }", self.swift)
        self.assertIn("input,textarea,[contenteditable=true]", self.overlay)

    def test_speculative_voice_start_keeps_the_key_down_focus_snapshot(self):
        run = self.swift[self.swift.index("    func run(_ t: String"):self.swift.index("\n    }\n}", self.swift.index("    func run(_ t: String"))]
        self.assertIn("if !busy && !engine.isRunning { noteHidden() }", run)

    def test_follow_keeps_side_offsets(self):
        geometry = self.swift[self.swift.index("enum PanelFrame {"):self.swift.index("\nlet kofi")]
        harness = "import Cocoa\n" + geometry + r'''
let a = NSRect(x: 0, y: 0, width: 1440, height: 875), b = NSRect(x: 1440, y: -200, width: 1920, height: 1055)
func go(_ f: NSRect) -> NSRect { PanelFrame.clamp(PanelFrame.follow(f, a, b, right: f.midX > a.midX, top: f.midY > a.midY), b) }
let shelf = NSRect(x: a.maxX - 272, y: a.maxY - 160, width: 260, height: 152)   // default: 12 from the right, 8 from the top
let moved = go(shelf)
precondition(b.maxX - moved.maxX == 12 && b.maxY - moved.maxY == 8 && moved.size == shelf.size)
let dragged = go(NSRect(x: 8, y: 8, width: 260, height: 52))   // dragged to the bottom-left
precondition(dragged.minX - b.minX == 8 && dragged.minY - b.minY == 8)
let small = NSRect(x: -800, y: 0, width: 800, height: 600)
let clamped = PanelFrame.clamp(PanelFrame.follow(shelf, a, small, right: true, top: true), small)
precondition(small.contains(clamped))
print("shelf follows")
'''
        self.assertIn("shelf follows", run_swift(self, harness))

    def test_every_floating_surface_jumps_to_the_pointer_display_through_one_check(self):
        shared = self.swift[self.swift.index("func pointerFollow("):self.swift.index("// Freeze the display")]
        self.assertIn("NSEvent.pressedMouseButtons == 0", shared)   # never mid-drag or while a button is held
        self.assertIn("from != to", shared)
        # the same side-and-offset formula the follow harness proves
        self.assertIn("PanelFrame.clamp(PanelFrame.follow(f, from, to, right: f.midX > from.midX, top: f.midY > from.midY), to)", shared)
        box = self.swift[self.swift.index("    func followPointerScreen()"):self.swift.index("    func pointElement(")]   # box, typing box, answer, dictation pill
        self.assertIn("pointerFollow(", box)
        for slide in ["animator()", "NSAnimationContext", "glide(", "animate: true", "PanelFrame.follow("]:
            self.assertNotIn(slide, box)
        self.assertEqual(self.swift.count("pointerFollow("), 2)   # definition and box: no per-panel copies
        self.assertEqual(self.swift.count("PanelFrame.follow("), 1)
        show = self.swift[self.swift.index("    func show()"):self.swift.index("    func hide(")]
        self.assertIn("startFollowingPointerScreen()", show)   # the dictation pill opens through show() too
        self.assertIn("pill(true); show()", self.swift)

    def test_target_app_also_matches_the_app_bundle_name(self):
        lookup = self.swift[self.swift.index('["--window-target","--target-app"].contains'):]
        lookup = lookup[:lookup.index("exit(0)")]
        self.assertIn("bundleURL?.deletingPathExtension().lastPathComponent.localizedCaseInsensitiveCompare(name)", lookup)   # "Visual Studio Code.app" runs as "Code"

    def test_window_target_reports_a_visible_unfocused_window(self):
        # A game window on a second display, uncovered but not key: --front must see it as reachable and leave it in place.
        start = self.swift.index("    static func visible(_ r: CGRect")
        visible = self.swift[start:self.swift.index("\n    }\n", self.swift.index("    static func paintRect(", start)) + 6]
        lookup = self.swift[self.swift.index('["--window-target","--target-app"].contains'):]
        self.assertIn('target["visible"] = onScreen && target["minimized"] as? Bool != true &&', lookup[:lookup.index("\n    exit(0)\n}")])
        look = self.swift[self.swift.index('CommandLine.arguments[1] == "--look"'):self.swift.index('// `Delphi --text <app>')]
        self.assertIn("SCContentFilter(desktopIndependentWindow: w)", look)   # the window's own pixels: right even when covered
        self.assertIn("MiniScreen.paintRect(w.frame, display: d.frame, pictureHeight: img.height)", look)
        self.assertLess(look.index("c.draw(shot, in: spot)"), look.index('print("window")'))   # it says painted only after painting
        out = run_swift(self, "import CoreGraphics\nenum MiniScreen {\n" + visible + r'''}
// Monitor at x 1512, 2560x1440 points -> a 1280x720 picture (scale 0.5); the window's top-left at (1900, 200) is picture pixel (194, 100)
precondition(MiniScreen.paintRect(CGRect(x:1900,y:200,width:1100,height:800), display:CGRect(x:1512,y:0,width:2560,height:1440), pictureHeight:720) == CGRect(x:194,y:220,width:550,height:400))
let laptop = CGRect(x:0,y:0,width:1512,height:982), monitor = CGRect(x:1512,y:0,width:2560,height:1440), game = CGRect(x:1900,y:200,width:1100,height:800)
precondition(MiniScreen.visible(game, displays:[laptop, monitor], above:[CGRect(x:0,y:0,width:1512,height:982)]))   // the user's window is on the other display
precondition(MiniScreen.visible(game, displays:[laptop, monitor], above:[CGRect(x:1900,y:200,width:100,height:80)]))   // a small corner overlap
precondition(!MiniScreen.visible(game, displays:[laptop, monitor], above:[CGRect(x:2000,y:300,width:600,height:500)]))   // covered
precondition(!MiniScreen.visible(game, displays:[laptop], above:[]))   // its display is gone: off-screen
precondition(!MiniScreen.visible(CGRect(x:3800,y:200,width:800,height:600), displays:[laptop, monitor], above:[]))   // mostly past the edge
precondition(!MiniScreen.visible(.zero, displays:[monitor], above:[]))
print("visible ok")
''')
        self.assertIn("visible ok", out)

    def test_settings_describe_all_shortcuts_and_remove_dead_pointer_toggle(self):
        self.assertGreaterEqual(self.settings.count("a modifier on its own"), 2)
        self.assertNotIn('data-k="pointer"', self.settings)
        self.assertNotIn(">Show me where<", self.settings)


if __name__ == "__main__":
    unittest.main()
