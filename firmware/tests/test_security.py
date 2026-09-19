import unittest,sys,pathlib,hmac,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]))
from security import Security,mac
class SecurityTests(unittest.TestCase):
 def setUp(self):
  self.now=0;self.key='k'*64;self.s=Security(self.key,lambda:self.now,lambda a,b:a-b)
 def auth(self,c=1):
  self.assertTrue(self.s.open(c)); n=self.s.challenge(c);self.assertTrue(self.s.authenticate(c,mac(self.key,'auth:v2:'+n)));return n
 def cmd(self,n,seq=1,name='LOCK'):
  return 'CMD2:%d:%s:%s'%(seq,name,mac(self.key,'cmd:v2:%s:%d:%s'%(n,seq,name)))
 def test_hmac_vectors(self):
  self.assertEqual(mac(bytes([11])*20,'Hi There'),'b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7')
  for key in ['k','k'*131,'中文']:
   self.assertEqual(mac(key,'消息'),hmac.new(key.encode(),'消息'.encode(),hashlib.sha256).hexdigest())
 def test_replay_and_changed_command(self):
  n=self.auth(); packet=self.cmd(n);self.assertEqual(self.s.command(1,packet),'lock');self.assertIsNone(self.s.command(1,packet))
  n=self.auth();self.assertIsNone(self.s.command(1,self.cmd(n).replace(':LOCK:',':START:')))
 def test_cross_session_replay(self):
  n=self.auth();packet=self.cmd(n);self.s.close(1);self.auth();self.assertIsNone(self.s.command(1,packet))
 def test_timeout_not_extended_by_hello(self):
  self.s.open(1);self.now=14999;self.s.challenge(1);self.now=15000;self.assertTrue(self.s.expired(1))
 def test_failures_cooldown_and_single_connection(self):
  self.s.open(1);self.assertFalse(self.s.open(2));self.s.close(1)
  for i in range(5):self.assertTrue(self.s.open(1));self.s.challenge(1);self.assertFalse(self.s.authenticate(1,'0'*64))
  self.assertFalse(self.s.open(1));self.now=30000;self.assertTrue(self.s.open(1))
 def test_plaintext_rejected_idle_and_placeholder(self):
  self.auth();self.assertIsNone(self.s.command(1,'CMD:UNLOCK'))
  self.auth();self.now=300000;self.assertTrue(self.s.expired(1))
  s=Security('CHANGE_THIS_TO_A_LONG_RANDOM_SECRET',lambda:0,lambda a,b:a-b);s.open(1);self.assertIsNone(s.challenge(1))
if __name__=='__main__':unittest.main()
