Page({
 data: { status: '已启动', actions: 0 },
 requestResource() { wx.request({ url: 'http://127.0.0.1:19529/health', success: () => this.setData({ status: '本地资源成功' }), fail: () => this.setData({ status: '本地接收器未启动' }) }) },
 recordAction() { this.setData({ actions: this.data.actions + 1 }) },
 triggerError() { throw new Error('RUM acceptance controlled error') },
 handleInput() { /* Input content intentionally stays out of telemetry and context. */ }
})
