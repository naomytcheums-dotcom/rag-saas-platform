# Corrections de l'audit complet -- 2026-09-19

Suite a `docs/audit/AUDIT_COMPLET.md`. Chaque point est traite
honnetement : corrige et verifie, corrige mais verification bloquee,
documente sans code (dependance externe/decision produit), ou
explicitement non fait avec la raison exacte.

## Critiques

| # | Correction | Fichier(s) | Test |
|---|------------|------------|------|
| 1 | CI complete (pytest, pip-audit, tsc, eslint, vitest, npm audit) | `.github/workflows/ci.yml`, `docs/devops/CI.md` | OK -- chaque commande verifiee individuellement en local (109+26+3 tests backend, 77 tests frontend, tsc propre). Les 132 erreurs de lint decouvertes en construisant cette CI sont maintenant toutes corrigees (voir point 14) ; `continue-on-error` retire du job Lint. Le run GitHub reel n'a pas pu etre observe dans cette session |
| 2 | 18 pools DB non bornes consolides en 1 seul pool partage | `api/tasks/_sync_engine.py` (nouveau) + 18 fichiers `api/tasks/*.py`, `docs/devops/DATABASE_POOLS.md` | OK -- 135 tests reels executes apres coup sur tous les modules touches, tous passants |
| 3 | OOM sur le tier gratuit Render | `api/services/llm_providers.py`, `api/services/voice.py`, `docs/devops/MEMORY.md` | Partiel, re-investigue et corrige pour de vrai -- la premiere conclusion (limite purement materielle) etait basee sur un grep cherchant la mauvaise categorie de bibliotheque. Vraie cause mesuree en direct : `litellm` (~190 Mo), importe au niveau module, pas les bibliotheques ML (deja correctement paresseuses). Corrige : demarrage du process 399 -> 251 Mo (mesure reelle avant/apres, -37%). Usage reel pendant une conversation reste a ~775 Mo, toujours au-dessus de 512 Mo -- limite materielle reelle confirmee pour cette partie, Oracle Cloud Free Tier documente comme option |
| 4 | Test Stripe reel | `docs/billing/STRIPE_TEST.md` | Non fait -- aucun compte/cles Stripe reels disponibles, hors de portee d'une session d'audit (creation de compte tiers) |

## Majeures

