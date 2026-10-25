"""ui/ui.html in a real WKWebView that is never put in a window: a streamed answer, math, the pointer tint and the Learned pill."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''import Cocoa
import WebKit
// Loads the box page; on its "ready" post runs argv[2] as an async function body, prints {"result", "posts"}.
final class Harness: NSObject, WKScriptMessageHandler {
    var posts: [Any] = [], web: WKWebView!
    func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
        if m.name == "errors" { posts.append(["error": m.body]); return }
        posts.append(m.body)
        guard (m.body as? [String: Any])?["ready"] != nil else { return }
        web.callAsyncJavaScript(CommandLine.arguments[2], arguments: [:], in: nil, in: .page) { r in
            switch r {
            case .success(let x):
                let out = try! JSONSerialization.data(withJSONObject: ["result": x ?? NSNull(), "posts": self.posts])
                print(String(data: out, encoding: .utf8)!); exit(0)
            case .failure(let e): print(e); exit(1)
            }
        }
    }
}
NSApplication.shared.setActivationPolicy(.prohibited)   // no Dock icon, no menu, no window
let h = Harness(), cfg = WKWebViewConfiguration()
cfg.userContentController.add(h, name: "c"); cfg.userContentController.add(h, name: "h"); cfg.userContentController.add(h, name: "errors")
cfg.userContentController.addUserScript(WKUserScript(source: "addEventListener('error',e=>webkit.messageHandlers.errors.postMessage(String(e.message)));addEventListener('unhandledrejection',e=>webkit.messageHandlers.errors.postMessage(String(e.reason)))", injectionTime: .atDocumentStart, forMainFrameOnly: true))
h.web = WKWebView(frame: NSRect(x: 0, y: 0, width: 260, height: 400), configuration: cfg)
h.web.loadHTMLString(try! String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8), baseURL: nil)
DispatchQueue.main.asyncAfter(deadline: .now() + 50) { print("timeout"); exit(1) }
NSApplication.shared.run()
'''
SCRIPT = r'''
const a = () => document.querySelector('#thread .turn:last-child .a'), out = {};
ui.listen(); ui.words('what is it'); ui.think();
ui.line('… See [1] and a[0]\u2028- [ ] a task and'); out.brackets = [...a().querySelectorAll('p, li')].map(e => e.textContent.trim());
ui.line('… '); ui.line('… It [the link](https://x.co'); out.open = a().textContent.trim();
ui.line('… It [the link](https://x.co) and'); out.link = [a().querySelector('a')?.textContent, a().textContent.trim()];
ui.line('✓ It [the link](https://x.co) and more.'); out.final = [a().textContent, a().classList.contains('streaming')];
ui.listen(); ui.words('area'); ui.think(); out.math = [];
for (const s of ['the area is $', 'the area is $\\pi r', 'the area is $\\pi r^2', 'the area is $\\pi r^2$ cm', 'the area is $\\pi r^2$ cm and costs $5 today']) { ui.line('… ' + s); out.math.push(a().textContent.trim()); }
out.math.push(!!a().querySelector('math'));
out.off = [ui.pointer([]), document.querySelectorAll('.hot').length];
out.x = [ui.pointer([1, 1], true), document.getElementById('x').classList.contains('hot')]; ui.pointer([]);
ui.dictate(true); ui.learned('Delphi'); const dn = document.getElementById('dn');
out.learned = [dn.textContent, getComputedStyle(dn).display, dn.className];
return out;
'''


@unittest.skipUnless(sys.platform == 'darwin', 'macOS WebKit page check')
class BoxPageTests(unittest.TestCase):
    def test_box_on_real_webkit(self):
        harness = HARNESS
        with tempfile.TemporaryDirectory() as tmp:
            page, src, binary = Path(tmp) / 'ui.html', Path(tmp) / 'page.swift', Path(tmp) / 'page'
            page.write_text((ROOT / 'ui/ui.html').read_text().replace('/*ORBS*/', (ROOT / 'ui/orbs.js').read_text()))
            src.write_text(harness)
            built = subprocess.run(['swiftc', str(src), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary), str(page), SCRIPT], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        got = json.loads(run.stdout.strip().splitlines()[-1])
        self.assertEqual([p for p in got['posts'] if isinstance(p, dict) and 'error' in p], [])
        out = got['result']
        self.assertEqual(out['brackets'], ['See [1] and a[0]', '[ ] a task'])   # a bracket that is no link shows at once
        self.assertEqual(out['open'], 'It')   # a link still arriving waits
        self.assertEqual(out['link'], ['the link', 'It the link'])
        self.assertEqual(out['final'], ['It the link and more.', False])
        self.assertEqual(out['off'], [False, 0])   # off the box: arrow, no tint
        self.assertEqual(out['x'], [True, True])   # native's × corner lights the ×
        self.assertEqual(out['math'][:3], ['the area is', 'the area is', 'the area is'])   # math still arriving waits, never a raw $
        self.assertNotIn('$', out['math'][3]); self.assertTrue(out['math'][3].startswith('the area is π'))
        self.assertTrue(out['math'][4].endswith('and costs $5'))   # a price shows at once
        self.assertTrue(out['math'][5])
        self.assertEqual(out['learned'], ['Learned “Delphi” Undo', 'flex', 'dn tick'])


if __name__ == '__main__':
    unittest.main()
