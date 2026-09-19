"""ESP32 BLE remote-key controller. Board-specific GPIOs drive optocouplers."""
import bluetooth
import ubinascii
import uhashlib
import os
import gc
import machine
import network
from security import Security
from machine import Pin
from micropython import const
from time import ticks_add, ticks_diff, ticks_ms, sleep_ms

# ESP32-S3 GPIO26/27 are reserved for flash/PSRAM.
IS_S3 = "ESP32S3" in os.uname().machine.upper().replace("-", "")
LOCK_PIN, UNLOCK_PIN, START_PIN, FIND_PIN = (4, 5, 6, 7) if IS_S3 else (26, 27, 25, 33)
PRESS_MS = 180
# Keep BLE connectable continuously; do not use machine sleep modes.
ADV_INTERVAL_US = 1000000
HEARTBEAT_MS = 30000
# Local pairing configuration is excluded from Git.
try:
    from pairing_config import BLE_PAIRING_SECRET
except ImportError:
    BLE_PAIRING_SECRET = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET"
BLE_DEVICE_NAME = "ESP32-Car-Remote"
SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
COMMAND_UUID = bluetooth.UUID("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
LOG_UUID = bluetooth.UUID("6e400004-b5a3-f393-e0a9-e50e24dcca9e")
STATUS_UUID = bluetooth.UUID("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
CONNECT, DISCONNECT, WRITE = const(1), const(2), const(3)
READ, WRITE_FLAG, NOTIFY = const(0x0002), const(0x0008), const(0x0010)

buttons = {"lock": Pin(LOCK_PIN, Pin.OUT, value=0), "unlock": Pin(UNLOCK_PIN, Pin.OUT, value=0), "start": Pin(START_PIN, Pin.OUT, value=0), "find": Pin(FIND_PIN, Pin.OUT, value=0)}
release_at = {name: None for name in buttons}
connections, authenticated, nonces = set(), set(), {}
receive_buffers = {}
security = Security(BLE_PAIRING_SECRET, ticks_ms, ticks_diff)
pending_disconnect = set()
packet_windows = {}

# Buffer diagnostics; never print from BLE callbacks or while a button is held.
log_queue = []
log_dropped = 0
log_history = []
log_streams = {}

def log(event, *fields):
    global log_dropped
    if event == "RX_FRAGMENT":
        return  # Packet details obscure user actions.
    if len(log_queue) < 64:
        log_queue.append((ticks_ms(), event, fields))
    else:
        log_dropped += 1

def describe_log(event, fields):
    names = {"lock": "锁车", "unlock": "解锁", "start": "启动（闪电键）", "find": "寻车（喇叭键）"}
    if event in ("COMMAND_RECEIVED", "BUTTON_ON", "BUTTON_OFF", "BUTTON_BUSY"):
        name = names.get(fields[0], "未知按键")
        if event == "COMMAND_RECEIVED":
            return "收到手机指令：" + name
        if event == "BUTTON_ON":
            return "正在模拟按下【%s】键，持续 %d 毫秒" % (name, PRESS_MS)
        if event == "BUTTON_OFF":
            return "【%s】按键已释放，输出已关闭（车辆状态未反馈）" % name
        return "暂未执行【%s】：上一次按键尚未释放，请稍后再试" % name
    if event == "SECURITY_TIMEOUT":
        return "连接验证超时或长期无操作，已断开连接，请重新连接"
    if event == "SECURITY_REJECT":
        return "指令校验失败或检测到重复指令，已拒绝执行并断开连接"
    if event == "BOOT":
        return "程序启动：%s，%s，复位原因代码 %s" % (fields[0], fields[1], fields[3])
    if event == "GPIO_READY":
        return "引脚就绪：锁车 GPIO%d，解锁 GPIO%d，启动 GPIO%d，寻车 GPIO%d；默认全部关闭" % (LOCK_PIN, UNLOCK_PIN, START_PIN, FIND_PIN)
    if event == "PAIRING_CONFIGURED":
        return "配对密钥已配置" if fields[0] else "尚未配置配对密钥，无法接受手机控制"
    if event == "POWER_SETTINGS":
        return "常连省电设置：Wi-Fi 已关闭，蓝牙每 1 秒广播，心跳每 30 秒输出"
    if event == "POWER_SETTINGS_FAILED":
        return "关闭 Wi-Fi 未成功，继续运行蓝牙；错误码：%s" % fields[0]
    if event == "BLE_ACTIVE":
        return "蓝牙已开启" if fields[0] else "蓝牙未开启"
    if event == "GATT_READY":
        return "蓝牙控制和日志服务已就绪"
    if event == "ADVERTISE_STARTED":
        return "已开启广播，等待手机连接：" + BLE_DEVICE_NAME
    if event == "CONNECTED":
        return "手机已连接，等待身份验证"
    if event == "DISCONNECTED":
        return "手机已断开，已清除认证状态"
    if event == "HELLO_RECEIVED":
        return "收到手机握手请求，开始验证身份"
    if event == "AUTH_OK":
        return "身份验证成功，现在可以锁车、解锁、启动或寻车"
    if event == "AUTH_FAILED":
        return "身份验证失败，请检查手机与 ESP32 的配对配置是否一致"
    if event == "STATUS":
        reasons = {"ERROR:NOT_CONFIGURED": "配对密钥未配置", "ERROR:AUTH_REQUIRED": "尚未通过身份验证", "ERROR:BUSY": "按键忙，请稍后重试", "ERROR:TOO_LONG": "指令过长", "ERROR:BAD_ENCODING": "指令编码错误", "ERROR:UNKNOWN_COMMAND": "无法识别的指令"}
        return "指令未执行：" + reasons.get(fields[-1], "未知状态")
    if event == "NOTIFY_FAILED":
        return "向手机发送状态失败，错误码：%s" % fields[-1]
    if event == "HEARTBEAT":
        return "运行正常｜蓝牙%s｜连接 %d 台，已验证 %d 台｜剩余内存 %d KB｜输出：锁车%s / 解锁%s / 启动%s / 寻车%s" % ("开启" if fields[1] else "关闭", fields[3], fields[5], fields[7] // 1024, "开" if fields[9] else "关", "开" if fields[10] else "关", "开" if fields[11] else "关", "开" if fields[12] else "关")
    return "诊断事件：" + event

def flush_logs():
    global log_dropped
    if any(deadline is not None for deadline in release_at.values()):
        return
    for _ in range(min(4, len(log_queue))):
        stamp, event, fields = log_queue.pop(0)
        line = "[设备计时 %d秒] %s" % (stamp // 1000, describe_log(event, fields))
        print(line)
        line = line[:240]
        log_history.append(line)
        if len(log_history) > 30:
            log_history.pop(0)
        for conn in tuple(authenticated):
            stream = log_streams.get(conn)
            if stream is None:
                continue
            if len(stream["lines"]) < 40:
                stream["lines"].append(line)
            else:
                stream["dropped"] += 1
    if log_dropped:
        print("[ESP32] 日志繁忙，已省略条数：", log_dropped)
        log_dropped = 0

def stream_logs():
    # One <=20-byte packet per connection per loop; control/pulse release wins.
    if any(deadline is not None for deadline in release_at.values()):
        return
    for conn in tuple(log_streams):
        if conn not in authenticated:
            log_streams.pop(conn, None)
            continue
        stream = log_streams[conn]
        if not stream["pending"]:
            if stream["dropped"]:
                stream["pending"] = ("[ESP32] 日志繁忙，已省略 %d 条\n" % stream["dropped"]).encode()
                stream["dropped"] = 0
            elif stream["lines"]:
                stream["pending"] = (stream["lines"].pop(0) + "\n").encode()
            else:
                continue
        try:
            ble.gatts_notify(conn, log_handle, stream["pending"][:20])
            stream["pending"] = stream["pending"][20:]
        except OSError:
            # Retry without recursive logging. Logs must never break control.
            pass

def digest(value):
    return ubinascii.hexlify(uhashlib.sha256(value.encode()).digest()).decode()

def advertise():
    name = BLE_DEVICE_NAME.encode()
    ble.gap_advertise(ADV_INTERVAL_US, adv_data=b"\x02\x01\x06" + bytes((len(name) + 1, 9)) + name)
    log("ADVERTISE_STARTED", "name=" + BLE_DEVICE_NAME, "interval_ms=", ADV_INTERVAL_US // 1000)

def status(value, conn=None):
    if value.startswith("ERROR:"):
        log("STATUS", "conn=", conn, "type=", value)
    payload = value.encode()
    ble.gatts_write(status_handle, payload)
    targets = (conn,) if conn is not None else tuple(connections)
    for target in targets:
        try:
            framed = payload + b"\n"
            for offset in range(0, len(framed), 20):
                ble.gatts_notify(target, status_handle, framed[offset:offset + 20])
        except OSError as error:
            log("NOTIFY_FAILED", "conn=", target, "errno=", error.args[0] if error.args else None)

def press(name):
    if any(value is not None for value in release_at.values()):
        log("BUTTON_BUSY", name)
        return False
    if release_at[name] is None:
        log("BUTTON_ON", name, "duration_ms=", PRESS_MS)
        buttons[name].on()
        release_at[name] = ticks_add(ticks_ms(), PRESS_MS)
        return True

def release_buttons():
    now = ticks_ms()
    for name, deadline in release_at.items():
        if deadline is not None and ticks_diff(now, deadline) >= 0:
            buttons[name].off()
            release_at[name] = None
            log("BUTTON_OFF", name)

def disconnect_client(conn):
    authenticated.discard(conn)
    log_streams.pop(conn, None)
    receive_buffers.pop(conn, None)
    packet_windows.pop(conn, None)
    security.close(conn)
    pending_disconnect.add(conn)

def check_connections():
    for conn in tuple(connections):
        if security.expired(conn) and conn not in pending_disconnect:
            log("SECURITY_TIMEOUT")
            disconnect_client(conn)
    for conn in tuple(pending_disconnect):
        try:
            ble.gap_disconnect(conn)
        except OSError:
            pass
        pending_disconnect.discard(conn)

def irq(event, data):
    if event == CONNECT:
        conn, _, _ = data
        if not security.open(conn):
            pending_disconnect.add(conn)
            return
        receive_buffers.pop(conn, None)
        log("CONNECTED", "conn=", conn)
        connections.add(conn); authenticated.discard(conn)
        nonces.pop(conn, None)
    elif event == DISCONNECT:
        conn, _, _ = data
        receive_buffers.pop(conn, None)
        log_streams.pop(conn, None)
        security.close(conn)
        pending_disconnect.discard(conn)
        packet_windows.pop(conn, None)
        log("DISCONNECTED", "conn=", conn)
        connections.discard(conn); authenticated.discard(conn); nonces.pop(conn, None); advertise()
    elif event == WRITE:
        conn, handle = data
        if handle != command_handle: return
        if conn not in connections or conn in pending_disconnect or security.expired(conn):
            disconnect_client(conn)
            return
        started, count = packet_windows.get(conn, (ticks_ms(), 0))
        if ticks_diff(ticks_ms(), started) >= 1000:
            started, count = ticks_ms(), 0
        packet_windows[conn] = (started, count + 1)
        if count >= 40:
            security.reject(conn)
            disconnect_client(conn)
            return
        chunk = ble.gatts_read(command_handle)
        pending = receive_buffers.get(conn, b"") + chunk
        log("RX_FRAGMENT", "conn=", conn, "bytes=", len(chunk), "buffered=", len(pending))
        if len(pending) > 128:
            receive_buffers.pop(conn, None)
            status("ERROR:TOO_LONG", conn)
            disconnect_client(conn)
            return
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            try:
                handle_message(conn, line.decode().strip())
            except UnicodeError:
                status("ERROR:BAD_ENCODING", conn)
                disconnect_client(conn)
        if conn not in pending_disconnect:
            receive_buffers[conn] = pending

def handle_message(conn, message):
    if conn in pending_disconnect or security.expired(conn):
        disconnect_client(conn)
        return
    if message == "HELLO2":
        nonce = security.challenge(conn)
        if nonce is None:
            status("ERROR:AUTH_REQUIRED", conn)
            disconnect_client(conn)
            return
        log("HELLO_RECEIVED")
        status("CHALLENGE2:" + nonce, conn)
    elif message.startswith("AUTH2:"):
        if security.authenticate(conn, message[6:]):
            authenticated.add(conn)
            log("AUTH_OK")
            log_streams[conn] = {"lines": list(log_history), "pending": b"", "dropped": 0}
            status("AUTH_OK", conn)
        else:
            log("AUTH_FAILED")
            status("ERROR:AUTH_REQUIRED", conn)
            disconnect_client(conn)
    elif conn not in authenticated:
        status("ERROR:AUTH_REQUIRED", conn)
        disconnect_client(conn)
    else:
        name = security.command(conn, message)
        if name is None:
            log("SECURITY_REJECT")
            status("ERROR:AUTH_REQUIRED", conn)
            disconnect_client(conn)
            return
        log("COMMAND_RECEIVED", name)
        status("OK:" + name.upper() if press(name) else "ERROR:BUSY", conn)

try:
    network.WLAN(network.STA_IF).active(False)
    network.WLAN(network.AP_IF).active(False)
    log("POWER_SETTINGS")
except OSError as error:
    log("POWER_SETTINGS_FAILED", error.args[0] if error.args else None)

log("BOOT", os.uname().machine, "MicroPython=" + os.uname().release, "reset_cause=", machine.reset_cause())
log("GPIO_READY", "lock=", LOCK_PIN, "unlock=", UNLOCK_PIN, "start=", START_PIN, "find=", FIND_PIN, "levels=", buttons["lock"].value(), buttons["unlock"].value(), buttons["start"].value(), buttons["find"].value())
log("PAIRING_CONFIGURED", BLE_PAIRING_SECRET != "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")
ble = bluetooth.BLE(); ble.active(True)
log("BLE_ACTIVE", ble.active())
((command_handle, status_handle, log_handle),) = ble.gatts_register_services(((SERVICE_UUID, ((COMMAND_UUID, WRITE_FLAG), (STATUS_UUID, NOTIFY), (LOG_UUID, NOTIFY))),))
ble.gatts_set_buffer(command_handle, 128)
log("GATT_READY", "command_handle=", command_handle, "status_handle=", status_handle, "log_handle=", log_handle)
ble.irq(irq); status("READY"); advertise()
print("蓝牙服务已启动：", BLE_DEVICE_NAME)
heartbeat_at = ticks_add(ticks_ms(), HEARTBEAT_MS)
try:
    while True:
        release_buttons()
        check_connections()
        if ticks_diff(ticks_ms(), heartbeat_at) >= 0:
            log("HEARTBEAT", "ble=", ble.active(), "connections=", len(connections), "authenticated=", len(authenticated), "free_heap=", gc.mem_free(), "outputs=", buttons["lock"].value(), buttons["unlock"].value(), buttons["start"].value(), buttons["find"].value())
            heartbeat_at = ticks_add(ticks_ms(), HEARTBEAT_MS)
        flush_logs()
        stream_logs()
        sleep_ms(20)
finally:
    for button in buttons.values():
        button.off()
