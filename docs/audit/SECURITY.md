# Rapport de sécurité — audit du 2026-09-16

Revue ciblée, sceptique, du backend `api/` : autorisation multi-tenant, gating admin,
gestion des secrets (clés API, webhooks), couverture du rate limiting, validation des
entrées (SSRF, uploads), et recherche de secrets codés en dur.

## Méthode

Lecture directe du code, pas de checklist générique. Fichiers examinés en profondeur :
`documents.py`, `billing.py`, `webhooks.py`, `agent_api_keys.py`, `external_sources.py`,
`batch_jobs.py`, `feedback.py`, `human_approval.py`, `questions.py`, `compliance.py`,
`integrations_universal.py`, plus les modules `api/security/*.py` pertinents.

## Constat général

Codebase inhabituellement disciplinée : la quasi-totalité des routers suit le même motif
"charger → vérifier l'appartenance à l'organisation → agir", avec un 404 uniforme (pas de
403 qui révèle l'existence d'une ressource d'une autre organisation — anti-énumération
correcte). L'infrastructure sécurité (défense SSRF, hachage des secrets, vérification HMAC
des webhooks) est nettement au-dessus de la moyenne.

## 1. Autorisation / isolation multi-tenant

**Faille trouvée et corrigée** — `api/routers/human_approval.py`,
`approve_approval`/`reject_approval` :

Les deux routes appelaient `approve_human_request`/`reject_human_request` — qui
**modifient** la ligne `HumanApproval` en base — **avant** de vérifier que cette ligne
appartient bien à l'organisation `org_id` du chemin. Le contrôle `organization_id != org_id`
n'intervenait qu'après coup, sur le résultat déjà modifié.

