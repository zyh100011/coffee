// 开发者工具使用loopback；真机选择同一可信局域网中的电脑IP。
// 复制为config.js后手工选择；不要放服务令牌。无鉴权，禁止公网隧道。
const ENV = 'dev';
const ENDPOINTS = {dev: 'http://127.0.0.1:5000', phone: 'http://192.168.1.100:5000'}; // phone为待替换的地址模板
module.exports = {BASE_URL: ENDPOINTS[ENV]};
