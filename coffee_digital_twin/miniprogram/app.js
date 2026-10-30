App({
  globalData: {
    appName: '咖啡农事循证决策助手',
    latestTaskId: '',
    plotId: ''
  },

  onLaunch() {
    this.globalData.latestTaskId = wx.getStorageSync('latestTaskId') || '';
    require('./utils/session').getHealth().catch(() => {});
    this.globalData.plotId = wx.getStorageSync('plotId') || '';
  }
});
