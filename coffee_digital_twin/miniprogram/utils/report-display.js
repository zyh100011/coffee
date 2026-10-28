// 用户展示副本；报告原JSON和HTML仍保留完整证据。
const {formatValue}=require('./format');
function userSections(sections){
 return sections.filter(s=>['事实','情景差异','建议/核查'].includes(s.title)).map(s=>{
  const items=[];
  s.items.forEach(item=>{
   if(!item.text){items.push({...item});return;}
   if(/(MOCK|未校准|假设|来源|证据|回放|演示|trace|ev_)/.test(item.text))return;
   let difference;try{difference=JSON.parse(item.text);}catch(error){}
   if(difference && typeof difference==='object' && difference.theta_day7_by_depth){
    Object.entries(difference.theta_day7_by_depth).forEach(([depth,value])=>items.push({text:depth+'cm 含水率差值 '+formatValue(value,'moisture')+' cm³/cm³'}));
    if(difference.infiltration_depth_cm!==undefined)items.push({text:'湿润锋深度差值 '+formatValue(difference.infiltration_depth_cm)+' cm'});
    if(difference.root_uptake_ratio!==undefined)items.push({text:'根系吸水比差值 '+formatValue(difference.root_uptake_ratio)});
   }else items.push({...item,text:item.text.replace(/^\[未核验\]\s*/,'')});
  });
  return {...s,title:s.title==='建议/核查'?'建议':s.title,items,blocks:items.filter(i=>i.type==='fact'||i.type==='chart')};
 });
}
module.exports={userSections};
