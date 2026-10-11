"""Execute the shipped model-report viewer; every bound/unbound quote stays visible."""
import json
from pathlib import Path
import subprocess
import unittest


class FrontendReportTest(unittest.TestCase):
    def test_mixed_bound_unbound_references_are_all_rendered_and_escaped(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "frontend" / "deconstruction-report.js"
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const view = {innerHTML: ''};
const questions = {};
const contradictions = {};
const root = {querySelector(selector) {
  return selector === '.analysis-view' ? view : selector === '.analysis-questions' ? questions : contradictions;
}, addEventListener() {}};
const sandbox = {window: {}, document: {}};
vm.runInNewContext(fs.readFileSync(SOURCE, 'utf8'), sandbox);
const ids = Array.from({length: 10}, (_, index) => `Q${index + 1}`);
const claim = {text: '作者正文', status: 'fact', evidence_ids: ids};
const report = {characters: [{id: 'C1', name: '林舟', identity: claim, portrait: claim,
  motivation: claim, change: claim}], events: [], relations: [], story_order: [],
  evidence: [{id: 'Q10', chapter_number: 1, quote: '<未绑定引文>'}]};
const refs = ids.slice(0, 9).map(id => ({evidence_id: id}));
sandbox.window.XumaiAnalysis.mount({querySelector() {return root;}}, report, refs,
  items => items.map(item => `<button data-id="${item.evidence_id}">核对</button>`).join(''),
  {character: 'C1'});
for (const id of ids.slice(0, 9)) assert.ok(view.innerHTML.includes(`data-id="${id}"`), id);
assert.ok(view.innerHTML.includes('&lt;未绑定引文&gt;'));
assert.ok(view.innerHTML.includes('这条旧结果没有绑定当前正文回链'));
assert.ok(!view.innerHTML.includes('<未绑定引文>'));
assert.equal(typeof sandbox.window.XumaiAnalysis.closeModal, 'function');
'''.replace("SOURCE", json.dumps(str(source)))
        result = subprocess.run(["node", "-"], input=script, text=True,
                                capture_output=True, cwd=root, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
