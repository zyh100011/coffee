const { numberText } = require('../../utils/format');
Component({properties:{label:String,value:{type:null,value:null},unit:String,sub:String,sourceType:String,status:String},data:{unavailable:false,valueText:'—'},observers:{value(value){this.setData({valueText:numberText(value)});},status(status){this.setData({unavailable:['failed','timeout','missing_input','fallback'].includes(status)});}}});
