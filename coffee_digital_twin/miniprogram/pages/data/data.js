const { numberText } = require('../../utils/format');
const { request } = require('../../utils/request');
const ui = require('../../utils/page');
const { PARAMETERS } = require('../../utils/labels');
const MISSING = {
  sensor_calibration: '土壤湿度探头标定资料',
  actual_probe_depths: '探头实际埋深', soil_humidity_basis: '湿度百分比定义',
  station_hardware_ids_and_pairing: '监测来源的设备编号和配对', rainfall_accumulation_mode: '降雨累计方式',
  site_hydraulic_calibration: '本站土壤水力参数校准', irrigation_records: '实际灌溉记录',
  fertilizer_records: '实际施肥记录', tree_age: '树龄', area_mu: '面积', coordinates: '经纬度',
  shade_level: '遮阴情况', plant_spacing: '株行距', soil_report_sample_date: '土壤报告采样日期',
  soil_report_sample_depth: '土壤报告采样深度'
};
Page({
  data: { ...ui.defaults, catalog: [], options: [], selected: 0, start: '', end: '', aggIndex: 0,
    aggs: ['日均读数', '原始记录'], result: null, blocks: [], querying: false, includeFlagged: false,
    reports: [], reportIndex: 0, importStatus: null, missingText: '', statusWarnings: [], reportError: '', reportWarnings: [] },
  onShow() { this.reload(); },
  async reload() {
    const token = {}; this.loadToken = token; this.queryToken = null;
    this.setData({ querying: false, state: 'loading', error: null, result: null, blocks: [], reports: [], reportIndex: 0,
      importStatus: null, missingText: '', statusWarnings: [], reportError: '', reportWarnings: [] });
    try {
      const plot = await ui.context(this); if (this.loadToken !== token) return;
      if (!plot) { this.setData({ state: 'empty', options: [] }); return; }
      const [r, lab, status] = await Promise.all([
        request({ url: '/api/data/catalog', data: { plot_id: plot.plot_id } }),
        request({ url: '/api/data/soil-reports', data: { plot_id: plot.plot_id } }).catch(() => ({ items: [], failed: true })),
        request({ url: '/api/data/import-status', data: { plot_id: plot.plot_id } }).catch(() => null)
      ]);
      if (this.loadToken !== token) return;
      const options = r.items.map(c => ({ ...c, label: (c.parameter_label || PARAMETERS[c.parameter] || c.parameter)
        + (c.depth_cm === null ? '' : ' · ' + c.depth_cm + 'cm')
        + ' · ' + (c.source_label || c.devices.join('/')) + ' · ' + (c.display_unit || c.unit || '单位未注明')
        + (c.usable_count === 0 ? '（待核查）' : '') }));
      const preferred = options.findIndex(c => c.parameter === 'soil_humidity_layer1_raw' && c.usable_count > 0);
      this.setData({ catalog: r.items, options, selected: 0, reports: (lab.items || []).map(s => ({ ...s, measurements: s.measurements.map(m => ({ ...m, displayValue: numberText(m.value) })) })),
        reportWarnings: lab.warnings || [], reportError: lab.failed ? '土壤检测报告加载失败，请重试' : '',
        importStatus: status, missingText: status ? (status.missing_fields || []).map(k => MISSING[k] || k).join('、') : '',
        statusWarnings: status ? status.warnings || [] : [], state: options.length || (lab.items || []).length ? 'ready' : 'empty' });
      if (options.length) this.setRange(preferred < 0 ? 0 : preferred);
    } catch (e) { if (this.loadToken === token) ui.fail(this, e); }
  },
  setRange(index) {
    this.queryToken = null;
    const c = this.data.options[index];
    const last = new Date(c.end + 'T00:00:00Z'); last.setUTCDate(last.getUTCDate() - 6);
    const recent = last.toISOString().slice(0, 10);
    this.setData({ selected: index, start: recent < c.start ? c.start : recent, end: c.end,
      result: null, blocks: [], querying: false });
  },
  select(e) { this.setRange(Number(e.detail.value)); },
  reportSelect(e) { this.setData({ reportIndex: Number(e.detail.value) }); },
  invalidate() { this.queryToken = null; this.setData({ querying: false, result: null, blocks: [] }); },
  dates(e) { this.invalidate(); this.setData({ [e.currentTarget.dataset.key]: e.detail.value }); },
  agg(e) { this.invalidate(); this.setData({ aggIndex: Number(e.detail.value) }); },
  flagged(e) { this.invalidate(); this.setData({ includeFlagged: e.detail.value }); },
  async query(event, offset = 0) {
    if (this.data.querying || !this.data.options.length) return;
    const token = {}; this.queryToken = token; this.setData({ querying: true, error: null });
    const c = this.data.options[this.data.selected];
    try {
      const data = { plot_id: this.data.plot.plot_id, parameter: c.parameter, depth_cm: c.depth_cm,
        start: this.data.start, end: this.data.end, agg: this.data.aggIndex ? 'raw' : 'daily_mean',
        include_flagged: this.data.includeFlagged, offset, limit: 500 };
      if (c.device_id) data.device_id = c.device_id;
      if (c.data_version) data.data_version = c.data_version;
      if (typeof c.unit === 'string') data.unit = c.unit;
      const r = await request({ url: '/api/data/query', method: 'POST', data });
      if (this.queryToken !== token) return;
      const labels = { n: '有效记录数', mean: '平均读数', min: '最小读数', max: '最大读数', missing_days: '无有效记录天数' };
      this.setData({ result: r, blocks: [
        ...Object.keys(labels).map(key => ({ type: 'fact', label: labels[key], value: r.outputs[key],
          unit: key === 'n' || key === 'missing_days' ? '' : r.units.value, evidence_id: r.evidence_id, source_type: r.source_type })),
        { type: 'chart', series: [{ name: c.label, data: r.outputs.series.map(s => [s.ts || s.date, s.value]) }], unit: r.units.value },
        { type: 'evidence', items: [{ evidence_id: r.evidence_id, label: r.source_type === 'demo' ? '演示' : '实测' }] },
        ...r.warnings.map(text => ({ type: 'warning', text }))
      ], state: 'ready' });
    } catch (e) { if (this.queryToken === token) ui.fail(this, e); }
    finally { if (this.queryToken === token) this.setData({ querying: false }); }
  },
  nextPage() { if (this.data.result && this.data.result.outputs.next_offset !== null) this.query(null, this.data.result.outputs.next_offset); },
  openEvidence(e) { ui.openEvidence(e.detail.evidence_id); },
  source(e) { ui.openEvidence('', e.currentTarget.dataset.id); },
  create() { wx.navigateTo({ url: '/pages/plots/plots' }); }
});
