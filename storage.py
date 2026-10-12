"""
Stockage documentaire — abstraction à repli sûr (correctif A-06).

Même philosophie que `payout_gateway` / `notifications` : aucune dépendance réseau
tant que rien n'est configuré, et jamais d'échec silencieux de perte de donnée.

- **LocalStorage** (défaut) : écrit dans un répertoire PERSISTANT (`WASALAIRE_STORAGE_DIR`,
  défaut `storage/`), destiné à être monté sur un volume Docker/Coolify. Corrige A-06
  (les artefacts ne sont plus sur le FS éphémère du conteneur dès lors que le volume
  est monté).
- **S3Storage** : S3 / MinIO si configuré (`S3_BUCKET` + `S3_ACCESS_KEY` + `S3_SECRET_KEY`,
  `S3_ENDPOINT` optionnel pour MinIO, `S3_REGION` optionnel). `boto3` est importé
  PARESSEUSEMENT : il n'est requis que si le stockage S3 est effectivement activé.

API : `put(key, data: bytes, content_type) -> uri` ; `get(key) -> bytes`.
`default_storage()` choisit S3 si configuré, sinon Local.
"""
from __future__ import annotations
import os
from pathlib import Path


class Storage:
    backend = "base"
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        raise NotImplementedError
    def get(self, key: str) -> bytes:
        raise NotImplementedError


class LocalStorage(Storage):
    """Défaut sûr : écrit sous un répertoire (à monter sur un volume en production)."""
    backend = "local"
    def __init__(self, base_dir: str | None = None):
        self.base = Path(base_dir or os.environ.get("WASALAIRE_STORAGE_DIR", "storage"))

    def _path(self, key: str) -> Path:
        # Empêche toute évasion de répertoire (path traversal) par une clé malveillante.
        p = (self.base / key).resolve()
        base = self.base.resolve()
        if base not in p.parents and p != base:
            raise ValueError("Clé de stockage hors du répertoire autorisé.")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"file://{p.as_posix()}"

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class S3Storage(Storage):
    """S3 / MinIO. `boto3` importé paresseusement (dépendance optionnelle)."""
    backend = "s3"
    def __init__(self, bucket: str | None = None, endpoint: str | None = None,
                 access_key: str | None = None, secret_key: str | None = None,
                 region: str | None = None):
        self.bucket = bucket or os.environ.get("S3_BUCKET")
        self.endpoint = endpoint or os.environ.get("S3_ENDPOINT") or None
        self.access_key = access_key or os.environ.get("S3_ACCESS_KEY")
        self.secret_key = secret_key or os.environ.get("S3_SECRET_KEY")
        self.region = region or os.environ.get("S3_REGION") or None
        self._client = None

    def _c(self):
        if self._client is None:
            try:
                import boto3  # import paresseux : requis uniquement si S3 activé
            except ImportError as e:
                raise RuntimeError(
                    "Stockage S3 configuré mais boto3 absent : `pip install boto3`.") from e
            self._client = boto3.client(
                "s3", endpoint_url=self.endpoint, region_name=self.region,
                aws_access_key_id=self.access_key, aws_secret_access_key=self.secret_key)
        return self._client

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._c().put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        return self._c().get_object(Bucket=self.bucket, Key=key)["Body"].read()


def s3_configured() -> bool:
    return bool(os.environ.get("S3_BUCKET") and os.environ.get("S3_ACCESS_KEY")
                and os.environ.get("S3_SECRET_KEY"))


def default_storage() -> Storage:
    """S3/MinIO si configuré, sinon stockage local (sur volume en production)."""
    return S3Storage() if s3_configured() else LocalStorage()


def store_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Raccourci : écrit `data` sous `key` via le backend par défaut, renvoie l'URI."""
    return default_storage().put(key, data, content_type)
