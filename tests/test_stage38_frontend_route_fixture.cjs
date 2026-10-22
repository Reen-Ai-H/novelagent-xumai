/* Synthetic 12 people / 8 directed relations, 7 events / 5 relations.
 * No service setup or mutation: imported by geometry and intercepted UI tests. */
function denseFixture(){
 const names=['林舟','程夏','沈砚','周岚','顾平','许禾','陆遥','叶青','陈渡','方宁','苏棠','闻远'];
 const titles=['返抵旧港','收到旧信','回看往事','核对名册','渡口会面','交还钥匙','结伴离港'];
 const quotes=titles.map((title,i)=>`合成第${i+1}章：${title}，仅供界面密度检查。`);
 const claim=(text,i,status='fact')=>({text,status,evidence_ids:[`Q${i}`]});
 const report={schema_version:'1',producer:'synthetic-route-no-model',title:'十二人物 · 合成密度检查',scope:'第1至7章',chapter_numbers:[1,2,3,4,5,6,7],findings:[],
  characters:names.map((name,i)=>({id:`C${i}`,name,importance:i<4?'main':'support',role:i===4?'主要人物的导师':`${name}的合成身份`,aliases:[],identity:claim(`${name}参与旧港往事的核对。`,i%7),portrait:claim('遇事谨慎，态度仍有待观察。',i%7,'inferred'),motivation:claim('希望厘清一封旧信的来历。',i%7),change:claim('开始主动与同行者核对经过。',i%7),insights:[]})),
  events:titles.map((title,i)=>({id:`E${i}`,title,chapter_number:i+1,story_time:`合成时刻${i+1}`,actor_ids:[`C${i}`,`C${(i+4)%12}`],action:claim(quotes[i],i),consequence:claim('合成后续在下一个事件中展开。',i),sub_events:[]})),
  character_relations:[['C0','C1','记录同伴','fact'],['C0','C4','受托照看','reported'],['C1','C5','送信协作','fact'],['C2','C6','旧识待核','inferred'],['C6','C7','共同调查','fact'],['C3','C8','师徒关系（人物说法）','reported'],['C8','C9','邻里往来','fact'],['C10','C11','短期同行','fact']].map(([from_id,to_id,label,status],i)=>({from_id,to_id,label,...claim(`合成记录：${names[+from_id.slice(1)]}与${names[+to_id.slice(1)]}存在“${label}”联系。`,i%7,status)})),
  relations:[['E0','E1','causes'],['E1','E3','enables'],['E2','E4','reveals'],['E3','E5','follows'],['E5','E6','foreshadow_payoff']].map(([from_id,to_id,kind],i)=>({from_id,to_id,kind,...claim('合成事件关系，仅检验方向与点击依据。',i)})),
  story_order:['E2','E0','E1','E4','E3','E5','E6'],time_note:'合成叙述与故事顺序不同，只用于顺序切换验证。',evidence:quotes.map((quote,i)=>({id:`Q${i}`,chapter_number:i+1,quote})),open_questions:[],contradictions:[]};
 const chapters=quotes.map((quote,i)=>({chapter_id:`c${i+1}`,chapter_number:i+1,title:titles[i],content:quote,word_count:quote.length,status:'ready',server_revision:1}));
 const archive={characters:[],storylines:[],foreshadowing:[],questions:[],snapshots:[]};
 const workspace={project_id:'p1',title:report.title,mode:'independent',initialized:true,archive,tasks:[],active_version:{version_id:'v1',revision:1,chapters,archive}};
 const refs=quotes.map((quote,i)=>({evidence_id:`Q${i}`,document_id:'doc',source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64),chapter_id:`c${i+1}`,chapter_number:i+1,granularity:'span',offset_unit:'utf16_code_unit',start_offset:0,end_offset:quote.length,excerpt:quote}));
 const result={status:'completed',document_id:'doc',analysis_contract_version:'model.1',source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64),scope_start:1,scope_end:7,scope_hash:'b'.repeat(64),report,evidence:refs};
 const response={project_id:'p1',title:report.title,effective_status:'completed',run_status:'completed',source_match:true,focus_document_id:'doc',progress:{percent:100,current_stage:'completed'},source:{version_id:'v1',revision:1,hash:'a'.repeat(64),chapter_count:7,total_word_count:quotes.join('').length,match:true},actions:{retry:false,rebuild:false},result,active_run:{...result,run_status:'completed'},history:[],volumes:[]};
 return {workspace,response,refs};
}
module.exports={denseFixture};
