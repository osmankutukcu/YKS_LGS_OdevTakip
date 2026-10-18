// V25.7 controlled Baileys test: no browser, no bulk, NO credentials persisted.
import {createInterface} from 'node:readline';
import {readFileSync,existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {checkCommand,TEST_TEXT,resultCode} from './rules.mjs';
const ROOT=dirname(fileURLToPath(import.meta.url));
let socket=null, connected=false, finished=false, claimed=false, restarts=0, qrCount=0;
const emit=(type,more={})=>process.stdout.write(JSON.stringify({type,...more})+'\n');
function die(reason){if(!finished){finished=true;emit('stopped',{reason});}try{socket?.end(new Error('test stopped'));}catch{} setTimeout(()=>process.exit(0),60).unref();}
function preflight(){
  if(Number(process.versions.node.split('.')[0])<20) throw Error('Node.js 20+ gerekiyor');
  const pkg=JSON.parse(readFileSync(join(ROOT,'package.json'),'utf8'));
  if(pkg.dependencies?.['@whiskeysockets/baileys']!=='7.0.0-rc14') throw Error('Baileys sürümü doğrulanamadı');
  if(!existsSync(join(ROOT,'package-lock.json'))) throw Error('Kilit dosyası eksik; Windows_Hazirla_V257.cmd çalıştırın');
  const lock=JSON.parse(readFileSync(join(ROOT,'package-lock.json'),'utf8'));
  const direct=lock.packages?.['node_modules/@whiskeysockets/baileys'];
  if(direct?.version!=='7.0.0-rc14'||!direct?.integrity?.startsWith('sha512-')) throw Error('Baileys bütünlük kilidi geçersiz');
}
const log={level:'silent',trace(){},debug(){},info(){},warn(){},error(){},fatal(){},child(){return this}};
async function main(){
  preflight();
  // Third-party code is only loaded after the preflight checks.
  const {default:makeWASocket,initAuthCreds,DisconnectReason} = await import('@whiskeysockets/baileys');
  const creds=initAuthCreds();
  const stored=new Map();
  const state={creds,keys:{
    get:async (kind,ids)=>Object.fromEntries(ids.map(id=>[id,stored.get(kind+':'+id)]).filter(([,val])=>val!==undefined)),
    set:async data=>{for(const [kind,entries] of Object.entries(data)){for(const [key,val] of Object.entries(entries)){const id=kind+':'+key; if(val==null) stored.delete(id);else stored.set(id,val);}}}
  }};
  async function connect(){
    socket=makeWASocket({auth:state,logger:log,syncFullHistory:false,markOnlineOnConnect:false,connectTimeoutMs:45000});
    socket.ev.on('creds.update',update=>Object.assign(creds,update));
    socket.ev.on('connection.update',data=>{
      if(finished)return;
      if(data.qr){if(++qrCount>5){die('QR sınırı aşıldı');return;}emit('qr',{qr:data.qr});}
      if(data.connection==='open'){connected=true;emit('connected');}
      if(data.connection==='close'){
        connected=false;
        const code=data.lastDisconnect?.error?.output?.statusCode;
        if(!claimed&&code===DisconnectReason.restartRequired&&restarts++===0){
          try{socket?.end(new Error('pair restart'));}catch{} connect().catch(()=>die('Eşleştirme sonrası yeniden bağlanılamadı'));return;
        }
        die(claimed?'Gönderim sonrası bağlantı kapandı; sonucu belirsiz':'Bağlantı kapandı; yeniden bağlanmayı siz başlatın');
      }
    });
  }
  const commands=createInterface({input:process.stdin,crlfDelay:Infinity});
  commands.on('line',line=>{
    if(finished)return;
    let req;
    try{if(line.length>350)throw Error('Komut çok uzun');req=checkCommand(JSON.parse(line));}
    catch{emit('rejected',{reason:'Geçersiz komut veya onay'});return;}
    if(req.cmd==='stop'){die('Kullanıcı durdurdu');return;}
    if(!connected){emit('rejected',{reason:'Bağlantı henüz hazır değil'});return;}
    if(claimed){emit('rejected',{reason:'Bu oturumda yalnızca tek deneme mümkün'});return;}
    claimed=true; // set before send; do not ever retry.
    emit('attempting');
    socket.sendMessage(req.phone+'@s.whatsapp.net',{text:TEST_TEXT})
      .then(res=>{emit('result',{status:resultCode(res?.key?.id)});die('Tek deneme tamamlandı');})
      .catch(()=>{emit('result',{status:'SONUC_BELIRSIZ'});die('Tek deneme tamamlandı; tekrar etmeyin');});
  });
  emit('starting');
  setTimeout(()=>die('Oturum zaman aşımı, mesaj otomatik tekrarlanmayacak'),180000).unref();
  await connect();
}
main().catch(()=>{emit('error',{reason:'Bağlantı bileşeni çalışmadı. Bağımlılık ve kurulum durumunu kontrol edin.'});die('Kurulum/bağlantı hazırlığı başarısız');});
