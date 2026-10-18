// Validates the isolated, opt-in bulk protocol without loading WhatsApp or Python.
export const MAX_BATCH=150;
export const MIN_DELAY_MS=15000;  // anti-flood; never claim this guarantees account safety
export const MAX_TEXT=3000;
export function validateSend(req) {
  if(req?.cmd!=='send-one'||req?.approval!=='IZINLI_TOPLU_V258') throw Error('Komut/onay hatası');
  if(typeof req.id!=='string'||!/^[a-f0-9]{32}$/.test(req.id)) throw Error('İş kimliği geçersiz');
  if(typeof req.phone!=='string'||!/^905\d{9}$/.test(req.phone)) throw Error('Telefon geçersiz');
  if(typeof req.text!=='string'||!req.text.trim()||req.text.length>MAX_TEXT) throw Error('Mesaj sınırı');
  return {id:req.id, phone:req.phone, text:req.text};
}
export function allowedToSend({connected, busy, count, previousAt, now, seen}, req) {
  if(!connected||busy||count>=MAX_BATCH||seen.has(req.phone))return false;
  if(previousAt && now-previousAt<MIN_DELAY_MS)return false;
  return true;
}
