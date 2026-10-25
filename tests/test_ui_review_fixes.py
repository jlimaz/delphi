"""Regressions from the 1.3.2 UI review; source and Node checks only, no windows."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


def node(test, script):
    if not shutil.which('node'):
        test.skipTest('Node runs the overlay checks')
    result = subprocess.run(['node', '--input-type=module'], input=script, capture_output=True, text=True)
    test.assertEqual(result.returncode, 0, result.stderr)


def contrast(fg, bg):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    a, b = lum(fg), lum(bg)
    return (max(a, b) + .05) / (min(a, b) + .05)


def tint(color, alpha, bg='#ffffff'):
    return '#' + ''.join('%02x' % round(alpha * int(color[i:i + 2], 16) + (1 - alpha) * int(bg[i:i + 2], 16)) for i in (1, 3, 5))


class UIReviewFixTests(unittest.TestCase):
    def setUp(self):
        self.swift = (ROOT / 'Delphi.swift').read_text()
        self.box = (ROOT / 'ui/ui.html').read_text()
        self.settings = (ROOT / 'ui/settings.html').read_text()
        self.onboarding = (ROOT / 'ui/onboarding.html').read_text()

    def test_native_clicks_reach_the_pill_buttons(self):
        tap = self.box[self.box.index('    tap([x, y])'):self.box.index('    size(h)')]
        node(self, r'''let clicked = '';
const make = key => { const el = { closest: s => s.split(', ').includes(key) ? el : null, click() { clicked = key; } }; return el; };
let dictating = false;
const document = { elementFromPoint: () => current, body: { classList: { contains: c => c === 'dictate' && dictating } } }; let current;
const $ = () => ({ classList: { contains: () => false }, value: '' }), drop = () => { clicked = 'typing'; }, comp = () => { clicked = 'typing box'; }, post = () => {}, status = () => {}, fit = () => {};
const ui = {''' + tap + r'''};
for (const key of ['.dn button']) { current = make(key); clicked = ''; ui.tap([0, 0]); if (clicked !== key) { console.error(key + ' opened the ' + clicked); process.exit(1); } }
dictating = true; current = make('.dn'); clicked = ''; ui.tap([0, 0]); if (clicked) { console.error('a click on the dictation pill opened the ' + clicked); process.exit(1); }
''')

    def test_typing_row_animates_everything_it_changes(self):
        # Oct 20, 2026: the open row's -4px side margins jumped while its 4px padding animated, so the field and buttons slid
        closed = re.search(r'  #comp \{([^}]*)\}', self.box).group(1)
        opened = re.search(r'  #comp\.open \{([^}]*)\}', self.box).group(1)
        animated = {p.split()[0] for p in re.search(r'transition: ([^;]*);', closed).group(1).split(',')}
        for prop in re.findall(r'([a-z-]+):', opened):
            self.assertIn(prop, animated)

    def test_choice_number_shortcuts_work_from_the_empty_composer(self):
        handler = self.box[self.box.index("  $('ask').onkeydown = e => {"):self.box.index('  // the model row:')]
        node(self, r'''let picked = 0, clicked = 0, prevented = false;
const choices = Array.from({length: 3}, (_, i) => ({choose() { picked = i + 1; }, click() { clicked++; }, focus() {}}));
const ask = {value: ''}, thread = {querySelector: () => null, querySelectorAll: () => choices};
const $ = id => id === 'ask' ? ask : thread, part = () => null, status = () => {}, post = () => {};
const window = {ui: {respond: () => false}}; let listening = false, working = false;
''' + handler + r'''
const key = value => ask.onkeydown({key: value, target: ask, isComposing: false, metaKey: false, ctrlKey: false, altKey: false, preventDefault() { prevented = true; }});
key('2'); if (picked !== 2 || clicked || !prevented) process.exit(1);
picked = 0; prevented = false; ask.value = 'version '; key('2'); if (picked || prevented) process.exit(2);
''')
        self.assertIn('c.choose = () => done(i)', self.box)
        self.assertIn('cs[e.key - 1].choose()', self.box)

    def test_full_access_badge_is_a_keyboard_control(self):
        self.assertIn('id="mode" role="button" tabindex="0"', self.box)
        self.assertIn('#mode:focus-visible', self.box)
        self.assertIn("$('mode').onclick = enableSafeMode", self.box)
        self.assertIn("if (e.key === 'Enter' || e.key === ' ')", self.box)
        self.assertIn("if (el?.closest('#mode')) return enableSafeMode()", self.box)

    def test_failed_dictation_offers_its_words_to_copy(self):
        dictated = self.box[self.box.index('    dictated({'):self.box.index('    learned(word)')]
        node(self, r'''let sent, button;
const fit = () => {}, setState = () => {}, $ = () => ({ style: {} }), post = m => { sent = m; };
let listening = true, boost = 1;
const document = { body: { classList: { remove() {} } }, createElement: () => ({}) }, pill = () => ({ append: (...a) => { button = a[1]; } });
const ui = {''' + dictated + r'''};
ui.dictated({ text: 'Nothing selected to insert — saved to History.', ok: false }); if (button) process.exit(1);
ui.dictated({ text: 'Couldn’t insert. Your words are still here.', ok: false, words: 'my words' }); button.onclick();
if (sent?.copy !== 'my words' || button.textContent !== 'Copied') process.exit(1);
ui.dictated({ text: 'Couldn’t insert. Press ⌃⌘V to paste it.', ok: false, history: true }); button.onclick();
if (sent?.dictationHistory !== true || button.textContent !== 'History') process.exit(1);
''')

    def test_learned_word_shows_in_the_pill_after_it_folded(self):
        self.assertIn('learnedWord = word; pill(true); show(); js("learned", word)', self.swift)

    def test_reduce_motion_stops_onboarding_loops(self):
        rule = re.search(r'@media \(prefers-reduced-motion: reduce\) \{ \*, \*::before, \*::after \{(.*?)\}', self.onboarding).group(1)
        self.assertIn('animation-iteration-count: 1 !important', rule)
        self.assertIn("const reduced = matchMedia('(prefers-reduced-motion: reduce)')", self.onboarding)
        self.assertIn("reduced.addEventListener('change'", self.onboarding)
        self.assertIn('welcomeGeneration++; previewGeneration++;', self.onboarding)
        self.assertIn('Object.keys(loops).forEach(id => finals[id]())', self.onboarding)
        self.assertIn('if (reduced.matches) { finals[id](); await motionChange(); }', self.onboarding)
        self.assertNotIn("const still = matchMedia('(prefers-reduced-motion: reduce)').matches", self.onboarding)

    def test_onboarding_welcome_orb_keeps_animating(self):
        start = self.onboarding.index("    const cv = $('orb')")
        loop = self.onboarding[start:self.onboarding.index('})(prev);', start) + len('})(prev);')]
        node(self, r'''const run = (isReduced, page) => { let frames = 0, timers = 0, painted = 0;
const canvas2d = { setTransform() {}, clearRect() {} }, $ = () => ({ getContext: () => canvas2d }), E = { r: () => ({ mode: 'm', speed: 1, opts: {} }), M: { m: () => ({}) }, p: () => painted++ };
globalThis.requestAnimationFrame = () => frames++; globalThis.setTimeout = () => timers++;
let reduced = { matches: isReduced }, cur = page, orbWake = null;
''' + loop + r'''
return {frames, timers, painted, waiting: typeof orbWake === 'function'}; };
const active = run(false, 'welcome'), still = run(true, 'welcome'), away = run(false, 'text');
if (active.painted !== 1 || active.frames !== 1 || active.timers || active.waiting) process.exit(1);
if (still.painted !== 1 || still.frames || still.timers || !still.waiting) process.exit(2);
if (away.frames || away.timers || !away.waiting) process.exit(3);
''')

    def test_settings_and_setup_text_colours_are_readable(self):
        light = re.search(r':root \{(.*?)\}', self.settings, re.S).group(1)
        dark = re.search(r'prefers-color-scheme: dark\) \{ :root \{(.*?)\}', self.settings, re.S).group(1)
        var = lambda block, name: re.search(r'--' + name + r': (#[0-9a-f]{6})', block).group(1)
        for name in ('fg3', 'warn', 'danger'):
            self.assertGreaterEqual(contrast(var(light, name), '#f5f5f7' if name == 'fg3' else '#ffffff'), 4.5, name)
        for name in ('fg3', 'warn'):
            self.assertGreaterEqual(contrast(var(dark, name), '#2a2a2c'), 4.5, 'dark ' + name)
        self.assertGreaterEqual(contrast(var(light, 'ok-text'), tint('#34c759', .13)), 4.5)
        self.assertGreaterEqual(contrast(var(light, 'warn'), tint('#ff9f0a', .14)), 4.5)
        self.assertNotRegex(self.settings, r'\{[^}]*\bcolor: #ff(9f0a|453a)')   # text uses the tokens; fills may keep the bright colours
        setup_light = re.search(r':root \{(.*?)\}', self.onboarding, re.S).group(1)
        setup_dark = re.search(r'prefers-color-scheme: dark\) \{ :root \{(.*?)\}', self.onboarding, re.S).group(1)
        self.assertGreaterEqual(contrast(var(setup_light, 'fg3'), '#fbfbfd'), 4.5)
        self.assertGreaterEqual(contrast(var(setup_dark, 'fg3'), '#2a2a2c'), 4.5)

    def test_settings_exposes_the_current_page_and_app_list_choice(self):
        self.assertIn('class="on" aria-current="page"', self.settings)
        self.assertIn("b.toggleAttribute('aria-current', b === nav)", self.settings)
        self.assertIn('id="appview" role="group" aria-label="App list"', self.settings)
        self.assertIn("b.setAttribute('aria-pressed', on)", self.settings)

    def test_onboarding_recorder_names_a_lone_modifier(self):
        self.assertIn('a modifier on its own', self.onboarding)
        self.assertNotIn('Use modifiers with a key', self.onboarding)

    def test_turned_off_tips_come_back_from_the_menu_bar(self):
        menu = self.swift[self.swift.index('final class MenuBar'):self.swift.index('// Settings window (ui/settings.html)')]
        self.assertIn('if !Prefs.bool("tips") { add(m, "Show Tips Again", #selector(tipsOn), "") }', menu)
        self.assertIn('@objc func tipsOn() { settings.apply("tips", true); settings.push() }', menu)

    def test_removed_sonnet_offer_leaves_no_card_branch(self):
        self.assertNotIn('Sonnet', self.box[self.box.index('    respond(text)'):self.box.index('    improve()')])
        self.assertNotIn('"escalate"', self.swift[self.swift.index('func userContentController'):self.swift.index('    func show()')])
        self.assertNotIn("j.get('off'", (ROOT / 'delphi.py').read_text())

    def test_a_new_ask_drops_a_paused_card_left_by_resuming_elsewhere(self):
        listen = self.box[self.box.index('    listen(mode)'):self.box.index('    level(v)')]
        self.assertIn("querySelectorAll('.rewrite, .paused, .worker').forEach(e => e.remove())", listen)

    def test_rewrite_buttons_answer_hover_and_press_like_card_buttons(self):
        self.assertIn('.rewrite button:not(:disabled):is(:hover,.hot) { transform: scale(1.03); }', self.box)
        self.assertIn('.rewrite button:not(:disabled):active { transform: scale(.96); }', self.box)

    def test_box_status_markers_share_compact_centered_rows(self):
        self.assertRegex(self.box, r'\.a\.stopped \{[^}]*align-items: center;[^}]*line-height: 16px;')
        self.assertRegex(self.box, r'\.a\.stopped i \{ flex: none; width: 7px; height: 7px;')
        self.assertRegex(self.box, r'\.step \{[^}]*line-height: 16px;[^}]*align-items: center;')

    def test_rewrite_actions_sit_above_the_timer_and_answers_have_no_try_again(self):
        self.assertNotIn('redo', self.box)   # an answer offers no Try again; the rewrite bar keeps its own
        rewrite = self.box[self.box.index('    rewrite([draft, mode, editable])'):self.box.index('    mini(m)')]
        node(self, r'''let placed = '';
const clockRow = { before: () => { placed = 'above the timer'; } }, d = { querySelector: s => s === '.elapsed' ? clockRow : null, append: () => { placed = 'last'; } };
const turn = () => d, part = () => null, post = () => {}, fit = () => {}, $ = () => ({ querySelectorAll: () => [] });
const document = { createElement: () => ({ dataset: {}, append() {}, setAttribute() {} }) };
const ui = {''' + rewrite + r'''};
ui.rewrite(['Hi Dana,', 'draft', true]); if (placed !== 'above the timer') { console.error(placed); process.exit(1); }
''')

    def test_resize_releases_fixed_height_and_uses_live_box_spacing(self):
        methods = self.box[self.box.index('    hold(h)'):self.box.index('    respond(text)')]
        self.assertIn('const chrome = c.offsetHeight - t.offsetHeight', methods)
        self.assertNotIn('h - 26', methods)
        node(self, r'''const classes = new Set(), card = {offsetHeight: 246, style: {minHeight: '', getPropertyValue: () => '700'}, classList: {add: x => classes.add(x), remove: x => classes.delete(x)}};
const thread = {offsetHeight: 120, style: {}}, nodes = {card, thread}, $ = id => nodes[id], sent = [], post = x => sent.push(x);
let fitted = 0; const fit = () => fitted++;
const ui = {''' + methods + r'''};
ui.hold(500);
if (!classes.has('held') || card.style.minHeight !== '500px' || thread.style.maxHeight !== '374px' || sent[0].boxH !== 374) process.exit(1);
ui.resizeDone();
if (classes.has('held') || card.style.minHeight || fitted !== 2) process.exit(2);
''')
        mouse_up = self.swift[self.swift.index('            default:', self.swift.index('var sizing:')):self.swift.index('            return nil', self.swift.index('            default:', self.swift.index('var sizing:')))]
        self.assertIn('js("resizeDone")', mouse_up)

    def test_settings_disabled_segment_looks_off(self):
        self.assertIn("[data-k=dictateMode] [data-v=cleanup]').disabled = other", self.settings)
        self.assertIn('.seg button:disabled { opacity: .4; pointer-events: none; }', self.settings)
        self.assertIn('.seg button:disabled { opacity: .4; pointer-events: none; }', self.onboarding)

    def test_small_leftovers(self):
        self.assertNotIn('js("shortcut"', self.swift)
        self.assertNotIn('shortcut() {}', self.box)
        self.assertIn('d.hidden = skip(pages[i])', self.onboarding)   # Devin/Pi/server: no dots for skipped pages
        self.assertNotIn('These need your click', self.onboarding)
        self.assertNotIn('Use Verbatim instead', self.onboarding)
        self.assertIn('id="appsback" onclick="st.tab(\'account\')"', self.settings)
        self.assertEqual(self.settings.count('[hidden] {'), 1)
        self.assertNotIn('.ok:hover code', self.box)


if __name__ == '__main__':
    unittest.main()
