# 01 — Inventaire des fonctionnalités et vérification du chiffre « 515 »

Audit du 2026-10-10, HEAD `59d5ec9`. Source : `docs/CAHIER_DES_CHARGES.md`.

## 1. Le cahier des charges : taille et structure (mesurées)
- Taille : **649 176 octets** (≈ 634 Kio ; annoncé « ≈ 649 Ko » : cohérent), **3 898 lignes** (Get-Content), 623 482 caractères.
- Titres : 29 de niveau 2, 46 de niveau 3, 136 de niveau 4.
- Parties présentes (titres `## PARTIE N`) : 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 24, 25. Les parties 16 et 17 n'ont **pas** d'en-tête : le document explique que « Partie 16 (bis) » (modèles de vente) et « 16 (ter) » (marketplace de plugins) sont rédigées à l'intérieur de la Partie 15 et qu'aucun numéro 17 n'a jamais existé.
- **Partie 15 (Human-in-the-loop) : INCOMPLÈTE dans la source** (« le message original s'arrête à 15.1.1 Ticke… »). Aucun texte n'est reconstitué dans cet audit.
- Addendum : présent, **`## ADDENDUM — 2026-09-19 — Session de correction (chat/citations, navigation, i18n)`** (ligne 3836) ; section « Reste à faire » (ligne 3874). Une section `[ARCHIVE -- PERIME]` (ligne 3654) contient une ancienne feuille de route qui n'est pas comptée.
- Le document est une **reconstitution** (il le dit) : « le texte brut d'origine n'existe plus nulle part ».

## 2. Reproductibilité des chiffres annoncés
| Chiffre annoncé | Où | Résultat du recomptage | Verdict |
|---|---|---|---|
| 515 fonctionnalités, 15 parties | en-tête, ligne 5 (une seule occurrence de « 515 » dans tout le fichier) | aucune méthode de comptage dans le document ; décomptes reproductibles ci-dessous : 150 / 275 / 323 | **NON CONFIRMÉ — non reproductible** |
| 110 lignes explicites (90 ✅ / 17 🟡 / 3 ⬜) | section « Total recompté (2026-10-07) » | **150 lignes** de tableau dont l'identifiant est de la forme `N.N.N` ; statuts **130 ✅ / 18 🟡 / 2 ⬜** ; aucun identifiant dupliqué | **NON CONFIRMÉ** (écart : +40 lignes ; la différence 110→150 n'est pas expliquée par le document — probablement des lignes « bonus » ajoutées depuis, non vérifié) |
| 90 réalisées / 17 partielles / 3 non commencées | idem | 130 / 18 / 2 (statut déclaré par le document, non revérifié) | NON CONFIRMÉ |

### Méthodes de comptage (toutes calculées par `cahier.py` / `cahier2.py`)
| Définition de « fonctionnalité » | Nombre | Remarque |
|---|---:|---|
| Lignes de tableau dont la 1ʳᵉ cellule est un identifiant `N.N.N` | **150** | uniquement les parties 1 (44), 2 (35), 3 (33), 4 (18), 10 (20) ; les parties 5 à 9 et 11 à 25 n'ont pas de tableau d'inventaire de ce type |
| Identifiants `N.N.N` distincts figurant dans un tableau **ou** un titre (avant la section archive) | **275** | parties 1:44, 2:35, 3:37, 4:18, 5:47, 6:22, 7:32, 8:20, 10:20 ; les parties 9, 11 à 14, 18 à 25 n'ont aucun identifiant de ce format |
| Tous les jetons `N.N.N` du fichier (même dans la narration) | 323 | surestimé : inclut des numéros de versions, de dates, de renvois |
| Sous-actions narratives non numérotées | **NON MESURÉ** | le document lui-même dit que ~500 sous-actions n'ont pas de marqueur individuel |

