const { numberText, displayUnit, formatValue } = require('../../utils/format');
// 纵轴刻度按跨度取小数位，窄范围时避免四个刻度都显示同一个数。
function tickText(v, span) {
  const step = span / 3, d = step >= 0.01 ? 2 : Math.min(4, Math.ceil(-Math.log10(step)) + 1);
  return Number.isFinite(v) ? (Object.is(v, -0) ? 0 : v).toFixed(Math.max(2, d)) : '—';
}
const { layout } = require('../../utils/chart');
// 用普通 view 绘制折线：随页面滚动，不使用原生 canvas 层，避免在 scroll-view 中漂移。
const PAD = { left: 40, right: 10, top: 10, bottom: 24 };
function windowWidth() { try { return (wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()).windowWidth || 375; } catch (e) { return 375; } }
function thin(data, limit) {
  if (data.length <= limit) return data;
  const step = data.length / limit, out = [];
  for (let i = 0; i < limit; i++) out.push(data[Math.floor(i * step)]);
  out[out.length - 1] = data[data.length - 1];
  return out;
}
function draw(model, width, height) {
  const w = Math.max(width - PAD.left - PAD.right, 40), h = Math.max(height - PAD.top - PAD.bottom, 40);
  const span = model.max - model.min || 1;
  const index = new Map(model.xs.map((x, i) => [x, i]));
  const xpos = x => PAD.left + (model.xs.length === 1 ? w / 2 : index.get(x) * w / (model.xs.length - 1));
  const ypos = y => PAD.top + (model.max - y) * h / span;
  const r1 = v => Math.round(v * 10) / 10;
  const grid = [0, 1, 2, 3].map(i => ({ top: r1(PAD.top + h * i / 3), label: tickText(model.max - span * i / 3, span) }));
  const segs = [], dots = [];
  model.lines.forEach((line, li) => {
    const points = thin(line.data, 120);
    let prev = null;
    points.forEach(([x, y]) => {
      if (y === null) { prev = null; return; }
      const p = [xpos(x), ypos(y)];
      if (prev) {
        const dx = p[0] - prev[0], dy = p[1] - prev[1];
        segs.push({ left: r1(prev[0]), top: r1(prev[1]), len: r1(Math.sqrt(dx * dx + dy * dy)), deg: r1(Math.atan2(dy, dx) * 180 / Math.PI), color: line.color });
      }
      if (points.length <= 31) dots.push({ left: r1(p[0]), top: r1(p[1]), color: line.color });
      prev = p;
    });
  });
  const xs = model.xs, ticks = [];
  if (xs.length) {
    const label = x => (x.length >= 10 ? x.slice(5, 10) : x);
    const picks = xs.length <= 3 ? xs.map((_, i) => i) : [0, Math.round((xs.length - 1) / 2), xs.length - 1];
    picks.forEach((i, n) => ticks.push({ left: r1(xpos(xs[i])), text: label(xs[i]), align: n === 0 && picks.length > 1 ? 'start' : n === picks.length - 1 && picks.length > 1 ? 'end' : 'mid' }));
  }
  return { grid, segs, dots, ticks, plotLeft: PAD.left, plotRight: PAD.right };
}
Component({
  options: { styleIsolation: 'apply-shared' },
  properties: { series: { type: Array, value: [] }, unit: String, yMin: { type: null, value: null }, yMax: { type: null, value: null }, height: { type: Number, value: 420 }, compact: Boolean },
  data: { table: false, rows: [], legend: [], empty: true, grid: [], segs: [], dots: [], ticks: [], heightPx: 210, unitText: '' },
  observers: { 'series,unit,yMin,yMax,height': function () { if (this._ready) this.update(); } },
  lifetimes: {
    ready() { this._ready = true; this.update(); this.measure(); },
    detached() { this._ready = false; }
  },
  methods: {
    toggle() { this.setData({ table: !this.data.table }); },
    measure() {
      const query = wx.createSelectorQuery().in(this);
      query.select('#plot').boundingClientRect(rect => {
        if (this._ready && rect && rect.width && Math.abs(rect.width - (this._width || 0)) > 1) { this._width = rect.width; this.update(); }
      }).exec();
    },
    update() {
      const model = layout(this.data.series, this.data.yMin, this.data.yMax);
      const ww = windowWidth();
      const heightPx = Math.round(this.data.height * ww / 750);
      const width = this._width || ww - 64;
      const legend = model.lines.map(l => ({ name: l.name, color: l.color }));
      const view = model.empty ? { grid: [], segs: [], dots: [], ticks: [] } : draw(model, width, heightPx);
      this.setData({ unitText: displayUnit(this.data.unit), rows: model.rows, legend, empty: model.empty, heightPx, ...view });
    }
  }
});
