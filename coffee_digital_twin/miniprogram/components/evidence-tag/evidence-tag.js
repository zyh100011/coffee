const viewMode=require('../../utils/viewMode');
const { evidenceLabel } = require('../../utils/labels');
Component({behaviors:[viewMode.behavior],properties:{sourceType:String,status:String,mode:String,size:{type:String,value:'md'}},data:{label:{}},observers:{'sourceType,status,mode':function(source,status,mode){this.setData({label:evidenceLabel(source,status,mode)});}},lifetimes:{attached(){this.setData({label:evidenceLabel(this.data.sourceType,this.data.status,this.data.mode)});}}});
