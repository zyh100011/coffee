const viewMode=require('../../utils/viewMode');
Component({behaviors:[viewMode.behavior],options:{styleIsolation:'apply-shared'},properties:{kind:String,text:String,actionText:String},methods:{act(){this.triggerEvent('action');}}});
