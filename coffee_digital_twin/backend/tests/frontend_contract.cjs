const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../miniprogram');
const { layout } = require(path.join(root, 'utils/chart'));
const { numberText, formatValue, displayUnit } = require(path.join(root, 'utils/format'));
assert.equal(numberText(0.23561887694145697), '0.24');
assert.equal(numberText(0), '0.00');
assert.equal(formatValue(10),'10');assert.equal(formatValue(1050),'1050');assert.equal(formatValue(124),'124');
assert.equal(formatValue(.2439032258,'moisture'),'0.24');assert.equal(formatValue(12.30),'12.3');
assert.equal(formatValue(null),'—');assert.equal(formatValue(-0),'0');
assert.equal(displayUnit('cm3/cm3'),'cm³/cm³');assert.equal(displayUnit('uS/cm'),'μS/cm');
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
const { organize } = require(path.join(root, 'utils/data-options'));
const options = organize([
 {parameter:'soil_humidity_layer1_raw',depth_top_cm:0,depth_bottom_cm:15,display_source:'土壤监测点1'},
 {parameter:'soil_humidity_layer3_raw',depth_top_cm:30,depth_bottom_cm:45,display_source:'土壤监测点2'},
 {parameter:'air_temperature',depth_cm:null,display_source:'基地气象站'},
 {parameter:'air_pressure_raw',hidden_reason:'仅一条原始记录'}
]);
assert.equal(options.groups.length,2);assert.equal(options.options.length,3);
assert.equal(options.groups[0].indexes.join(','),'0,1');assert.equal(options.options[1].label,'30–45cm · 土壤监测点2');
const { evidenceLabel } = require(path.join(root, 'utils/labels'));
const { localISO, shiftISO } = require(path.join(root, 'utils/dates'));
assert.equal(localISO(new Date(2026, 8, 1)), '2026-09-01');
assert.equal(shiftISO('2026-01-02', -6), '2025-12-27');
assert.equal(evidenceLabel('observation', 'failed').text, '不可用');
assert(evidenceLabel('simulation_uncalibrated', 'replay').text.includes('回放'));
assert.equal(evidenceLabel('proxy_model', 'fallback').text, '演示数据');
assert.equal(evidenceLabel('internal_tool_description').text, '工具说明');
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
      setInterval: () => 1, clearInterval: () => {}, Date, wx: { navigateTo() {}, switchTab() {}, showToast() {} }
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
  advice.data.typing = false;
  advice.data.pending = {message:'旧查询待补条件'};
  advice.setEntryMode('knowledge');
  await advice.sendMessage('咖啡叶片营养采样需要记录哪些信息？');
  assert.equal(replies[2].entry_mode,'knowledge');assert.equal(replies[2].supplement,null);
  assert.equal(replies[2].message,'咖啡叶片营养采样需要记录哪些信息？');assert.equal(replies[2].history.length,0);
  let modelQuestion;
  const modelPage=definition('result',{'../../utils/session':{setPendingQuestion:value=>{modelQuestion=value;}}});
  modelPage.taskId='case_original_record';modelPage.data.tools=[{name:'hydrus',available:true}];modelPage.goAdvice();
  assert.equal(modelQuestion.supplement.task_id,'case_original_record');assert.equal(modelQuestion.supplement.tool,'hydrus');
  const modelReplies=[];
  const modelAdvice=definition('advice',{
    '../../utils/request':{request:async o=>{modelReplies.push(o.data);return {turn_id:'tm',blocks:[]};}},
    '../../utils/page':{defaults:{},context:async()=>({plot_id:'p'}),fail:()=>{throw Error('model advice failed');}},
    '../../utils/session':{consumePendingQuestion:()=>modelQuestion,getSessionId:()=>'s-model',resetSession:()=>{}}
  });
  await modelAdvice.onShow();
  assert.equal(modelReplies[0].entry_mode,'auto');assert.equal(modelReplies[0].supplement.task_id,'case_original_record');
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
  const historical=definition('scenario',{
    '../../utils/page':{defaults:{health:{}},context:async()=>({plot_id:'p'}),fail:()=>{throw Error('historical range failed');}},
    '../../utils/request':{request:async()=>({items:[{parameter:'soil_humidity_layer1_raw',device_id:'source:soil1',usable_count:10,start:'2026-05-10',end:'2026-06-15',valid_start:'2026-05-11',valid_end:'2026-06-15'}]})}
  });
  await historical.reload();assert.equal(historical.data.start,'2026-06-09');assert.equal(historical.data.maxStart,'2026-06-09');assert.equal(historical.data.minStart,'2026-05-11');
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
  const weatherRequests=[];
  const weatherPage=definition('data',{
    '../../utils/page':{defaults:{}},
    '../../utils/request':{request:async o=>{weatherRequests.push(o);return {
      items:[{date:'2024-01-01',ts:'2024-01-01T00:00:00',tavg:12.3,rain_mm:2.5,radiation_mj:15}],warnings:[]};}}
  });
  Object.assign(weatherPage.data,{plot:{plot_id:'p'},weatherDaily:{start:'2006-01-01',end:'2025-12-31'},weatherStart:'2024-01-01',weatherEnd:'2024-01-01'});
  await weatherPage.queryWeather();
  assert.equal(weatherRequests[0].data.plot_id,'p');assert.equal(weatherRequests[0].data.resolution,'daily');
  assert.equal(weatherPage.data.weatherSeries[0].data[0][1],2.5);
  weatherPage.weatherDates({currentTarget:{dataset:{key:'weatherStart'}},detail:{value:'2024-02-01'}});
  assert.equal(weatherPage.data.weatherResult,null);
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

