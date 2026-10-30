const { formatValue, displayUnit } = require('../../utils/format');
const { request } = require('../../utils/request');
const ui = require('../../utils/page');
const { PARAMETERS } = require('../../utils/labels');
const { organize } = require('../../utils/data-options');
const MISSING = {
  irrigation_event_dates_and_amounts: '逐次灌溉日期与用量', fertilizer_event_dates_and_amounts: '逐次施肥日期与用量',
  soil_bulk_density: '土壤容重', soil_texture: '土壤质地', soil_hydraulic_parameters: '土壤水力参数',
  sensor_calibration: '土壤湿度探头标定资料',
  actual_probe_depths: '探头实际埋深', soil_humidity_basis: '湿度百分比定义',
  station_hardware_ids_and_pairing: '监测来源的设备编号和配对', rainfall_accumulation_mode: '降雨累计方式',
  site_hydraulic_calibration: '本站土壤水力参数校准', irrigation_records: '实际灌溉记录',
  fertilizer_records: '实际施肥记录', tree_age: '树龄', area_mu: '面积', coordinates: '经纬度',
  shade_level: '遮阴情况', plant_spacing: '株行距', soil_report_sample_date: '土壤报告采样日期',
  soil_report_sample_depth: '土壤报告采样深度'
};
Page({
  data: { ...ui.defaults, catalog: [], options: [], groups: [], groupIndex: 0, variants: [], variantIndex: 0, notesOpen: false, allSamplesOpen: false, methodId: '', selected: 0, start: '', end: '', aggIndex: 0,
    aggs: ['日均读数', '原始记录'], result: null, blocks: [], querying: false, includeFlagged: false,
    reports: [], reportIndex: 0, importStatus: null, missingText: '', statusWarnings: [], reportError: '', reportWarnings: [],
    weatherCatalog: [], weatherStart: '', weatherEnd: '', weatherResult: null, weatherSeries: [],
    weatherQuerying: false, weatherError: '' },
  onShow() { this.reload(); },
  async reload() {
    const token = {}; this.loadToken = token; this.queryToken = null;
    this.weatherToken = null;
    this.setData({ querying: false, state: 'loading', error: null, result: null, blocks: [], reports: [], reportIndex: 0,
      importStatus: null, missingText: '', statusWarnings: [], reportError: '', reportWarnings: [],
      weatherCatalog: [], weatherDaily: null, weatherRows: [], weatherResult: null, weatherSeries: [], weatherQuerying: false, weatherError: '' });
    try {
      const plot = await ui.context(this); if (this.loadToken !== token) return;
      if (!plot) { this.setData({ state: 'empty', options: [] }); return; }
      const [r, lab, status, weather] = await Promise.all([
        request({ url: '/api/data/catalog', data: { plot_id: plot.plot_id } }),
        request({ url: '/api/data/soil-reports', data: { plot_id: plot.plot_id } }).catch(() => ({ items: [], failed: true })),
        request({ url: '/api/data/import-status', data: { plot_id: plot.plot_id } }).catch(() => null),
        request({ url: '/api/data/historical-weather/catalog', data: { plot_id: plot.plot_id } }).catch(() => ({ items: [], failed: true }))
      ]);
      if (this.loadToken !== token) return;
      this.rawCatalog=r.items;
      const { options, groups } = organize(this.visibleCatalog(r.items));
      const preferred = options.findIndex(c => c.parameter === 'soil_humidity_layer1_raw' && c.usable_count > 0);
      const weatherDaily = (weather.items || []).find(c => c.resolution === 'daily');
      let weatherStart = '';
      if (weatherDaily) {
        const last = new Date(weatherDaily.end + 'T00:00:00Z'); last.setUTCDate(last.getUTCDate() - 6);
        weatherStart = last.toISOString().slice(0, 10);
        if (weatherStart < weatherDaily.start) weatherStart = weatherDaily.start;
      }
      this.setData({ catalog: r.items, options, groups, selected: 0, reports: (lab.items || []).map(s => ({ ...s, measurements: s.measurements.map(m => ({ ...m, displayValue: formatValue(m.value), displayUnit: m.unit === '无量纲' ? '' : displayUnit(m.unit), displayItem: m.item.replace(/（[^）]*）/g, '') })) })),
        reportIndex: Math.max(0, (lab.items || []).findIndex(s => s.is_representative)), reportWarnings: lab.warnings || [], reportError: lab.failed ? '土壤检测报告加载失败，请重试' : '',
        importStatus: status, missingText: status ? (status.missing_fields || []).map(k => MISSING[k] || k).join('、') : '',
        statusWarnings: status ? status.warnings || [] : [], state: options.length || (lab.items || []).length || weatherDaily ? 'ready' : 'empty',
        weatherCatalog: weather.items || [], weatherDaily: weatherDaily || null,
        weatherStart, weatherEnd: weatherDaily ? weatherDaily.end : '',
        weatherError: weather.failed ? '历史气象加载失败，请重试' : '' });
      if (options.length) this.setRange(preferred < 0 ? 0 : preferred);
    } catch (e) { if (this.loadToken === token) ui.fail(this, e); }
  },
  visibleCatalog(items) { return this.data.isDev ? items : items.filter(c=>c.parameter!=='rainfall_raw'); },
  setRange(index) {
    this.queryToken = null;
    const c = this.data.options[index];
    const last = new Date((c.valid_end || c.end) + 'T00:00:00Z'); last.setUTCDate(last.getUTCDate() - 6);
    const recent = last.toISOString().slice(0, 10);
    const groupIndex = this.data.groups.findIndex(g => g.indexes.includes(index));
    const indexes = this.data.groups[groupIndex].indexes;
    this.setData({ groupIndex, variants: indexes.map(i => this.data.options[i]), variantIndex: indexes.indexOf(index), selected: index, start: recent < (c.valid_start || c.start) ? (c.valid_start || c.start) : recent, end: c.valid_end || c.end,
      result: null, blocks: [], querying: false });
  },
  select(e) { const group = this.data.groups[this.data.groupIndex]; this.setRange(group.indexes[Number(e.detail.value)]); },
  selectGroup(e) { this.setRange(this.data.groups[Number(e.detail.value)].indexes[0]); },
  toggleNotes() { this.setData({ notesOpen: !this.data.notesOpen }); },
  method(e) { const id=e.currentTarget.dataset.id; this.setData({ methodId: this.data.methodId===id?'':id }); },
  rawRecords() { if(this.data.result) ui.openEvidence(this.data.result.evidence_id); },
  toggleSamples() { this.setData({ allSamplesOpen: !this.data.allSamplesOpen }); },
  reportSelect(e) { this.setData({ reportIndex: Number(e.detail.value) }); },
  weatherDates(e) {
    this.weatherToken = null;
    this.setData({ [e.currentTarget.dataset.key]: e.detail.value, weatherResult: null, weatherSeries: [], weatherQuerying: false });
  },
  async queryWeather() {
    if (this.data.weatherQuerying || !this.data.weatherDaily) return;
    const token = {}; this.weatherToken = token;
    this.setData({ weatherQuerying: true, weatherError: '', weatherResult: null });
    try {
      const r = await request({ url: '/api/data/historical-weather/query', method: 'POST', data: {
        plot_id: this.data.plot.plot_id, resolution: 'daily', start: this.data.weatherStart, end: this.data.weatherEnd
      } });
      if (this.weatherToken !== token) return;
      this.setData({ weatherResult: r, weatherSeries: [{ name: '日降雨', data: r.items.map(s => [s.date, s.rain_mm]) }],
        weatherRows: r.items.map(s => ({ ...s, tavgText: formatValue(s.tavg), rainText: formatValue(s.rain_mm), radiationText: formatValue(s.radiation_mj) })) });
    } catch (e) { if (this.weatherToken === token) this.setData({ weatherError: e.message || '历史气象查询失败，请检查日期后重试' }); }
    finally { if (this.weatherToken === token) this.setData({ weatherQuerying: false }); }
  },
  invalidate() { this.queryToken = null; this.setData({ querying: false, result: null, blocks: [] }); },
  dates(e) { this.invalidate(); this.setData({ [e.currentTarget.dataset.key]: e.detail.value }); },
  agg(e) { this.invalidate(); this.setData({ aggIndex: Number(e.detail.value) }); },
  flagged(e) { this.invalidate(); this.setData({ includeFlagged: e.detail.value }); },
  async query(event, offset = 0) {
    if (this.data.querying || !this.data.options.length) return;
    const token = {}; this.queryToken = token; this.setData({ querying: true, error: null });
    const c = this.data.options[this.data.selected];
    try {
      const daily=c.parameter==='rainfall_daily';
      const data = { plot_id: this.data.plot.plot_id, parameter: c.parameter, depth_cm: c.depth_cm,
        start: this.data.start, end: this.data.end, agg: daily ? 'daily_mean' : this.data.aggIndex ? 'raw' : 'daily_mean',
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
        { type: 'evidence', items: [{ evidence_id: r.evidence_id, label: r.source_type === 'demo' ? '演示' : '实测', display_source: c.label }] }
      ], state: 'ready' });
    } catch (e) { if (this.queryToken === token) ui.fail(this, e); }
    finally { if (this.queryToken === token) this.setData({ querying: false }); }
  },
  nextPage() { if (this.data.result && this.data.result.outputs.next_offset !== null) this.query(null, this.data.result.outputs.next_offset); },
  openEvidence(e) { ui.openEvidence(e.detail.evidence_id); },
  source(e) { ui.openEvidence('', e.currentTarget.dataset.id); },
  create() { wx.navigateTo({ url: '/pages/plots/plots' }); }
});
