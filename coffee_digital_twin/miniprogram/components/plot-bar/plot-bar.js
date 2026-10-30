const viewMode=require('../../utils/viewMode');
const {formatValue}=require('../../utils/format');
function subText(plot){if(!plot)return '';const parts=[];if(plot.coffee_variety)parts.push(plot.coffee_variety);if(plot.area_mu!==null&&plot.area_mu!==undefined)parts.push(formatValue(plot.area_mu)+' 亩');if(plot.elevation_m!==null&&plot.elevation_m!==undefined)parts.push('海拔 '+formatValue(plot.elevation_m)+' m');return parts.join(' · ');}
Component({behaviors:[viewMode.behavior],properties:{plot:Object,modeSwitch:Boolean,variant:String},data:{subText:''},observers:{plot(plot){this.setData({subText:subText(plot)});}},methods:{change(){if(this.data.modeSwitch){viewMode.tapBase();this.triggerEvent('modechange',{isDev:viewMode.isDev()});return;}wx.navigateTo({url:'/pages/plots/plots'});}}});
