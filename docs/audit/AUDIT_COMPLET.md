# Audit complet -- RAG SaaS Platform

Date : 2026-09-19. Perimetre et methode, honnetement : cet audit combine
des findings **verifies en direct** (accumules sur une session tres longue
de tests reels en production -- authentification, Celery, CORS, chat,
i18n, navigation) et une **revue de code statique** ciblee (securite,
architecture, DevOps) effectuee specifiquement pour cet audit. Aucune
ligne ci-dessous n'est fabriquee : chaque probleme est soit une trace
reelle (log Render, erreur console, commit de correction), soit une
citation exacte de fichier/ligne. Ce que je n'ai PAS teste en direct dans
cette session (execution reelle d'un fine-tuning, d'un agent autonome,
integration Stripe avec une vraie carte, etc.) est marque explicitement
"non teste en direct" plutot que presente comme verifie.

---

## 1. Audit de l'architecture

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | Deux bases de code coexistent : `src/` (prototype Streamlit mono-tenant original) et `api/` (le vrai backend SaaS multi-tenant). `src/` n'a aucune notion d'organisation et duplique des constantes deja presentes dans `api/` (`CHUNK_SIZE_TOKENS`, `EMBEDDING_MODEL_NAME`, etc., documente dans `docs/CAHIER_DES_CHARGES.md` ligne 136). Un futur contributeur peut facilement modifier le mauvais fichier. | 🟠 Majeur | Archiver ou supprimer `src/` une fois sa fonction de reference historique jugee inutile, ou le deplacer dans un dossier `legacy/` explicite avec un README d'avertissement. |
| 2 | 18 moteurs SQLAlchemy synchrones separes dans `api/tasks/*.py`, chacun avec un pool par defaut non borne (5 + 10 overflow = 15 connexions potentielles par moteur). Le pooler Supabase en mode session (utilise par `DATABASE_URL`) plafonne a 15 connexions **au total**, tous processus confondus. Deja documente dans `docs/deployment/RENDER.md`, jamais corrige. | 🔴 Critique | Appliquer le meme `pool_size=3, max_overflow=2` deja pose sur le moteur async principal (`api/database.py`) a chacun des 18 moteurs de `api/tasks/`, ou factoriser un seul moteur partage. |
| 3 | Le worker Celery de production tourne via un workflow GitHub Actions programme (toutes les 10 min), pas un vrai worker permanent -- consequence directe de l'absence de tier gratuit Render pour les Background Workers. Documente honnetement dans `docs/deployment/GITHUB_ACTIONS.md`, mais reste une dependance d'infrastructure fragile (quota Actions, health check 5s, RAM 512MB partagee avec l'API web). | 🟠 Majeur | Budgetiser un vrai worker Render paye (7$/mois) des que le revenu le justifie ; en attendant, documenter clairement aux clients le delai de traitement de ~10 min. |
| 4 | Couplage fort entre le prompt d'agent et le contenu recupere : `context` est concatene en texte brut dans le prompt (`"\n\n".join(...)`), sans limite de longueur ni troncature -- un document tres volumineux ou une organisation avec beaucoup de chunks pertinents pourrait depasser la fenetre de contexte du LLM silencieusement. | 🟡 Mineur | Ajouter une troncature explicite du `context` construit (par nombre de tokens, via le meme tokenizer deja mis en cache pour le chunking) avant l'appel LLM. |

## 2. Audit de la securite

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | **XSS stockee reelle et exploitable** dans la recherche de conversations : `highlight_matches()` (`api/services/conversation_management.py`) renvoyait le texte d'un message utilisateur (contenu arbitraire) avec des balises `<mark>` injectees, sans jamais echapper le HTML -- et le frontend l'injecte via `dangerouslySetInnerHTML` (`ConversationSearch.tsx`). Un message contenant `<script>` s'executait dans le navigateur de quiconque recherchait un terme correspondant. Capable d'exfiltrer le token d'acces (stocke en `localStorage`, pas en cookie httpOnly). | 🔴 Critique | **Corrige dans cet audit** : `html.escape()` applique a chaque segment de texte avant l'ajout des balises `<mark>`. 2 tests de regression ajoutes, 5/5 tests passent. Commit `2d92ae7`. |
| 2 | Aucune pipeline CI n'execute les 284 fichiers de tests ni aucun linting/scan de securite automatique. Le seul workflow GitHub Actions existant (`celery-worker.yml`) est le worker planifie cree cette session, pas un CI. Un ancien workflow de tests a d'ailleurs existe puis disparu (voir `docs/deployment/GITHUB_ACTIONS.md`, il a epuise le quota Actions gratuit en tournant en echec des dizaines de fois sans que personne ne le remarque). | 🔴 Critique | Ajouter un workflow `.github/workflows/ci.yml` : `pytest`, `npx tsc --noEmit`, `npm run lint`, `pip-audit`, `npm audit`, declenche sur chaque push/PR. |
| 3 | `pip-audit -r requirements-api.txt` execute a son terme (tres lent, plusieurs minutes -- reseau probablement restreint dans cet environnement) : **0 vulnerabilite connue trouvee** (sortie vide, code de sortie 0) sur les 443 lignes de `requirements-api.txt`. `npm audit --production` cote frontend : egalement 0 vulnerabilite. | 🟢 Suggestion (verifie, sain) | Rien a corriger sur l'etat actuel ; integrer ces deux commandes en CI (point 2 ci-dessus) pour que ce resultat reste vrai a chaque changement de dependance, pas seulement aujourd'hui. |
| 4 | `WIDGET_CORS_ALLOWED_ORIGINS` par defaut a `["*"]` -- deliberement documente et scope au prefixe `/widget/*` uniquement (le widget embarquable doit accepter n'importe quel site tiers par design). Pas une vraie faille, mais merite une verification manuelle que les routes `/widget/*` ne renvoient jamais de donnees sensibles cross-tenant sur la seule foi de l'origine. | 🟢 Suggestion | Documenter explicitement (README ou commentaire) la liste exacte des endpoints sous `/widget/*` et confirmer qu'aucun ne peut lire les donnees d'une AUTRE organisation que celle du widget-key fourni. |
| 5 | CORS applicatif principal corrige cette session (trouve en testant en direct sur le vrai domaine de production) : `CORSMiddleware` n'autorisait qu'UNE seule origine statique (`FRONTEND_URL`), cassant l'authentification sur le vrai domaine de prod des qu'il differait de l'alias de preview. Corrige avec une liste + une regex pour les URLs de deploiement Vercel. | 🔴 Critique (deja corrige) | Fait, commit `eb934aa`. Verifie par un vrai test de connexion reussi en production. |
| 6 | Accessibilite securitaire correcte par ailleurs : JWT HS256, access token 15 min / refresh 30 jours avec rotation documentee, 2FA (TOTP + WebAuthn) presents (`api/routers/two_factor.py`, `webauthn.py`), RLS Postgres activee sur au moins 108 references de migration, secrets chiffres via Fernet (`api/security/secret_encryption.py`), rate limiting configure (login 5/15min, inscription 3/h, etc.). Aucun secret en dur trouve dans le code trackee par un scan par motif. | 🟢 Suggestion | Rien a corriger ; documenter cette liste dans un `SECURITY.md` public pour rassurer des clients potentiels (souvent demande en due diligence B2B). |

## 3. Audit de la performance

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | **Deux appels CPU-bloquants dans le pipeline de recherche** (`generate_embeddings` et `CrossEncoder.predict`, `api/services/retrieval_pipeline.py`) etaient executes de facon synchrone a l'interieur de fonctions `async` -- geler toute la boucle asyncio du worker pendant leur duree, empechant meme le health check de repondre. Trouve en testant un vrai message de chat en direct (crash confirme dans les logs Render). | 🔴 Critique (corrige) | `loop.run_in_executor(None, ...)` applique aux deux. Commit `76481af`. |
| 2 | Timeout par defaut de gunicorn (30s) trop court pour une reponse en streaming SSE, qui peut legitimement prendre jusqu'a `SSE_TIMEOUT` (120s). Gunicorn tuait le worker en plein stream, independamment de tout bug applicatif. | 🔴 Critique (corrige) | `timeout = 130` ajoute a `gunicorn.conf.py`. Commit `a6b6955`. |
| 3 | **Plafond memoire du tier gratuit Render (512MB) reste depasse** lors d'un vrai appel de chat (embedding + LLM streaming simultanes, au-dessus des modeles ML deja charges en memoire -- torch, sentence-transformers, et d'apres l'historique du Dockerfile egalement ultralytics/opencv). Confirme par l'evenement Render exact : *"Ran out of memory (used over 512MB) while running your code."* Limite d'infrastructure, pas un bug de code identifiable a ce stade. | 🔴 Critique (non corrige -- limite d'infra) | Options reelles : (a) charger les modeles ML de maniere paresseuse/conditionnelle pour reduire l'empreinte de base ; (b) verifier si `ultralytics`/`opencv` (vision/traitement d'image) sont importes au demarrage meme quand non utilises par le chemin de chat, et les rendre import-differe ; (c) passer a un tier Render avec plus de RAM. |
| 4 | Strategie de recherche par defaut est `hybrid` (BM25 + vectoriel), sans reranking -- un choix raisonnable pour la latence, mais signifie que `hybrid_reranked` (le seul mode qui ameliore vraiment la pertinence via le cross-encoder) n'est jamais utilise sauf configuration explicite par organisation. | 🟡 Mineur | Documenter ce choix comme un compromis assume latence/pertinence, pas un oubli -- deja le cas en pratique, juste a rendre explicite dans la doc client. |
| 5 | Aucune mesure de bundle size frontend effectuee dans cette session (`next build` non execute en local faute de temps). 203 fichiers `.tsx` au total -- une taille de bundle non auditee est un risque reel pour le temps de chargement initial sur un tier gratuit Vercel deja sujet a des cold starts cote API. | 🟡 Mineur (non audite) | Executer `npm run build` et inspecter le rapport de taille des chunks Next.js ; envisager du `dynamic import()` pour les pages lourdes (Analytics, Fine-tuning) qui ne sont pas visitees par tous les utilisateurs. |

