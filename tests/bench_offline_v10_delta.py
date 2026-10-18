"""Synthetic-only delta bandwidth benchmark. Never opens user SQLite databases."""
import copy
import json
import time
from web_api.delta_pages_v9 import build_patch, DeltaStart, record_hash

def sample(n):
    return {
        "version": 1, "database_id": "synthetic-only-db",
        "generated_at": "synthetic",
        "students": [{"id": i, "ad": f"Öğrenci {i}", "soyad": "TEST",
                      "ana_grup": "Sinif"} for i in range(1, n + 1)],
        "curriculum": {str(i): {
            "lessons": [{"id": j, "ad": "Fizik"} for j in range(1, 4)],
            "books": {str(j): [{"id": j * 10 + k, "ad": "TestKitap", "aktif": 1}
                               for k in range(1, 3)] for j in range(1, 4)},
            "topics": {str(j): [{"id": j * 100 + k, "topic": "Kuvvet ve Hareket",
                                 "done": k % 2 == 0} for k in range(1, 8)]
                       for j in range(1, 4)},
            "active_homeworks": [{"id": i * 10 + k, "status": "devam"}
                                 for k in range(1, 4)],
            "status_fingerprints": {}
        } for i in range(1, n + 1)}
    }

def main():
    for n in (2000, 5000):
        before = sample(n)
        t0 = time.perf_counter()
        previous = {str(st["id"]): record_hash(st, before["curriculum"][str(st["id"])])
                    for st in before["students"]}
        hash_sec = time.perf_counter() - t0
        updated = copy.deepcopy(before)
        for i in range(n // 50):
            updated["curriculum"][str(i + 1)]["topics"]["1"][0]["done"] = True
        t0 = time.perf_counter()
        delta = build_patch(updated, DeltaStart(database_id="synthetic-only-db",
                                               manifest=previous))
        build_sec = time.perf_counter() - t0
        full_bytes = len(json.dumps(updated, ensure_ascii=True, separators=(",", ":")).encode())
        patch_bytes = len(json.dumps(delta, ensure_ascii=True, separators=(",", ":")).encode())
        print(json.dumps({"students": n, "changed": len(delta["changed"]),
                          "full_bytes": full_bytes, "delta_bytes": patch_bytes,
                          "reduction_pct": round(100 * (1 - patch_bytes / full_bytes), 1),
                          "client_hash_seconds": round(hash_sec, 2),
                          "server_build_seconds": round(build_sec, 2)}, ensure_ascii=False))
if __name__ == "__main__": main()
