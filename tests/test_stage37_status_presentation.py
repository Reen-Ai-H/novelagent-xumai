"""State presentation only. Synthetic inputs, no app server, models or author data.

Optional CUA preview: python tests/test_stage37_status_presentation.py --serve 8068
Serves only synthetic markup and the explicit frontend asset directory on loopback.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {
    innerHTML:'', textContent:'', dataset:{}, classList:{add(){},remove(){},toggle(){}},
    setAttribute(name,value){this[name]=value;}, querySelector(){return null;},
    querySelectorAll(){return [];}, insertAdjacentHTML(position,html){this.innerHTML+=html;},
  });
  return nodes.get(id);
};
const location = new URL('http://127.0.0.1/independent/synthetic?view=deconstruction');
const document = {querySelector:node,querySelectorAll:()=>[],getElementById:id=>node('#'+id),body:node('body')};
const window = {location,clearTimeout(){},setTimeout(){return 1;},matchMedia:()=>({matches:true})};
const sandbox = {document,window,location,URL,URLSearchParams,
  fetch(){throw Error('Network forbidden in presentation test');}};
let source = fs.readFileSync('frontend/app.js','utf8').replace(/\r\n/g,'\n');
const hook = '  start();\n})();';
assert.ok(source.includes(hook));
source = source.replace(hook, `  globalThis.api = {renderDeconstructionStatus,
  renderDeconstructionDiagnostics,renderDeconstructionPage,normalizeDeconstructionResponse,
  renderAnalysisSource,renderDeconstructionLoading,elements};\n})();`);
vm.runInNewContext(source,sandbox);
const api = sandbox.api;
const payload = status => ({project_id:'synthetic',title:'合成状态检查',effective_status:status,
  run_status:['empty','rebuild_required'].includes(status)?'none':status==='stale'?'completed':status,
  source_match:status==='completed',progress:{percent:null,current_stage:status},
  source:{version_id:'synthetic-version-abcdefghijklmnopqrstuvwxyz',revision:7,hash:'abc123'.repeat(16),
    chapter_count:6,total_word_count:21224,match:status==='completed'},
  error:status==='failed_retryable'?{code:'provider_bad_json',message:'分析结果格式不完整，请重试。'}:null,
  actions:{retry:status==='failed_retryable',rebuild:status==='stale'},history:[],volumes:[]});
const data = status => api.normalizeDeconstructionResponse(payload(status));
const visibleText = html => html.replace(/<[^>]*>/g,'');
'''


def run_js(checks):
    result = subprocess.run(["node", "-"], input=HARNESS + checks, cwd=ROOT,
                            text=True, encoding="utf-8", capture_output=True, timeout=15)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


class StatusPresentationTest(unittest.TestCase):
    def test_all_states_keep_chinese_headings_reasons_and_source_size(self):
        run_js(r'''
const headings = {empty:'还没有足够正文',queued:'已排队',running:'正在把正文',completed:'已经可以回看',
  failed_retryable:'没有完成',stale:'正文已更新',rebuild_required:'需要先确认'};
for (const [status,heading] of Object.entries(headings)) {
  const d=data(status),html=api.renderDeconstructionStatus(d),text=visibleText(html);
  assert.ok(text.includes(heading),status);
  assert.ok(text.includes(d.message),status);
  assert.match(text,/6 章.*21,224 字/);
  assert.doesNotMatch(text,/SOURCE|REV|HASH|none|queued|running|completed|failed_retryable|stale|rebuild_required/);
  assert.ok(!text.includes(d.source.versionId));assert.ok(!text.includes(d.source.contentHash));
}
api.renderDeconstructionLoading();
assert.equal(api.elements.deconstructionStatusPill.textContent,'读取中');
assert.doesNotMatch(visibleText(api.elements.deconstructionPageContent.innerHTML),/loading/);
''')

    def test_retry_rebuild_and_confirmation_capabilities_are_preserved(self):
        run_js(r'''
for (const status of ['empty','queued','running','completed','failed_retryable','stale','rebuild_required']) {
  for(const retry of [true,false]) for(const rebuild of [true,false]) {
    const d=data(status);d.actions={retry,rebuild};const html=api.renderDeconstructionStatus(d);
    assert.equal(html.includes('data-action="deconstruction-retry"'),status==='failed_retryable'&&retry);
    assert.equal(html.includes('data-action="deconstruction-rebuild"'),['stale','rebuild_required'].includes(status)&&rebuild);
    assert.equal(html.includes('data-action="deconstruction-open-editor"'),status==='empty'||status==='rebuild_required'&&!rebuild);
    if(status==='rebuild_required'&&rebuild) assert.match(html,/旧结果保留为历史只读/);
  }
}
''')

    def test_unknown_progress_and_empty_counts_never_become_zero(self):
        run_js(r'''
for (const status of ['queued','running']) for(const percent of [null,undefined,'']) {
  const d=data(status);d.progress.percent=percent;d.source.chapterCount=null;d.source.wordCount=null;
  const html=api.renderDeconstructionStatus(d);
  assert.match(html,/role="progressbar"/);assert.match(html,/进度待更新/);
  assert.doesNotMatch(html,/aria-valuenow|width: 0|已完成 0%|0 章|0 字/);
  assert.match(html,/来源规模待识别/);
}
for (const [percent,expected] of [[0,0],[42.4,42],[-1,0],[140,100]]) {
  const d=data('running');d.progress.percent=percent;
  const html=api.renderDeconstructionStatus(d);
  assert.ok(html.includes(`aria-valuenow="${expected}"`));assert.ok(html.includes(`已完成 ${expected}%`));
}
for(const stage of ['loading','running','queued','completed','failed_retryable','unknown_stage','处理中 running']) {
  const d=data('running');d.progress.currentStage=stage;
  assert.ok(!visibleText(api.renderDeconstructionStatus(d)).includes(stage));
  assert.ok(api.renderDeconstructionDiagnostics(d).includes(stage));
}
const d=data('running');d.progress.currentStage='正在核对来源';
assert.match(api.renderDeconstructionStatus(d),/正在核对来源/);
''')

    def test_technical_details_closed_complete_escaped_and_not_truncated(self):
        run_js(r'''
const d=data('failed_retryable'),html=api.renderDeconstructionDiagnostics(d);
assert.match(html,/<details class="analysis-details deconstruction-technical-details"><summary>技术详情<\/summary>/);
assert.doesNotMatch(html,/<details[^>]*\bopen\b/);
for(const value of [d.runStatus,d.source.versionId,d.source.contentHash,'provider_bad_json']) assert.ok(html.includes(value));
for(const field of ['runStatus','versionId','contentHash','revision']) {
  const bad=data('failed_retryable');
  if(field==='runStatus') bad[field]='<img src=x onerror="alert(1)">';
  else bad.source[field]='<img src=x onerror="alert(1)">';
  const output=api.renderDeconstructionDiagnostics(bad);
  assert.doesNotMatch(output,/<img/);assert.match(output,/&lt;img/);assert.match(output,/&quot;/);
}
d.error.code='<script>bad</script>';d.progress.currentStage='<svg onload="bad">';
assert.doesNotMatch(api.renderDeconstructionDiagnostics(d),/<script|<svg/);
d.message='<img src=x>正文仍保留';
assert.doesNotMatch(api.renderDeconstructionStatus(d),/<img/);
d.source.revision=null;assert.match(api.renderDeconstructionDiagnostics(d),/来源修订<\/dt><dd>未记录/);
d.source.revision=0;assert.match(api.renderDeconstructionDiagnostics(d),/来源修订<\/dt><dd>0/);
''')

    def test_real_page_mounts_diagnostics_even_without_report(self):
        run_js(r'''
for(const status of ['empty','queued','running','failed_retryable','stale','rebuild_required']) {
  const d=data(status);api.renderDeconstructionPage(d);
  const content=node('#deconstructionPageContent').innerHTML,tools=node('#workspaceSource').innerHTML;
  assert.match(tools,/技术详情/);assert.ok(tools.includes(d.source.versionId));
  assert.ok(!visibleText(content).includes(d.source.versionId));
  assert.ok(!visibleText(content).includes(d.runStatus));
  assert.equal(api.elements.deconstructionRefreshButton.disabled,['queued','running'].includes(status));
}
const d=data('completed');
d.result={analysisContractVersion:'1.0',report:{},sourceVersionId:'report-version',sourceRevision:3,
  sourceHash:'report-hash',analysisLabel:'基础分析'};
api.renderDeconstructionPage(d);
assert.match(node('#workspaceSource').innerHTML,/范围与来源/);
assert.match(node('#workspaceSource').innerHTML,/report-version/);
assert.match(node('#workspaceSource').innerHTML,/技术详情/);
''')

    def test_tools_entry_and_responsive_accessibility_styles(self):
        html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
        self.assertIn('aria-labelledby="workspaceToolsTitle"', html)
        self.assertIn('data-action="open-workspace-tools">分析与来源', html)
        css = (ROOT / "frontend/styles.css").read_text(encoding="utf-8")
        self.assertIn('.deconstruction-technical-details > summary:focus-visible', css)
        self.assertIn('.deconstruction-state-side .button { max-width: 100%; white-space: normal; }', css)
        self.assertIn('.deconstruction-progress.is-indeterminate span { display: none; }', css)
        self.assertIn('overflow-wrap: anywhere', css)


def serve_synthetic(port):
    """CUA-only preview of production render functions; no application API routes."""
    rendered = json.loads(run_js(r'''
const output={};
for(const status of ['empty','queued','running','completed','failed_retryable','stale','rebuild_required']) {
  const d=data(status);output[status]={card:api.renderDeconstructionStatus(d),details:api.renderDeconstructionDiagnostics(d)};
}
console.log(JSON.stringify(output));
'''))
    index = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assets = re.findall(r'<link rel="stylesheet"[^>]+>', index)
    dialog = index[index.index('<dialog id="workspaceToolsDialog"'):]
    dialog = dialog[:dialog.index('</dialog>') + len('</dialog>')]
    # Model controls are intentionally absent from this presentation-only service.
    dialog = dialog[:dialog.index('<button id="deconstructionRefreshButton"')] + '</div></dialog>'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            if url.path.startswith('/static/'):
                name = url.path.removeprefix('/static/')
                if name not in {p.name for p in (ROOT / 'frontend').glob('*.css')}:
                    self.send_error(404)
                    return
                body = (ROOT / 'frontend' / name).read_bytes()
                content_type = 'text/css; charset=utf-8'
            elif url.path == '/':
                selected = parse_qs(url.query).get('case', ['failed_retryable'])[0]
                if selected not in rendered:
                    self.send_error(404)
                    return
                fragment = rendered[selected]
                labels = ['空白', '排队', '运行', '成功', '失败', '失效', '需确认']
                links = ' · '.join(f'<a href="/?case={key}">{label}</a>'
                                   for key, label in zip(rendered, labels))
                body = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                        '<meta name="viewport" content="width=device-width,initial-scale=1">'
                        '<title>合成状态检查</title>' + ''.join(assets) + '<body><main class="deconstruction-main">'
                        '<nav aria-label="合成状态">' + links + '</nav><header class="deconstruction-header">'
                        '<div class="deconstruction-heading"><h1>人物</h1></div>'
                        '<button class="button button-outline" id="openTools">分析与来源</button></header>'
                        '<section class="deconstruction-page-content">' + fragment['card'] + '</section>'
                        + dialog.replace('<div id="workspaceSource"></div>', '<div id="workspaceSource">' + fragment['details'] + '</div>')
                        + '</main><script>const dialog=document.querySelector("dialog");'
                        'document.querySelector("#openTools").onclick=()=>dialog.showModal();'
                        'document.querySelector(".dialog-close").onclick=()=>dialog.close();'
                        '</script></body></html>').encode('utf-8')
                content_type = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'Synthetic presentation only: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--serve':
        serve_synthetic(int(sys.argv[2]))
    else:
        unittest.main()