## 4. Audit de la scalabilite

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | Le worker Celery via GitHub Actions ne peut traiter qu'une file a la fois, toutes les 10 minutes, borne a 7 minutes d'execution -- inadapte a un volume de documents important (un pic d'uploads depasserait la fenetre). | 🟠 Majeur | Prevu pour rester un pont temporaire ; a remplacer par un vrai worker degressif des la premiere clientele payante. |
| 2 | Voir Architecture #2 (18 moteurs sync non bornes) -- risque reel d'epuisement de connexions Postgres des que Celery traite un volume significatif de taches en parallele. | 🔴 Critique | Meme correction que ci-dessus. |
| 3 | Stockage S3/Supabase Storage non audite pour des limites de taille de fichier ou de bande passante specifiques a ce projet -- non teste avec un gros fichier dans cette session. | 🟡 Mineur (non audite) | Tester un upload de document proche de la limite documentee (`MAX_DOCUMENT_SIZE_MB` ou equivalent) pour confirmer le comportement reel. |

## 5. Audit de l'UX/UI

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | 3 pages entierement fonctionnelles (Analytics, Fine-tuning, Agents autonomes) etaient invisibles dans la navigation -- decouvert en testant les 12 parcours en direct. | 🟠 Majeur (corrige) | Ajoutees a `frontend/app/dashboard/layout.tsx`. Verifie visible et cliquable en production. |
| 2 | Formulaire de creation d'agent autonome entierement en anglais, incoherent avec le reste de l'interface francaise. | 🟡 Mineur (corrige) | Traduit (`AgentCreateForm.tsx`). Verifie en direct. |
| 3 | Aucun selecteur de langue fonctionnel n'existait avant cette session, malgre toute la plomberie i18n deja en place cote hook (`setLanguage()` jamais appele par aucun composant). | 🟠 Majeur (corrige) | `LanguageSelector.tsx` cree, teste en direct (bascule FR/EN confirmee sans crash). |
| 4 | Accessibilite : seulement 12 des 203 fichiers `.tsx` contiennent un `aria-label` (~6%). Non mesure : contraste des couleurs, navigation clavier complete, lecteurs d'ecran. | 🟠 Majeur (non corrige) | Audit d'accessibilite dedie recommande (WCAG 2.1 AA a minima) avant toute vente a un client avec obligations d'accessibilite (secteur public, grands comptes). |
| 5 | Responsive : teste uniquement au niveau desktop dans cette session (aucun test mobile/tablette effectue). | 🟡 Mineur (non audite) | Tester explicitement en largeur mobile (375px) chaque page critique (chat, dashboard, formulaires). |
| 6 | Fenetre "Chargement..." generique et sans limite de temps affichee sur plusieurs pages en cas de lenteur backend (observe plusieurs fois cette session, notamment sur Facturation et Admin) -- aucun etat "ca prend plus longtemps que prevu" ni retry visible pour l'utilisateur final. | 🟡 Mineur | Ajouter un message de repli apres quelques secondes ("Ca prend plus de temps que prevu...") sur les etats de chargement partages. |

## 6. Audit de la qualite du code

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | 284 fichiers de tests presents -- couverture large en apparence, mais **jamais executee automatiquement** (voir Securite #2, absence de CI). Une regression peut donc etre mergee sans qu'aucun test ne tourne. | 🔴 Critique | Meme correction : CI obligatoire. |
| 2 | Style de commentaires tres verbeux partout dans le code (blocs de plusieurs paragraphes par fonction, ex. `agent_orchestrator.py`, `retrieval_pipeline.py`) -- utile pour la tracabilite des decisions, mais alourdit reellement la lecture et le diff review pour un nouveau contributeur. | 🟢 Suggestion | Deplacer l'historique des decisions vers `CHANGELOG.md`/ADRs plutot que des docstrings de plusieurs paragraphes par fonction, une fois l'equipe elargie. |
| 3 | `frontend/lib/mockChat.ts` (mock jamais retire malgre un commentaire pretendant que "le backend reel n'est pas encore branche" -- stale depuis que le login fonctionnait reellement) est reste en production pendant une periode indeterminee avant d'etre trouve et supprime cette session. Signe d'un risque plus large : des commentaires "TODO temporaire" peuvent rester obsoletes longtemps sans etre revus. | 🟡 Mineur (corrige pour ce cas) | Grep periodique (ou regle de lint) pour les commentaires contenant "temporaire"/"pas encore"/"TODO" plus vieux qu'un certain nombre de commits. |
| 4 | Documentation technique tres riche (`docs/CAHIER_DES_CHARGES.md`, 3800+ lignes) mais son propre etat interne est incoherent : se termine par "On commence par laquelle ?" (artefact de planification tres ancien), alors que le corps du document montre de nombreuses parties a 100%. | 🟢 Suggestion | Nettoyer la section finale perimee ou la deplacer dans une archive `docs/archive/`. |

## 7. Audit DevOps et infrastructure

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | Aucune pipeline CI/CD (voir points precedents, repete ici car c'est le sujet central de cette section). | 🔴 Critique | A traiter en priorite absolue -- impact transverse sur securite, qualite, fiabilite. |
| 2 | Stack d'observabilite reelle et presente : Prometheus, Grafana/Loki, Tempo, Datadog, OpenTelemetry tous configurables (`api/config.py`), `docker-compose.observability.yml` dedie. Non verifie si reellement branche et alimente en production (aucune des variables `DD_*`/`PROMETHEUS_*`/`LOKI_*` n'est confirmee configuree sur Render dans cette session). | 🟠 Majeur (a verifier) | Confirmer sur le dashboard Render quelles variables d'observabilite sont reellement definies ; sinon, la stack de monitoring documentee est en realite eteinte en production. |
| 3 | Quota GitHub Actions du compte epuise par un ancien workflow de tests casse qui a tourne des dizaines de fois en echec sans alerte -- personne ne surveillait ce quota. Reset mensuel, mais peut se reproduire. | 🟠 Majeur (deja documente) | Ajouter une alerte (email GitHub natif, deja disponible) sur le depassement de quota Actions ; supprimer tout workflow qui echoue systematiquement plutot que de le laisser tourner. |
| 4 | Tier gratuit Render (0.1 CPU, 512MB RAM) structurellement insuffisant pour les dependances ML reelles de ce projet des qu'un vrai appel LLM+embedding a lieu -- confirme par un OOM reel en production cette session (voir Performance #3). | 🔴 Critique | Necessite soit une reduction de l'empreinte memoire (audit des imports lourds), soit un budget d'hebergement paye avant toute mise en production reelle avec des clients. |
| 5 | Base de donnees Supabase en mode pooler session (15 connexions max total) alors que l'application ouvre potentiellement 18+3 = 21 moteurs de connexion distincts si tous actifs simultanement. | 🔴 Critique (voir Architecture #2) | Meme correction. |

## 8. Audit de la conformite

| # | Probleme | Severite | Correction |
|---|----------|----------|------------|
| 1 | Fonctionnalites GDPR presentes au niveau code : `api/routers/account.py` (suppression de compte avec delai de grace + rappel), `api/routers/compliance.py`, `api/services/data_export.py` (export de donnees). Non testees en direct dans cette session (aucune suppression/export reel effectue). | 🟡 Mineur (non teste en direct) | Tester en direct : creer un compte, demander un export, verifier le contenu reel du fichier produit ; demander une suppression, confirmer le delai de grace puis la purge reelle via la tache planifiee correspondante. |
| 2 | Audit logs presents (`api/security/audit_log.py`, HMAC signes d'apres les variables d'environnement vues cette session `AUDIT_LOG_HMAC_SECRET_KEY`) -- non verifie si chaque action sensible (connexion, changement de mot de passe, suppression de donnees) est effectivement journalisee en pratique. | 🟡 Mineur (non audite) | Verifier en direct qu'une action sensible (ex. changement d'email) produit bien une entree d'audit log consultable. |
| 3 | Consentement/bannieres cookies : non trouve de composant dedie dans le frontend lors de cette session (aucune recherche exhaustive effectuee specifiquement pour ce point). | 🟡 Mineur (non audite) | Verifier la presence reelle d'un mecanisme de consentement cookies si des cookies non essentiels sont poses (le cookie `UI_LANGUAGE_COOKIE_NAME` semble fonctionnel/necessaire, donc probablement hors du perimetre RGPD du consentement, a confirmer). |

## 9. Audit des fonctionnalites

| # | Fonctionnalite | Statut | Probleme |
|---|----------------|--------|----------|
| 1 | Inscription / Connexion | OK | Verifie en direct sur le vrai domaine de production apres correction CORS. |
| 2 | Upload de document | OK | Verifie en direct, y compris le traitement complet par Celery (statut `completed`, chunking, resume genere). |
| 3 | Creation d'agent | OK | Verifie en direct. |
| 4 | Conversation (chat) | Partiel | Backend corrige (grounding, streaming), mais verification finale de bout en bout bloquee par l'OOM du tier gratuit (voir Performance #3). |
| 5 | Widget embarquable | Partiel | Page de configuration verifiee en direct ; l'integration reelle sur un site tiers n'a pas ete testee dans cette session. |
| 6 | Cles API | OK | Creation, listage, revocation verifies en direct. |
| 7 | Facturation | OK (donnees de base) | Plan Free / credits affiches correctement ; integration Stripe reelle jamais testee contre une vraie cle API (confirme par `api/services/billing_stripe.py` lui-meme, qui documente l'absence de compte Stripe reel dans cet environnement). |
| 8 | Administration | Partiel | Controle d'acces RBAC verifie correct (refus propre pour un non-superadmin) ; contenu reel de l'admin jamais vu faute de compte superadmin. |
| 9 | Marketplace de plugins | Partiel | Liste et recherche affichees en direct ; installation/execution reelle d'un plugin non testee. |
| 10 | Analytics | OK (affichage) | Page accessible, etats vides corrects pour un compte neuf ; jamais vue avec des donnees reelles significatives. |
| 11 | Fine-tuning | Partiel | Page accessible, compteurs corrects, mais aucun bouton de creation trouve -- fonctionnalite peut-etre incomplete cote frontend. |
| 12 | Agents autonomes | OK (creation) | Creation verifiee en direct ; execution reelle d'un plan autonome non testee. |
| 13 | Celery / traitement asynchrone | OK | Verifie en direct via GitHub Actions, y compris apres correction d'un bug TLS Redis et d'un bug de configuration S3. |
| 14 | i18n (FR/EN) | OK | Limitation et selecteur verifies en direct. |
| 15 | Recherche de conversations | Corrige | Fonctionnelle, mais contenait la faille XSS critique decrite en Securite #1, corrigee dans cet audit. |
| 16 | 2FA / WebAuthn | Non teste en direct | Code present et structure correctement (routers dedies), jamais exerce en direct dans cette session. |
| 17 | Export/suppression GDPR | Non teste en direct | Voir Conformite #1. |

## 10. Audit de la valeur business

| # | Force/Faiblesse | Impact | Recommandation |
|---|-----------------|--------|-----------------|
| 1 | Force : ampleur reelle des fonctionnalites construites (agents, workflow, fine-tuning, multi-modal, A/B testing, marketplace, white-label, integrations 6+ sources externes) -- une couverture fonctionnelle rare pour un projet de cette taille. | Positif fort | Mettre en avant cette largeur fonctionnelle dans le positionnement commercial face a des concurrents plus etroits. |
| 2 | Faiblesse : infrastructure de production actuelle (tier gratuit Render + Vercel) ne tient pas la charge d'un vrai usage de chat concurrentiel (OOM confirme sur un SEUL message de test). Vendre le produit dans cet etat exposerait des clients reels a des pannes. | Negatif critique | Ne pas commercialiser avant d'avoir budgetise un hebergement de production reel (minimum : backend avec >=1GB RAM). |
| 3 | Faiblesse : integration de paiement (Stripe) jamais testee contre un vrai compte -- impossible de facturer un client reel aujourd'hui sans le faire pour la premiere fois en conditions reelles. | Negatif fort | Configurer et tester un vrai compte Stripe (mode test d'abord) avant toute offre commerciale. | 
| 4 | Faiblesse : absence de CI signifie que chaque futur changement risque de re-introduire silencieusement les memes classes de bugs deja trouvees et corrigees cette session (CORS, blocage d'event loop, XSS). | Negatif fort | CI obligatoire avant d'ouvrir le developpement a une autre personne que le proprietaire actuel. |
| 5 | Neutre/a verifier : aucune analyse concurrentielle ni etude de marche effectuee dans cette session -- hors du perimetre de ce qui est verifiable par un audit technique. | -- | A traiter separement, hors competence d'un audit de code. |

## 11. Corrections appliquees

| # | Correction | Fichier | Test |
|---|------------|---------|------|
| 1 | XSS stockee : echappement HTML dans `highlight_matches` | `api/services/conversation_management.py` | OK (5/5 tests, dont 2 nouveaux) |
| 2 | (Rappel, corrige avant cet audit dans la meme session) CORS mono-origine cassant la production | `api/main.py`, `api/config.py` | OK (connexion reussie en direct) |
| 3 | (Rappel) Appels bloquants gelant la boucle asyncio | `api/services/retrieval_pipeline.py` | OK (compile ; comportement confirme par logs Render post-deploiement) |
| 4 | (Rappel) Timeout gunicorn trop court pour le streaming | `gunicorn.conf.py` | OK (deploiement confirme, requete a depasse l'ancien seuil de 30s) |
| 5 | (Rappel) Contexte RAG jamais transmis au LLM | `api/routers/chat_stream.py`, `api/services/public_api.py` | Partiel (verifie en code, verification live bloquee par OOM) |
| 6 | (Rappel) Navigation incomplete (3 pages invisibles) | `frontend/app/dashboard/layout.tsx` | OK (verifie en direct) |
| 7 | (Rappel) Formulaire non traduit | `frontend/components/autonomous/AgentCreateForm.tsx` | OK (verifie en direct) |
| 8 | (Rappel) i18n limite a FR/EN + selecteur cree | `api/config.py`, `frontend/components/LanguageSelector.tsx` | OK (verifie en direct) |

## 12. Synthese

- **Points forts** : couverture fonctionnelle tres large et reellement construite (pas juste des maquettes) ; securite de fond serieuse (JWT, 2FA, RLS, chiffrement, rate limiting) ; observabilite prevue et outillee ; 284 fichiers de tests existent reellement.
- **Points faibles** : absence totale de CI (le risque transverse le plus grave -- il permet a tout le reste de se degrader sans alerte) ; infrastructure de production actuelle structurellement insuffisante pour le chat reel (OOM confirme) ; une faille XSS critique dormait en production avant cet audit ; integration de paiement jamais testee en conditions reelles.
- **Risques** : un client reel utilisant le chat aujourd'hui rencontrerait probablement le meme crash memoire observe cette session ; toute regression de securite future ne serait pas attrapee avant la production faute de CI ; facturer un vrai client echouerait probablement au premier essai (Stripe jamais valide).
- **Recommandations prioritaires** (par ordre) : (1) CI complete (tests + lint + scans) avant tout autre changement ; (2) resoudre le plafond memoire Render (reduction d'empreinte ou upgrade payant) ; (3) valider Stripe en mode test reel ; (4) corriger les 18 moteurs de connexion non bornes ; (5) audit d'accessibilite dedie avant toute vente B2B avec exigences de conformite.

## 13. Statut final

- **Note globale** : 6/10 -- base technique et fonctionnelle serieuse, mais des lacunes operationnelles (CI, infra, paiement) qui bloquent une mise en production reelle responsable.
- **Pret pour la production ?** 🟡 Partiel -- fonctionnel pour une demo/beta fermee avec des utilisateurs prevenus des limites ; pas pret pour un usage production sans surveillance.
- **Pret pour la vente ?** ❌ Non -- paiement jamais valide en conditions reelles, chat reel instable sous charge minimale, aucune garantie de non-regression (pas de CI). Ces trois points sont des blocants directs pour facturer un client aujourd'hui.
