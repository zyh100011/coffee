// 本届 T4.2：沿用旧原生框架，改为确认式灌溉情景向导。
const {formatValue}=require('../../utils/format');
const {request}=require('../../utils/request');
const ui=require('../../utils/page');
const session=require('../../utils/session');
const {shiftISO}=require('../../utils/dates');
Page({
 data:{...ui.defaults,step:1,start:'',minStart:'',maxStart:'',dataEnd:'',amount:'20',sliderValue:20,preview:null,result:null,running:false,mode:'live',fieldError:'',creatingReport:false},
 onShow(){this.reload();},onHide(){this.loadToken=null;this.token=null;this.setData({running:false});},
 async reload(){
  const load={};this.loadToken=load;this.setData({state:'loading',error:null});
  try{
   const plot=await ui.context(this);if(this.loadToken!==load)return;
   const id=plot?plot.plot_id:'';const changed=this.plotId!==id;
   if(changed){this.token=null;this.setData({step:1,preview:null,result:null,running:false,fieldError:'',start:'',minStart:'',maxStart:'',dataEnd:''});}
   this.plotId=id;
   if(plot && (changed||!this.data.start)){
    const r=await request({url:'/api/data/catalog',data:{plot_id:id}});if(this.loadToken!==load)return;
    const candidates=(r.items||[]).filter(c=>c.usable_count>0 && !c.hidden_reason && (/^soil_humidity_layer/.test(c.parameter)||c.parameter==='soil_moisture')).sort((a,b)=>(b.valid_end||b.end).localeCompare(a.valid_end||a.end));
    const c=candidates.find(c=>/:soil1$/.test(c.device_id||''))||candidates[0];
    if(c){const first=c.valid_start||c.start,last=c.valid_end||c.end;const start=shiftISO(last,-6);this.setData({start:start<first?first:start,minStart:first,maxStart:start<first?first:start,dataEnd:last});}
    else this.setData({fieldError:'没有可用的历史监测窗口；不自动使用今天日期'});
   }
   this.setData({state:plot?'ready':'empty',mode:this.data.health.scenario_mode||this.data.health.hydrus_mode||'live'});
  }catch(e){if(this.loadToken===load)ui.fail(this,e);}
 },
 date(e){this.setData({start:e.detail.value,preview:null,result:null});},
 amount(e){const amount=e.detail.value;this.setData({amount,sliderValue:Number.isFinite(Number(amount))?Number(amount):0,preview:null,result:null,fieldError:''});},
 quick(e){this.amount({detail:{value:String(e.currentTarget.dataset.amount)}});},
 back(){if(!this.data.running)this.setData({step:1,error:null,result:null});},
 async next(){if(this.data.running)return;const n=Number(this.data.amount);if(!String(this.data.amount).trim()||!Number.isFinite(n)||n<0||n>100||!this.data.start){this.setData({fieldError:'请填写起始日期和0–100mm额外灌溉量'});return;}await this.submit(false,this.data.mode);},
 confirm(){return this.submit(true,this.data.mode);},
 retry(){return this.data.step===3?this.confirm():this.next();},
 replay(){this.setData({mode:'replay',result:null});return this.submit(false,'replay');},
 async submit(confirm,mode){if(this.data.running||!this.plotId)return;const token={};this.token=token;this.setData({running:true,error:null,fieldError:'',...(confirm?{step:3,result:null}:{})});try{const r=await request({url:'/api/scenario/compare',method:'POST',timeout:70000,data:{plot_id:this.plotId,start_date:this.data.start,change:{extra_irrigation_mm:Number(this.data.amount)},confirm,mode}});if(this.token!==token)return;if(!confirm)this.setData({preview:r,step:2,mode:r.mode,state:'ready'});else this.setData({result:{...r,rows:(r.rows||[]).map(p=>({...p,baselineText:formatValue(p.baseline,'moisture'),variantText:formatValue(p.variant,'moisture'),differenceText:formatValue(p.difference,'moisture')})),baselineFront:formatValue((r.baseline||{}).outputs?.infiltration_depth_cm),variantFront:formatValue((r.variant||{}).outputs?.infiltration_depth_cm),baselineUptake:formatValue((r.baseline||{}).outputs?.root_uptake_ratio),variantUptake:formatValue((r.variant||{}).outputs?.root_uptake_ratio)},mode:r.mode,state:'ready',error:r.status==='failed'&&r.code?require('../../utils/errors').normalizeError(r):null});}catch(e){if(this.token===token)ui.fail(this,e);}finally{if(this.token===token)this.setData({running:false});}},
 evidence(e){ui.openEvidence(e.currentTarget.dataset.id);},
 async report(){if(this.data.creatingReport||!this.data.result)return;this.setData({creatingReport:true});try{const r=await request({url:'/api/report/create',method:'POST',data:{plot_id:this.plotId,compare_id:this.data.result.compare_id}});wx.navigateTo({url:'/pages/report/report?report_id='+encodeURIComponent(r.report_id)});}catch(e){ui.fail(this,e);}finally{this.setData({creatingReport:false});}},
 ask(){if(!this.data.result)return;session.setPendingQuestion('解释情景对比 '+this.data.result.compare_id);wx.switchTab({url:'/pages/advice/advice'});},
 plots(){wx.navigateTo({url:'/pages/plots/plots'});}
});
