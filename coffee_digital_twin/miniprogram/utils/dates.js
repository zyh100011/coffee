// Local calendar dates without locale-dependent formatting.
function localISO(value) {
  const d = value || new Date();
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');
}
function shiftISO(value, days) {
  const parts = value.split('-').map(Number);
  const d = new Date(parts[0], parts[1] - 1, parts[2]);
  d.setDate(d.getDate() + days);
  return localISO(d);
}
module.exports = { localISO, shiftISO };
