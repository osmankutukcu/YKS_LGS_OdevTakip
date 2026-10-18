/* V8 user-authorized encrypted backup directory; NEVER writes unencrypted student data.
 * Browser-private IndexedDB remains the working store. Folder is an independent
 * explicitly user-approved recovery copy, not the app's actual database.
 */
(function (window) {
    'use strict';
    const NAME = 'YKS_Offline_Store_v1';
    const VERSION = 3;
    const HANDLE_KEY = 'v8_recovery_folder';
    const ext = '.yksbackup';
    let active = false;

    function openDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(NAME, VERSION);
            request.onupgradeneeded = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', {keyPath:'key'});
                if (!db.objectStoreNames.contains('snapshots')) db.createObjectStore('snapshots',{keyPath:'key'});
                if (!db.objectStoreNames.contains('outbox')) db.createObjectStore('outbox',{keyPath:'id'});
            };
            request.onsuccess = () => {const db=request.result; resolve(db);};
            request.onerror = () => reject(request.error);
            request.onblocked = () => reject(new Error('Diğer uygulama sekmelerini kapatın.'));
        });
    }
    async function metadata(readOrWrite, entry) {
        const db = await openDB();
        try {
            return await new Promise((resolve,reject) => {
                const tx=db.transaction('meta',readOrWrite);
                let req;
                if (readOrWrite === 'readonly') req=tx.objectStore('meta').get(HANDLE_KEY);
                else req=tx.objectStore('meta').put({key:HANDLE_KEY,value:entry});
                tx.oncomplete=()=>resolve(readOrWrite==='readonly' ? req.result?.value || null : true);
                tx.onerror=()=>reject(tx.error);
                tx.onabort=()=>reject(tx.error || new Error('Klasör izni kaydedilemedi.'));
            });
        } finally {db.close();}
    }
    const supportsDirectory = () => typeof window.showDirectoryPicker === 'function' && window.isSecureContext === true;
    async function chooseFolder() {
        if (!supportsDirectory()) throw new Error('Bu tarayıcı klasör seçimine izin vermiyor. Şifreli yedeği Dosyalar’a kaydetme seçeneğini kullanın.');
        // Must be invoked directly from a button (user gesture).
        const handle = await window.showDirectoryPicker({id:'yks-offline-recovery',mode:'readwrite'});
        if (handle?.kind !== 'directory' || typeof handle.getFileHandle !== 'function') throw Error('Klasör seçilemedi.');
        await metadata('readwrite',handle);
        return handle.name || 'Seçili klasör';
    }
    async function getStoredFolder() {return await metadata('readonly');}
    async function permission(handle) {
        let granted='prompt';
        if (typeof handle.queryPermission==='function') granted=await handle.queryPermission({mode:'readwrite'});
        if (granted!=='granted' && typeof handle.requestPermission==='function') {
            granted=await handle.requestPermission({mode:'readwrite'});
        }
        if (granted!=='granted') throw new Error('Klasöre yazma izni verilmedi. Şifreli yedeğinizi Dosyalar üzerinden kaydedebilirsiniz.');
    }
    function backupName() {
        const stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d+Z$/, 'Z');
        const suffix=Array.from(crypto.getRandomValues(new Uint8Array(4)), b => b.toString(16).padStart(2,'0')).join('');
        return `YKS_LGS_Yedek_${stamp}_${suffix}${ext}`;
    }
    async function hash(file) {return new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()));}
    function sameHash(a,b) {return a.length===b.length && a.every((v,i)=>v===b[i]);}
    async function writeBackup(handle,blob,filename) {
        if (!handle || handle.kind!=='directory') throw Error('Önce klasör seçin.');
        await permission(handle);
        // Unique filename, old backups never overwritten; failed writes cannot
        // delete previous backups. A partial newly created file is not trusted.
        const file=await handle.getFileHandle(filename,{create:true});
        const writable=await file.createWritable();
        try {await writable.write(blob);await writable.close();}
        catch (error) {try {await writable.abort();} catch (_) {} throw error;}
        const recorded=await file.getFile();
        if (recorded.size!==blob.size || !sameHash(await hash(recorded),await hash(blob))) {
            throw new Error('Yedek dosyası doğrulanamadı. Önceki yedekler korunuyor.');
        }
        return filename;
    }
    async function downloadOrShare(blob,filename) {
        const file = new File([blob],filename,{type:'application/octet-stream'});
        if (window.navigator?.canShare?.({files:[file]}) && window.navigator?.share) {
            // Share sheet is always a manual user action; selecting Files is
            // controlled by the OS, not by the web page.
            await window.navigator.share({files:[file],title:'Şifreli YKS–LGS yedeği'});
            return {method:'share',filename};
        }
        const url=URL.createObjectURL(blob);
        try {
            const a=window.document.createElement('a');
            a.href=url;a.download=filename;window.document.body.append(a);a.click();a.remove();
            return {method:'download',filename};
        } finally {setTimeout(()=>URL.revokeObjectURL(url),30000);}
    }
    async function save({password,preferFolder=true}={}) {
        if (active || window.OfflineSync?.syncing || window.OfflineSync?.restoring ||
            window.OfflineVault?.busy || window.OfflineSecureStore?.busy) {
            throw Error('Önce devam eden kayıt/eşitleme işlemi bitmeli.');
        }
        if (window.OfflineSecureStore && await window.OfflineSecureStore.enabled() &&
            !window.OfflineSecureStore.unlocked) {
            throw Error('Önce şifreli çalışma alanını açın.');
        }
        active=true;
        try {
            // Ask for folder write permission BEFORE the expensive PBKDF2 backup
            // encryption, while user activation from the Save button may remain.
            const handle=preferFolder ? await getStoredFolder() : null;
            if (handle && supportsDirectory()) await permission(handle);
            // V4/V5 AES-256-GCM authenticated encrypted bundle, identical restore format.
            const blob=await window.OfflineVault.exportEncryptedBackup(password);
            const filename=backupName();
            if (handle && supportsDirectory()) {
                return {method:'folder',filename:await writeBackup(handle,blob,filename),folder:handle.name};
            }
            return await downloadOrShare(blob,filename);
        } finally {active=false;}
    }
    async function status() {
        const handle=await getStoredFolder().catch(()=>null);
        return {supported:supportsDirectory(), folder: handle?.name || null};
    }
    window.OfflineFolderV8=Object.freeze({supportsDirectory,chooseFolder,save,status,writeBackup,downloadOrShare});
})(window);
