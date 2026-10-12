-- =====================================================================
-- 008 — Stockage documentaire persistant (correctif A-06)
--
-- Les artefacts documentaires (bulletins PDF, documents RH) étaient produits sur
-- le disque LOCAL du conteneur et donc PERDUS à chaque redeploy. On introduit une
-- référence de stockage objet/volume (`storage_uri`) persistée avec chaque document,
-- renseignée par la couche `storage.py` (LocalStorage sur volume, ou S3/MinIO).
--
-- `payslip.pdf_url` existe déjà (001) et sert le même rôle pour les bulletins.
-- Migration incrémentale et immuable.
-- =====================================================================

ALTER TABLE document ADD COLUMN IF NOT EXISTS storage_uri text;
