"""Local dictation storage and conservative corrections; no UI, mic, apps or model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

from tests import run_swift

ROOT = Path(__file__).resolve().parents[1]


class DictationDataTests(unittest.TestCase):
    def test_dictionary_never_keeps_dictated_text(self):
        source = (ROOT / 'Delphi.swift').read_text()
        store = source[source.index('enum DictationData {'):source.index('enum Prefs {')]
        swift = r'''import AppKit
struct Prefs {
    static let path = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString).path + "/settings.json"
    static var d: [String: Any] = [:]
    static func bool(_ k: String) -> Bool { d[k] as? Bool ?? false }
    static func set(_ k: String, _ v: Any) -> Bool { d[k] = v; return true }
}
''' + store + r'''
defer { try? FileManager.default.removeItem(atPath: (Prefs.path as NSString).deletingLastPathComponent) }
precondition(DictationData.word("Saarth"))
precondition(DictationData.word("Saarth") && DictationData.words == ["Saarth"])
precondition(DictationData.word("Delphi", replacing: "Saarth") && DictationData.words == ["Delphi"])
precondition(!DictationData.word("\n") && !DictationData.word("bad\nword") && !DictationData.word(String(repeating:"a", count:81)))
precondition(DictationData.state().keys.sorted() == ["words"])
print("private dictation data ok")
'''
        self.assertIn('private dictation data ok', run_swift(self, swift))

    def test_corrections_are_single_words_and_reject_rewrites(self):
        source = (ROOT / 'Delphi.swift').read_text()
        store = source[source.index('enum DictationData {'):source.index('enum Prefs {')]
        swift = r'''import AppKit
struct Prefs {
    static var path = "/tmp/unused-delphi-dictation-test/settings.json"
    static var d: [String: Any] = [:]
    static func bool(_ k: String) -> Bool { false }
    static func set(_ k: String, _ v: Any) -> Bool { true }
}
''' + store + r'''
let saarth = DictationData.correction("Hello Sarth.", "Hello Saarth.")
precondition(saarth?.heard == "Sarth" && saarth?.word == "Saarth")
precondition(DictationData.correction("open delphi", "open Delphi")?.word == "Delphi")
precondition(DictationData.correction("Hi Andree", "Hi André")?.word == "André")
precondition(DictationData.correction("I went their", "I went there") == nil)   // an everyday word is no name to learn
let sarda = DictationData.correction("Can you make sure Sarda does that?", "Can you make sure Saarth does that?")
precondition(sarda?.heard == "Sarda" && sarda?.word == "Saarth", "sound-alike fix")
let two = DictationData.correction("You make sure start to does that.", "You make sure Saarth does that.")
precondition(two?.heard == "start to" && two?.word == "Saarth", "two heard words, one name")
let three = DictationData.correction("Can you ask some of you to do that?", "Can you ask Semva to do that?")
precondition(three?.heard == "some of you" && three?.word == "Semva", "three heard words, one name")
precondition(DictationData.correction("ask some of b to", "ask Semva to")?.word == "Semva", "garbled three words")
precondition(DictationData.correction("Can you ask somebody to do that?", "Can you ask Semva to do that?")?.heard == "somebody", "a real word that sounds like the name")
precondition(DictationData.correction("send it to the team", "send it Tuesday") == nil, "several words that don't sound alike")
precondition(DictationData.correction("Ship it Friday.", "Ship it Monday.") == nil, "a new idea")
precondition(DictationData.correction("ask Sarda now", "ask Saarth there now") == nil, "one word became two")
precondition(DictationData.sound("Saarth") == "srt" && DictationData.sound("start to") == "strt" && DictationData.sound("André") == "amtr")
var keys = DictationData.Replay("make sure start to does")
for (code, typed, option) in [(123, "", true), (51, "", true), (51, "", true)] { precondition(keys.key(code, typed, option: option, control: false, command: false)) }
for c in "Saarth " { precondition(keys.key(0, String(c), option: false, control: false, command: false)) }
precondition(keys.text == "make sure Saarth does", keys.text)
precondition(DictationData.correction("make sure start to does", keys.text)?.heard == "start to", "replayed fix")
var ends = DictationData.Replay("hi")
precondition(!ends.key(36, "\r", option: false, control: false, command: false), "Return")
precondition(!ends.key(9, "v", option: false, control: false, command: true), "⌘V")
precondition(!ends.key(126, "\u{F700}", option: false, control: false, command: false), "up arrow")
precondition(ends.key(51, "", option: false, control: false, command: false) && ends.key(4, "h", option: false, control: true, command: false) && !ends.key(51, "", option: false, control: false, command: false), "deleting past the dictated words")
for text in ["Hello", "Hello Sarth. again", "Changed everything.", "Hello 123.", "Hello Sarth.", "Hi Saarth."] {
    precondition(DictationData.correction("Hello Sarth.", text) == nil, text)
}
print("correction bounds ok")
'''
        self.assertIn('correction bounds ok', run_swift(self, swift))

    def test_learned_fix_swaps_the_heard_word_until_forgotten(self):
        source = (ROOT / 'Delphi.swift').read_text()
        store = source[source.index('enum DictationData {'):source.index('enum Prefs {')]
        swift = r'''import AppKit
struct Prefs {
    static var path = "/tmp/unused-delphi-dictation-test/settings.json"
    static var d: [String: Any] = [:]
    static func bool(_ k: String) -> Bool { false }
    static func set(_ k: String, _ v: Any) -> Bool { d[k] = v; return true }
}
''' + store + r'''
precondition(DictationData.word("Saarth") && DictationData.fix("Sarth", "Saarth"), "saved fix")
precondition(DictationData.fixed("sarth met Sarth's friend, not Sarthak.") == "Saarth met Saarth's friend, not Sarthak.", "whole-word swap")
precondition(DictationData.word("cache") && DictationData.fix("cash", "cache"), "real heard word kept for hints")
precondition(DictationData.fixed("cash it") == "cash it", "real word swapped")   // only cleanup, with context, may change it
precondition(!DictationData.fix("Bob", "Robert"), "non-dictionary fix")   // only a dictionary word gets a fix
precondition(DictationData.word("vexlar") && DictationData.fix("vexlor", "vexlar"), "lowercase fix")
precondition(DictationData.fixed("Vexlor then vexlor.") == "Vexlar then vexlar.", "capital kept")
precondition(DictationData.word("Vexlar", replacing: "vexlar") && DictationData.fixes["vexlor"] == "Vexlar", "edit retargets")
precondition(DictationData.forget("Saarth") && DictationData.fixes["sarth"] == nil && !DictationData.words.contains("Saarth"), "forget")
precondition(DictationData.fixed("Sarth") == "Sarth", "forgotten swap")
print("learned fixes ok")
'''
        self.assertIn('learned fixes ok', run_swift(self, swift))
        self.assertIn('let value = DictationData.fixed(heard)', source)   # every insert path goes through insertDictation
        self.assertIn('DictationData.fix(fix.heard, word)', source)
        self.assertEqual(source.count('DictationData.forget('), 2)   # Undo and Settings remove both drop the fix

    def test_dictionary_reaches_cleanup_and_keeps_saved_rules(self):
        import delphi
        with patch.object(delphi, 'pref', return_value=['Saarth', 'Delphi', None, 'bad\nword']), \
             patch.object(delphi, 'relevant_rules', return_value='Spell my name Saarth.'):
            request = delphi.dictate_request('say Sarth')
            self.assertIn('["Saarth", "Delphi"]', request)
            self.assertIn('Spell my name Saarth.', request)
            self.assertNotIn('bad', request)
            self.assertEqual(delphi.dictate_result('say Sarth', '<cleaned>Say Saarth.</cleaned>', {'Sarth': 'Saarth'}), 'Say Saarth.')

    def test_cleanup_gets_sound_alike_hints_and_may_write_the_name(self):
        import delphi
        prefs = {'dictateWords': ['Saarth'], 'dictateFixes': {'some veto': 'Saarth', 'old': 'Gone'}}
        with patch.object(delphi, 'pref', side_effect=lambda k, d=None: prefs.get(k, d)), \
             patch.object(delphi, 'relevant_rules', return_value=''):
            self.assertEqual(delphi.dictate_hints('Can you make sure Sarda does that?', ['Saarth']), {'Sarda': 'Saarth'})
            self.assertEqual(delphi.dictate_hints('You make sure some veto that.', ['Saarth']), {'some veto': 'Saarth'})   # a learned heard form
            self.assertEqual(delphi.dictate_hints('Saarth sorted it', ['Saarth']), {})   # already said right
            self.assertEqual(delphi.dictate_hints('Hi there', ['Saarth']), {})
            self.assertEqual(delphi.dictate_hints('Can you ask some of you to do that?', ['Semva']).get('some of you'), 'Semva')
            text = 'You make sure start to does that.'
            request = delphi.dictate_spellings(text)
            self.assertIn('"start": "Saarth"', request)
            hints = delphi.dictate_hints(text, ['Saarth'])
            self.assertEqual(delphi.dictate_result(text, '<cleaned>You make sure Saarth does that.</cleaned>', hints), 'You make sure Saarth does that.')
            ordinary = 'Send the update to him this afternoon please.'
            changed = '<cleaned>Send the update to Saarth this afternoon please.</cleaned>'
            self.assertEqual(delphi.dictate_result(ordinary, changed, {}), ordinary)
            self.assertEqual(delphi.dictate_result(ordinary, changed, {'him': 'Saarth'}),
                             'Send the update to Saarth this afternoon please.')
        self.assertEqual((delphi.dictate_sound('Saarth'), delphi.dictate_sound('start to'), delphi.dictate_sound('André')), ('srt', 'strt', 'amtr'))   # same as DictationData.sound

    def test_correction_window_is_scoped_and_secure_before_read(self):
        source = (ROOT / 'Delphi.swift').read_text()
        monitor = source[source.index('    func prepareDictation('):source.index('    func stopDictationCleanup(')]
        for guard in ['addingTimeInterval(20)', 'dictateID == id', '!engine.isRunning', '!busy',
                      'frontmostApplication == target.app', 'CFEqual(focused, target.focus)',
                      'current.hasPrefix(prefix)', 'current.hasSuffix(suffix)', 'timer.invalidate()']:
            self.assertIn(guard, monitor)
        self.assertLess(monitor.index('kAXSecureTextFieldSubrole'), monitor.index('target.value'))
        poll = monitor[monitor.index('Timer.scheduledTimer'):]
        self.assertLess(poll.index('kAXSecureTextFieldSubrole'), poll.index('target.value'))
        # Keys are read only where the field can't be: in the dictated app, never under secure input, for 20 s, then the monitor goes.
        self.assertLess(monitor.index('kAXSecureTextFieldSubrole'), monitor.index('replayEdits(value'))
        replay = source[source.index('    func replayEdits('):source.index('    func stopReplay()')]
        for guard in ['dictateID != id', 'frontmostApplication != app', 'IsSecureEventInputEnabled() ? "secure input"', 'guard why == nil',
                      'withTimeInterval: 20', 'stopReplay()']:
            self.assertIn(guard, replay)
        self.assertIn('NSEvent.removeMonitor(editKeys)', source[source.index('    func stopReplay()'):])
        capture = source[source.index('    static func capture('):source.index('    var caret:')]
        self.assertLess(capture.index('kAXSecureTextFieldSubrole'), capture.index('kAXValueAttribute'))
        session = source[source.index('    func captureDictationSelection('):source.index('    func start()')]
        self.assertIn('onSecure: { secureField = true }', session)
        self.assertLess(session.index('if secureField'), session.index('dictateSelectionPending = false'))
        self.assertIn('hush(); js("dictated"', session)
        self.assertIn('guard let selected else', session)
        self.assertIn('dictateSelection = selected', session)
        self.assertNotIn('selected.text.count <= 6000', session)
        self.assertIn('if AXIsProcessTrusted() {', session)   # no text field: keep listening, the words stay in the pill
        self.assertLess(session.index('dictateSelectionPending = false'), session.index('guard let selected else'))
        self.assertIn('dictationTargetApp = NSWorkspace.shared.frontmostApplication', session)
        self.assertIn('if retry { finishDictation() }', session)
        finish = source[source.index('    func finishDictation()'):source.index('    func recordDictationEvent(')]
        self.assertIn('captureDictationSelection(retry: true)', finish)
        self.assertIn('!dictateSelectionRetried', finish)
        self.assertIn('NSWorkspace.shared.frontmostApplication == app', finish)
        self.assertLess(finish.index('dictateSelectionRetried = true'), finish.index('captureDictationSelection(retry: true)'))
        self.assertLess(finish.index('captureDictationSelection(retry: true)'), finish.index('let spoken ='))
        start = source[source.index('    func start(dictate: Bool)'):source.index('    func heard(')]
        self.assertLess(start.index('if dictate && !AXIsProcessTrusted()'), start.index('captureDictationSelection()'))
        self.assertIn('Allow Accessibility in System Settings → Privacy & Security → Accessibility', start)


@unittest.skipUnless(shutil.which('node'), 'Node UI logic check')
class DictationUIDataTests(unittest.TestCase):
    def test_dictionary_actions_use_text(self):
        page = (ROOT / 'ui/settings.html').read_text()
        code = page[page.index('  const svg = d =>'):page.index("  document.querySelectorAll('nav button[data-s] .ni')")]
        script = r'''const assert = (x, m) => { if (!x) throw Error(m); };
class Element {
  constructor() { this.children = []; this.value = ''; this.style = {}; }
  append(...x) { this.children.push(...x); }
  replaceChildren(...x) { this.children = x; }
  setAttribute() {}
}
const ids = new Map(), $ = id => { if (!ids.has(id)) ids.set(id, new Element()); return ids.get(id); };
const document = {createElement: () => new Element()}, posts = [];
const post = m => posts.push(m);
''' + code + r'''
dictations = {words:['<Saarth>']};
paintDictation();
const word = $('dictationwords').children[0];
assert(word.children[0].value === '<Saarth>', 'dictionary did not preserve literal text');
assert(word.children[1].hidden === true, 'save icon showed before an edit');
word.children[0].value = 'Saarth'; word.children[0].oninput(); assert(word.children[1].hidden === false, 'save icon hidden after an edit');
word.onsubmit({preventDefault(){}});
assert(posts.at(-1).word === 'Saarth' && posts.at(-1).old === '<Saarth>', 'edit lost original word');
word.children[2].onclick(); assert(posts.at(-1).do === 'dictationWordDelete', 'remove not wired');
$('dictationword').value = 'New'; $('dictationadd').onsubmit({preventDefault(){}});
assert(posts.at(-1).word === 'New' && $('dictationword').value === '', 'add not wired');
dictations = {words: []}; paintDictation();
assert($('dictationwords').hidden && $('dictationnote').textContent.startsWith('No words yet'), 'empty dictionary not a quiet line');
'''
        result = subprocess.run(['node'], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_learned_toast_undo_posts_and_disables_its_button(self):
        page = (ROOT / 'ui/ui.html').read_text()
        method = page[page.index('    learned(word)'):page.index('    line(l)')]
        script = r'''let label, sent, button;
const pill = (state, text) => { label = text; return {append: (...args) => { button = args[1]; }}; }, fit = () => {};
const document = {createElement: () => ({})};
const post = message => { sent = message; };
const ui = {''' + method + r'''};
ui.learned('Saarth'); button.onclick();
if (label !== "Learned “Saarth”" || !button.disabled || !sent.learnedUndo) throw Error('learned undo failed');
'''
        result = subprocess.run(['node'], input=script, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
