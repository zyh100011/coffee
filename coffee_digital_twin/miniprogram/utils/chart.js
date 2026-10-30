const { formatValue } = require('./format');
// Pure chart layout: gaps stay gaps; non-finite values never become zero.
function layout(series, yMin, yMax) {
  const lines = (series || []).slice(0, 3).map((line, index) => ({ name: line.name || `序列${index + 1}`, color: line.color || ['#1f5a3a', '#5f6b63', '#1d4f91'][index], data: (line.data || []).filter(p => Array.isArray(p) && p.length >= 2).map(p => [String(p[0]), typeof p[1] === 'number' && Number.isFinite(p[1]) ? p[1] : null]) }));
  const xs = [...new Set(lines.flatMap(line => line.data.map(p => p[0])))].sort();
  const ys = lines.flatMap(line => line.data.map(p => p[1])).filter(y => y !== null);
  if (!ys.length) return { lines, xs, min: 0, max: 1, rows: [], empty: true };
  let min = typeof yMin === 'number' ? yMin : Math.min(...ys);
  let max = typeof yMax === 'number' ? yMax : Math.max(...ys);
  const pad = max === min ? Math.max(Math.abs(max) * 0.1, 0.01) : (max - min) * 0.1;
  if (typeof yMin !== 'number') min -= pad;
  if (typeof yMax !== 'number') max += pad;
  if (max <= min) max = min + pad;
  const rows = lines.flatMap(line => line.data.map(p => ({ name: line.name, x: p[0], value: p[1] === null ? '缺测' : formatValue(p[1], 'moisture') })));
  return { lines, xs, min, max, rows, empty: false };
}
module.exports = { layout };
