/* Read-only UTF-16 projection. Never split, rename or rewrite official chapters. */
(() => {
  'use strict';
  const labels={opening:'开篇',explicit:'原文小节',inferred:'推定小节'};
  function read(projection,key,content) {
    if (!projection || !Array.isArray(projection[key])) return [];
    return projection[key].filter(s=>s && typeof s.section_id==='string' && typeof s.title==='string' &&
      Number.isInteger(s.start) && Number.isInteger(s.end) && s.start>=0 && s.end>s.start &&
      s.end<=String(content || '').length && Object.hasOwn(labels,s.kind));
  }
  function locate(editor,section,source) {
    // Textareas normalize CRLF, while projection offsets refer to server content.
    const normalized=String(source).replace(/\r\n?/g,'\n');
    if(editor.value!==normalized)return false;
    const start=source.slice(0,section.start).replace(/\r\n?/g,'\n').length;
    const end=source.slice(0,section.end).replace(/\r\n?/g,'\n').length;
    const mirror=document.createElement('div'),style=getComputedStyle(editor);
    for(const key of ['font','letterSpacing','lineHeight','padding','boxSizing','borderWidth','wordBreak','overflowWrap','tabSize'])mirror.style[key]=style[key];
    Object.assign(mirror.style,{position:'absolute',visibility:'hidden',whiteSpace:'pre-wrap',width:`${editor.clientWidth}px`,height:'auto'});
    mirror.textContent=normalized.slice(0,start);
    const marker=document.createElement('span');marker.textContent=normalized.slice(start,end) || ' ';mirror.append(marker);document.body.append(mirror);
    const top=marker.offsetTop;mirror.remove();
    editor.focus({preventScroll:true});editor.setSelectionRange(start,end);editor.scrollTop=Math.max(0,top-editor.clientHeight*.2);
    editor.scrollIntoView({block:'nearest',behavior:'instant'});return true;
  }
  window.XumaiChapterSections=Object.freeze({read,locate,labels});
})();
