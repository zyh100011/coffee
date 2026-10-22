// 本届 T4.2：沿用旧原生框架，改为确认式灌溉情景向导。
const {request}=require('../../utils/request');
const ui=require('../../utils/page');
const session=require('../../utils/session');
const {localISO}=require('../../utils/dates');
Page({
 data:{...ui.defaults,step:1,start:'',amount:'20',sliderValue:20,preview:null,result:null,running:false,mode:'live',fieldError:'',creatingReport:false},
 onShow(){this.reload();},onHide(){this.token=null;this.setData({running:false});},
 async reload(){this.setData({state:'loading',error:null});try{const plot=await ui.context(this);const id=plot?plot.plot_id:'';if(this.plotId!==id){this.token=null;this.setData({step:1,preview:null,result:null,running:false,fieldError:'',start:localISO()});}this.plotId=id;this.setData({state:plot?'ready':'empty',mode:this.data.health.scenario_mode||this.data.health.hydrus_mode||'live'});}catch(e){ui.fail(this,e);}},
 date(e){this.setData({start:e.detail.value,preview:null,result:null});},
 amount(e){const amount=e.detail.value;this.setData({amount,sliderValue:Number.isFinite(Number(amount))?Number(amount):0,preview:null,result:null,fieldError:''});},
 quick(e){this.amount({detail:{value:String(e.currentTarget.dataset.amount)}});},
 back(){if(!this.data.running)this.setData({step:1,error:null,result:null});},
 async next(){if(this.data.running)return;const n=Number(this.data.amount);if(!String(this.data.amount).trim()||!Number.isFinite(n)||n<0||n>100||!this.data.start){this.setData({fieldError:'请填写起始日期和0–100mm额外灌溉量'});return;}await this.submit(false,this.data.mode);},
 confirm(){return this.submit(true,this.data.mode);},
 retry(){return this.data.step===3?this.confirm():this.next();},
 replay(){this.setData({mode:'replay',result:null});return this.submit(false,'replay');},
 async submit(confirm,mode){if(this.data.running||!this.plotId)return;const token={};this.token=token;this.setData({running:true,error:null,fieldError:'',...(confirm?{step:3,result:null}:{})});try{const r=await request({url:'/api/scenario/compare',method:'POST',timeout:70000,data:{plot_id:this.plotId,start_date:this.data.start,change:{extra_irrigation_mm:Number(this.data.amount)},confirm,mode}});if(this.token!==token)return;if(!confirm)this.setData({preview:r,step:2,mode:r.mode,state:'ready'});else this.setData({result:r,mode:r.mode,state:'ready',error:r.status==='failed'&&r.code?require('../../utils/errors').normalizeError(r):null});}catch(e){if(this.token===token)ui.fail(this,e);}finally{if(this.token===token)this.setData({running:false});}},
 evidence(e){ui.openEvidence(e.currentTarget.dataset.id);},
 async report(){if(this.data.creatingReport||!this.data.result)return;this.setData({creatingReport:true});try{const r=await request({url:'/api/report/create',method:'POST',data:{plot_id:this.plotId,compare_id:this.data.result.compare_id}});wx.navigateTo({url:'/pages/report/report?report_id='+encodeURIComponent(r.report_id)});}catch(e){ui.fail(this,e);}finally{this.setData({creatingReport:false});}},
 ask(){if(!this.data.result)return;session.setPendingQuestion('解释情景对比 '+this.data.result.compare_id);wx.switchTab({url:'/pages/advice/advice'});},
 plots(){wx.navigateTo({url:'/pages/plots/plots'});}
});
