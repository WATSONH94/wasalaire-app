-- 011 — Création de société IN-APP (onboarding), sans affaiblir la RLS.
-- La RLS WITH CHECK impose company.id ∈ current_scope() à l'INSERT : une société NEUVE
-- ne peut donc pas s'auto-insérer (son périmètre n'existe pas encore). On passe par une
-- fonction SECURITY DEFINER qui (1) VÉRIFIE l'autorisation du demandeur, (2) insère la
-- société + son nœud 'societe' sous un nœud dont l'appelant est administrateur.
-- L'autorisation n'est PAS déléguée à la RLS : elle est contrôlée explicitement ici.

CREATE OR REPLACE FUNCTION create_company_under_node(
    p_user        uuid,
    p_parent_node uuid,
    p_raison      text,
    p_ifu         text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_tenant      uuid;
    v_is_platform boolean := false;
    v_is_admin    boolean := false;
    v_company     uuid;
BEGIN
    IF p_raison IS NULL OR length(btrim(p_raison)) = 0 THEN
        RAISE EXCEPTION 'Raison sociale obligatoire';
    END IF;

    SELECT tenant_id INTO v_tenant FROM org_node WHERE id = p_parent_node;
    IF v_tenant IS NULL THEN
        RAISE EXCEPTION 'Nœud parent introuvable';
    END IF;

    -- Autorisation 1 : rôle plateforme transverse (super-admin / admin plateforme).
    SELECT platform_role IN ('super_admin', 'admin_plateforme')
      INTO v_is_platform
      FROM app_user WHERE id = p_user;

    -- Autorisation 2 : administrateur applicatif sur le nœud parent ou un de ses ancêtres.
    SELECT EXISTS (
        SELECT 1
        FROM access_grant g
        JOIN org_closure c ON c.ancestor_id = g.org_node_id
        JOIN role r        ON r.id = g.role_id
        WHERE g.user_id = p_user
          AND c.descendant_id = p_parent_node
          AND r.code = 'admin'
          AND (g.date_fin IS NULL OR g.date_fin >= current_date)
    ) INTO v_is_admin;

    IF NOT (coalesce(v_is_platform, false) OR coalesce(v_is_admin, false)) THEN
        RAISE EXCEPTION 'Non autorisé à créer une société sous ce nœud';
    END IF;

    -- Idempotence douce : réutilise une société de même raison dans le même workspace.
    SELECT id INTO v_company
      FROM company
     WHERE workspace_id = v_tenant AND raison_sociale = btrim(p_raison);

    IF v_company IS NULL THEN
        INSERT INTO company(workspace_id, raison_sociale, ifu)
        VALUES (v_tenant, btrim(p_raison), nullif(btrim(coalesce(p_ifu, '')), ''))
        RETURNING id INTO v_company;
    END IF;

    -- Nœud 'societe' rattaché (le trigger de closure met à jour org_closure → périmètre).
    IF NOT EXISTS (SELECT 1 FROM org_node WHERE company_id = v_company) THEN
        INSERT INTO org_node(tenant_id, type, parent_id, nom, company_id)
        VALUES (v_tenant, 'societe', p_parent_node, btrim(p_raison), v_company);
    END IF;

    RETURN v_company;
END;
$$;

REVOKE ALL ON FUNCTION create_company_under_node(uuid, uuid, text, text) FROM PUBLIC;

-- Nœuds d'organisation sur lesquels un utilisateur est administrateur (points de création).
-- SECURITY DEFINER : lecture contrôlée par le filtre sur g.user_id = p_user uniquement.
CREATE OR REPLACE FUNCTION admin_nodes(p_user uuid)
RETURNS TABLE (node_id uuid, node_type text, nom text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
    SELECT DISTINCT n.id, n.type, n.nom
    FROM access_grant g
    JOIN role r      ON r.id = g.role_id AND r.code = 'admin'
    JOIN org_node n  ON n.id = g.org_node_id
    WHERE g.user_id = p_user
      AND (g.date_fin IS NULL OR g.date_fin >= current_date);
$$;

REVOKE ALL ON FUNCTION admin_nodes(uuid) FROM PUBLIC;
