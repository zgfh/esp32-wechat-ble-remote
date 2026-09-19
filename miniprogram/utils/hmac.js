const sha256 = require('./sha256');
const utf8 = s => Array.from(unescape(encodeURIComponent(s)), c => c.charCodeAt(0));
const unhex = s => s.match(/../g).map(x => parseInt(x, 16));
module.exports = function hmac(key, message) {
  let k = typeof key === 'string' ? utf8(key) : key.slice();
  if (k.length > 64) k = unhex(sha256(k));
  while (k.length < 64) k.push(0);
  return sha256(k.map(x => x ^ 0x5c).concat(unhex(sha256(k.map(x => x ^ 0x36).concat(utf8(message))))));
};
