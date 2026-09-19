"""Host-side protocol regression tests; never touches physical GPIO."""
import ast
import hashlib
import pathlib
import unittest
import sys
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
from security import Security, mac

class ProtocolTest(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((pathlib.Path(__file__).parents[1] / 'main.py').read_text())
        functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('irq', 'handle_message', 'press', 'release_buttons', 'disconnect_client', 'check_connections')], type_ignores=[])
        class Pin:
            value = 0
            def on(self): self.value = 1
            def off(self): self.value = 0
        class BLE:
            chunk = b''
            def gatts_read(self, handle): return self.chunk
        import os, binascii
        self.events = []
        self.ns = dict(log_streams={}, log_history=[], log=lambda *args: None, os=os, ubinascii=binascii, BLE_PAIRING_SECRET='k'*64, authenticated=set(), nonces={}, connections={1}, receive_buffers={}, command_handle=7, CONNECT=1, DISCONNECT=2, WRITE=3, ble=BLE(), advertise=lambda: None, digest=lambda s: hashlib.sha256(s.encode()).hexdigest(), status=lambda s,c=None:self.events.append(s), buttons={'lock':Pin(),'unlock':Pin(),'start':Pin(),'find':Pin()}, release_at={'lock':None,'unlock':None,'start':None,'find':None}, ticks_ms=lambda:100, ticks_add=lambda x,y:x+y, ticks_diff=lambda x,y:x-y, PRESS_MS=180)
        self.ns.update(pending_disconnect=set(), packet_windows={})
        self.ns['security'] = Security('k'*64, lambda:self.ns['ticks_ms'](), lambda a,b:a-b)
        self.ns['security'].open(1)
        self.seq = 0
        exec(compile(functions, '<firmware>', 'exec'), self.ns)
    def send(self, message):
        if message.startswith('CMD:') and 1 in self.ns['authenticated']:
            self.seq += 1
            name=message[4:]; nonce=self.ns['security'].sessions[1]['nonce']
            message='CMD2:%d:%s:%s' % (self.seq,name,mac('k'*64,'cmd:v2:%s:%d:%s' % (nonce,self.seq,name)))
        framed=(message+'\n').encode()
        for offset in range(0,len(framed),20):
            self.ns['ble'].chunk=framed[offset:offset+20]
            self.ns['irq'](3,(1,7))
    def authenticate(self):
        if 1 not in self.ns['security'].sessions:
            self.ns['pending_disconnect'].discard(1); self.ns['security'].open(1); self.ns['receive_buffers'].clear()
        self.send('HELLO2')
        nonce=self.events[-1].split(':')[1]
        self.send('AUTH2:'+mac('k'*64,'auth:v2:'+nonce))
        self.assertEqual(self.events[-1],'AUTH_OK')
    def test_fragment_auth_and_pulse(self):
        self.authenticate(); self.send('CMD:LOCK')
        self.assertEqual(self.events[-1],'OK:LOCK')
        self.send('CMD:UNLOCK'); self.assertEqual(self.events[-1],'ERROR:BUSY')
        self.assertEqual(self.ns['buttons']['unlock'].value,0)
        self.ns['ticks_ms']=lambda:280; self.ns['release_buttons']()
        self.assertEqual(self.ns['buttons']['lock'].value,0)
    def test_no_auth_and_disconnect(self):
        self.send('CMD:UNLOCK'); self.assertEqual(self.events[-1],'ERROR:AUTH_REQUIRED')
        self.authenticate(); self.ns['irq'](2,(1,0,0)); self.send('CMD:UNLOCK')
        self.assertNotIn(1,self.ns['authenticated']); self.assertEqual(self.ns['buttons']['unlock'].value,0)
    def test_nonce_single_use_and_default_rejected(self):
        self.authenticate()
        self.send('HELLO2')
        self.assertIn(1,self.ns['pending_disconnect'])
        self.assertNotIn(1,self.ns['authenticated'])

    def test_start_auth_interlock_and_release(self):
        self.send('CMD:START'); self.assertEqual(self.events[-1],'ERROR:AUTH_REQUIRED')
        self.assertEqual(self.ns['buttons']['start'].value,0)
        self.authenticate(); self.send('CMD:START')
        self.assertEqual(self.events[-1],'OK:START')
        self.assertEqual(self.ns['buttons']['start'].value,1)
        for command in ('CMD:LOCK','CMD:UNLOCK','CMD:START'):
            self.send(command); self.assertEqual(self.events[-1],'ERROR:BUSY')
        self.ns['ticks_ms']=lambda:280; self.ns['release_buttons']()
        self.assertEqual(self.ns['buttons']['start'].value,0)
        self.send('CMD:LOCK'); self.send('CMD:START')
        self.assertEqual(self.events[-1],'ERROR:BUSY')

    def test_find_auth_interlock_and_release(self):
        self.send('CMD:FIND'); self.assertEqual(self.events[-1],'ERROR:AUTH_REQUIRED')
        self.assertEqual(self.ns['buttons']['find'].value,0)
        self.authenticate(); self.send('CMD:FIND')
        self.assertEqual(self.events[-1],'OK:FIND')
        self.assertEqual(self.ns['buttons']['find'].value,1)
        for command in ('CMD:LOCK','CMD:UNLOCK','CMD:FIND'):
            self.send(command); self.assertEqual(self.events[-1],'ERROR:BUSY')
        self.ns['ticks_ms']=lambda:280; self.ns['release_buttons']()
        self.assertEqual(self.ns['buttons']['find'].value,0)
        self.send('CMD:LOCK'); self.send('CMD:FIND')
        self.assertEqual(self.events[-1],'ERROR:BUSY')

    def test_partial_and_oversized(self):
        self.ns['ble'].chunk=b'CMD:LOCK'; self.ns['irq'](3,(1,7)); self.assertEqual(self.events,[])
        self.ns['ble'].chunk=b'a'*129; self.ns['irq'](3,(1,7)); self.assertEqual(self.events[-1],'ERROR:TOO_LONG')

class LogStreamTest(unittest.TestCase):
    def test_auth_gate_fragmentation_and_pulse_priority(self):
        tree = ast.parse((pathlib.Path(__file__).parents[1] / 'main.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'stream_logs')
        packets = []
        class BLE:
            def gatts_notify(self, conn, handle, payload): packets.append((conn, payload))
        stream = lambda: {'lines':['x'*55], 'pending':b'', 'dropped':0}
        ns = dict(log_streams={1:stream(),2:stream()}, authenticated={1}, release_at={'lock':None}, ble=BLE(), log_handle=9)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<stream>', 'exec'), ns)
        ns['stream_logs'](); self.assertNotIn(2,ns['log_streams'])
        ns['release_at']['lock']=180; ns['stream_logs'](); self.assertEqual(len(packets),1)
        ns['release_at']['lock']=None
        ns['stream_logs'](); ns['stream_logs']()
        self.assertEqual(b''.join(p[1] for p in packets), b'x'*55+b'\n')
        self.assertTrue(all(p[0]==1 and len(p[1])<=20 for p in packets))

if __name__=='__main__': unittest.main()
