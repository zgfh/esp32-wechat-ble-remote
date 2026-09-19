# 微信小程序 BLE 遥控端

## 使用方法

1. 在微信开发者工具导入本目录，重新编译并打开手机测试版。
2. 在“设备配对密码”输入框填写 ESP32 上 `pairing_config.py` 中配置的相同密码（至少 32 个字符，建议随机生成）。
3. 点击“连接 ESP32”，验证成功后使用锁车、解锁或启动按钮。
4. ESP32 日志窗口会补发近期记录并继续显示中文日志，可展开、清空。

密码按用户要求通过 `wx.setStorageSync` 保存在本机小程序存储，键名为 `remoteKey.pairingPassword.v1`；下次打开自动回填。清空输入框时通过 `wx.removeStorageSync` 删除。页面关闭仅清除内存变量，不删除本地存储。存储不是系统钥匙串，不额外加密；密码不写入日志、不随小程序包发布。连接过程中及连接成功后不能修改密码，需先断开。输入框不会修改 ESP32 的设备密码。

旧 `pairing.local.js` 已移出项目目录，打包配置也明确排除该文件及测试目录。之前生成的小程序包仍可能含旧密钥，删除源码不能撤销旧包；正式使用前应更换设备密码并停止使用旧测试包。

## 安全协议 v2

安全版已部署到普通 ESP32（MicroPython 1.28.0）；原 S3 未同步更新。需要同时更新设备的 `main.py`、`security.py`，并保留 `pairing_config.py`。旧版设备不能与新版小程序认证，不做降级兼容。

使用 HMAC-SHA256 验证随机会话挑战，每条指令绑定会话、递增序号及操作内容，拒绝篡改和重放。15 秒内未完成认证会断开；累计 5 次失败后冷却 30 秒；已认证会话 5 分钟没有有效操作会断开，重新连接即可。

本版尚未启用 BLE 链路加密绑定；操作和日志不保密，也不防实时中继。设备密码仍存储在板上普通文件中，实体访问仍有风险。短弱密码可能被离线猜测，因此保留至少 32 字符的要求。

## 日志与接线

开发者工具真机调试 Console 筛选 `[BLE]` 可看手机连接阶段，但不会输出密码和签名。蓝牙日志每包最多 20 字节，按整行 UTF-8 解码，保留最近 100 条。

![遥控器和 LED 接线](../remote-key-web-controller/docs/pc817-remote-led-wiring.svg)

[完整接线及触点测量方法](../remote-key-web-controller/README.md#圆形触点的测量方法与接线)。当前 S3：GPIO4 锁车、GPIO5 解锁、GPIO6 启动。LED 保留在 GPIO 侧，遥控器通过 PC817 隔离，不与 ESP32 共地。

## 验证

在仓库根目录运行 `node remote-key-miniapp/tests/security.test.js` 和 `python3 -m unittest discover -s remote-key-web-controller/tests`。


## 当前实机：普通 ESP32（2026-09-19）

已将 `main.py`、`security.py`、新的 `pairing_config.py` 安装到普通 ESP32，运行 MicroPython 1.28.0。蓝牙广播、GATT 服务和默认低电平已实机确认；HMAC 标准向量、认证、重放、超时测试通过。新密码独立于旧 S3，未写入文档和小程序包。

**当前接线：GPIO26 锁车、GPIO27 解锁、GPIO25 启动。** 顶部当前接线图已同步，原 S3 图另存为 `docs/pc817-remote-led-wiring-s3.svg`（位于固件项目）。保留三路独立光耦，遥控器不与 ESP32 共地。

串口 `/dev/cu.wchusbserial141120`；VS Code 日志工具支持自动识别 CH340/CP210x 及原生 ESP32 USB，存在多个候选串口时需显式指定。重新编译手机小程序，在密码框输入新密码再连接。手机实际操作尚待验证。
