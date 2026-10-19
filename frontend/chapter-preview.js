/* Server-owned, lossless chapter previews. Only boundaries and titles leave
 * this editor: source text is a read-only preview, never a confirm payload. */
(() => {
  'use strict';
  const esc=window.XumaiReportBrowser.esc;
  const label={explicit:'已识别',inferred:'待核对',manual:'已调整',fallback:'待分章'};
  let active=null;
  function sourceOffset(source,normalizedOffset) {
    let original=0,display=0;
    while(original<source.length && display<normalizedOffset) {
      original += source[original]==='\r' && source[original+1]==='\n' ? 2 : 1;display++;
    }
    return original;
  }
  function open(preview,options) {
    active?.close();
    const opener=document.activeElement,dialog=document.createElement('dialog');
    dialog.className='review-dialog chapter-preview-dialog';dialog.setAttribute('aria-labelledby','chapterPreviewTitle');
    document.body.append(dialog);
    let current=preview,boundaries=[],selected=0,dirty=false,busy=false,closed=false;
    const api=`/api/independent/projects/${encodeURIComponent(options.projectId)}/chapter-previews`;
    const updateRoute=id=>{const u=new URL(location.href);if(id)u.searchParams.set('chapter_preview',id);else if(u.searchParams.get('chapter_preview')===current.preview_id)u.searchParams.delete('chapter_preview');history.replaceState({},'',u);};
    const close=()=>{if(busy)return;dialog.close();};
    const acceptPreview=value=>{current=value;boundaries=value.chapters.map(c=>({start:c.start,title:c.title}));selected=Math.min(selected,boundaries.length-1);dirty=false;render();};
    const message=text=>{dialog.querySelector('[data-preview-notice]').textContent=text;};
    const expired=()=>Date.parse(current.expires_at)<=Date.now();
    function chapterText(index=selected) {return current.source_text.slice(boundaries[index]?.start || 0,boundaries[index+1]?.start ?? current.source_length);}
    function renderBody() {
      const editor=dialog.querySelector('[data-preview-source]');editor.value=chapterText();
      let offset=0;
      dialog.querySelector('[data-preview-paragraph]').innerHTML='<option value="">点击原文，或选择一段</option>'+editor.value.split('\n').map(line=>{
        const start=offset;offset+=line.length+1;
        return line.trim()?`<option value="${start}">${esc(line.trim().slice(0,70))}</option>`:'';
      }).join('');
      dialog.querySelector('[data-preview-current]').textContent=boundaries[selected]?.title || '正文';
      dialog.querySelectorAll('[data-preview-chapter]').forEach(n=>n.setAttribute('aria-current',Number(n.dataset.previewChapter)===selected?'page':'false'));
      dialog.querySelector('[data-preview-merge]').disabled=selected===0 || busy;
    }
    function controls() {
      const locked=busy || expired() || current.status!=='pending';
      dialog.querySelector('[data-preview-update]').disabled=!dirty || locked;
      dialog.querySelector('[data-preview-confirm]').disabled=dirty || busy || expired() || current.status!=='pending';
      dialog.querySelector('[data-preview-split]').disabled=locked;
      dialog.querySelector('[data-preview-paragraph]').disabled=locked;
      dialog.querySelector('[data-preview-refresh]').disabled=busy;
      dialog.querySelector('[data-preview-merge]').disabled=selected===0 || busy || expired() || current.status!=='pending';
      dialog.querySelector('[data-preview-close]').disabled=busy;
      dialog.querySelectorAll('[data-preview-title]').forEach(n=>n.disabled=locked);
    }
    function render() {
      dialog.innerHTML=`<div class="review-dialog-shell"><button class="dialog-close" type="button" data-preview-close aria-label="关闭分章预览">×</button><header><span class="eyebrow">${current.kind==='resegment'?'重新分章':'导入预览'}</span><h2 id="chapterPreviewTitle">核对正式章节</h2><p class="chapter-preview-meta">${boundaries.length} 章 · ${Number(current.source_length).toLocaleString('zh-CN')} 字符</p></header><p data-preview-notice role="status">${expired()?'预览已过期，请重新生成。':current.status==='confirmed'?'这份预览已经确认。':(current.warnings || []).map(w=>typeof w==='string'?w:w.message || w.code || '').join('；')}</p><div class="chapter-preview-layout"><section class="chapter-preview-index" aria-label="预览章节">${boundaries.map((b,i)=>`<div class="chapter-preview-row"><button type="button" data-preview-chapter="${i}" aria-label="预览第 ${i+1} 章">${String(i+1).padStart(2,'0')}</button><label><span>${label[current.chapters.find(c=>c.start===b.start)?.confidence] || '已调整'}</span><input data-preview-title="${i}" value="${esc(b.title)}" aria-label="第 ${i+1} 章标题" maxlength="200"></label></div>`).join('')}</section><section class="chapter-preview-manuscript"><h3 data-preview-current></h3><textarea readonly data-preview-source aria-label="分章原文预览" spellcheck="false"></textarea><div class="chapter-preview-edit-actions"><button type="button" class="quiet-link" data-preview-split>将当前段落设为章首</button><button type="button" class="quiet-link" data-preview-merge>与前章合并</button></div></section></div><footer class="chapter-preview-footer"><span>有效至 ${esc(new Date(current.expires_at).toLocaleString('zh-CN'))}</span><div><button type="button" class="button button-outline" data-preview-update>更新预览</button><button type="button" class="button button-primary" data-preview-confirm>${current.kind==='resegment'?'确认生成新稿本':'确认导入正式章节'}</button></div></footer></div>`;
      dialog.querySelector('.chapter-preview-footer').insertAdjacentHTML('afterbegin','<button type="button" class="quiet-link" data-preview-refresh>重新读取预览</button>');
      dialog.querySelector('.chapter-preview-edit-actions').insertAdjacentHTML('beforebegin','<label class="chapter-preview-paragraph">选择章首段落<select data-preview-paragraph aria-label="选择章首段落"></select></label>');
      renderBody();controls();
    }
    async function run(action) {
      if(busy)return;busy=true;controls();
      try {await action();} catch(error) {
        if(!closed)message(error.message || '请求失败，预览保留。请重试。');
      } finally {busy=false;if(!closed)controls();}
    }
    dialog.addEventListener('input',event=>{
      if(!event.target.matches('[data-preview-title]'))return;
      boundaries[Number(event.target.dataset.previewTitle)].title=event.target.value;dirty=true;controls();
    });
    dialog.addEventListener('change',event=>{
      if(!event.target.matches('[data-preview-paragraph]') || event.target.value==='')return;
      const editor=dialog.querySelector('[data-preview-source]'),pos=Number(event.target.value),source=chapterText();
      const start=sourceOffset(source,pos);
      window.XumaiChapterSections?.locate(editor,{start,end:start},source);
      editor.setSelectionRange(pos,pos);event.target.focus();
    });
    dialog.addEventListener('click',event=>{
      const button=event.target.closest('button');if(!button || busy)return;
      if(button.hasAttribute('data-preview-close'))close();
      if(button.hasAttribute('data-preview-refresh'))void run(async()=>{
        if(dirty && !window.confirm('重新读取会放弃尚未更新的分章调整，继续吗？'))return;
        const result=await options.request(`${api}/${encodeURIComponent(current.preview_id)}`);
        acceptPreview(result.preview);message('已读取最新预览。');
      });
      if(button.hasAttribute('data-preview-chapter')){selected=Number(button.dataset.previewChapter);renderBody();}
      if(button.hasAttribute('data-preview-merge') && selected>0){boundaries.splice(selected,1);selected--;dirty=true;render();message('已合并边界，请更新预览核对。');}
      if(button.hasAttribute('data-preview-split')){
        const editor=dialog.querySelector('[data-preview-source]'),pos=editor.selectionStart;
        const lineStart=editor.value.lastIndexOf('\n',Math.max(-1,pos-1))+1;
        const start=boundaries[selected].start+sourceOffset(chapterText(),lineStart);
        if(boundaries.some(b=>b.start===start) || start>=current.source_length){message('请选择章内另一段正文。');return;}
        const title=editor.value.slice(lineStart).split('\n')[0].trim().slice(0,80) || '新章';
        boundaries.splice(selected+1,0,{start,title});selected++;dirty=true;render();message('已增加章首，请更新预览核对。');
      }
      if(button.hasAttribute('data-preview-update'))void run(async()=>{
        const result=await options.request(`${api}/${encodeURIComponent(current.preview_id)}`,{method:'PUT',body:JSON.stringify({expected_revision:current.revision,boundaries})});
        acceptPreview(result.preview);message('预览已更新，正文未改动。');
      });
      if(button.hasAttribute('data-preview-confirm'))void run(async()=>{
        if(dirty || expired())throw new Error('请先更新有效预览，再确认。');
        if(options.beforeConfirm && !(await options.beforeConfirm()))throw new Error('当前正文尚未保存成功，未确认分章。');
        const result=await options.request(`${api}/${encodeURIComponent(current.preview_id)}/confirm`,{method:'POST',body:JSON.stringify({expected_revision:current.revision})});
        // Close only after the server accepted the exact preview revision.
        updateRoute(null);closed=true;dialog.close();await options.onConfirmed(result);
      });
    });
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    dialog.addEventListener('keydown',event=>{
      if(event.key!=='Tab')return;
      const nodes=Array.from(dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea')).filter(n=>n.getClientRects().length),first=nodes[0],last=nodes.at(-1);
      if(event.shiftKey && document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
    });
    const routeChanged=()=>{if(new URL(location.href).searchParams.get('chapter_preview')!==current.preview_id)dialog.close();};
    window.addEventListener('popstate',routeChanged);
    dialog.addEventListener('close',()=>{closed=true;window.removeEventListener('popstate',routeChanged);updateRoute(null);dialog.remove();if(active?.dialog===dialog)active=null;if(opener?.isConnected)opener.focus();});
    active={dialog,close};acceptPreview(preview);updateRoute(preview.preview_id);dialog.showModal();
    dialog.querySelector('[data-preview-chapter]')?.focus();return active;
  }
  window.XumaiChapterPreview=Object.freeze({open,sourceOffset});
})();
