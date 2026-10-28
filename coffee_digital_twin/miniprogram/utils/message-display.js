// 只合并展示副本；原始 blocks、证据ID和完整精度保留。
const { formatValue, displayUnit, FACT_LABELS } = require('./format');
function displayBlocks(blocks, hideMock, isDev=true) {
 const all=blocks||[], groups=new Map();
 all.forEach(b=>{if(b.type==='fact' && b.evidence_id && ['mean','min','max','n','missing_days'].includes(b.label)){
  const group=groups.get(b.evidence_id)||{};group[b.label]=b;groups.set(b.evidence_id,group);
 }});
 const emitted=new Set(), result=[];
 all.forEach(b=>{
  if(!isDev && ['warning','evidence','trace','check_items'].includes(b.type))return;
  if(hideMock && b.type==='warning' && /MOCK|规则生成/.test(b.text||''))return;
  const group=groups.get(b.evidence_id);
  if(b.type==='fact' && group && group.mean && group.n && ['mean','min','max','n','missing_days'].includes(b.label)){
   if(emitted.has(b.evidence_id))return;
   emitted.add(b.evidence_id);
   const unit=group.mean.unit;
   result.push({...group.mean,type:'fact_summary',meanText:formatValue(group.mean.value,unit),
    minText:formatValue(group.min && group.min.value,unit),maxText:formatValue(group.max && group.max.value,unit),
    countText:formatValue(group.n.value),missingDays:group.missing_days?group.missing_days.value:0,unit:displayUnit(unit)});
  }else if(!(b.type==='text' && /^历史观测：/.test(b.text||'') && emitted.size))result.push({...b,
   ...(b.type==='text'&&!isDev?{text:(b.text||'').replace(/^\[未核验\]\s*/,'')}: {})});
 });
 const ordered=emitted.size?[...result.filter(b=>b.type==='text'),...result.filter(b=>b.type!=='text')]:result;
 return ordered.map((b,index)=>({...b,index,displayValue:formatValue(b.value,b.unit),label:FACT_LABELS[b.label]||b.label,
  unit:displayUnit(b.unit),expanded:false,stepCount:(b.steps||[]).filter(s=>s.status==='done'||s.status==='saved').length}));
}
module.exports={displayBlocks};
