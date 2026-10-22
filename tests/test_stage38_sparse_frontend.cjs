/* Explicit public versions and sparse analysis. Deterministic VM only. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),template=require('./browser_stage37_fixture.cjs').report;
const context={window:{},document:{querySelector:()=>null,querySelectorAll:()=>[]},URL,URLSearchParams};
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/\r\n/g,'\n'),hook='  start();\n})();';
assert.equal(source.split(hook).length,2);
vm.runInNewContext(source.replace(hook,'  globalThis.api={normalizeDeconstructionResponse,normalizeResult,normalizeHistoryItem,hasDeconstructionResults,isModelAnalysisReport,deconstructionEvidenceMatchesSource,renderDeconstructionHistoryItem,renderDeconstructionGuideContent};\n})();'),context);
const a=context.api,cases=[];
function envelope(version='2') {
 const report=structuredClone(template);report.schema_version=version;
 if(version==='2')for(const p of report.characters){p.motivation=null;p.change=null;}
 const result={status:'completed',document_id:'doc',analysis_contract_version:`model.${version}`,source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64),scope_start:1,scope_end:6,scope_hash:'b'.repeat(64),report};
 return {project_id:'p1',effective_status:'completed',run_status:'completed',source_match:true,source:{version_id:'v1',revision:1,hash:'a'.repeat(64),match:true},progress:{percent:100},actions:{},result,active_run:{...result,run_status:'completed'},focus_document_id:'doc',history:[],volumes:[]};
}
function test(name,run){run();cases.push(name);}
test('both explicit versions normalize without rewriting any report value',()=>{
 for(const v of ['1','2']){const raw=envelope(v),before=JSON.stringify(raw),n=a.normalizeDeconstructionResponse(raw);
  assert.equal(n.result.analysisContractVersion,`model.${v}`);assert.equal(a.hasDeconstructionResults(n),true);
  assert.equal(JSON.stringify(n.result.report),JSON.stringify(raw.result.report));assert.equal(JSON.stringify(raw),before);
  assert.equal(a.normalizeHistoryItem(raw.result).analysisContractVersion,`model.${v}`);
  assert.match(a.renderDeconstructionHistoryItem(n,{...a.normalizeHistoryItem(raw.result),status:'completed'}),/模型报告/);
 }
});
for(const key of ['motivation','change'])test(`schema 2 requires ${key} even when null is allowed`,()=>{
 const raw=envelope();delete raw.result.report.characters[0][key];assert.throws(()=>a.normalizeDeconstructionResponse(raw),/版本不完整/);
});
for(const key of ['identity','motivation','change'])for(const value of [{},'',{text:'无据判断',status:'fact',evidence_ids:[]},{text:'伪造来源',status:'fact',evidence_ids:['missing']}, {text:' ',status:'fact',evidence_ids:['Q0']}])test(`schema 2 rejects malformed/unsourced ${key}: ${JSON.stringify(value)}`,()=>{
 const raw=envelope();raw.result.report.characters[0][key]=value;assert.throws(()=>a.normalizeDeconstructionResponse(raw),/版本不完整/);
});
test('identity cannot be null',()=>{const raw=envelope();raw.result.report.characters[0].identity=null;assert.throws(()=>a.normalizeDeconstructionResponse(raw),/版本不完整/);});
test('explicit schema/envelope/active-run versions cannot be guessed or mixed',()=>{
 for(const [schema,version]of [['2','model.1'],['1','model.2'],['3','model.2'],[2,'model.2'],['2','model.3']]){
  const raw=envelope();raw.result.report.schema_version=schema;raw.result.analysis_contract_version=version;assert.throws(()=>a.normalizeDeconstructionResponse(raw),/版本/);
 }
 for(const key of ['schema_version','analysis_contract_version']){const raw=envelope();delete (key==='schema_version'?raw.result.report:raw.result)[key];assert.throws(()=>a.normalizeDeconstructionResponse(raw),/版本/);}
 const raw=envelope();raw.active_run.analysis_contract_version='model.1';assert.throws(()=>a.normalizeDeconstructionResponse(raw),/运行不一致/);
});
test('legacy report_version 1.0 viewer input remains readable',()=>{
 const raw=envelope('1');delete raw.result.report.schema_version;raw.result.report.report_version='1.0';assert.equal(a.hasDeconstructionResults(a.normalizeDeconstructionResponse(raw)),true);
});
test('new model report retains scope and canonical run binding checks',()=>{
 for(const change of [r=>r.result.scope_hash='',r=>r.result.scope_end=0,r=>r.focus_document_id='another',r=>r.active_run.source_hash='other',r=>r.source_match=false]){
  const raw=envelope();change(raw);assert.throws(()=>a.normalizeDeconstructionResponse(raw));
 }
});
test('new model evidence uses the same strict historical source identity',()=>{
 const raw=envelope();raw.source.revision=2;raw.source.hash='current';
 const data=a.normalizeDeconstructionResponse(raw),ref={documentId:'doc',chapterNumber:1,sourceVersionId:'v1',sourceRevision:1,sourceHash:'a'.repeat(64),chapterId:'c1',id:'Q0'};
 assert.equal(a.deconstructionEvidenceMatchesSource(data,ref,data.result),true);
 for(const change of [{documentId:'other'},{chapterNumber:7},{sourceVersionId:'v2'},{sourceRevision:2},{sourceHash:'current'}])assert.equal(a.deconstructionEvidenceMatchesSource(data,{...ref,...change},data.result),false);
});
const readerContext={window:{XumaiReportBrowser:{esc:String},XumaiVisualReading:{short:String}}},reader=fs.readFileSync(path.join(root,'frontend/workspace-reader.js'),'utf8'),marker='  function mount(root, data, options) {';
assert.equal(reader.split(marker).length,2);vm.runInNewContext(reader.replace(marker,marker+' return data;'),readerContext);
test('all four optional combinations hide only null sections and never invoke claim(null)',()=>{
 for(const motivation of [null,template.characters[0].motivation])for(const change of [null,template.characters[0].change]){
  const report=envelope().result.report;Object.assign(report.characters[0],{motivation,change,portrait:null,insights:[{title:'有据补充',...template.characters[0].identity}]});
  const before=JSON.stringify(report),data=readerContext.window.XumaiWorkspaceReader.mountModel({},report,{claim:c=>{assert.ok(c);return c.text;},evidence:()=>''});
  const html=data.personAnalysis(data.people[0]);
  assert.equal(html.includes('<h3>动机</h3>'),motivation!==null);assert.equal(html.includes('<h3>关键经历与变化</h3>'),change!==null);
  assert.match(html,/<h3>身份与处境<\/h3>/);assert.match(html,/有据补充/);assert.doesNotMatch(html,/暂无|未交代|未知|待补充/);
  assert.ok(data.personExperiences(data.people[0]).length);assert.equal(JSON.stringify(report),before);
 }
});
test('guide preserves an identity snapshot when change is null without manufacturing a change',()=>{
 const raw=envelope(),p=raw.result.report.characters[0],before=JSON.stringify(raw);
 const html=a.renderDeconstructionGuideContent([{volume:{documentId:'doc',scopeLabel:'第1–6章'},report:raw.result.report}],[{name:p.name,stages:[{scope_start:1,scope_end:6,identity:p.identity,change:null}]}]);
 assert.ok(html.includes(p.identity.text));assert.ok(html.includes(raw.result.report.events[0].title));assert.doesNotMatch(html,/阶段信息待补充/);assert.equal(JSON.stringify(raw),before);
});
console.log(JSON.stringify({synthetic:true,count:cases.length,cases},null,2));
