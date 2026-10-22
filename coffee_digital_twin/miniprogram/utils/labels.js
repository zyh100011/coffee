const SOURCES = {
  observation: { text: '实测', className: 'tag-observation' },
  literature: { text: '文献', className: 'tag-literature' },
  simulation_uncalibrated: { text: '模拟·未校准', className: 'tag-simulation' },
  proxy_model: { text: '代理模型', className: 'tag-proxy' },
  simplified_model: { text: '简化模型', className: 'tag-proxy' },
  demo: { text: '演示数据', className: 'tag-demo' }
};
const STATUSES = { success: '可用', replay: '历史回放', partial: '部分可用', failed: '失败', timeout: '超时', missing_input: '缺少条件', fallback: '演示回退' };
function evidenceLabel(source, status, mode) {
  if (['failed', 'timeout', 'missing_input'].includes(status)) return { text: '不可用', className: 'tag-proxy', aria: `工具不可用：${STATUSES[status]}` };
  const label = status === 'fallback' ? SOURCES.demo : (SOURCES[source] || { text: '来源未核验', className: 'tag-proxy' });
  const replay = mode === 'replay' || status === 'replay';
  return { text: label.text + (replay ? '·回放' : ''), className: label.className, aria: `证据类型：${label.text}${replay ? '，历史结果回放' : ''}` };
}
const PARAMETERS = { soil_moisture: '土壤含水量', soil_temperature: '土壤温度', air_temperature: '空气温度', rainfall: '降雨', rain: '降雨' };
const FIELDS = { plot_name: '名称', coffee_variety: '品种', tree_age: '树龄', area_mu: '面积', latitude: '纬度', longitude: '经度', elevation_m: '海拔', soil_type: '土质', shade_level: '遮阴', plant_density: '密度', row_spacing_m: '行距', plant_spacing_m: '株距' };
module.exports = { SOURCES, STATUSES, PARAMETERS, FIELDS, evidenceLabel };
