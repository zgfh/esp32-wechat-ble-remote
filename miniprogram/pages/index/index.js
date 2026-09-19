const app = getApp();
const PASSWORD_STORAGE_KEY = 'remoteKey.pairingPassword.v1';
const LOG_ID = '6e400004-b5a3-f393-e0a9-e50e24dcca9e';
const hmac = require('../../utils/hmac');
const log = (stage, details = {}) => console.info('[BLE]', new Date().toISOString(), stage, details);
const errorInfo = error => ({errCode: error.errCode, errno: error.errno, errMsg: error.errMsg, message: error.message});
const call = (method, options = {}) => new Promise((resolve, reject) => {
  const started = Date.now();
  log(method + ':start', {bytes: options.value ? options.value.byteLength : undefined});
  wx[method]({...options,
    success: result => { log(method + ':ok', {ms: Date.now() - started}); resolve(result); },
    fail: error => { console.error('[BLE]', method + ':fail', errorInfo(error)); reject(error); }
  });
});
const logEnvironment = () => {
  try {
    if (wx.getDeviceInfo) { const d = wx.getDeviceInfo(); log('device', {platform: d.platform, system: d.system}); }
    if (wx.getAppBaseInfo) { const d = wx.getAppBaseInfo(); log('wechat', {version: d.version, SDKVersion: d.SDKVersion}); }
    if (wx.getSystemSetting) log('system', {bluetoothEnabled: wx.getSystemSetting().bluetoothEnabled});
    if (wx.getAppAuthorizeSetting) log('permission', {bluetoothAuthorized: wx.getAppAuthorizeSetting().bluetoothAuthorized});
    if (wx.getSetting) wx.getSetting({success: r => log('miniappPermission', {bluetooth: r.authSetting['scope.bluetooth']})});
  } catch (error) { console.warn('[BLE] diagnostics unavailable', errorInfo(error)); }
};
const bytes = text => { const data = new Uint8Array(text.length); for (let i = 0; i < text.length; i++) data[i] = text.charCodeAt(i); return data.buffer; };
Page({
  data: {passwordValue: '', passwordHint: '密码保存在本机，清空输入框即可删除', status: '未连接', ok: false, connecting: false, disconnecting: false, logs: [], logsOpen: true, logHint: '连接并验证后接收 ESP32 日志', logBottom: ''},
  onLoad() {
    log('page loaded');
    this.pairingPassword = '';
    try {
      const saved = wx.getStorageSync(PASSWORD_STORAGE_KEY);
      if (typeof saved === 'string' && saved.length <= 128) this.pairingPassword = saved;
    } catch (_) {
      this.setData({passwordHint: '读取已保存密码失败，请重新输入'});
    }
    this.setData({passwordValue: this.pairingPassword});
    this.logPending = ''; this.logLines = []; this.logSequence = 0;
    this.sessionNonce = null; this.commandSeq = 0;
    this.deviceId = null; this.pending = ''; this.queue = Promise.resolve();
    this.connectionListener = e => { log('connection changed', {connected: e.connected}); if (e.deviceId === this.deviceId && !e.connected) this.reset('连接已断开'); };
    this.valueListener = e => {
      if (e.deviceId !== this.deviceId) return;
      if (e.characteristicId.toLowerCase() === LOG_ID) { this.receiveLog(e.value); return; }
      if (e.characteristicId.toLowerCase() !== app.statusId) return;
      this.pending += Array.from(new Uint8Array(e.value), v => String.fromCharCode(v)).join('');
      if (this.pending.length > 256) { this.fail(new Error('状态消息过长')); return; }
      let end;
      while ((end = this.pending.indexOf('\n')) >= 0) {
        const message = this.pending.slice(0, end); this.pending = this.pending.slice(end + 1); this.status(message);
      }
    };
    this.foundListener = result => {
      const device = result.devices.find(d => d.name === app.deviceName || d.localName === app.deviceName);
      log('discovery', {count: result.devices.length, targetFound: !!device});
      if (!this.searching || this.deviceId || !device) return;
      this.searching = false; this.deviceId = device.deviceId;
      wx.stopBluetoothDevicesDiscovery({}); this.link().catch(e => this.fail(e));
    };
    wx.onBLEConnectionStateChange(this.connectionListener);
    wx.onBLECharacteristicValueChange(this.valueListener);
    wx.onBluetoothDeviceFound(this.foundListener);
  },
  receiveLog(value) {
    this.logPending += Array.from(new Uint8Array(value), v => String.fromCharCode(v)).join('');
    let end;
    while ((end = this.logPending.indexOf('\n')) >= 0) {
      const raw = this.logPending.slice(0, end); this.logPending = this.logPending.slice(end + 1);
      let text;
      try { text = decodeURIComponent(Array.from(raw, c => '%' + ('0' + c.charCodeAt(0).toString(16)).slice(-2)).join('')); }
      catch (_) { text = '日志数据不完整，此条无法显示'; }
      this.logLines.push({id: 'log-' + (++this.logSequence), text});
    }
    if (this.logPending.length > 1024) this.logPending = '';
    this.logLines = this.logLines.slice(-100);
    if (!this.logTimer) this.logTimer = setTimeout(() => {
      this.logTimer = null;
      this.setData({logs: this.logLines.slice(), logBottom: this.logLines.length ? this.logLines[this.logLines.length - 1].id : ''});
    }, 250);
  },
  toggleLogs() { this.setData({logsOpen: !this.data.logsOpen}); },
  clearLogs() {
    clearTimeout(this.logTimer); this.logTimer = null; this.logLines = [];
    this.setData({logs: [], logBottom: ''});
  },
  reset(status) {
    this.sessionNonce = null; this.commandSeq = 0;
    this.logPending = '';
    this.setData({logHint: '已断开，保留最近日志'});
    clearTimeout(this.timer); this.searching = false; this.deviceId = null;
    this.pending = ''; this.queue = Promise.resolve(); this.setData({status, ok: false, connecting: false, disconnecting: false});
  },
  fail(error) {
    console.error('[BLE] failure', errorInfo(error));
    const deviceId = this.deviceId;
    this.reset((error.message || error.errMsg || '蓝牙连接失败') + (error.errCode !== undefined ? ' [' + error.errCode + ']' : ''));
    wx.stopBluetoothDevicesDiscovery({});
    if (deviceId) wx.closeBLEConnection({deviceId});
  },
  onPasswordInput(event) {
    if (this.data.ok || this.data.connecting || this.data.disconnecting) return;
    this.pairingPassword = event.detail.value;
    this.setData({passwordValue: this.pairingPassword});
    try {
      if (this.pairingPassword) wx.setStorageSync(PASSWORD_STORAGE_KEY, this.pairingPassword);
      else wx.removeStorageSync(PASSWORD_STORAGE_KEY);
      this.setData({passwordHint: this.pairingPassword ? '密码已保存在本机，下次自动填入' : '已删除保存的密码'});
    } catch (_) {
      this.setData({passwordHint: '本地保存失败，本次仍可使用输入的密码'});
    }
  },
  toggleConnection() {
    if (this.data.connecting || this.data.disconnecting) return;
    if (this.data.ok) this.disconnect();
    else this.connect();
  },
  async disconnect() {
    const deviceId = this.deviceId;
    if (!deviceId) { this.reset('已断开连接'); return; }
    this.setData({disconnecting: true});
    try {
      await call('closeBLEConnection', {deviceId});
      this.reset('已断开连接');
    } catch (error) {
      console.error('[BLE] disconnect failed', errorInfo(error));
      this.setData({disconnecting: false, status: '断开失败，请重试'});
    }
  },
  async connect() {
    log('connect requested'); logEnvironment();
    if (this.deviceId || this.searching) return;
    if (!this.pairingPassword || this.pairingPassword.length < 32) {
      this.setData({status: '请输入 ESP32 的配对密码（至少 32 个字符）', ok: false}); return;
    }
    this.setData({status: '正在搜索…', ok: false, connecting: true}); this.searching = true;
    this.timer = setTimeout(() => this.fail(new Error('搜索或验证超时，请重试')), 20000);
    try {
      await call('openBluetoothAdapter');
      await call('startBluetoothDevicesDiscovery', {allowDuplicatesKey: true});
    } catch (e) { this.fail(e); }
  },
  async link() {
    const deviceId = this.deviceId;
    await call('createBLEConnection', {deviceId, timeout: 10000});
    const result = await call('getBLEDeviceServices', {deviceId});
    const service = result.services.find(s => s.uuid.toLowerCase() === app.serviceId);
    if (!service) throw new Error('未找到遥控器服务，请检查 ESP32 固件');
    this.serviceId = service.uuid;
    const chars = await call('getBLEDeviceCharacteristics', {deviceId, serviceId: this.serviceId});
    const command = chars.characteristics.find(c => c.uuid.toLowerCase() === app.commandId && c.properties.write);
    const status = chars.characteristics.find(c => c.uuid.toLowerCase() === app.statusId && c.properties.notify);
    if (!command || !status) throw new Error('蓝牙特征不匹配');
    this.commandId = command.uuid;
    const logChar = chars.characteristics.find(c => c.uuid.toLowerCase() === LOG_ID && c.properties.notify);
    this.setData({logHint: logChar ? '等待验证后接收日志' : '当前固件不支持蓝牙日志'});
    if (logChar) {
      try {
        await call('notifyBLECharacteristicValueChange', {deviceId, serviceId: this.serviceId, characteristicId: logChar.uuid, state: true});
        this.setData({logHint: '已订阅日志（验证后发送），保留最近 100 条'});
      } catch (error) {
        console.warn('[BLE] log subscription failed', errorInfo(error));
        this.setData({logHint: '日志订阅失败，车辆按钮仍可使用'});
      }
    }
    await call('notifyBLECharacteristicValueChange', {deviceId, serviceId: this.serviceId, characteristicId: status.uuid, state: true});
    this.setData({status: '已连接，正在验证…'}); this.send('HELLO2');
  },
  status(message) {
    log('protocol received', {type: message.split(':')[0]});
    if (message.startsWith('CHALLENGE2:')) {
      const nonce = message.slice(11);
      if (!/^[0-9a-f]{32}$/.test(nonce) || this.sessionNonce) { this.fail(new Error('验证数据异常，请重新连接')); return; }
      this.sessionNonce = nonce; this.commandSeq = 0;
      this.send('AUTH2:' + hmac(this.pairingPassword, 'auth:v2:' + nonce));
    }
    else if (message === 'AUTH_OK') { if (!this.sessionNonce) { this.fail(new Error('验证状态异常')); return; } clearTimeout(this.timer); this.setData({status: '已连接，验证成功', ok: true, connecting: false}); }
    else if (message.startsWith('OK:')) wx.showToast({title: ({'OK:LOCK': '已发送锁车', 'OK:UNLOCK': '已发送解锁', 'OK:START': '已发送启动', 'OK:FIND': '已发送寻车'}[message] || '指令已发送'), icon: 'success'});
    else if (message === 'ERROR:BUSY') wx.showToast({title: '按键忙，请稍后重试', icon: 'none'});
    else if (message.startsWith('ERROR:')) this.fail(new Error(message === 'ERROR:AUTH_REQUIRED' ? '密码错误、会话过期或指令验证失败，请重新连接' : message));
  },
  send(message) {
    log('protocol send', {type: message.split(':')[0], bytes: message.length + 1});
    const deviceId = this.deviceId, serviceId = this.serviceId, characteristicId = this.commandId;
    this.queue = this.queue.then(async () => {
      let wire = message;
      if (message.startsWith('CMD:')) {
        if (!this.data.ok || !this.sessionNonce || this.deviceId !== deviceId) throw new Error('请先重新连接并验证');
        const name = message.slice(4), seq = ++this.commandSeq;
        wire = 'CMD2:' + seq + ':' + name + ':' + hmac(this.pairingPassword, 'cmd:v2:' + this.sessionNonce + ':' + seq + ':' + name);
      }
      const framed = wire + '\n';
      for (let i = 0; i < framed.length; i += 20) {
        if (!deviceId || this.deviceId !== deviceId) throw new Error('连接已断开');
        await call('writeBLECharacteristicValue', {deviceId, serviceId, characteristicId, value: bytes(framed.slice(i, i + 20))});
      }
    }).catch(e => { if (this.deviceId === deviceId) this.fail(e); });
  },
  lock() { if (this.data.ok) this.send('CMD:LOCK'); },
  unlock() { if (this.data.ok) this.send('CMD:UNLOCK'); },
  findCar() { if (this.data.ok && !this.data.disconnecting) this.send('CMD:FIND'); },
  start() { if (this.data.ok && !this.data.disconnecting) this.send('CMD:START'); },
  onUnload() {
    this.pairingPassword = '';
    clearTimeout(this.logTimer);
    this.fail(new Error('已关闭'));
    wx.offBLEConnectionStateChange(this.connectionListener);
    wx.offBLECharacteristicValueChange(this.valueListener);
    wx.offBluetoothDeviceFound(this.foundListener);
  }
});