**Conclusion** : le chiffre de 515 n'est **ni confirmé ni infirmé comme valeur historique** (le texte d'origine est perdu) ; il n'est **pas reproductible** à partir du document actuel. Le seul total défendable est le nombre de lignes d'inventaire identifiables : **150 lignes (275 identifiants si l'on inclut les titres)**, sans prétendre couvrir les parties 9, 11-14 et 18-25 qui sont décrites en prose.

## 3. Statistiques de la matrice `02_MATRICE_EXIGENCES.csv`
- Total d'exigences atomiques **identifiables** : **150** (1 ligne de tableau = 1 exigence ; aucune décomposition ni regroupement appliqués).
- Statut **déclaré par le document** (non revérifié dans le code) : FAIT 130 ; PARTIEL 18 ; NON COMMENCÉ 2. Dénominateur des pourcentages : 150 (donc FAIT = 86.7 %, PARTIEL = 12.0 %, NON COMMENCÉ = 1.3 %).
- **Statut d'implémentation vérifié par cet audit : NON DÉTERMINÉ pour les 150 lignes** (le code n'a pas été relu exigence par exigence ; la colonne `statut_implementation_audit` le dit explicitement). Ce n'est pas une vérification : c'est un inventaire honnête.
- Exigences dont l'identifiant est cité près des mots « Partie/item/étape » dans un fichier de test : **79** ; dans le code `api/` : **93** (heuristique, sous-estime les liens réels). Les 71 autres ne sont pas pour autant « non testées » : elles ne sont simplement pas reliées par cette heuristique.
- Exigences **validées par un test réussi** : **NON ÉTABLI** exigence par exigence (la suite complète réussit en CI, mais le lien exigence→test n'est pas prouvé). Le statut de validation du CSV est donc « TEST PRÉSENT MAIS NON EXÉCUTÉ (liaison heuristique) » ou « NON VALIDÉ ».
- Tests en échec : **0** sur la dernière CI de HEAD (GitHub success, CircleCI success) ; exigences bloquées par un fournisseur externe : NON MESURÉ ; doublons : 0 ; références obsolètes : au moins 1 (note « GitHub Actions désactivé »).

## 4. Parties du cahier des charges (en-têtes tels qu'écrits)
- PARTIE 1 — Structure & Multi-tenant
- PARTIE 2 — Knowledge Base universelle — 🟡 DÉMARRÉ (27✅/8🟡/0⬜ sur 35, via les Étapes 2.1.1/2.1.2/2.1.3/2.1.4/2.1.5/2.1.6/2.1.7/2.1.8/2.1.9/2.1.10/2.1.11/2.1.12/2.1.13/2
- PARTIE 3 — Pipeline RAG avancé — 🟡 PARTIEL (~15/41, dont 3.1.1-3.1.10 réels dans `api/`, 2026-09-04)
- PARTIE 4 — Multi-LLM & Embeddings — ✅ (18/18)
- PARTIE 5 — Agent IA — 🟡 PARTIEL (Partie 5.1 complète -- 14/14 -- + Partie 5.2 complète -- 9/9 -- + Partie 5.3 démarrée -- 9/10 (5.3.8 non demandé) -- + Partie 5.4 -- 1
- PARTIE 6 — Citations & Anti-hallucination — 🟡 PARTIEL
- PARTIE 7 — Evaluation Lab — ✅ COMPLET (7.1 + 7.2 + 7.3, aucune portée restante identifiée)
- PARTIE 8 — Interface Utilisateur — 🟡 EN COURS (32/32 backend+composants ; assemblage final en 8.3)
- PARTIE 9 — API publique & Intégrations — ✅ COMPLET (37/37)
- PARTIE 10 — Sécurité & Governance — 🟡 PARTIEL (~10/49)
- PARTIE 11 — Admin Dashboard & Analytics — 🟡 PARTIEL (~11/34)
- PARTIE 12 — Facturation & Monétisation — 🟡 PARTIEL (~18/23)
- PARTIE 13 — Developer Experience — 🟡 PARTIEL (~10/52)
- PARTIE 14 — Documentation & Livrables — 🟡 PARTIEL (~5/33)
- PARTIE 15 — Human-in-the-loop — ⚠️ INCOMPLET DANS CE DOCUMENT
- PARTIE 18 — Modèles de vente (SaaS / Self-hosted / Partenaire / White-label) — ✅ COMPLET (scope honnête)
- PARTIE 19 — White-label complet — ✅ COMPLET (scope honnête)
- PARTIE 20 — Analytics avancés — ✅ COMPLET (scope honnête)
- PARTIE 21 — A/B testing avancé — ✅ COMPLET (scope honnête)
- PARTIE 22 — Multi-modal (images, audio, vidéo) — ✅ COMPLET (scope honnête, 2 décisions déclinées documentées)
- PARTIE 23 — Agents autonomes — ✅ COMPLET (scope honnête)
- PARTIE 24 — Fine-tuning — ✅ COMPLET (scope honnête, 1 fournisseur réellement non supportable documenté)
- PARTIE 25 — Documentation finale — ✅ COMPLET (scope honnête)

*Les emojis et les ratios (ex. « 14/14 ») des en-têtes sont des auto-déclarations du document ; ils ne sont pas des résultats de cet audit.*

## 5. Lignes d'inventaire par partie (parties 1, 2, 3, 4, 10) — statut **déclaré**

### Partie 1 — 44 lignes (FAIT 38, PARTIEL 6, NON COMMENCÉ 0)
| ID source | Texte (résumé, tronqué) | Déclaré | Test cité | Ligne |
|---|---|---|---|---:|
| 1.1.1 | Inscription email+mdp / Route POST /auth/register, hash passlib[bcrypt], table users / ✅ /  | FAIT | — | 87 |
| 1.1.2 | Connexion/Déconnexion / POST /auth/login → JWT access token ; logout = suppression cookie/refre | FAIT | — | 88 |
| 1.1.3 | Reset mot de passe / Token à usage unique en DB (expire 1h), envoi via Resend/SES / ✅ /  | FAIT | — | 89 |
| 1.1.4 | Vérification email (OTP) / Code 6 chiffres généré, stocké hashé, TTL 10 min / ✅ /  | FAIT | — | 90 |
| 1.1.5 | OAuth Google / Authlib (flow Authorization Code), mapping vers users.oauth_accounts / ✅ /  | FAIT | — | 91 |
| 1.1.6 | OAuth GitHub / Même mécanisme Authlib, provider GitHub / ✅ /  | FAIT | — | 92 |
| 1.1.7 | 2FA (TOTP) / pyotp, QR code d'enrôlement, vérif à chaque login si activé / ✅ (+ WebAuthn/FIDO2  | FAIT | — | 93 |
| 1.1.8 | Sessions JWT + refresh / Access token 15 min + refresh token rotatif en DB / ✅ (+ rotation auto | FAIT | — | 94 |
| 1.1.9 | Sessions actives (liste/révocation) / Table sessions avec device/IP/last_seen, endpoint DELETE  | FAIT | oui | 95 |
| 1.1.10 | Suppression de compte / Soft-delete + purge différée (job Celery à J+30) / ✅ /  | FAIT | — | 96 |
| 1.1.11 | Export RGPD (JSON) / Endpoint qui agrège toutes les tables liées à user_id / ✅ (+ export CSV aj | FAIT | — | 97 |
| 1.1.12 | Consentement RGPD / Champ consent_given_at + version des CGU acceptée / ✅ /  | FAIT | — | 98 |
| 1.1.13 | Profil (avatar, nom, entreprise) / Table users + upload avatar vers S3/R2 / ✅ /  | FAIT | — | 99 |
| 1.1.14 | Préférences (langue, fuseau) / Colonnes locale, timezone sur users / ✅ /  | FAIT | — | 100 |
| 1.1.15 | *(ajouté, hors liste initiale)* Révocation des tokens d'accès / Blacklist des access tokens (jt | FAIT | — | 101 |
| 1.1.16 | *(ajouté, hors liste initiale)* Protection CSRF / Double-submit cookie sur /auth/refresh et /au | FAIT | — | 102 |
| 1.2.1 | Super Admin / Rôle global hors-org, flag is_superadmin sur users / ✅ (implémenté via l'enum `ro | FAIT | — | 113 |
| 1.2.2 | Organization Owner / Rôle le plus élevé dans organization_members.role / ✅ (tables `organizatio | FAIT | — | 114 |
| 1.2.3 | Admin / Idem, niveau juste sous Owner / ✅ (`OrganizationRole.admin` + `require_org_admin()`. En | FAIT | — | 115 |
| 1.2.4 | Manager / Idem / ✅ (`require_org_manager()` -- Owner/Admin/Manager, strictement entre Member et | FAIT | — | 116 |
| 1.2.5 | Member / Idem (rôle par défaut à l'invitation) / ✅ (rôle par défaut confirmé -- `OrganizationMe | FAIT | — | 117 |
| 1.2.6 | Viewer / Idem, lecture seule / ✅ (effet de bord honnête de 1.2.5, pas construit délibérément po | FAIT | — | 118 |
| 1.2.7 | RBAC complet / casbin ou décorateur @require_role() sur chaque route / 🟡 (Casbin installé, migr | PARTIEL | — | 119 |
| 1.2.8 | Permissions granulaires par ressource / Table permissions (resource_type, action, role) / 🟡 (ta | PARTIEL | — | 120 |
| 1.3.1 | Organizations / Table organizations, FK sur toutes les tables métier / ✅ (`api/models/organizat | FAIT | — | 128 |
| 1.3.2 | Workspaces / Table workspaces (FK org), regroupe KB + agents / 🟡 (table `workspaces` créée à l' | PARTIEL | — | 129 |
| 1.3.3 | Teams / Table teams (FK org), M2M avec users / ✅ (`api/models/team.py` : `Team` -- FK `organiza | FAIT | oui | 130 |
| 1.3.4 | Invitations (email+lien) / Table invitations (token, email, rôle, expiry) / ✅ (`api/models/invi | FAIT | oui | 131 |
| 1.3.5 | Isolation des données / org_id obligatoire sur chaque requête + collection Chroma dédiée / 🟡 (i | PARTIEL | oui | 132 |
| 1.3.6 | Quotas par organisation / Table organization_limits, vérifiées en middleware / ✅ (`api/models/o | FAIT | oui | 133 |
| 1.3.7 | Limites par utilisateur / Colonne daily_request_limit sur organization_members / ✅ (6 colonnes  | FAIT | oui | 134 |
| 1.3.8 | Usage par organisation / Agrégation telemetry filtrée par org_id / ✅ (deux tables -- `api/model | FAIT | oui | 135 |
| 1.3.9 | Configuration par organisation / Table organization_settings (JSON) / ✅ (`api/models/organizati | FAIT | oui | 136 |
| 1.3.10 | Branding par organisation / Table organization_branding / ✅ (`api/models/organization_branding. | FAIT | oui | 137 |
| 1.4.1 | Custom domains / Table custom_domains, reverse-proxy dynamique (Caddy/Traefik) / ✅ (`api/models | FAIT | oui | 143 |
| 1.4.2 | Instructions DNS / Page générée avec les enregistrements CNAME/TXT attendus / ✅ (chaque `DnsRec | FAIT | — | 144 |
| 1.4.3 | SSL auto (Let's Encrypt) / Traefik + resolver ACME, ou Caddy / 🟡 (`api/models/acme_account.py`  | FAIT | oui | 145 |
| 1.4.4 | Vérification domaine / Challenge TXT DNS, job Celery de polling / ✅ (le challenge TXT DNS lui-m | FAIT | oui | 146 |
| 1.4.5 | Custom email domain / Resend/SES avec domaine vérifié (DKIM/SPF) par org / 🟡 (neuf nouvelles co | FAIT | oui | 147 |
| 1.4.6 | White-label complet / Flag hide_platform_branding + templates conditionnels / ✅ (une colonne `h | FAIT | oui | 148 |
| 1.4.7 | Logo/favicon/brand name / Champs dans organization_branding / ✅ (déjà livré par 1.3.10 -- `orga | FAIT | — | 149 |
| 1.4.8 | Couleurs/polices/thème / CSS custom properties depuis organization_branding.theme_json / 🟡 (cou | PARTIEL | — | 150 |
| 1.4.9 | Email sender custom / En-tête From: dynamique selon domaine vérifié / 🟡 (partiellement satisfai | PARTIEL | — | 151 |
| 1.4.10 | System prompt/persona IA / Colonne organization_settings.system_prompt / ✅ (déjà livré par 1.3. | FAIT | — | 152 |

### Partie 2 — 35 lignes (FAIT 29, PARTIEL 6, NON COMMENCÉ 0)
| ID source | Texte (résumé, tronqué) | Déclaré | Test cité | Ligne |
|---|---|---|---|---:|
| 2.1.1 | PDF / ✅ `pymupdf` (fitz) -- exactement la bibliothèque prévue ici, vérifiée pour de vrai (contr | FAIT | oui | 162 |
| 2.1.2 | DOCX / ✅ `python-docx` -- exactement la bibliothèque prévue ici. **Même structure que le code P | FAIT | oui | 163 |
| 2.1.3 | TXT / ✅ Lecture brute + détection réelle d'encodage (`charset-normalizer`, déjà présent transit | FAIT | oui | 164 |
| 2.1.4 | Markdown / ✅ **Existait déjà dans `src/ingestion.py`, mais pour le pipeline RAG mono-tenant de  | FAIT | oui | 165 |
| 2.1.5 | HTML / ✅ **Exactement les bibliothèques prévues ici** : `readability-lxml` (le vrai algorithme  | FAIT | oui | 166 |
| 2.1.6 | CSV / ✅ **Exactement la bibliothèque prévue ici** (`pandas`, déjà présente depuis 2.1.1). Détec | FAIT | oui | 167 |
| 2.1.7 | JSON / ✅ Parsing réel via le module stdlib `json` de Python (accéléré en C), sans nouvelle dépe | FAIT | oui | 168 |
| 2.1.8 | XML / ✅ **Exactement la bibliothèque prévue ici** (`lxml`, déjà présente depuis 2.1.5). **Quest | FAIT | oui | 169 |
| 2.1.9 | EPUB / ✅ **Exactement la bibliothèque prévue ici** (`ebooklib`), tranchant directement la visio | FAIT | oui | 170 |
| 2.1.10 | URLs / pages web / ✅ `httpx` + `readability-lxml` (exactement comme prévu, tous deux déjà prése | FAIT | oui | 171 |
| 2.1.11 | Sitemap / ✅ Parsing réel via `lxml` (déjà présent depuis 2.1.5/2.1.8, réutilisant directement l | FAIT | oui | 172 |
| 2.1.12 | GitHub repos / ✅ **API GitHub REST uniquement -- PAS de `git clone` (même superficiel), une vra | FAIT | oui | 173 |
| 2.1.13 | GitHub issues / ✅ **API GitHub REST "Issues List" (`/repos/{owner}/{repo}/issues`), PAS l'API S | FAIT | oui | 174 |
| 2.1.14 | Google Drive / 🟡 **API Google Drive v3 réelle + un vrai flux OAuth 2.0 refresh-token serveur-à- | FAIT | oui | 175 |
| 2.1.15 | Google Docs / ✅ **API Drive `files.export`, PAS l'API Docs séparée, et export DOCX par défaut,  | FAIT | oui | 176 |
| 2.1.16 | Notion / ✅ **API REST Notion réelle via un simple client httpx, PAS le SDK officiel `notion-cli | FAIT | oui | 177 |
| 2.1.17 | Confluence / 🟡 **API REST Confluence v1 réelle, contre une documentation publiée et stable, PAS | PARTIEL | oui | 178 |
| 2.1.18 | OneDrive / 🟡 **API Microsoft Graph v1.0 réelle + un vrai flux OAuth 2.0 refresh-token serveur-à | FAIT | oui | 179 |
| 2.1.19 | Fichiers ZIP / ✅ **stdlib `zipfile` uniquement -- le SEUL import de toute la série 2.1.10-2.1.1 | FAIT | oui | 180 |
| 2.2.1 | Upload multiple / ✅ **Nouvelle route dédiée `POST /organizations/{org_id}/documents/batch`, PAS | FAIT | oui | 186 |
| 2.2.2 | Drag & drop / 🟡 **100% frontend, zéro surface backend propre à cette étape -- honnêtement non d | PARTIEL | — | 187 |
| 2.2.3 | Barre de progression / 🟡 **Backend réel et complet, UI explicitement différée** (voir 2.2.2). ` | PARTIEL | oui | 188 |
| 2.2.4 | Preview / 🟡 **Backend réel et complet, UI (PDF.js, pagination, zoom) explicitement différée** ( | PARTIEL | oui | 189 |
| 2.2.5 | Extraction metadata / 🟡 **Extraction/normalisation backend réelle et complète, affichage UI exp | PARTIEL | oui | 190 |
| 2.2.6 | Tags/catégories / ✅ **Deux vraies tables** (migration `0034`) : `document_tags` (`organization_ | FAIT | — | 191 |
| 2.2.7 | Versioning / ✅ **Nouvelle table réelle** (migration `0035`), `document_versions` : un vrai inst | FAIT | oui | 192 |
| 2.2.8 | Suppression/remplacement / ✅ **Deux nouvelles colonnes réelles** (migration `0036`) : `deleted_ | FAIT | oui | 193 |
| 2.2.9 | Réindexation manuelle / ✅ **Deux nouvelles routes réelles** (`POST /documents/{id}/reindex`, Me | FAIT | oui | 194 |
| 2.2.10 | Historique modifications / ✅ **Nouvelle table réelle** `document_audit_logs` (migration `0038`, | FAIT | oui | 195 |
| 2.2.11 | Statut d'indexation / 🟡 **Backend réel et complet, UI (polling frontend) explicitement différée | PARTIEL | oui | 196 |
| 2.2.12 | Détection doublons / ✅ **Nouvelle colonne réelle** `content_hash` (migration `0040`) : vrai has | FAIT | oui | 197 |
| 2.2.13 | Détection docs modifiés / ✅ **Deux nouvelles colonnes réelles** `last_modified`/`last_checked`  | FAIT | oui | 198 |
| 2.2.14 | Sync automatique / ✅ **Nouvelle table réelle** `external_sources` (migration `0042`, RLS activé | FAIT | oui | 199 |
| 2.2.15 | Réindexation programmée / ✅ **Nouvelle colonne réelle** `Document.reindex_schedule` (override c | FAIT | oui | 200 |
| 2.2.16 | Batch processing / ✅ **Deux nouvelles tables réelles** `batch_jobs`/`batch_job_items` (migratio | FAIT | oui | 201 |

### Partie 3 — 33 lignes (FAIT 33, PARTIEL 0, NON COMMENCÉ 0)
| ID source | Texte (résumé, tronqué) | Déclaré | Test cité | Ligne |
|---|---|---|---|---:|
| 3.1.1 | Nettoyage du texte / ✅ Voir détails ci-dessous /  | FAIT | oui | 213 |
| 3.1.2 | Normalisation du texte / ✅ Voir détails ci-dessous /  | FAIT | oui | 214 |
| 3.1.3 | Extraction du texte (amélioration) / ✅ Voir détails ci-dessous /  | FAIT | oui | 215 |
| 3.1.4 | Extraction des tableaux / ✅ Voir détails ci-dessous /  | FAIT | oui | 216 |
| 3.1.5 | Extraction des images / ✅ Voir détails ci-dessous /  | FAIT | oui | 217 |
| 3.1.6 | OCR / ✅ Voir détails ci-dessous (vérification réelle via CI, binaires système absents de cette  | FAIT | oui | 218 |
| 3.1.7 | Détection de langue / ✅ Voir détails ci-dessous /  | FAIT | oui | 219 |
| 3.1.8 | Détection de structure documentaire / ✅ Voir détails ci-dessous /  | FAIT | oui | 220 |
| 3.1.9 | Extraction des titres et sections / ✅ Voir détails ci-dessous /  | FAIT | oui | 221 |
| 3.1.10 | Extraction avancée des métadonnées / ✅ Voir détails ci-dessous /  | FAIT | oui | 222 |
| 3.2.1 | Fixed-size (512 tokens, overlap 50) / ✅ Existe déjà (`chunk_text`, `api/security/documents.py`, | FAIT | — | 272 |
| 3.2.2 | Recursive / ✅ Voir détails ci-dessous /  | FAIT | oui | 273 |
| 3.2.3 | Semantic chunking / ✅ Voir détails ci-dessous /  | FAIT | oui | 274 |
| 3.2.4 | Markdown-aware / ✅ Voir détails ci-dessous /  | FAIT | oui | 275 |
| 3.2.5 | Code-aware (tree-sitter) / ✅ Voir détails ci-dessous (sans tree-sitter, voir raisons) /  | FAIT | oui | 276 |
| 3.2.6 | Sentence-based / ✅ Voir détails ci-dessous /  | FAIT | oui | 277 |
| 3.2.7 | Paragraph-based / ✅ Voir détails ci-dessous /  | FAIT | oui | 278 |
| 3.2.8 | Parent-child chunks / ✅ Voir détails ci-dessous /  | FAIT | oui | 279 |
| 3.3.1 | Chunk size configurable / ✅ Voir détails ci-dessous /  | FAIT | oui | 313 |
| 3.3.2 | Chunk overlap configurable / ✅ Voir détails ci-dessous /  | FAIT | — | 314 |
| 3.3.3 | Embedding model configurable / ✅ Voir détails ci-dessous /  | FAIT | oui | 315 |
| 3.3.4 | Retrieval strategy configurable / ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir | FAIT | oui | 316 |
| 3.3.5 | Reranker configurable / ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir détails)  | FAIT | — | 317 |
| 3.3.6 | Top-K configurable / ✅ Câblé pour de vrai dans un vrai endpoint de recherche (voir détails) /  | FAIT | — | 318 |
| 3.3.7 | Score threshold configurable / ✅ Voir détails ci-dessous /  | FAIT | oui | 319 |
| 3.4.1 | BM25 / ✅ Existe déjà (`src/retrieval.py`) ET réel dans `api/` (`bm25_search`, Partie 3.3.4) /  | FAIT | — | 355 |
| 3.4.2 | Query rewriting / ✅ Voir détails ci-dessous /  | FAIT | oui | 356 |
| 3.4.3 | HyDE / ✅ Voir détails ci-dessous /  | FAIT | oui | 357 |
| 3.4.4 | Multi-query retrieval / ✅ Voir détails ci-dessous /  | FAIT | oui | 358 |
| 3.4.5 | Metadata filtering / ✅ Voir détails ci-dessous /  | FAIT | — | 359 |
| 3.4.6 | Semantic filtering / ✅ Voir détails ci-dessous /  | FAIT | oui | 360 |
| 3.4.10 | Context compression / ✅ Voir détails ci-dessous /  | FAIT | oui | 364 |
| 3.4.11 | Duplicate removal / ✅ Voir détails ci-dessous /  | FAIT | oui | 365 |

### Partie 4 — 18 lignes (FAIT 18, PARTIEL 0, NON COMMENCÉ 0)
| ID source | Texte (résumé, tronqué) | Déclaré | Test cité | Ligne |
|---|---|---|---|---:|
| 4.1.1 | Anthropic Claude / ✅ Voir détails ci-dessous /  | FAIT | oui | 412 |
| 4.1.2 | OpenAI GPT / ✅ Voir détails ci-dessous /  | FAIT | — | 413 |
| 4.1.3 | Google Gemini / ✅ Voir détails ci-dessous /  | FAIT | — | 414 |
| 4.1.4 | Mistral / ✅ Voir détails ci-dessous /  | FAIT | — | 415 |
| 4.1.5 | Ollama (local) / ✅ Voir détails ci-dessous /  | FAIT | — | 416 |
| 4.1.6 | OpenAI-compatible APIs / ✅ Voir détails ci-dessous /  | FAIT | — | 417 |
| 4.1.7 | Abstraction LLM (LiteLLM) / ✅ Voir détails ci-dessous /  | FAIT | — | 418 |
| 4.2.1 | OpenAI Embeddings / ✅ Voir détails ci-dessous /  | FAIT | oui | 440 |
| 4.2.2 | Voyage AI Embeddings / ✅ Voir détails ci-dessous /  | FAIT | — | 441 |
| 4.2.3 | Cohere Embeddings / ✅ Voir détails ci-dessous /  | FAIT | — | 442 |
| 4.2.4 | Sentence Transformers / ✅ Voir détails ci-dessous /  | FAIT | — | 443 |
| 4.2.5 | Hugging Face Embeddings / ✅ Voir détails ci-dessous /  | FAIT | — | 444 |
| 4.2.6 | Abstraction Embeddings / ✅ Voir détails ci-dessous /  | FAIT | — | 445 |
| 4.3.1 | Choix du modèle par organisation / ✅ Voir détails ci-dessous /  | FAIT | oui | 467 |
| 4.3.2 | Temperature configurable / ✅ Voir détails ci-dessous /  | FAIT | — | 468 |
| 4.3.3 | Top P configurable / ✅ Voir détails ci-dessous /  | FAIT | oui | 469 |
| 4.3.4 | System prompt custom / ✅ Voir détails ci-dessous /  | FAIT | — | 470 |
| 4.3.5 | Max tokens configurable / ✅ Voir détails ci-dessous /  | FAIT | oui | 471 |

### Partie 10 — 20 lignes (FAIT 12, PARTIEL 6, NON COMMENCÉ 2)
| ID source | Texte (résumé, tronqué) | Déclaré | Test cité | Ligne |
|---|---|---|---|---:|
| 10.1.1 | JWT / ✅ /  | FAIT | — | 2263 |
| 10.1.2 | Refresh tokens / ✅ /  | FAIT | — | 2264 |
| 10.1.3 | OAuth / ✅ /  | FAIT | — | 2265 |
| 10.1.4 | RBAC / 🟡 (hiérarchie fixe voir 1.2.7 ; rôles personnalisés + permissions granulaires réels ajou | PARTIEL | — | 2266 |
| 10.1.5 | Rate limiting / ✅ (+ géo-adaptatif, IP de confiance) /  | FAIT | — | 2267 |
| 10.1.6 | Request validation / ✅ (Pydantic partout) /  | FAIT | — | 2268 |
| 10.1.7 | Input sanitization / 🟡 /  | PARTIEL | — | 2269 |
| 10.1.8 | Prompt injection protection / 🟡 (écrit, pas intégré en filtre live) /  | PARTIEL | — | 2270 |
| 10.1.9 | SSRF protection / ✅ Protection des accès HTTP externes vérifiée dans les clients SSRF-safe util | FAIT | — | 2271 |
| 10.1.10 | File validation / ✅ /  | FAIT | — | 2272 |
| 10.1.11 | MIME validation / ✅ (vérification magic-bytes) /  | FAIT | — | 2273 |
| 10.1.12 | Malware scanning (ClamAV) / ⬜ /  | NON COMMENCÉ | — | 2274 |
| 10.1.13 | Secret management / 🟡 (.env pour la clé maîtresse ; pas de KMS/Vault réel dans cet environnemen | PARTIEL | — | 2275 |
| 10.1.14 | Encryption at rest / 🟡 (réel, applicatif : AES-256-GCM ajouté pour `Webhook.secret` + Fernet dé | PARTIEL | — | 2276 |
| 10.1.15 | Encryption in transit / ✅ (HTTPS, voir guide de déploiement) /  | FAIT | — | 2277 |
| 10.3.1 | Audit log (actions admin) / ✅ (log inviolable HMAC, Catégorie 2 ; étendu avec organization_id/r | FAIT | — | 2288 |
| 10.3.2 | Structured logging / 🟡 /  | PARTIEL | — | 2289 |
| 10.3.9 | Error tracking (Sentry) / ✅ `sentry_sdk` est initialisé quand `SENTRY_DSN` est configuré, avec  | FAIT | — | 2292 |
| 10.4.1 | SSO / ✅ (OIDC générique, Catégorie 4 item 27) /  | FAIT | — | 2299 |
| 10.4.2 | SAML / ⬜ (choix documenté : OIDC à la place) /  | NON COMMENCÉ | — | 2300 |

## 6. Domaines fonctionnels présents dans le code (au-delà de la liste du cahier des charges)
Constat par lecture de l'arborescence (`api/routers` 101 fichiers, `api/services` 284, `api/security` 71, `api/tasks` 49, `api/tools` 10). **Présence dans le code ≠ fonctionnement démontré.**
- Compte, authentification, 2FA, WebAuthn, SSO, invitations, sessions, RGPD (export/suppression/consentement).
- Organisations, membres, rôles, permissions personnalisées, quotas, branding/white-label, domaines personnalisés, certificats.
- Documents : upload, extraction multi-formats, OCR, chunking, versions, doublons, imports (URL, sitemap, GitHub, Drive, Notion, Confluence, OneDrive, ZIP).
- RAG : recherche hybride, reranking, requêtes (HyDE/MMR/multi-requêtes), citations, anti-hallucination, chat streaming, mémoire.
- Agents : orchestrateur, agents autonomes, workflows, outils, A2A, MCP client/serveur, marketplace de plugins avec sandbox, voix/téléphonie.
- Évaluation : Eval Lab (datasets, runs, métriques, échecs), A/B tests, fine-tuning, analytics avancés.
- Facturation : plans, abonnements, factures, crédits, Stripe, Paystack, licences, partenaires/revendeurs, super-administration.
- Intégrations : webhooks, Slack/Discord/Teams/Twilio, Airbyte, SDK Python/JS/React/Vue, API publique, widget embarquable.
- Exploitation : audit log chaîné, chiffrement des champs, Prometheus/Sentry, health checks, i18n.

**Pour la distinction implémenté / validé / prouvé en production, voir `00_SYNTHESE_EXECUTIVE.md`.**