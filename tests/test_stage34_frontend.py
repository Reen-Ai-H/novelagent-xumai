"""Execute the shipped browser functions in Node; no model, data store or browser fixtures."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class Stage34FrontendBehaviorTest(unittest.TestCase):
    app_source_path = ROOT / "frontend" / "app.js"

    def run_js(self, checks: str) -> subprocess.CompletedProcess[str]:
        harness = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
const location = new URL('http://127.0.0.1/independent/p');
let fetchHandler = async url => { throw new Error(`Unexpected fetch ${url}`); };
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', textContent: '', innerHTML: '', dataset: {}, open: false,
    classList: {add() {}, remove() {}, toggle() {}},
    setAttribute(name, value) { this[name] = value; }, removeAttribute(name) { delete this[name]; },
    querySelector(selector) { return node(`${id} ${selector}`); }, querySelectorAll() { return []; },
    focus() { document.activeElement = this; }, select() {}, getClientRects() { return [{}]; },
    showModal() { this.open = true; }, close() { this.open = false; }, addEventListener() {},
  });
  return nodes.get(id);
};
const document = {
  querySelector: node, querySelectorAll: () => [], getElementById: id => node(`#${id}`),
  body: node('body'), activeElement: null,
};
const window = {location, setTimeout, clearTimeout, scrollTo() {}, matchMedia: () => ({matches: true}),
  history: {replaceState(a,b,path) { location.href = new URL(path, location).href; },
    pushState(a,b,path) { location.href = new URL(path, location).href; }},
};
const sandbox = {document, window, location, URL, URLSearchParams, setTimeout, clearTimeout,
  fetch: (...args) => fetchHandler(...args), CSS: {escape: String}};
let source = fs.readFileSync(APP_PATH, 'utf8');
// Git's Windows checkout may use CRLF. Only normalize line terminators in
// this test copy; preserve the exact hook and every behavior assertion below.
source = source.replace(/\r\n/g, '\n');
assert.ok(source.includes('  start();\n})();'));
source = source.replace('  start();\n})();', `  globalThis.api = {
  state, elements, normalizeResult, normalizeDeconstructionResponse, hasDeconstructionResults,
  isModelAnalysisReport, renderDeconstructionEvidence, deconstructionEvidenceMatchesSource,
  deconstructionEvidenceIdentityMatches, deconstructionApi, chooseActiveChapter,
  updateChapterUrl, flushPendingSave, navigate, previewVersion, openRestoreVersionConfirm
};\n})();`);
vm.runInNewContext(source, sandbox);
const api = sandbox.api;
const reply = data => ({ok: true, status: 200, json: async () => data});
const evidence = {evidence_id: 'Q1', document_id: 'doc', source_version_id: 'v', source_revision: 1,
  source_hash: 'a'.repeat(64), chapter_id: 'c1', chapter_number: 1, start_offset: 0,
  end_offset: 2, excerpt: '正文', offset_unit: 'utf16_code_unit'};
const modelPayload = () => ({project_id: 'p', title: '合同样本', effective_status: 'completed',
  run_status: 'completed', source_match: true, progress: {percent: 100}, actions: {},
  source: {version_id: 'v', revision: 7, hash: 'b'.repeat(64), match: true},
  focus_document_id: 'doc', active_run: {document_id: 'doc', analysis_contract_version: 'model.1',
    run_status: 'completed', source_version_id: 'v', source_revision: 1, source_hash: 'a'.repeat(64)},
  result: {status: 'completed', document_id: 'doc', analysis_contract_version: 'model.1',
    source_version_id: 'v', source_revision: 1, source_hash: 'a'.repeat(64),
    scope_start: 1, scope_end: 2, scope_hash: 'c'.repeat(64), evidence: [evidence],
    report: {schema_version: '1', chapter_numbers: [1,2], characters: [], events: [], evidence: []}},
});
'''.replace("APP_PATH", json.dumps(str(self.app_source_path)))
        result = subprocess.run(
            ["node", "-"], input=harness + "\n(async () => {\n" + checks +
            "\n})().catch(error => { console.error(error); process.exitCode = 1; });\n",
            text=True, encoding="utf-8", capture_output=True, cwd=ROOT, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_lf_and_crlf_real_app_execute_identical_behavior_assertions(self):
        source = self.app_source_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        regression_name = "test_lf_and_crlf_real_app_execute_identical_behavior_assertions"
        behavior_names = [name for name in unittest.defaultTestLoader.getTestCaseNames(type(self))
                          if name != regression_name]
        self.assertTrue(behavior_names)
        with tempfile.TemporaryDirectory(prefix="xumai-frontend-line-endings-") as directory:
            for ending in ("LF", "CRLF"):
                with self.subTest(line_ending=ending):
                    raw_source = source if ending == "LF" else source.replace("\n", "\r\n")
                    fixture = Path(directory) / f"app-{ending}.js"
                    # newline="" prevents Windows from translating CRLF into
                    # CRCRLF. Node reads these real fixture bytes unchanged.
                    fixture.write_text(raw_source, encoding="utf-8", newline="")
                    self.assertEqual(fixture.read_bytes(), raw_source.encode("utf-8"))
                    self.assertIn(b"  start();\n})();" if ending == "LF" else b"  start();\r\n})();",
                                  fixture.read_bytes())
                    cases = []
                    for name in behavior_names:
                        case = type(self)(name)
                        case.app_source_path = fixture
                        cases.append(case)
                    result = unittest.TestResult()
                    unittest.TestSuite(cases).run(result)
                    self.assertEqual(result.testsRun, len(behavior_names))
                    self.assertEqual(result.skipped, [])
                    self.assertEqual(result.errors, [], str(result.errors))
                    self.assertEqual(result.failures, [], str(result.failures))

    def test_utf8_pipes_ignore_cp1252_default(self):
        # Exercise the same Chinese stdin harness used by every behavior test.
        # If explicit pipe encoding regresses, cp1252 cannot encode this input.
        with patch("subprocess._text_encoding", return_value="cp1252"):
            result = self.run_js("console.log('正文输入与输出🧭'); console.error('错误诊断中文🧭');")
        self.assertEqual(result.stdout, "正文输入与输出🧭\n")
        self.assertEqual(result.stderr, "错误诊断中文🧭\n")

    def test_model_contract_accepts_both_versions_and_scoped_revision(self):
        self.run_js(r'''
const raw = modelPayload();
const data = api.normalizeDeconstructionResponse(raw);
assert.equal(api.hasDeconstructionResults(data), true);
assert.equal(data.result.depthReport, null);
assert.equal(data.source.revision, 7);
assert.equal(data.result.sourceRevision, 1);
raw.result.report.report_version = '1.0';
assert.equal(api.hasDeconstructionResults(api.normalizeDeconstructionResponse(raw)), true);
raw.result.report.report_version = '9.0';
assert.throws(() => api.normalizeDeconstructionResponse(raw));
''')

    def test_result_rejects_inconsistent_source_run_scope_and_depth(self):
        self.run_js(r'''
for (const mutate of [
  p => {p.source_match = false;}, p => {p.result.source_version_id = 'other';},
  p => {p.active_run.document_id = 'other';}, p => {p.active_run.source_hash = 'wrong';},
  p => {p.focus_document_id = 'other';}, p => {p.result.scope_hash = '';},
  p => {p.result.scope_start = 4;}, p => {p.result.analysis_contract_version = '2.0';},
]) { const p = modelPayload(); mutate(p); assert.throws(() => api.normalizeDeconstructionResponse(p)); }
const legacy = modelPayload(); legacy.result.analysis_contract_version = '1.0'; delete legacy.result.report;
assert.throws(() => api.normalizeDeconstructionResponse(legacy), /来源版本不一致/);
''')

    def test_evidence_stays_bound_to_report_and_range(self):
        self.run_js(r'''
const data = api.normalizeDeconstructionResponse(modelPayload());
const ref = data.result.evidenceRefs[0];
assert.equal(api.deconstructionEvidenceMatchesSource(data, ref, data.result), true);
for (const wrong of [{documentId: 'other'}, {chapterNumber: 3}, {sourceRevision: 7},
  {sourceHash: data.source.contentHash}, {sourceVersionId: 'old'}]) {
  assert.equal(api.deconstructionEvidenceMatchesSource(data, {...ref, ...wrong}, data.result), false);
}
assert.equal(api.deconstructionEvidenceMatchesSource({...data, sourceMatch: false}, ref, data.result), false);
assert.equal(api.deconstructionEvidenceIdentityMatches(ref, {...ref, charEnd: 3}), false);
''')

    def test_evidence_request_disambiguates_document_and_preserves_legacy_url(self):
        self.run_js(r'''
const urls = []; fetchHandler = async url => {urls.push(url); return reply({});};
await api.deconstructionApi.readEvidence('p', 'Q1', '卷 /1');
await api.deconstructionApi.readEvidence('p', 'Q1');
assert.equal(urls[0], '/api/independent/projects/p/deconstruction/evidence/Q1?document_id=' + encodeURIComponent('卷 /1'));
assert.equal(urls[1], '/api/independent/projects/p/deconstruction/evidence/Q1');
''')

    def test_all_evidence_remains_reachable_and_unbound_quotes_are_inert(self):
        self.run_js(r'''
const ref = api.normalizeDeconstructionResponse(modelPayload()).result.evidenceRefs[0];
const refs = Array.from({length: 9}, (_, n) => ({...ref, id: `Q${n+1}`}));
const html = api.renderDeconstructionEvidence(refs);
assert.equal((html.match(/data-action="open-deconstruction-evidence"/g) || []).length, 9);
assert.ok(html.includes('data-evidence-id="Q9"'));
const unbound = api.renderDeconstructionEvidence([{...ref, documentId: '', excerpt: '<img onerror=x>'}]);
assert.ok(!unbound.includes('<button'));
assert.ok(unbound.includes('&lt;img onerror=x&gt;'));
''')

    def test_chapter_query_and_fallback_select_real_chapters_only(self):
        self.run_js(r'''
const chapters = [{chapter_id:'c1',chapter_number:1,status:'ready'},
 {chapter_id:'c3',chapter_number:3,status:'draft'}, {chapter_id:'c2',chapter_number:2,status:'draft'}];
assert.equal(api.chooseActiveChapter({chapters}).chapter_id, 'c3');
location.search = '?chapter=c1'; assert.equal(api.chooseActiveChapter({chapters}).chapter_id, 'c1');
location.search = '?chapter=missing'; assert.equal(api.chooseActiveChapter({chapters}).chapter_id, 'c3');
chapters.forEach(c => c.status = 'ready'); assert.equal(api.chooseActiveChapter({chapters}).chapter_id, 'c3');
location.search = '?view=deconstruction&section=plot'; api.updateChapterUrl('c2');
assert.equal(location.searchParams.get('chapter'), 'c2'); assert.equal(location.searchParams.get('section'), 'plot');
''')

    def test_save_during_typing_flushes_latest_buffer_using_updated_revision(self):
        self.run_js(r'''
Object.assign(api.state, {editorProjectId:'p', activeChapterId:'c1', editorRevision:4,
 editorDirty:true, editorBuffer:'先写', editorTitleBuffer:'标题', editorChangeToken:1});
let finishFirst; const gate = new Promise(resolve => {finishFirst = resolve;}); const writes = [];
fetchHandler = async (url, options) => {
 const body = JSON.parse(options.body); writes.push(body);
 if (writes.length === 1) await gate;
 return reply({chapter:{server_revision:body.expected_revision + 1},workspace:{archive:{},active_version:null}});
};
const flush = api.flushPendingSave();
api.state.editorBuffer = '请求期间继续写'; api.state.editorChangeToken += 1;
finishFirst(); assert.equal(await flush, true);
assert.deepEqual(writes.map(w => [w.content,w.expected_revision]), [['先写',4],['请求期间继续写',5]]);
assert.equal(api.state.editorBuffer, '请求期间继续写'); assert.equal(api.state.editorRevision,6);
assert.equal(api.state.editorDirty,false); assert.equal(api.elements.editorSaveState.textContent,'已保存');
''')

    def test_failed_flush_preserves_buffer_and_blocks_navigation(self):
        self.run_js(r'''
Object.assign(api.state,{screen:'independent',editorProjectId:'p',activeChapterId:'c1',
 editorDirty:true,editorBuffer:'尚未保存的正文',editorTitleBuffer:'保留标题',editorRevision:4});
fetchHandler = async () => ({ok:false,status:503,json:async()=>({detail:{code:'unavailable',message:'保存失败'}})});
assert.equal(await api.flushPendingSave(),false);
assert.equal(await api.navigate('/library'),false);
assert.equal(api.state.editorBuffer,'尚未保存的正文'); assert.equal(api.state.editorTitleBuffer,'保留标题');
assert.equal(api.state.editorDirty,true); assert.equal(api.state.editorSaveFailed,true);
assert.equal(location.pathname,'/independent/p'); assert.equal(api.elements.editorSaveState.textContent,'保存失败');
''')

    def test_full_version_preview_ignores_late_response_and_does_not_restore(self):
        self.run_js(r'''
api.state.editorProjectId='p'; api.elements.versionHistoryDialog.open=true;
const pending = new Map(); const methods=[];
fetchHandler = (url, options) => { methods.push(options.method || 'GET'); return new Promise(resolve => pending.set(url,resolve)); };
const old = api.previewVersion('old'); const selected = api.previewVersion('selected');
const version = id => ({version:{version_id:id,label:id,status:'historical',chapters:[
 {chapter_number:1,title:'第一章',content:'前'.repeat(500)+'末尾<安全>',status:'ready'},
 {chapter_number:2,title:'第二章',content:'第二章全文',status:'ready'}]}});
pending.get('/api/independent/projects/p/versions/selected/preview')(reply(version('selected'))); await selected;
pending.get('/api/independent/projects/p/versions/old/preview')(reply(version('old'))); await old;
assert.equal(api.state.versionPreviewId,'selected');
assert.equal((api.elements.versionPreviewContent.innerHTML.match(/class="version-preview-chapter"/g)||[]).length,2);
assert.ok(api.elements.versionPreviewContent.innerHTML.includes('末尾&lt;安全&gt;'));
api.openRestoreVersionConfirm('old'); assert.equal(api.elements.restoreVersionDialog.open,false);
api.openRestoreVersionConfirm('selected'); assert.equal(api.elements.restoreVersionDialog.open,true);
assert.deepEqual(methods,['GET','GET']);
''')


if __name__ == "__main__":
    unittest.main()
