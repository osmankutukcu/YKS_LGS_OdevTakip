/** V9 changed-student transport. Pure read until caller commits a full validated baseline. */
(function (window) {
  'use strict';
  const HEX64 = /^[a-f0-9]{64}$/;
  const ID = /^(0|[1-9][0-9]{0,19})$/;
  const MAX_STUDENTS = 10000;
  function canonical(value) {
    if (value === null) return 'null';
    if (typeof value === 'string') return JSON.stringify(value);
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) throw Error('Geçersiz yerel sayı');
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (typeof value === 'object' && value) {
      return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
    }
    throw Error('Geçersiz çevrimdışı kayıt türü');
  }
  async function hash(s) {
    if (window.crypto?.subtle) {
      const out = new Uint8Array(await window.crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)));
      return Array.from(out, x => x.toString(16).padStart(2,'0')).join('');
    }
    if (typeof window._pureSha256 === 'function') {
      return window._pureSha256(s);
    }
    throw Error('SHA-256 için HTTPS gerekli');
  }
  const rowHash = (student, curriculum) => hash(canonical({student, curriculum}));
  function baselineIndex(data) {
    if (!data || data.version !== 1 || !data.database_id || !Array.isArray(data.students) ||
        !data.curriculum || data.students.length > MAX_STUDENTS) throw Error('Yerel tam veri paketi geçersiz');
    const lookup = new Map();
    for (const student of data.students) {
      const id = String(student.id);
      if (!ID.test(id) || lookup.has(id) || !Object.prototype.hasOwnProperty.call(data.curriculum,id))
        throw Error('Yerel öğrenci/veri eşleşmesi tutarsız');
      lookup.set(id,student);
    }
    if (Object.keys(data.curriculum).length !== lookup.size) throw Error('Yerel veri fazlalığı veya eksikliği');
    return lookup;
  }
  async function download({api, baseline, expectedDatabaseId, assertOwned = async () => {}, progress=()=>{}}) {
    if (typeof api !== 'function') throw Error('Yetkili API çağrısı gerekli');
    const lookup = baselineIndex(baseline);
    if (expectedDatabaseId && baseline.database_id !== expectedDatabaseId)
      throw Error('Yerel veritabanı kimliği değişmiş');
    const manifest = {};
    for (const [id,student] of lookup) {
      manifest[id] = await rowHash(student,baseline.curriculum[id]);
    }
    await assertOwned();
    const session = await api('/api/sync/delta9/start','POST',{
      database_id: baseline.database_id, manifest
    });
    if (session.version !== 9 || !HEX64.test(session.sha256) ||
        !session.database_id || session.database_id !== baseline.database_id ||
        !Number.isInteger(session.pages) || session.pages < 1 || session.pages > 2048 ||
        !Number.isInteger(session.size) || session.size < 1 || session.size > 24*1024*1024 ||
        !Number.isInteger(session.page_chars) || session.page_chars < 1 ||
        !session.token || typeof session.token !== 'string' || session.token.length < 30)
      throw Error('Geçersiz V9 değişiklik oturumu veya yanlış masaüstü');
    const chunks = [];
    try {
      for (let n = 0; n < session.pages; n++) {
        await assertOwned();
        const page = await api(`/api/sync/delta9/${encodeURIComponent(session.token)}/${n}`);
        if (page.version !== 9 || page.page !== n || page.pages !== session.pages ||
            page.sha256 !== session.sha256 || typeof page.chunk !== 'string' ||
            page.chunk.length > session.page_chars) throw Error('Değişiklik parçası hatalı');
        chunks.push(page.chunk);
        progress(n+1,session.pages);
      }
      await assertOwned();
      const raw = chunks.join('');
      if (raw.length !== session.size || await hash(raw) !== session.sha256)
        throw Error('Değişiklik paketi bütünlük kontrolünden geçmedi');
      const patch = JSON.parse(raw);
      if (patch.version !== 9 || patch.snapshot_version !== 1 || patch.database_id !== baseline.database_id ||
          typeof patch.generated_at !== 'string' || !Array.isArray(patch.order) ||
          patch.order.length > MAX_STUDENTS || !patch.index || !patch.changed || !Array.isArray(patch.removed))
        throw Error('Sunucunun değişiklik paketi geçersiz');
      const order = patch.order.map(String), orderSet = new Set(order);
      if (orderSet.size !== order.length || order.some(x=>!ID.test(x)) ||
          Object.keys(patch.index).length !== order.length ||
          Object.keys(patch.changed).some(x=>!orderSet.has(x)) ||
          order.some(x=>!HEX64.test(patch.index[x] || '')))
        throw Error('Değişiklik listesi tutarsız');
      const deletion = new Set(patch.removed.map(String));
      const shouldRemove = [...lookup.keys()].filter(x=>!orderSet.has(x));
      if (deletion.size !== patch.removed.length ||
          deletion.size !== shouldRemove.length || shouldRemove.some(x=>!deletion.has(x)))
        throw Error('Silinme kayıtları eksik; eski veriler korunuyor');
      const nextStudents=[], nextCurriculum={};
      for (const id of order) {
        const rec = Object.prototype.hasOwnProperty.call(patch.changed,id) ? patch.changed[id] : null;
        const student = rec ? rec.student : lookup.get(id);
        const curriculum = rec ? rec.curriculum : baseline.curriculum[id];
        if (!student || !curriculum || String(student.id) !== id ||
            await rowHash(student,curriculum) !== patch.index[id])
          throw Error(`Öğrenci #${id} doğrulanamadı; eski paket korunuyor`);
        nextStudents.push(student);
        // Prototype-safe keys: numeric student IDs only.
        nextCurriculum[id]=curriculum;
      }
      return {
        snapshot: {version:1,database_id:patch.database_id,generated_at:patch.generated_at,
          students:nextStudents,curriculum:nextCurriculum},
        stats: {changed:Object.keys(patch.changed).length,removed:deletion.size,
          total:nextStudents.length,bytes:raw.length}
      };
    } finally {
      try { await api(`/api/sync/delta9/${encodeURIComponent(session.token)}/close`,'POST'); }
      catch (_) { /* Session TTL expiry is still safe. */ }
    }
  }
  window.OfflineDeltaV9 = Object.freeze({download,canonical,rowHash,baselineIndex});
})(window);
