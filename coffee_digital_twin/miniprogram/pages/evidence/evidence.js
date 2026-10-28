const {request}=require('../../utils/request');const ui=require('../../utils/page');
Page({
 data:{state:'loading',error:null,result:null,inputs:[],sources:[],source:null,sourceRows:[],offset:0,nextOffset:null,total:0,paging:false},
 onLoad(o){this.id=o.evidence_id;this.obs=o.obs_id;this.reload();},
 async reload(){this.setData({state:'loading',error:null});try{if(this.obs){const source=await request({url:'/api/data/source/'+encodeURIComponent(this.obs)});this.setData({source,state:'ready'});return;}const r=await request({url:'/api/evidence/'+encodeURIComponent(this.id||'')});this.setData({result:r,inputs:Object.keys(r.inputs||{}).map(key=>({key,value:JSON.stringify(r.inputs[key])})),sources:(r.outputs||{}).source_obs_ids||[],state:'ready'});if(r.tool==='data_query'&&r.status==='success')await this.loadSources(0);}catch(e){ui.fail(this,e);}},
 async loadSources(offset){if(this.data.paging)return;this.setData({paging:true});try{const r=await request({url:'/api/data/evidence/'+encodeURIComponent(this.id)+'/sources',data:{offset,limit:20}});this.setData({sourceRows:r.items,offset:r.offset,nextOffset:r.next_offset,total:r.total});}catch(e){ui.fail(this,e);}finally{this.setData({paging:false});}},
 next(){if(this.data.nextOffset!==null)return this.loadSources(this.data.nextOffset);},previous(){return this.loadSources(Math.max(0,this.data.offset-20));},
 async source(e){try{const source=await request({url:'/api/data/source/'+encodeURIComponent(e.currentTarget.dataset.id)});this.setData({source});}catch(e){ui.fail(this,e);}}
});
