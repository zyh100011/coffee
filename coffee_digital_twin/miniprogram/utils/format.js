// Display precision only; source values and calculations retain full precision.
function numberText(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'number') return value;
  if (!Number.isFinite(value)) return '—';
  return (Object.is(value, -0) ? 0 : value).toFixed(2);
}
function formatValue(value, kind) {
  if (value === null || value === undefined || value === '' || (typeof value === 'number' && !Number.isFinite(value))) return '—';
  if (typeof value !== 'number') return String(value);
  const clean = Object.is(value, -0) ? 0 : value;
  if (kind === 'moisture' || kind === 'cm3/cm3' || kind === 'cm³/cm³') return clean.toFixed(2);
  return Number(clean.toFixed(2)).toString();
}
function displayUnit(unit) {
  return ({'cm3/cm3':'cm³/cm³','uS/cm':'μS/cm','μg/m3':'μg/m³'})[unit] || unit || '';
}
const FACT_LABELS = {n:'有效记录数',mean:'平均值',min:'最小值',max:'最大值',first:'首值',last:'末值',missing_days:'无有效记录天数',excluded_count:'排除记录数',series_total:'序列点数',offset:'分页起点',limit:'每页条数',infiltration_depth_cm:'湿润锋深度',root_uptake_ratio:'根系吸水比'};
module.exports = { numberText, formatValue, displayUnit, FACT_LABELS };
