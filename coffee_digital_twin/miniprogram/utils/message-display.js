// 只合并展示副本；原始 blocks、证据ID和完整精度保留。
const { formatValue, displayUnit, factLabel } = require('./format');
const STATS = ['mean', 'min', 'max', 'n', 'missing_days'];
const EXTRACT = /^以下为工程层从有效工具结果直接提取的数值摘要[:：]/;
// 通用免责提示统一由气泡底部“以上内容仅供参考”代替；工具失败等实际警告保留。
const DISCLAIMER = /待专业核验|专家审阅|语义正确|语义准确|仅供参考|不等于田间实测|不能直接形成|非实际灌溉指令/;
const CAVEAT = /。?请保留原任务假设；模拟、代理及简化模型不等于田间实测，不能直接形成实际水肥处方。?$/;
// 用户模式：去掉方括号内的机器编号（证据ID、文档编号），保留中文标注。
function stripIds(text) {
  const src = String(text || '');
  return src.replace(/\s*\[(?=[^\]]*[A-Za-z0-9_])[A-Za-z0-9_:.\-–,，\s]{4,}\]\s*/g, (m, offset) => {
    const before = src[offset - 1] || '', after = src[offset + m.length] || '';
    return /[A-Za-z0-9]/.test(before) && /[A-Za-z0-9]/.test(after) ? ' ' : '';
  }).replace(/\s+([，。；：！？])/g, '$1').trim();
}
// 业务层抽取式摘要 → 可读句子；有统计卡时直接省略。
function readableExtract(text) {
  const body = String(text).replace(EXTRACT, '').replace(CAVEAT, '');
  const parts = body.split('；').map(part => {
    const m = /^\s*([A-Za-z][A-Za-z0-9_]*)=([-+\d.eE]+)\s*([^\[]*?)\s*(\[[^\]]*\])?\s*$/.exec(part);
    if (!m) return stripIds(part);
    const unit = m[3].trim();
    const value = formatValue(Number(m[2]), unit);
    return factLabel(m[1]) + ' ' + value + (m[1] === 'n' ? ' 条' : displayUnit(unit) ? ' ' + displayUnit(unit) : '');
  }).filter(Boolean);
  return parts.length ? '本次查询结果：' + parts.join('；') + '。' : '';
}
function displayBlocks(blocks, hideMock, isDev = true) {
  const all = blocks || [], groups = new Map();
  all.forEach(b => {
    if (b.type === 'fact' && b.evidence_id && STATS.includes(b.label)) {
      const group = groups.get(b.evidence_id) || {}; group[b.label] = b; groups.set(b.evidence_id, group);
    }
  });
  const hasSummary = [...groups.values()].some(g => g.mean && g.n);
  const history = all.find(b => b.type === 'text' && /^历史观测：/.test(b.text || ''));
  const emitted = new Set(), result = [];
  all.forEach(b => {
    if (!isDev && ['warning', 'evidence', 'trace', 'check_items'].includes(b.type)) return;
    if (b.type === 'warning' && DISCLAIMER.test(b.text || '')) return;
    if (hideMock && b.type === 'warning' && /MOCK|规则生成/.test(b.text || '')) return;
    const group = groups.get(b.evidence_id);
    if (b.type === 'fact' && group && group.mean && group.n && STATS.includes(b.label)) {
      if (emitted.has(b.evidence_id)) return;
      emitted.add(b.evidence_id);
      const unit = group.mean.unit;
      result.push({ ...group.mean, type: 'fact_summary', meanText: formatValue(group.mean.value, unit),
        minText: formatValue(group.min && group.min.value, unit), maxText: formatValue(group.max && group.max.value, unit),
        countText: formatValue(group.n.value), missingDays: group.missing_days ? group.missing_days.value : 0, unit: displayUnit(unit),
        caption: !isDev && history ? history.text.replace(/^历史观测：\s*/, '') : '' });
      return;
    }
    if (b.type === 'text' && /^历史观测：/.test(b.text || '') && (emitted.size || (!isDev && hasSummary))) return;
    if (b.type === 'text' && !isDev) {
      let text = (b.text || '').replace(/^\[未核验\]\s*/, '');
      if (EXTRACT.test(text)) { if (hasSummary) return; text = readableExtract(text); }
      else text = stripIds(text);
      if (!text) return;
      result.push({ ...b, text });
      return;
    }
    result.push({ ...b });
  });
  // 用户模式隐藏了警告；若没有任何可显示的回答内容，给出原因，避免出现空气泡。
  if (!isDev && all.length && !result.some(b => ['text', 'fact_summary', 'fact', 'chart', 'missing', 'report_link'].includes(b.type))) {
    const warn = all.filter(b => b.type === 'warning');
    const why = warn.some(b => /needs_tool_evidence/.test(b.answer_status || '')) ? '这次没有查到可用数据，无法给出解释。可以补充深度和日期后再问。'
      : warn.some(b => /generation_check_failed/.test(b.answer_status || '')) ? '这次生成的回答没有通过核查，请换个问法或稍后再试。'
      : warn.some(b => /智能解释暂不可用|失败|超时/.test(b.text || '')) ? '智能解释服务暂时不可用，请稍后再试。'
      : '这次没有生成回答，请稍后再试。';
    result.push({ type: 'text', text: why, fallback: true });
  }
  const ordered = emitted.size ? [...result.filter(b => b.type === 'text'), ...result.filter(b => b.type !== 'text')] : result;
  return ordered.map((b, index) => ({ ...b, index, displayValue: formatValue(b.value, b.unit), label: factLabel(b.label),
    unit: displayUnit(b.unit), expanded: false, stepCount: (b.steps || []).filter(s => s.status === 'done' || s.status === 'saved').length }));
}
module.exports = { displayBlocks, stripIds };
