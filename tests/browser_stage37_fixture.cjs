/* HTTP-only fixture preparation for CUA. Never starts a browser or calls a model.
 * Run against tests/browser_server.py on an isolated loopback port. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const origin=process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8054';
assert.equal(new URL(origin).hostname,'127.0.0.1');
assert.ok(!['8052','8057'].includes(new URL(origin).port),'Do not use a user/integration service');
const out=path.join(__dirname,'..','test-results','stage37-cua');
const email=`stage37-cua-${Date.now()}@example.test`;
let cookie='';
async function api(url,method='GET',body) {
  assert.ok(!/analyze-preview|book\/start/.test(url),'No model calls');
  const res=await fetch(origin+url,{method,headers:{'content-type':'application/json',cookie},body:body===undefined?undefined:JSON.stringify(body)});
  if(res.headers.get('set-cookie'))cookie=res.headers.get('set-cookie').split(';')[0];
  const data=await res.json();assert.equal(res.status,200,JSON.stringify(data));return data;
}
const names=['林舟','程夏','沈砚','周岚','顾平','许禾'];
const titles=['第一章 潮声','第二章 信笺','第三章 故人','第四章 旧灯','第五章 归航','第六章 清晨'];
const quotes=['周岚是林舟的母亲。','程夏说顾平曾救过她，但无人核实。','沈砚把旧钥匙交给林舟。','许禾留下一封没有署名的信。','林舟与程夏在渡口重逢。','周岚带着众人走出旧屋。'];
const chapters=titles.map((title,i)=>`${title}\r\n  😀${quotes[i]}\r\n\r\n${Array.from({length:i===0?18:4},(_,j)=>`海风穿过第${j+1}扇窗，${names[i]}停下来，听见港口的钟声。`).join('\r\n')}\r\n\r\n`);
const source=chapters.join('');
const claim=(text,q,status='fact')=>({text,status,evidence_ids:[q]});
const report={schema_version:'1',producer:'synthetic-cua-no-model',title:'潮声 · 合成验收',scope:'第1至6章',chapter_numbers:[1,2,3,4,5,6],
 findings:[{id:'F1',title:'重返旧港',...claim('众人在旧港重逢。','Q4')}],
 characters:names.map((name,i)=>({id:`C${i}`,name,role:i<3?'主要人物':'配角',aliases:[],identity:claim(`${name}的故事从旧港开始。`,`Q${i}`),portrait:claim('他在旧事前保持谨慎。',`Q${i}`,'inferred'),motivation:claim('动机尚不明确。',`Q${i}`,'unknown'),change:claim('此时重新面对往事。',`Q${i}`,'reported'),insights:[]})),
 events:quotes.map((text,i)=>({id:`E${i}`,title:['母亲归来','一段旧闻','交出钥匙','无名来信','渡口重逢','走出旧屋'][i],chapter_number:i+1,story_time:`当日${i+1}`,actor_ids:[`C${i}`,`C${(i+1)%6}`],action:claim(text,`Q${i}`,i===1?'reported':'fact'),consequence:claim('下一步仍待正文交代。',`Q${i}`,'unknown'),sub_events:[]})),
 relations:[{from_id:'E2',to_id:'E4',kind:'enables',...claim('钥匙可能为重逢提供契机。','Q2','inferred')}],
 character_relations:[{from_id:'C3',to_id:'C0',label:'母亲',...claim('周岚是林舟的母亲。','Q0')},{from_id:'C4',to_id:'C1',label:'传闻救助者',...claim('程夏说顾平救过她，此说法尚未核实。','Q1','reported')},{from_id:'C2',to_id:'C0',label:'可能信任',...claim('沈砚把钥匙交给林舟，可能信任他。','Q2','inferred')}],
 story_order:['E2','E0','E1','E3','E4','E5'],time_note:'合成时间顺序，仅用于交互验收。',evidence:quotes.map((quote,i)=>({id:`Q${i}`,chapter_number:i+1,quote})),open_questions:[],contradictions:[]};
async function setup(){
 await fs.mkdir(out,{recursive:true});await api('/api/auth/email','POST',{email});
 async function project(title){return api('/api/library/projects','POST',{title,mode:'independent',brief:''});}
 const created=await project('潮声 · 六章合成验收');
 const id=created.project?.project_id || created.project_id;
 assert.ok(id,JSON.stringify(created));
 const base=`/api/independent/projects/${id}`;
 const {preview}=await api(`${base}/chapter-previews/import`,'POST',{filename:'潮声合成.txt',content_base64:Buffer.from(source).toString('base64')});
 assert.equal(preview.chapters.length,6);assert.equal(preview.source_text,source);
 assert.equal(preview.chapters.map(c=>source.slice(c.start,c.end)).join(''),source);
 const confirmed=await api(`${base}/chapter-previews/${preview.preview_id}/confirm`,'POST',{expected_revision:preview.revision});
 assert.equal(confirmed.workspace.active_version.chapters.map(c=>c.content).join(''),source);
 const imported=await api(`${base}/deconstruction/import`,'POST',{report});
 const empty=await project('分章预览 · 合成边界验证');
 const blankId=empty.project?.project_id || empty.project_id;
 const documentId=imported.result.document_id;
 const fixture={email,projectId:id,blankId,documentId,origin,editorUrl:`${origin}/independent/${id}`,blankUrl:`${origin}/independent/${blankId}`,peopleUrl:`${origin}/independent/${id}?view=deconstruction&volume=${documentId}&section=characters`,plotUrl:`${origin}/independent/${id}?view=deconstruction&volume=${documentId}&section=plot`,sourceLength:source.length,sourceFile:path.join(out,'synthetic-six-chapters.txt')};
 await fs.writeFile(fixture.sourceFile,source);await fs.writeFile(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2));
 console.log(JSON.stringify(fixture,null,2));
}
module.exports={report,source};
if(require.main===module)setup().catch(e=>{console.error(e);process.exitCode=1;});
