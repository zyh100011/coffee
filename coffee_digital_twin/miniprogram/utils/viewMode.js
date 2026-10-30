// 团队核对模式只控制展示，不能改变接口数据或验证状态。
const KEY='coffee_view_mode';const listeners=new Set();let taps=0,lastTap=0;
function getMode(){return wx.getStorageSync(KEY)==='dev'?'dev':'user';}
function isDev(){return getMode()==='dev';}
function subscribe(listener){listeners.add(listener);return ()=>listeners.delete(listener);}
function setMode(mode){const value=mode==='dev'?'dev':'user';wx.setStorageSync(KEY,value);listeners.forEach(fn=>fn(value));return value;}
function tapBase(now=Date.now()){
 if(now-lastTap>1600)taps=0;lastTap=now;taps++;
 if(taps<5)return false;taps=0;setMode(isDev()?'user':'dev');return true;
}
const definition={
 data:{isDev:false},
 lifetimes:{attached(){this.setData({isDev:isDev()});this._viewUnsubscribe=subscribe(mode=>this.setData({isDev:mode==='dev'}));},detached(){if(this._viewUnsubscribe)this._viewUnsubscribe();}},
 pageLifetimes:{show(){this.setData({isDev:isDev()});}}
};
const behavior=typeof Behavior==='function'?Behavior(definition):definition;
module.exports={getMode,isDev,subscribe,setMode,tapBase,behavior};
