const app = getApp()
const CryptoJS = require('crypto-js')
let deviceId = null
const buffer = s => { const b = new ArrayBuffer(s.length); const v = new Uint8Array(b); for (let i = 0; i < s.length; i++) v[i] = s.charCodeAt(i); return b }
const text = b => Array.prototype.map.call(new Uint8Array(b), x => String.fromCharCode(x)).join('')
Page({
  data: { status: '未连接', authenticated: false },
  connect() {
    this.setData({ status: '正在搜索…', authenticated: false })
    wx.openBluetoothAdapter({ success: () => this.scan(), fail: () => this.setData({ status: '请开启蓝牙并授权“附近设备”' }) })
  },
  scan() {
    wx.onBluetoothDeviceFound(r => { const d = r.devices.find(x => x.name === app.deviceName || x.localName === app.deviceName); if (d && !deviceId) { deviceId = d.deviceId; wx.stopBluetoothDevicesDiscovery(); this.link() } })
    wx.startBluetoothDevicesDiscovery({ allowDuplicatesKey: false, fail: () => this.setData({ status: '蓝牙搜索失败' }) })
  },
  link() {
    wx.createBLEConnection({ deviceId, success: () => wx.getBLEDeviceServices({ deviceId, success: () => this.subscribe() }), fail: () => this.setData({ status: '连接失败，请靠近设备重试' }) })
  },
  subscribe() {
    this.setData({ status: '已连接，正在验证…' })
    wx.onBLECharacteristicValueChange(e => this.onStatus(text(e.value)))
    wx.notifyBLECharacteristicValueChange({ deviceId, serviceId: app.serviceId, characteristicId: app.statusId, state: true, success: () => wx.readBLECharacteristicValue({ deviceId, serviceId: app.serviceId, characteristicId: app.statusId }) })
  },
  onStatus(message) {
    if (message.indexOf('CHALLENGE:') === 0) this.send('AUTH:' + CryptoJS.SHA256(app.pairingSecret + ':' + message.slice(10)).toString())
    else if (message === 'AUTH_OK') this.setData({ status: '已验证，可操作', authenticated: true })
    else if (message.indexOf('OK:') === 0) wx.showToast({ title: message === 'OK:LOCK' ? '已发送锁车' : '已发送解锁', icon: 'success' })
    else if (message.indexOf('ERROR:') === 0) this.setData({ status: message })
  },
  send(message) { wx.writeBLECharacteristicValue({ deviceId, serviceId: app.serviceId, characteristicId: app.commandId, value: buffer(message), fail: () => this.setData({ status: '发送失败，请重新连接' }) }) },
  lock() { this.send('CMD:LOCK') },
  unlock() { this.send('CMD:UNLOCK') }
})