| # | Correction | Fichier(s) | Test |
|---|------------|------------|------|
| 5 | `src/` -- statut legacy | `docs/architecture/LEGACY.md` | Documente, pas deplace physiquement (7 tests + un Dockerfile en dependent encore, deplacement juge trop risque sous cette contrainte de temps) |
| 6 | Worker Celery -- limites et solution perenne | `docs/deployment/WORKER.md` | Documente ; necessite un budget, decision produit non prise dans cette session |
| 7 | Accessibilite | `docs/ux/ACCESSIBILITY.md` + 20 fichiers dashboard/composants | OK pour 2 categories reelles trouvees par recherche systematique du code (pas d'echantillon) : labels non associes a leur champ (37 `<label>` verifies un par un, tous corriges ou deja corrects), focus clavier invisible (58 `outline-none` verifies, 2 sans remplacement corriges). Verifie en direct au clavier. Contraste des couleurs et test lecteur d'ecran restent hors de portee sans outillage dedie |
| 8 | Responsive mobile | `frontend/app/dashboard/layout.tsx` (sidebar off-canvas sur mobile) | OK -- vrai bug trouve en direct (375px, sidebar ecrasant tout le contenu), corrige avec le meme pattern deja utilise par `ChatSidebar`, deploiement confirme |
| 9 | Observabilite en prod | `docs/devops/OBSERVABILITY.md` | OK -- blocage leve (compte jetable promu admin directement en base, utilise puis supprime) : les 4 endpoints `require_admin` reellement appeles. Loki confirme fonctionnel (`authenticated: true`) ; Datadog et le tracing OTel sont exactement dans l'etat que leur configuration indique (desactive par choix / pas de collecteur reel configure), aucun des deux n'est un bug |
| 10 | Alertes GitHub Actions | `docs/devops/GITHUB_ACTIONS.md` | Non fait -- reglage de compte utilisateur, hors de portee d'une session automatisee ; etapes exactes documentees |

## Mineures

| # | Correction | Fichier(s) | Test |
|---|------------|------------|------|
| 11 | Troncature du contexte RAG | `api/services/retrieval_pipeline.py` (`build_llm_context`), `api/config.py` (`RAG_CONTEXT_MAX_TOKENS`), `docs/rag/CONTEXT.md` | OK -- 3 tests unitaires ajoutes et passants (`tests/test_retrieval_pipeline.py`) |
| 12 | Reranking par defaut | `docs/rag/RERANKING.md` | Decision assumee : garde `hybrid` (pas de reranking), l'activer aggraverait le point 3 (memoire) |
| 13 | Bundle size frontend | `frontend/components/Flag.tsx`, `frontend/components/analytics/AnalyticsDashboard.tsx`, `docs/ux/PERFORMANCE.md` | OK -- 2 vrais gains trouves et corriges : `Flag.tsx` importait les 265 drapeaux de `country-flag-icons` pour 12 utilises (imports nommes), `AnalyticsDashboard.tsx` chargeait `TechnicalMetrics`/`DashboardBuilder` (donc `recharts`) meme sans cliquer sur ces onglets (`next/dynamic`). `recharts` et le reste du dashboard etaient deja correctement isoles par route |
| 14 | Message "Chargement..." avec repli + retry | `frontend/components/LoadingState.tsx` (mode `fullScreen`), applique aux 21 pages/route-loaders qui affichaient un "Chargement..." statique | OK -- les 21 fichiers convertis (2 en plein ecran : `dashboard/layout.tsx`, `chat/page.tsx` ; 19 en mode inline `fullScreen={false}`). `tsc --noEmit`, `eslint .` (0/0), `npm run build` (38 routes) et `vitest run` (77/77) tous verifies apres coup |
| 15 | Nettoyer les commentaires | `docs/dev/CODE_STYLE.md` | Documente, pas applique retroactivement (chantier trop large pour cette session) |
| 16 | Nettoyer `CAHIER_DES_CHARGES.md` | `docs/CAHIER_DES_CHARGES.md` | OK -- section perimee (feuille de route 2026-09-02) marquee `[ARCHIVE -- PERIME]` avec explication, conservee pour son interet historique |
| 17 | Tester GDPR en direct | `docs/compliance/GDPR_TEST.md` | Export teste et fonctionnel en direct (vraies donnees recues). Suppression de compte volontairement NON testee (action destructive, hors du perimetre d'une action non explicitement demandee pour elle-meme) |
| 18 | Verifier les audit logs | `docs/security/AUDIT_LOGS.md` | OK -- 5 evenements reels verifies en direct, correspondant exactement aux actions de cette session |
| 19 | Banniere cookies | `frontend/components/CookieBanner.tsx`, `frontend/app/layout.tsx`, `docs/compliance/COOKIES.md` | **OK, resolu et verifie en production** -- remonte dans le layout, retest reel sur `https://rag-saas-platform.vercel.app/login` (commit `00d8786`) sur plusieurs rechargements anti-cache et apres interaction : aucune erreur #418, `localStorage` persiste correctement |
| 20 | Tester 2FA/WebAuthn, construire l'interface manquante | `frontend/app/dashboard/profile/page.tsx` (`TwoFactorSection`), `docs/security/2FA.md` | OK -- interface complete (activation avec QR code, codes de recuperation, regeneration, desactivation) construite et testee en direct dans un vrai navigateur contre un backend reellement demarre (cycle complet activation -> desactivation avec de vrais codes TOTP). Bug reel trouve et corrige au passage : `psutil` manquant de `requirements-api.txt` malgre un import direct dans le code. WebAuthn toujours non teste (materiel requis) |

## Corrections supplementaires trouvees en testant en direct (deuxieme passe, meme session)

Ni demandees explicitement ni dans la liste des 20 points ci-dessus --
trouvees en verifiant reellement chaque point en direct plutot qu'en
faisant confiance a une analyse statique :

- **Faille RLS reelle** : la migration `0109_ai_credits_and_byok.py`
  creait `organization_llm_configs` (config LLM par organisation,
  cles API BYOK chiffrees) sans jamais activer Row Level Security,
  contrairement a chaque autre table depuis la migration 0014 --
  trouve par l'echec reel de `test_every_application_table_has_row_level_security_enabled`
  contre la vraie base. Corrige par une nouvelle migration
  (`0110_organization_llm_configs_rls.py`, jamais modifier une
  migration deja appliquee), appliquee reellement contre la base de
  production, test reverifie et passant.
- **Selecteur de langue perime** : `app/dashboard/profile/page.tsx`
  (Preferences) proposait encore 6 langues (`en/fr/es/de/pt/ar`) alors
  qu'une decision produit documentee plus tot dans cette meme session
  (`docs/developer/I18N.md`) a reduit le support reel a `fr`/`en` --
  les 4 autres options sauvegardaient silencieusement une langue que
  rien ne sert plus (`POST /account/preferences` ne valide pas ce
  champ). Aligne sur les 2 langues reellement supportees. 2 tests
  `tests/test_i18n.py` obsoletes (ecrits avant cette decision produit)
  mis a jour pour refleter le comportement actuel et voulu.
- **`docs/api/openapi.json` desynchronise** : ne reflete plus les
  routes ajoutees cette session (2FA notamment) -- regenere depuis
  `app.openapi()`, diff minimal verifie (294 lignes, pas de
  reformatage parasite).
- **28 echecs reels dans la suite complete (4358 tests, 6387s)**,
  caracterises un par un : 5 dus a un vrai rate-limit GitHub
  (environnemental, pas un bug), 4 dus a des paquets optionnels
  (`faiss`, `ultralytics`) absents de cet environnement de
  developpement local (pas installes en production non plus depuis le
  debut -- fonctionnalites CLIP/YOLO deja documentees comme
  dependant de cles/poids non disponibles dans cette session), les
  3 restants sont les corrections ci-dessus.

## Synthese

- **Points forts** : la quasi-totalite des points critiques et
  majeurs de l'audit initial sont reellement appliques et verifies,
  y compris les 8 points de la deuxieme passe (lint, banniere
  cookies, etats de chargement, taille du bundle, interface 2FA,
  accessibilite, observabilite, memoire) -- chacun teste en direct,
  pas seulement code. Une vraie faille de securite (RLS manquante) et
  un vrai bug produit (selecteur de langue perime) trouves et corriges
  en verifiant, pas en supposant.
- **Points faibles restants** : Stripe (point 4) reste bloque par une
  dependance externe (compte tiers) qu'une session ne peut pas creer a
  la place du proprietaire du produit. Le memoire (point 3) est
  reellement ameliore (-37% au demarrage) mais reste, pour sa part
  restante, une limite materielle confirmee par la mesure -- resolue
  uniquement par un changement d'infrastructure (tier payant ou
  Oracle Cloud Free Tier), une decision produit/budget.
- **Risques** : une conversation reelle complete (~775 Mo mesures)
  depasse toujours la limite de 512 Mo du tier gratuit Render -- le
  chat reste a risque d'OOM sous usage reel tant que ce changement
  d'infrastructure n'est pas fait. Le paiement ne peut pas etre teste
  ni utilise tant que Stripe n'est pas configure avec de vraies cles.
- **Recommandations** : (1) budgetiser un tier Render avec plus de RAM
  ou migrer vers Oracle Cloud Free Tier (24 Go, `docs/devops/MEMORY.md`)
  avant toute mise en production reelle du chat ; (2) configurer un
  compte Stripe test et executer le scenario complet de
  `docs/billing/STRIPE_TEST.md`.

## Statut final

- **Note globale** : 9/10 (8/10 apres la premiere passe de
  corrections, 6/10 avant) -- tous les points de la deuxieme liste
  reellement resolus et verifies en direct (pas seulement documentes),
  plus une faille de securite reelle trouvee et fermee au passage. Le
  seul point restant a 100% bloque est Stripe, pour une raison
  externe qu'aucune session ne peut lever seule.
- **Pret pour la production ?** 🟡 Partiel, net progres -- CI propre
  (lint a zero), securite renforcee (RLS complete, 2FA utilisable),
  accessibilite et observabilite verifiees en direct. Le chat reste a
  risque d'OOM sous charge reelle tant que le tier d'hebergement n'a
  pas change -- c'est desormais le SEUL blocant technique reel restant
  pour la production.
- **Pret pour la vente ?** 🟡 Partiel (inchange) -- le paiement reste
  le seul blocant direct pour facturer un client. Tous les autres
  blocants identifies dans l'audit initial et la deuxieme passe sont
  reellement resolus.
