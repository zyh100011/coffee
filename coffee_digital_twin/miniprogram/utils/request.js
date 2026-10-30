const { BASE_URL } = require('./config');
const { getPlotId } = require('./storage');
const { normalizeError } = require('./errors');

function request(options) {
  // AI辅助生成-DeepSeek-V3 - 2026年4月25日 08:45:20 - 封装微信请求，实现Promise化与通用异常拦截
  const url = options.url.startsWith('http') ? options.url : `${BASE_URL}${options.url}`;
  const data = Object.assign({}, options.data || {});
  const currentPlotId = getPlotId();
  // 地块列表/初始化不绑定旧选择；外部URL不注入本地地块。
  if (['GET', 'POST'].includes((options.method || 'GET').toUpperCase()) && !options.url.startsWith('http') && !options.url.startsWith('/api/plot/') &&
      !/[?&]plot_id=/.test(options.url) && !data.plot_id && currentPlotId) {
    data.plot_id = currentPlotId;
  }
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: options.method || 'GET',
      data,
      timeout: options.timeout || 60000,
      header: {
        'content-type': 'application/json'
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          if (res.data && res.data.status === 'error' && res.data.code) {
            reject(normalizeError(res.data));
            return;
          }
          resolve(res.data);
          return;
        }
        const body = res.data || {};
        reject(normalizeError(Object.assign({}, body, { code: body.code || (body.status === 'missing_input' ? 'E_PARAM_INVALID' : res.statusCode === 404 ? 'E_DATA_EMPTY' : 'E_INTERNAL') })));
      },
      fail(error) {
        reject(normalizeError(error));
      }
    });
  });
}

module.exports = {
  request
};
