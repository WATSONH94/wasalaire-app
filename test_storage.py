"""
Tests du stockage documentaire (A-06) — SANS base de données ni réseau.
Vérifie LocalStorage (round-trip), le choix de backend, et le garde-fou anti
path-traversal. S3Storage n'est pas sollicité (aucune clé configurée).
"""
from __future__ import annotations
import os, sys, tempfile
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

import storage

res = []
def check(label, cond, detail=""):
    res.append(bool(cond)); print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
def raises(fn, *exc):
    try: fn(); return False
    except exc or (Exception,): return True


def main():
    with tempfile.TemporaryDirectory() as d:
        st = storage.LocalStorage(base_dir=d)

        # 1) round-trip put/get
        uri = st.put("documents/c1/doc1.txt", "bonjour".encode("utf-8"), "text/plain")
        check("LocalStorage.put renvoie une URI file://", uri.startswith("file://"), uri)
        check("LocalStorage.get relit le contenu écrit", st.get("documents/c1/doc1.txt") == b"bonjour")
        check("le fichier existe réellement sur disque",
              os.path.exists(os.path.join(d, "documents", "c1", "doc1.txt")))

        # 2) écrase proprement (idempotence d'écriture)
        st.put("documents/c1/doc1.txt", b"v2", "text/plain")
        check("réécriture OK (dernière valeur)", st.get("documents/c1/doc1.txt") == b"v2")

        # 3) anti path-traversal : une clé qui sort du répertoire est refusée
        check("path traversal refusé (../)", raises(lambda: st.put("../evade.txt", b"x"), ValueError))

    # 4) backend par défaut = Local tant que S3 n'est pas configuré
    for k in ("S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
        os.environ.pop(k, None)
    check("default_storage = LocalStorage sans S3", storage.default_storage().backend == "local")
    check("s3_configured() = False sans clés", storage.s3_configured() is False)

    # 5) bascule S3 détectée si les 3 clés sont posées (sans appel réseau)
    os.environ.update({"S3_BUCKET": "b", "S3_ACCESS_KEY": "a", "S3_SECRET_KEY": "s"})
    try:
        check("default_storage = S3Storage si configuré", storage.default_storage().backend == "s3")
        check("s3_configured() = True avec les 3 clés", storage.s3_configured() is True)
    finally:
        for k in ("S3_BUCKET", "S3_ACCESS_KEY", "S3_SECRET_KEY"):
            os.environ.pop(k, None)

    ok = sum(res); print(f"\nStockage (A-06) : {ok}/{len(res)} PASS")
    if ok != len(res): raise SystemExit(1)


if __name__ == "__main__":
    main()
