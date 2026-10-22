const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../miniprogram');
const { layout } = require(path.join(root, 'utils/chart'));
const { numberText } = require(path.join(root, 'utils/format'));
assert.equal(numberText(0.23561887694145697), '0.24');
assert.equal(numberText(0), '0.00');
assert.equal(numberText(null), '—');
const precise = layout([{data:[['2026-06-09',0.23561887694145697]]}]);
assert.equal(precise.rows[0].value, '0.24');
assert.equal(precise.lines[0].data[0][1], 0.23561887694145697);
assert.equal(layout([]).empty, true);
const single = layout([{ data: [['2026-09-01', 0.21]] }]);
assert(single.min < 0.21 && single.max > 0.21);
const multiple = layout([{ name: 'A', data: [['1', 0.2], ['2', null]] }, { name: 'B', data: [['1', 0.4], ['2', 0.3]] }]);
assert.equal(multiple.lines.length, 2); assert.equal(multiple.rows[1].value, '缺测');
assert(multiple.min < 0.2 && multiple.max > 0.4);
const { evidenceLabel } = require(path.join(root, 'utils/labels'));
const { localISO, shiftISO } = require(path.join(root, 'utils/dates'));
assert.equal(localISO(new Date(2026, 8, 1)), '2026-09-01');
assert.equal(shiftISO('2026-01-02', -6), '2025-12-27');
assert.equal(evidenceLabel('observation', 'failed').text, '不可用');
assert(evidenceLabel('simulation_uncalibrated', 'replay').text.includes('回放'));
assert.equal(evidenceLabel('proxy_model', 'fallback').text, '演示数据');
global.getApp = () => ({ globalData: { plotId: 'p' } });
let captured;
global.wx = { getStorageSync: () => 'p', request: options => { captured = options; options.success({ statusCode: 200, data: {} }); } };
const { request } = require(path.join(root, 'utils/request'));
async function main() {
  await request({ url: '/api/data/catalog' }); assert.equal(captured.data.plot_id, 'p');
  await request({ url: '/api/plot/list' }); assert.equal(captured.data.plot_id, undefined);
  await request({ url: '/api/data/query', method: 'POST', data: { plot_id: 'q' } }); assert.equal(captured.data.plot_id, 'q');
  await request({ url: '/api/x', method: 'PUT' }); assert.equal(captured.data.plot_id, undefined);
  wx.request = o => o.fail({ errMsg: 'request:fail timeout' });
  await assert.rejects(request({ url: '/api/x' }), e => e.code === 'E_REQUEST_TIMEOUT' && e.retryable);
  wx.request = o => o.fail({ errMsg: 'request:fail connection' });
  await assert.rejects(request({ url: '/api/x' }), e => e.code === 'E_OFFLINE');
  wx.request = o => o.success({ statusCode: 400, data: { code: 'E_PARAM_INVALID', message: 'invalid', retryable: false } });
  await assert.rejects(request({ url: '/api/x' }), e => e.code === 'E_PARAM_INVALID' && !e.retryable);
  wx.request = o => o.success({ statusCode: 200, data: { status: 'error', code: 'E_TOOL_NOT_ALLOWED', retryable: false, trace_id: 'tr_error' } });
  await assert.rejects(request({url:'/api/x'}), e => e.code === 'E_TOOL_NOT_ALLOWED' && e.trace_id === 'tr_error');
  for (const dir of fs.readdirSync(path.join(root, 'components'))) {
    const file = path.join(root, 'components', dir, dir + '.json');
    assert.equal(JSON.parse(fs.readFileSync(file)).component, true);
  }
  const definition = (name, overrides) => {
    let page;
    vm.runInNewContext(fs.readFileSync(path.join(root, `pages/${name}/${name}.js`), 'utf8'), {
      Page: value => { page = value; }, require: rel => overrides[rel] || require(path.resolve(root, 'pages', name, rel)),
      setInterval: () => 1, clearInterval: () => {}, Date, wx: { navigateTo() {} }
    });
    page.data = structuredClone(page.data);
    page.setData = data => Object.assign(page.data, data);
    return page;
  };
  const replies = [];
  const advice = definition('advice', { '../../utils/request': { request: async options => {
    replies.push(options.data);
    return replies.length === 1 ? { turn_id: 't1', trace_id: 'tr1', blocks: [{ type: 'missing', fields: ['start'], question: '日期?' }] } :
      { turn_id: 't2', trace_id: 'tr2', blocks: [{ type: 'text', text: 'verified result' }] };
  } } });
  advice.plotId = 'p';
  await advice.sendMessage('40cm含水率');
  assert.equal(advice.data.pending.message, '40cm含水率');
  await advice.sendMessage('最近7天');
  assert.equal(replies[1].message, '40cm含水率'); assert.equal(replies[1].supplement.text, '最近7天');
  assert.equal(advice.data.pending, null); assert.equal(advice.data.history.length, 4);
  advice.data.typing = true; await advice.sendMessage('duplicate'); assert.equal(replies.length, 2);
  let finish;
  const stale = definition('advice', {
    '../../utils/request': { request: () => new Promise(resolve => { finish = resolve; }) },
    '../../utils/page': { defaults: {}, context: async () => ({ plot_id: 'q' }), fail: () => { throw Error('stale error'); } }
  });
  stale.plotId = 'p';
  const flight = stale.sendMessage('old plot question');
  await stale.reload();
  assert.equal(stale.data.lastRequest, null); assert.equal(stale.data.typing, false);
  finish({ turn_id: 'old', blocks: [{ type: 'text', text: 'old result' }] });
  await flight; assert.deepEqual(Array.from(stale.data.messages), []);
  const comparisonRequests=[];
  const scenario=definition('scenario',{
    '../../utils/page':{defaults:{},context:async()=>({plot_id:'p'}),fail:(page,error)=>page.setData({error})},
    '../../utils/request':{request:async o=>{comparisonRequests.push(o.data);return o.data.confirm?{compare_id:'cmp_test',status:'success',parameter_verified:true,mode:o.data.mode}:{status:'confirmation_required',mode:o.data.mode,confirmation:{baseline:'backend baseline'}};}}
  });
  scenario.plotId='p'; scenario.data.start='2026-09-01';
  await scenario.next(); assert.equal(scenario.data.step,2);
  assert.equal(comparisonRequests[0].confirm,false);
  assert.equal(scenario.data.preview.confirmation.baseline,'backend baseline');
  await scenario.confirm(); assert.equal(scenario.data.step,3); assert(scenario.data.result.parameter_verified);
  await scenario.replay(); assert.equal(scenario.data.step,2);assert.equal(comparisonRequests[2].mode,'replay');assert.equal(comparisonRequests[2].confirm,false);
  scenario.back();scenario.data.amount='';await scenario.next(); assert(scenario.data.fieldError);assert.equal(comparisonRequests.length,3);
  const dataRequests=[]; let completeData;
  const dataPage=definition('data',{
    '../../utils/page':{defaults:{},context:async page=>{page.setData({plot:{plot_id:'p'}});return {plot_id:'p'};},fail:(page,error)=>page.setData({error})},
    '../../utils/request':{request:async o=>{
      if(o.url.endsWith('/catalog'))return {items:[{parameter:'soil_humidity_layer1_raw',parameter_label:'第1层湿度',depth_cm:null,device_id:'source:lujiangba:soil1',devices:['source:lujiangba:soil1'],source_label:'土壤1',data_version:'real-v1',unit:'%RH',usable_count:10,start:'2026-05-10',end:'2026-06-15'}]};
      if(o.url.endsWith('/soil-reports'))return {items:[]};
      if(o.url.endsWith('/import-status'))return {missing_fields:['soil_humidity_basis']};
      dataRequests.push(o.data);return new Promise(resolve=>{completeData=resolve;});
    }}
  });
  await dataPage.reload();assert.equal(dataPage.data.start,'2026-06-09');assert.equal(dataPage.data.end,'2026-06-15');
  const dataFlight=dataPage.query();
  assert.equal(dataRequests[0].device_id,'source:lujiangba:soil1');assert.equal(dataRequests[0].unit,'%RH');assert.equal(dataRequests[0].data_version,'real-v1');
  dataPage.select({detail:{value:0}});completeData({outputs:{},warnings:[]});await dataFlight;
  assert.equal(dataPage.data.result,null);assert.equal(dataPage.data.querying,false);
  const app = JSON.parse(fs.readFileSync(path.join(root, 'app.json')));
  assert(!app.pages.includes('pages/_dev/_dev'));
  for (const name of app.pages) {
    for (const ext of ['js', 'json', 'wxml', 'wxss']) assert(fs.existsSync(path.join(root, name + '.' + ext)));
  }
  for (const target of Object.values(app.usingComponents)) {
    const config = JSON.parse(fs.readFileSync(path.join(root, target + '.json')));
    assert.equal(config.component, true);
  }
  console.log('frontend behavior contract passed');
}
main().catch(e => { console.error(e); process.exitCode = 1; });
