/* V8 immutable page download; never commits partial data to IndexedDB. */
(function (window) {
  'use strict';
  function sha256Sync(ascii) {
    function rightRotate(value, amount) { return (value >>> amount) | (value << (32 - amount)); }
    const utf8Bytes = new TextEncoder().encode(ascii);
    const words = [];
    let hash = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    const k = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ];
    for (let i = 0; i < utf8Bytes.length; i++) {
        words[i >> 2] |= utf8Bytes[i] << ((3 - (i % 4)) * 8);
    }
    const byteLength = utf8Bytes.length;
    words[byteLength >> 2] |= 0x80 << ((3 - (byteLength % 4)) * 8);
    const targetWords = (((byteLength + 8) >> 6) + 1) * 16;
    while (words.length < targetWords) words.push(0);
    const bitLen = byteLength * 8;
    words[targetWords - 2] = Math.floor(bitLen / 0x100000000);
    words[targetWords - 1] = bitLen >>> 0;
    for (let j = 0; j < words.length; j += 16) {
        const w = words.slice(j, j + 16);
        let [a, b, c, d, e, f, g, h] = hash;
        for (let i = 0; i < 64; i++) {
            if (i >= 16) {
                const s0 = rightRotate(w[i - 15], 7) ^ rightRotate(w[i - 15], 18) ^ (w[i - 15] >>> 3);
                const s1 = rightRotate(w[i - 2], 17) ^ rightRotate(w[i - 2], 19) ^ (w[i - 2] >>> 10);
                w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
            }
            const S1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
            const ch = (e & f) ^ ((~e) & g);
            const temp1 = (h + S1 + ch + k[i] + (w[i] | 0)) | 0;
            const S0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
            const maj = (a & b) ^ (a & c) ^ (b & c);
            const temp2 = (S0 + maj) | 0;
            h = g; g = f; f = e; e = (d + temp1) | 0;
            d = c; c = b; b = a; a = (temp1 + temp2) | 0;
        }
        hash[0] = (hash[0] + a) | 0; hash[1] = (hash[1] + b) | 0;
        hash[2] = (hash[2] + c) | 0; hash[3] = (hash[3] + d) | 0;
        hash[4] = (hash[4] + e) | 0; hash[5] = (hash[5] + f) | 0;
        hash[6] = (hash[6] + g) | 0; hash[7] = (hash[7] + h) | 0;
    }
    return hash.map(val => (val >>> 0).toString(16).padStart(8, '0')).join('');
  }
  if (typeof window !== 'undefined') window._pureSha256 = sha256Sync;
  async function sha256Hex(raw) {
    if (window.crypto?.subtle) {
      const bytes = new TextEncoder().encode(raw);
      const hash = new Uint8Array(await window.crypto.subtle.digest('SHA-256', bytes));
      return Array.from(hash, x => x.toString(16).padStart(2, '0')).join('');
    }
    return sha256Sync(raw);
  }
  async function download({ api, expectedDatabaseId = null, progress = () => {}, assertOwned = async () => {} }) {
    if (typeof api !== 'function') throw new Error('Yetkili API çağrısı gerekli.');
    await assertOwned();
    const session = await api('/api/sync/paged/start', 'POST');
    if (session.version !== 8 || !/^[a-f0-9]{64}$/.test(session.sha256) ||
        !Number.isInteger(session.pages) || session.pages < 1 || session.pages > 2048 ||
        !Number.isInteger(session.size) || session.size < 1 || session.size > 24 * 1024 * 1024 ||
        !session.database_id || typeof session.token !== 'string' || session.token.length < 30) {
      throw new Error('Geçersiz parçalı indirme oturumu');
    }
    if (expectedDatabaseId && session.database_id !== expectedDatabaseId) {
      throw new Error('Masaüstü veritabanı kimliği farklı; yerel kayıtlar korunuyor.');
    }
    const chunks = [];
    try {
      for (let page = 0; page < session.pages; page++) {
        await assertOwned();
        const result = await api(`/api/sync/paged/${encodeURIComponent(session.token)}/${page}`);
        if (result.version !== 8 || result.page !== page || result.pages !== session.pages ||
            result.sha256 !== session.sha256 || typeof result.chunk !== 'string' ||
            result.chunk.length > session.page_chars) {
          throw new Error(`Sayfa ${page + 1} doğrulanamadı; önceki veriler korunuyor.`);
        }
        chunks.push(result.chunk);
        progress(page + 1, session.pages);
      }
      await assertOwned();
      const raw = chunks.join('');
      if (raw.length !== session.size || await sha256Hex(raw) !== session.sha256) {
        throw new Error('İndirilen veri SHA-256 kontrolünü geçemedi; kaydedilmedi.');
      }
      const data = JSON.parse(raw);
      if (data.version !== 1 || data.database_id !== session.database_id ||
          !Array.isArray(data.students) || !data.curriculum ||
          Object.keys(data.curriculum).length !== data.students.length) {
        throw new Error('Öğrenci veri paketi tutarsız; kaydedilmedi.');
      }
      return data;
    } finally {
      try { await api(`/api/sync/paged/${encodeURIComponent(session.token)}/close`, 'POST'); }
      catch (_) { /* Session also expires; never hide the original failure. */ }
    }
  }
  window.OfflinePagedV8 = Object.freeze({download, sha256Hex});
})(window);
