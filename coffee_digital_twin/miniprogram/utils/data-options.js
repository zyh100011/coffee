// 按参数分组；原始筛选字段保留在 option，展示不泄漏内部版本。
function category(c) {
 const p=c.parameter;
 if(p==='rainfall_daily')return '日降雨量（mm）';
 const entries=[['soil_humidity','土壤含水率'],['soil_moisture','土壤含水率'],['soil_temperature','土壤温度'],['soil_ec','电导率'],['soil_salt','盐分'],['soil_ph','pH'],['air_temperature','空气温度'],['air_humidity','空气湿度'],['rain','降雨读数'],['wind_speed','风速'],['wind_direction','风向'],['illuminance','光照'],['par_','光合有效读数'],['air_pressure','大气压'],['co2','二氧化碳']];
 const match=entries.find(e=>p.indexOf(e[0])===0);
 return match?match[1]:(c.parameter_label||p).replace(/（[^）]*）/g,'');
}
function organize(items) {
 const options=items.filter(c=>!c.hidden_reason).map(c=>({...c,group:category(c),label:
  (c.depth_top_cm!==undefined?c.depth_top_cm+'–'+c.depth_bottom_cm+'cm · ':c.depth_cm!==null?c.depth_cm+'cm · ':'')+(c.display_source||c.source_label||'监测点')}));
 const groups=[];
 options.forEach((c,index)=>{let group=groups.find(g=>g.label===c.group);if(!group){group={label:c.group,indexes:[]};groups.push(group);}group.indexes.push(index);});
 return {options,groups};
}
module.exports={organize};
