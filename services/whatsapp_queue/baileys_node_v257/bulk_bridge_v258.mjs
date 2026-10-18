// V25.8 opt-in 1..150, one recipient per request. No session persistence,
// no raw messages/phones in stdout, no automatic retry or reconnect after sends.
import {createInterface} from 'node:readline';
import {readFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {validateSend,allowedToSend,MAX_BATCH} from './bulk_rules_v258.mjs';
const ROOT=dirname(fileURLToPath(import.meta.url));
const emit=(type,extra={})=>process.stdout.write(JSON.stringify({type,...extra})+'\n');
let socket,connected=false,finished=false,busy=false,started=false,attempts=0,previousAt=0,restarts=0,qrCount=0;
let seen=new Set();
function stop(reason){if(finished)return;finished=true;emit('stopped',{reason});try{socket?.end(new Error('session finished'));}catch{}setTimeout(()=>process.exit(0),50).unref();}
function preflight(){
  if(Number(process.versions.node.split('.')[0])<20)throw Error('Node 20+ gerekli');
  const pkg=JSON.parse(readFileSync(join(ROOT,'package.json'),'utf8'));
  if(pkg.dependencies?.['@whiskeysockets/baileys']!=='7.0.0-rc14')throw Error('Bağımlılık sürümü uyumsuz');
  if(!existsSync(join(ROOT,'package-lock.json')))throw Error('Kilit dosyası yok');
  const lock=JSON.parse(readFileSync(join(ROOT,'package-lock.json'),'utf8'));
  const record=lock.packages?.['node_modules/@whiskeysockets/baileys'];
  if(record?.version!=='7.0.0-rc14'||!record?.integrity?.startsWith('sha512-'))throw Error('Kilit doğrulaması başarısız');
}
const log={level:'silent',trace(){},debug(){},info(){},warn(){},error(){},fatal(){},child(){return this}};
async function main(){
  preflight();
  const {default:makeWASocket,initAuthCreds,DisconnectReason}=await import('@whiskeysockets/baileys');
  const creds=initAuthCreds(),memory=new Map();
  const state={creds,keys:{
    get:async(kind,ids)=>Object.fromEntries(ids.map(id=>[id,memory.get(kind+':'+id)]).filter(([,v])=>v!==undefined)),
    set:async(data)=>{for(const [kind,items] of Object.entries(data))for(const [id,v] of Object.entries(items)){const k=kind+':'+id;if(v==null)memory.delete(k);else memory.set(k,v);}}
  }};
  async function connect(){
    socket=makeWASocket({auth:state,logger:log,syncFullHistory:false,markOnlineOnConnect:false,connectTimeoutMs:45000});
    socket.ev.on('creds.update',u=>Object.assign(creds,u));
    socket.ev.on('connection.update',d=>{
      if(finished)return;
      if(d.qr){if(++qrCount>6){stop('QR sınırı doldu');return;}emit('qr',{qr:d.qr});}
      if(d.connection==='open'){connected=true;started=true;emit('connected',{max:MAX_BATCH});}
      if(d.connection==='close'){
        connected=false;
        const code=d.lastDisconnect?.error?.output?.statusCode;
        if(!started&&!busy&&code===DisconnectReason.restartRequired&&restarts++===0){
          try{socket?.end(new Error('pair restart'));}catch{}
          connect().catch(()=>stop('Eşleştirme tamamlanamadı'));return;
        }
        stop('Oturum kapandı; devam eden işin sonucu belirsiz; otomatik yeniden bağlantı yok');
      }
    });
  }
  const stdin=createInterface({input:process.stdin,crlfDelay:Infinity});
  stdin.on('line',async line=>{
    if(finished)return;
    let req;
    try{if(line.length>16000)throw Error('çok uzun');req=JSON.parse(line);}catch{emit('rejected',{reason:'Komut okunamadı'});return;}
    if(req?.cmd==='stop'){stop('Kullanıcı durdurdu');return;}
    try{req=validateSend(req);}catch{emit('rejected',{reason:'İzin / numara / metin kontrolü başarısız'});return;}
    if(!allowedToSend({connected,busy,count:attempts,previousAt,now:Date.now(),seen},req)){
      emit('rejected',{reason:'Bağlantı/süre/tekilleştirme/sınır kontrolü geçersiz'});return;
    }
    busy=true;attempts++;seen.add(req.phone);previousAt=Date.now();
    emit('attempting',{id:req.id,number:attempts});
    let timer;
    try{
      // Avoid an infinite wait if the network stalls. A timed-out attempt
      // remains UNKNOWN and the entire session is stopped without retry.
      const reply=socket.sendMessage(req.phone+'@s.whatsapp.net',{text:req.text});
      const timeout=new Promise((_,reject)=>{
        timer=setTimeout(()=>reject(new Error('send timeout')),60000);
        timer.unref();
      });
      const message=await Promise.race([reply,timeout]);
      if(!finished)emit('result',{id:req.id,status:message?.key?.id?'ISTEMCI_KABUL_ETTI_TESLIM_BELIRSIZ':'SONUC_BELIRSIZ'});
    }catch{
      if(!finished){emit('result',{id:req.id,status:'SONUC_BELIRSIZ'});stop('Sonuç belirsiz; bu partide başka alıcı denenmedi');}
    }finally{if(timer)clearTimeout(timer);busy=false;}
  });
  emit('starting');
  setTimeout(()=>{if(!started)stop('QR oturumu zaman aşımı')},180000).unref();
  await connect();
}
main().catch(()=>{emit('error',{reason:'Baileys motoru başlatılamadı. Kurulum dosyalarını kontrol edin.'});stop('Motor başlatılamadı');});
