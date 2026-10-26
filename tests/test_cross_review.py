"""Offline cross-review regressions; Swift snippets use no windows or real apps."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def swift_check(test, code):
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / 'check.swift'
        source.write_text('import Foundation\n' + code)
        result = subprocess.run(['swift', str(source)], capture_output=True, text=True,
                                env={**os.environ, 'DELPHI_DIR': folder}, timeout=60)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CrossReviewTests(unittest.TestCase):
    def test_speculative_launch_failure_keeps_listening_until_confirmed(self):
        source = (ROOT / 'Delphi.swift').read_text()
        failure = source[source.index('        guard let w = warm ?? spawn()'):source.index('        warm = nil; proc = w.p')]
        swift_check(self, 'final class Fixture { var warm:Int?, busy=true, pinned=false, ahead="draft", calls=0\n'
                    + 'func spawn()->Int? { nil }; func js(_ s:String) { calls+=1 }; func show() {}; func telemetry(_ a:[String]) {}\n'
                    + 'func run(_ speculative:Bool) { let point:[String:Any]?=nil\n' + failure + ' _=w\n}\n}\n'
                    + 'let f=Fixture(); f.run(true); precondition(f.ahead.isEmpty && !f.busy && !f.pinned && f.calls==0)\n'
                    + 'f.run(false); precondition(f.pinned && f.calls==1)\n')

    def test_failed_resume_does_not_apply_success_effects(self):
        source = (ROOT / 'Delphi.swift').read_text()
        resume = source[source.index('            if b["resume"] != nil'):source.index('            if b["replace"]')]
        swift_check(self, 'enum Prefs { static func bool(_ k:String)->Bool { true } }\n'
                    + 'final class Settings { func apply(_ k:String,_ v:Bool) {}; func push() {} }\n'
                    + 'enum Delphi { static let settings=Settings() }\n'
                    + 'func js(_ c:String,_ v:Bool) { fatalError("resume success shown") }; func hide(after:Double) { fatalError() }\n'
                    + 'let b:[String:Bool]=["resume":true]\n' + resume)

    def test_out_of_order_model_responses_are_ignored(self):
        source = (ROOT / 'ui/settings.html').read_text()
        method = source[source.index('    models(result)'):source.index('    local(list)')].rstrip().rstrip(',')
        esc = source[source.index('  const esc = '):].split('\n', 1)[0]
        script = """const assert=require('assert');
""" + esc + """
const P={apiBase:'b',apiKey:'key',apiModel:''}, nodes={srvnote:{},apimodels:{},apiModel:{}};
const $=id=>nodes[id], document={activeElement:null}, set=(k,v)=>P[k]=v;
const st={""" + method + """};
st.models({base:'b',key:'key',list:['b-model']});
const before=JSON.stringify(nodes);
st.models({base:'a',key:'key',list:['a-model']});
st.models({base:'b',key:'old',list:['old-model']});
assert.equal(P.apiModel,'b-model'); assert.equal(JSON.stringify(nodes),before);
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_import_actions_only_offer_automation_for_actual_denials(self):
        source = (ROOT / 'ui/settings.html').read_text()
        method = source[source.index('    profileImport(result)'):source.index('    motion(on)')].rstrip().rstrip(',')
        script = """const assert=require('assert');
const nodes={profileImport:{},profileStatus:{textContent:'',children:[],append(v){this.children.push(v)}}};
const $=id=>nodes[id], document={createElement:()=>({})}, post=()=>{};
const st={""" + method + """};
st.profileImport({errors:['contacts','mail'],errorReasons:{contacts:'read',mail:'automation'},counts:{}});
assert.equal(nodes.profileStatus.children[1].textContent,'Allow Mail in Automation');
assert.ok(nodes.profileStatus.children[0].includes('Try importing again'));
nodes.profileStatus.children=[];
st.profileImport({errors:['mail'],errorReasons:{mail:'read'},counts:{contacts:3}});
assert.ok(nodes.profileStatus.children.every(c=>typeof c==='string'));
"""
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
