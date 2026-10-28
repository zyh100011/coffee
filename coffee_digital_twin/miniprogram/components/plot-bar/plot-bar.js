const viewMode=require('../../utils/viewMode');
Component({behaviors:[viewMode.behavior],properties:{plot:Object,modeSwitch:Boolean},methods:{change(){if(this.data.modeSwitch){viewMode.tapBase();this.triggerEvent('modechange',{isDev:viewMode.isDev()});return;}wx.navigateTo({url:'/pages/plots/plots'});}}});
