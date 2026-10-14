require('./rum').initializeRum()

App({ globalData: { launchCount: 0 }, onLaunch() { this.globalData.launchCount += 1 } })
