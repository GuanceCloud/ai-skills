const config = require('../../config/rum.local')
Page({
  data: { status: '请先检查网络', actions: 0, inputDone: false },
  requestResource() {
    wx.request({
      url: config.datakitOrigin + '/health?private_canary=RUM_PHONE_QUERY_CANARY',
      success: (res) => this.setData({ status: res.statusCode === 200 ? '网络成功，请继续点击交互和错误按钮' : '网络返回 ' + res.statusCode }),
      fail: (err) => this.setData({ status: '网络失败：' + err.errMsg })
    })
  },
  recordAction() { this.setData({ actions: this.data.actions + 1 }) },
  triggerError() {
    this.setData({ status: '已触发测试错误，请再次点击交互确认页面仍可使用' })
    throw new Error('RUM phone acceptance controlled error')
  },
  handleInput() { this.setData({ inputDone: true }) }
})
