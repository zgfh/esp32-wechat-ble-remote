"""Authenticated sessions and commands. No BLE or GPIO side effects."""
try:
    import uhashlib as hashlib
    import ubinascii as binascii
except ImportError:
    import hashlib, binascii
import os

def mac(key, message):
    key = key.encode() if isinstance(key, str) else key
    if len(key) > 64:
        key = hashlib.sha256(key).digest()
    key += b'\0' * (64 - len(key))
    inner = hashlib.sha256(bytes(x ^ 0x36 for x in key) + message.encode()).digest()
    return binascii.hexlify(hashlib.sha256(bytes(x ^ 0x5c for x in key) + inner).digest()).decode()

def equal(a, b):
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    return result == 0

class Security:
    def __init__(self, key, now, diff):
        self.key, self.now, self.diff = key, now, diff
        self.sessions = {}
        self.failures = 0
        self.cooldown = None

    def open(self, conn):
        if self.cooldown is not None:
            if self.diff(self.now(), self.cooldown) < 30000:
                return False
            self.cooldown = None
            self.failures = 0
        if self.sessions:
            return False
        self.sessions[conn] = {'since': self.now(), 'last': self.now(), 'nonce': None, 'ok': False, 'seq': 0}
        return True

    def close(self, conn):
        self.sessions.pop(conn, None)

    def expired(self, conn):
        s = self.sessions.get(conn)
        return s is None or self.diff(self.now(), s['last'] if s['ok'] else s['since']) >= (300000 if s['ok'] else 15000)

    def challenge(self, conn):
        s = self.sessions.get(conn)
        if self.expired(conn) or s['nonce'] is not None or len(self.key) < 32 or self.key.startswith('CHANGE_THIS'):
            return None
        s['nonce'] = binascii.hexlify(os.urandom(16)).decode()
        return s['nonce']

    def reject(self, conn):
        self.close(conn)
        self.failures += 1
        if self.failures >= 5:
            self.cooldown = self.now()

    def authenticate(self, conn, proof):
        s = self.sessions.get(conn)
        if self.expired(conn) or not s['nonce'] or s['ok'] or not equal(mac(self.key, 'auth:v2:' + s['nonce']), proof):
            self.reject(conn)
            return False
        s['ok'] = True
        s['last'] = self.now()
        self.failures = 0
        return True

    def command(self, conn, message):
        s = self.sessions.get(conn)
        parts = message.split(':')
        if self.expired(conn) or not s['ok'] or len(parts) != 4 or parts[0] != 'CMD2':
            self.reject(conn)
            return None
        _, seq, name, proof = parts
        expected = s['seq'] + 1
        if expected > 2147483647 or seq != str(expected) or name not in ('LOCK', 'UNLOCK', 'START', 'FIND') or not equal(mac(self.key, 'cmd:v2:%s:%s:%s' % (s['nonce'], seq, name)), proof):
            self.reject(conn)
            return None
        # Consume even when GPIO is busy: a signed packet can execute at most once.
        s['seq'] = expected
        s['last'] = self.now()
        return name.lower()
