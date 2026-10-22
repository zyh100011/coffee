// Display precision only; source values and calculations retain full precision.
function numberText(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'number') return value;
  if (!Number.isFinite(value)) return '—';
  return (Object.is(value, -0) ? 0 : value).toFixed(2);
}
module.exports = { numberText };
