import './shared/device-polyfill'
import { MessageBuilder } from './shared/message'
import { getPackageInfo } from '@zos/app'
import * as ble from '@zos/ble'

App({
  globalData: {
    messageBuilder: null,
  },
  onCreate() {
    const { appId } = getPackageInfo()
    const messageBuilder = new MessageBuilder({
      appId,
      appDevicePort: 20,
      appSidePort: 0,
      ble,
    })
    this.globalData.messageBuilder = messageBuilder
    messageBuilder.connect()
  },
  onDestroy() {
    const mb = this.globalData.messageBuilder
    if (mb) mb.disConnect()
  },
})
