const ERRORS = {
  E_PLOT_REQUIRED: ['请选择当前地块', false], E_PARAM_INVALID: ['请核对输入条件', false],
  E_TOOL_NOT_ALLOWED: ['工具请求未被允许', false], E_HYDRUS_TIMEOUT: ['计算超时，已保留输入，可重试或改用历史结果', true],
  E_HYDRUS_FAILED: ['HYDRUS 计算失败，请查看原因', true], E_HYDRUS_UNAVAILABLE: ['HYDRUS 引擎不可用，可使用历史回放', true],
  E_EVIDENCE_TIMEOUT: ['本地循证服务超时，可重试', true], E_EVIDENCE_DOWN: ['智能解释暂不可用，可直接查询农情', true],
  E_EVIDENCE_INVALID: ['循证服务响应格式不符', true], E_EVIDENCE_NOT_FOUND: ['证据未找到：该主张未核验', false],
  E_DATA_EMPTY: ['该地块暂无已入库的数据', false], E_INTERNAL: ['服务暂时出错，请重试', true],
  E_OFFLINE: ['后端未连接，请检查电脑与手机在同一网络、BASE_URL 是否正确', true],
  E_REQUEST_TIMEOUT: ['计算超时，已保留输入，可重试或改用历史结果', true]
};
function normalizeError(error) {
  error = error || {};
  const code = error.code || (String(error.errMsg || '').includes('timeout') ? 'E_REQUEST_TIMEOUT' : 'E_OFFLINE');
  const preset = ERRORS[code] || ['请求失败，请查看错误原因', true];
  return { code, message: error.message || preset[0], retryable: typeof error.retryable === 'boolean' ? error.retryable : preset[1], trace_id: error.trace_id || null };
}
module.exports = { ERRORS, normalizeError };