const {displayBlocks}=require(path.join(root,'utils/message-display'));
const stats=['mean','min','max','n','missing_days'].map((label,i)=>({type:'fact',label,value:[.2439032258,.18,.28,837,0][i],unit:i<3?'cm3/cm3':'',evidence_id:'ev-a'}));
const original=JSON.stringify(stats);const compact=displayBlocks(stats,false);
assert.equal(compact.length,1);assert.equal(compact[0].meanText,'0.24');assert.equal(compact[0].countText,'837');assert.equal(compact[0].missingDays,0);
assert.equal(JSON.stringify(stats),original);
assert.equal(displayBlocks([...stats,...stats.map(x=>({...x,evidence_id:'ev-b'}))],false).length,2);

const {TOOL_NAMES}=require(path.join(root,'utils/labels'));assert.equal(TOOL_NAMES.hydrus,'HYDRUS-1D 土壤水分');assert.equal(TOOL_NAMES.beps,'BEPS-Lite');

// User mode changes presentation only; saved blocks and precision remain intact.
const mode=require(path.join(root,'utils/viewMode'));
const values=new Map();wx.getStorageSync=key=>values.get(key);wx.setStorageSync=(key,value)=>values.set(key,value);
assert.equal(mode.getMode(),'user');let changes=[];const unsubscribe=mode.subscribe(value=>changes.push(value));
for(let i=0;i<4;i++)assert.equal(mode.tapBase(1000+i*100),false);
assert.equal(mode.getMode(),'user');assert.equal(mode.tapBase(1400),true);assert.equal(mode.getMode(),'dev');
for(let i=0;i<5;i++)mode.tapBase(1500+i*100);
assert.equal(mode.getMode(),'user');assert.deepEqual(changes,['dev','user']);unsubscribe();
mode.tapBase(2000);mode.tapBase(5000);assert.equal(mode.getMode(),'user');
const modeBlocks=[...stats,{type:'text',text:'[未核验] 需要连接知识服务'},
 {type:'warning',text:'MOCK'}, {type:'evidence',items:[{evidence_id:'ev-a'}]}, {type:'trace',trace_id:'trace-a'},
 {type:'missing',question:'请补充深度',quick_replies:['0–15cm','30–45cm']}];
const originalBlocks=JSON.stringify(modeBlocks);
const userBlocks=displayBlocks(modeBlocks,false,false),devBlocks=displayBlocks(modeBlocks,false,true);
assert(!userBlocks.some(b=>['warning','evidence','trace'].includes(b.type)));
assert.equal(userBlocks.find(b=>b.type==='text').text,'需要连接知识服务');
assert.equal(userBlocks.find(b=>b.type==='missing').quick_replies[1],'30–45cm');
assert(devBlocks.some(b=>b.type==='evidence'));assert(devBlocks.some(b=>b.type==='trace'));assert(devBlocks.some(b=>b.type==='warning'));
assert.equal(JSON.stringify(modeBlocks),originalBlocks);
// The standard WeChat Behavior constructor is used when available.
let behaviorDefinition;
global.Behavior=d=>{behaviorDefinition=d;return 'registered-view-mode';};
delete require.cache[require.resolve(path.join(root,'utils/viewMode'))];
const registeredMode=require(path.join(root,'utils/viewMode'));
assert.equal(registeredMode.behavior,'registered-view-mode');let componentData={};
const modeComponent={setData:data=>Object.assign(componentData,data)};
behaviorDefinition.lifetimes.attached.call(modeComponent);assert.equal(componentData.isDev,false);
registeredMode.setMode('dev');assert.equal(componentData.isDev,true);
behaviorDefinition.lifetimes.detached.call(modeComponent);registeredMode.setMode('user');
assert.equal(componentData.isDev,true);delete global.Behavior;

const reportDisplay=require(path.join(root,'utils/report-display'));
const rawReport=[{title:'依据',items:[{text:'ev-a'}]},{title:'缺项与限制',items:[{text:'假设'}]},
 {title:'情景差异',items:[{text:JSON.stringify({theta_day7_by_depth:{40:.01},root_uptake_ratio:.003})}]}];
const rawReportString=JSON.stringify(rawReport);const visibleReport=reportDisplay.userSections(rawReport);
assert.equal(visibleReport.length,1);assert(visibleReport[0].items[0].text.includes('40cm 含水率差值 0.01'));
assert.equal(JSON.stringify(rawReport),rawReportString);
