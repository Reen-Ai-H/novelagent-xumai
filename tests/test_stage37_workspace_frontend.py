"""Offline checks for the new reader adapters and release shell. No browser/model."""
from pathlib import Path
import json
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceFrontendTest(unittest.TestCase):
    def test_runtime_assets_are_present_ordered_and_one_release(self):
        html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
        assets = re.findall(r'(?:href|src)="/static/([^"?]+\.(?:css|js))\?v=([^"&]+)"', html)
        self.assertEqual(len(assets), 13)
        self.assertEqual({release for _, release in assets}, {"stage37-final"})
        self.assertEqual(len({name for name, _ in assets}), 13)
        for name, _ in assets:
            self.assertTrue((ROOT / "frontend" / name).is_file(), name)
        names = [name for name, _ in assets]
        for module in ("chapter-preview.js", "workspace-reader.js"):
            self.assertLess(names.index("report-browser.js"), names.index(module))
            self.assertLess(names.index(module), names.index("app.js"))
            self.assertIn(f'["node", "--check", "frontend/{module}"]',
                          (ROOT / "tests/run_quality_gates.py").read_text(encoding="utf-8"))

    def test_model_semantics_are_directed_status_preserving_and_complete(self):
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('frontend/workspace-reader.js','utf8');
const marker='  function mount(root, data, options) {';
assert.ok(source.includes(marker));
const context={window:{XumaiReportBrowser:{esc:String},XumaiVisualReading:{short:String}}};
vm.runInNewContext(source.replace(marker,marker+' return data;'),context);
const report=structuredClone(require('./tests/browser_stage37_fixture.cjs').report);
const options={claim:c=>JSON.stringify(c),evidence:()=>''};
const data=context.window.XumaiWorkspaceReader.mountModel({},report,options);
const a=data.personRelations(data.people[0]), b=data.personRelations(data.people[3]);
assert.equal(a[0].from,'C3');assert.equal(a[0].to,'C0');assert.equal(a[0].label,'母亲');
assert.equal(b[0].from,'C3');assert.equal(b[0].to,'C0');assert.equal(b[0].label,'母亲');
assert.equal(a[0].status,'fact');assert.equal(a[1].status,'inferred');
assert.equal(data.eventEdges[0].status,'inferred');
assert.match(a[0].body(),/Q0/);assert.match(a[1].body(),/inferred/);
assert.match(data.personAnalysis(data.people[0]),/inferred/);
assert.match(data.personAnalysis(data.people[0]),/reported/);
assert.match(data.personAnalysis(data.people[0]),/unknown/);
delete report.character_relations;
const old=context.window.XumaiWorkspaceReader.mountModel({},report,options);
assert.equal(old.personRelations(old.people[0]).length,0);
assert.ok(old.personExperiences(old.people[0]).length>0);
// More than a page in each collection; adapters may not truncate source data.
report.events=Array.from({length:180},(_,i)=>({...report.events[0],id:`E${i}`}));
report.relations=Array.from({length:350},(_,i)=>({...report.relations[0],from_id:`E${i%180}`,to_id:`E${(i+1)%180}`}));
const large=context.window.XumaiWorkspaceReader.mountModel({},report,options);
assert.equal(large.events.length,180);assert.equal(large.eventEdges.length,350);
assert.equal(large.personExperiences(large.people[0]).length,180);
const reachable=new Set();for(const event of large.events)large.eventEdges.forEach((r,i)=>{if(r.from===event.id || r.to===event.id)reachable.add(i);});
assert.equal(reachable.size,350,'Every event relation is reachable from its endpoints');
for(let count=0;count<=8;count++) {
 const slots=context.window.XumaiWorkspaceReader.plotSlots(count);
 assert.equal(slots.length,count);
 assert.equal(new Set(slots.map(p=>JSON.stringify(p))).size,count);
 slots.forEach(p=>assert.ok(p.x>=15 && p.x<=85 && p.y>=80));
}
for(let count=0;count<=6;count++) {
 const slots=context.window.XumaiWorkspaceReader.personSlots(count);
 assert.equal(slots.length,count);
 assert.equal(new Set(slots.map(p=>JSON.stringify(p))).size,count);
 slots.forEach(p=>assert.ok(p.x!==50 && p.y>=16 && p.y<=84));
}
'''
        result = subprocess.run(["node", "-"], input=script, text=True, encoding="utf-8",
                                cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_boundary_projection_preserves_utf16_crlf(self):
        script = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const context={window:{XumaiReportBrowser:{esc:String}}};
vm.runInNewContext(fs.readFileSync('frontend/chapter-preview.js','utf8'),context);
const convert=context.window.XumaiChapterPreview.sourceOffset;
const source='  😀第一段\r\n\r\n第二段  \r\n',normalized=source.replace(/\r\n/g,'\n');
for(let i=0;i<=normalized.length;i++)assert.equal(source.slice(0,convert(source,i)).replace(/\r\n/g,'\n'),normalized.slice(0,i));
'''
        result = subprocess.run(["node", "-"], input=script, text=True, encoding="utf-8",
                                cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