Non exploitable aujourd'hui dans l'état constaté : `db.flush()` ne pousse le SQL qu'à
l'intérieur de la transaction encore ouverte de cette requête ; le routeur lève l'exception
avant tout `db.commit()`, et la fermeture de la session annule implicitement cette
transaction. Mais c'était un piège latent : n'importe quel admin de **n'importe quelle**
organisation pouvait passer l'identifiant d'une demande d'approbation d'une autre
organisation et la faire silencieusement approuver/rejeter en session — seul le timing du
rollback empêchait une vraie conséquence, pas un contrôle d'autorisation. Un futur
changement ajoutant un effet de bord entre la mutation et le contrôle (déclenchement
synchrone de l'action approuvée, notification, `commit` intermédiaire) aurait pu
matérialiser la faille.

**Corrigé** : inversion de l'ordre — chargement et vérification de l'appartenance à
l'organisation d'abord (nouvelle fonction `_get_approval_scoped_to_org`), mutation ensuite
— aligné sur le motif de tous les autres routers de ressource unique. Vérifié : 36/36 tests
(`test_human_approval.py`, `test_workflow_block_human.py`) toujours verts après correction.

**Rien d'autre trouvé** : aucun IDOR où un appelant pourrait substituer l'identifiant d'une
ressource d'une autre organisation et récupérer des données — vérifié explicitement sur
`documents.py`, `billing.py` (`billing_invoices.get_invoice` vérifie explicitement
`invoice.organization_id != organization_id`), `webhooks.py`, `agent_api_keys.py`,
`external_sources.py`, `batch_jobs.py`, `feedback.py`, `questions.py`, `compliance.py`,
`integrations_universal.py`.

## 2. Gating admin / superadmin

`api/dependencies.py` : `require_admin` (rôle `admin`/`superadmin`, 404 pour un non-admin)
et `require_superadmin` (rôle exactement `superadmin`, 403) sont tous deux appliqués
côté serveur, au-dessus de `get_current_user`, revérifiés à chaque requête — aucune
confiance côté client, aucun indicateur d'en-tête/cookie. `admin_dashboard.py` applique
`require_admin` uniformément sur les statistiques/supervision/journaux, et monte
correctement à `require_superadmin` pour l'action destructrice `DELETE /logs/purge`.

**Aucun problème trouvé.**

## 3. Gestion des clés API / secrets de webhook

- **Clés API** (`api/services/organization_api_keys.py`, `api/security/agent_api_keys.py`) :
  stockées uniquement en `sha256(clé)`, jamais en clair — la valeur en clair n'est
  retournée qu'une seule fois, à la création. Vérification par recherche en base sur le
  hash (égalité d'index, pas d'oracle de timing exploitable). Correct.
- **Secrets de signature webhook** (`api/services/webhooks.py`) : générés via
  `secrets.token_urlsafe(32)`, chiffrés au repos (Fernet,
  `api/security/secret_encryption.py`) plutôt que stockés en clair — nécessaire puisqu'un
  secret de webhook doit rester récupérable pour signer les envois sortants (contrairement
  à un mot de passe, qui peut être à sens unique).
- **Vérification de signature entrante**
  (`api/security/chat_integrations_signature.py:42`) : utilise
  `hmac.compare_digest(calculé, signature)` — comparaison à temps constant, correct.

**Aucun problème trouvé.**

## 4. Couverture du rate limiting

`enforce_rate_limit` (fenêtre glissante Redis, fail-open avec timeout borné à 3s) est
appelé depuis `auth.py`, `webauthn.py`, `two_factor.py`, `invitations.py`, `account.py`,
`password.py`, `verify.py` — couvrant connexion, inscription, réinitialisation de mot de
passe, vérification 2FA, WebAuthn, vérification d'email et acceptation d'invitation. L'API
publique `/v1/*` est limitée séparément par clé API (`require_organization_api_key` →
`check_rate_limit`).

**Aucun endpoint sensible à l'authentification sans limite plausible trouvé.**

**Non exhaustivement vérifié** : que chaque appel utilise des valeurs `max_attempts`/
`window_seconds` réellement bien calibrées (seule la présence de l'appel a été confirmée,
pas le réglage fin de chaque site d'appel).

## 5. Validation des entrées / SSRF

`api/services/url_fetching.py` est particulièrement solide : résolution DNS maison via un
backend réseau `httpcore` personnalisé (`_SSRFSafeBackend.connect_tcp`), validation de
l'IP résolue par liste blanche (`ipaddress.ip_address(...).is_global and not is_multicast`)
**à chaque connexion**, y compris pour chaque redirection — ce qui déjoue le contournement
classique "URL sûre qui redirige en 302 vers 127.0.0.1", que la validation-puis-fetch
naïve laisse passer. Rejette aussi correctement `100.64.0.0/10` (plage CGNAT que `.is_private`
seul ne détecte pas), les schémas non-http(s), les identifiants intégrés à l'URL, et plafonne
la taille de réponse par comptage réel des octets reçus (pas confiance en `Content-Length`).
Réutilisé à la fois pour l'import de documents par URL et pour le bloc workflow `http_call`
— une seule implémentation, pas de version dupliquée plus faible.

Les uploads de fichiers (`api/routers/documents.py`) passent par `upload_document`/
`validate_upload_batch` avec une lecture plafonnée en taille.

**Non vérifié en profondeur** (voir portée restante ci-dessous) : validation magic-byte/
content-type dans chaque parser spécifique à un format ; vulnérabilités au niveau des
parsers eux-mêmes (XXE dans les formats basés XML/DOCX, gestion des zip bombs).

## 6. Secrets codés en dur

Recherche exhaustive de secrets/clés/tokens/mots de passe assignés littéralement dans
`*.py` (hors références `settings.*`/`getenv`) — **aucun secret codé en dur trouvé**. Tout
le matériel secret transite par `settings.*` (config par variable d'environnement) ou est
généré à l'exécution (`secrets.token_urlsafe`).

## Portée non couverte par cet audit (honnête)

- Les ~45 autres fichiers de routers non listés explicitement ci-dessus (`rbac.py`,
  `resource_permissions.py`, `tool_permissions.py`, `conversation_shares.py`,
  `custom_domains.py`, `enterprise_sso.py`...) — uniquement vérifiés par motif de recherche
  (`db.get(...)`), pas lus intégralement.
- Réglage fin de chaque appel `enforce_rate_limit` (valeurs `max_attempts`/`window_seconds`).
- Validation magic-byte/content-type dans les parsers de documents spécifiques à un format
  (`api/security/documents.py`) — pas tracée en profondeur pour des vulnérabilités au
  niveau parseur (XXE, zip bombs).
- `api/security/plugin_sandbox.py` et le modèle de sandboxing d'exécution de
  plugins/workflows — zone à risque plausiblement élevé non couverte cette fois.
- Détails d'implémentation JWT (`api/security/jwt.py`) — confusion d'algorithme, rotation
  de clé, vérification audience/issuer.
- Gestion CSRF (`api/security/csrf.py`) et attributs de cookie de session
  (`Secure`/`HttpOnly`/`SameSite`).
- SQL brut construit par formatage de chaîne en dehors de l'ORM (seuls les motifs de
  requête ORM ont été vérifiés).
- Vulnérabilités de dépendances (aucun `pip audit`/`safety` exécuté dans cet audit — un
  scan de sécurité réel existe déjà dans le produit lui-même, voir Partie 10.5).

## Bilan

1 faille réelle trouvée (sévérité faible, défense en profondeur), corrigée et vérifiée.
Aucune faille critique, haute ou moyenne trouvée dans le périmètre couvert.

## Re-vérification (2026-09-16, après correction)

- Lecture directe de [`api/routers/human_approval.py`](../../api/routers/human_approval.py) :
  confirmé que `_get_approval_scoped_to_org` (chargement + vérification d'appartenance à
  l'organisation) est bien appelée **avant** `approve_human_request`/`reject_human_request`
  (les fonctions qui mutent la ligne) dans les deux routes concernées.
- Suite de tests relancée en direct : **36/36 tests verts**
  (`tests/test_human_approval.py`, `tests/test_workflow_block_human.py`).
- Aucune régression trouvée.
