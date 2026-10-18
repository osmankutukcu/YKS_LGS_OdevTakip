// Pure functions; safe to import without loading Baileys.
export const TEST_TEXT='Ödev Takip V25.7 izinli bağlantı testi. Bu mesaj gerçek öğrenci/veli bilgisi içermez.';
export function phone(input) {
  const s=String(input??'').trim();
  if (!/^\+?[\d\s.()\-]+$/.test(s) || /[,;\/\r\n]/.test(s)) throw new Error('Telefon numarası biçimi geçersiz');
  let d=s.replace(/\D/g,'');
  if(d.startsWith('00')) d=d.slice(2);
  if(d.startsWith('0')) d='9'+d;
  if(d.length===10 && d.startsWith('5')) d='90'+d;
  if(!/^905\d{9}$/.test(d)) throw new Error('Yalnızca izinli tek Türkiye cep numarası');
  return d;
}
export function checkCommand(request) {
  if(request?.cmd==='stop') return {cmd:'stop'};
  if(request?.cmd!=='send-test'||request?.approval!=='TEK TEST ONAYI') throw new Error('Onaysız komut reddedildi');
  return {cmd:'send-test',phone:phone(request.phone)};
}
export function resultCode(messageId){return messageId?'ISTEMCI_KABUL_ETTI_TESLIM_BELIRSIZ':'SONUC_BELIRSIZ';}
