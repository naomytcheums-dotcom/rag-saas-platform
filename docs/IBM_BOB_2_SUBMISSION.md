# RAG SaaS Platform — Description du projet (soumission IBM Bob 2.0)

**Date** : 2026-09-24
**Auteur** : Naomy Tcheums
**Méthode** : chaque affirmation ci-dessous est vérifiée directement dans
le code réel (endpoints, modèles, fichiers) au moment de la rédaction —
aucune fonctionnalité listée comme "faite" n'est une intention ou un
plan. Les limites connues sont documentées explicitement (Section 12),
pas cachées.

---

## 1. Résumé exécutif

**RAG SaaS Platform** est une plateforme multi-tenant de Retrieval-
Augmented Generation destinée à l'entreprise : un backend FastAPI et un
frontend Next.js qui couvrent, dans un seul produit cohérent, tout le
cycle de vie d'une application IA d'entreprise — ingestion documentaire,
recherche hybride, agents autonomes avec appel d'outils et interopérabilité
MCP, orchestration de workflows visuels, évaluation systématique de la
qualité (Eval Lab), facturation, marque blanche, et une surface complète
d'administration/sécurité.

**Public cible** : équipes produit et plateforme en entreprise qui
veulent déployer une solution RAG/agents sans assembler elles-mêmes une
dizaine d'outils séparés (vector store, orchestrateur d'agents, outil
d'éval, facturation, SSO) — et les intégrateurs/revendeurs qui ont besoin
d'une base self-hosted, multi-tenant, avec un contrôle total du code.

**Proposition de valeur** : un socle self-hosted, réellement multi-tenant
dès la conception (organisations, RBAC à 52 permissions, SSO OIDC), avec
trois capacités que peu de plateformes open source réunissent en même
temps : une interopérabilité MCP bidirectionnelle (client **et** serveur),
un module d'évaluation de la qualité RAG avec analyse d'échecs réelle
(pas un tableau de bord vide), et une discipline d'ingénierie documentée
(chaque bug trouvé, chaque limite connue, chaque décision d'architecture
tracée dans [`ROADMAP.md`](../ROADMAP.md) et
[`docs/CAHIER_DES_CHARGES.md`](CAHIER_DES_CHARGES.md)).

---

## 2. Problème résolu

**Le problème** : construire une application RAG/agents de niveau
entreprise exige aujourd'hui d'assembler et de maintenir soi-même de
nombreux systèmes indépendants — authentification multi-tenant, pipeline
d'ingestion et de retrieval, orchestrateur d'agents, moteur de workflows,
facturation, marque blanche, observabilité, et un outillage d'évaluation
de la qualité. Chaque système open source existant en couvre une partie,
rarement toutes — et la plupart d'entre eux exposent la fonctionnalité
multi-tenant/entreprise (SSO, RBAC fin, audit) derrière une licence
commerciale fermée (Dify, Onyx, Flowise Enterprise), pas dans leur version
self-hosted gratuite.

**Pour qui** : une équipe qui veut un produit IA d'entreprise réel (pas un
prototype) — avec des utilisateurs multiples, une facturation, une marque
blanche, et une preuve mesurable de la qualité des réponses — sans acheter
une licence Enterprise séparée pour obtenir le SSO ou le RBAC.

**Pourquoi c'est important** : sans évaluation systématique, une équipe ne
sait pas si un changement de prompt, de modèle ou de stratégie de retrieval
améliore ou dégrade réellement les réponses — elle le découvre en
production. Sans interopérabilité MCP, les agents de la plateforme restent
isolés des outils métier déjà connectés à l'écosystème MCP (de plus en
plus large depuis son adoption 2024-2025). Ces deux gaps sont documentés
dans l'audit concurrentiel du projet ([`docs/COMPETITIVE_AUDIT_KNOWFLOW.md`](COMPETITIVE_AUDIT_KNOWFLOW.md))
comme absents de la plupart des alternatives open source à la date de
l'audit (2026-09-21) — ils sont aujourd'hui réels dans ce projet (voir
Section 11).

---

## 3. Solution

**Comment ça marche** : un utilisateur (ou une organisation) envoie des
documents, qui sont chunkés, vectorisés et indexés ; une requête déclenche
une recherche hybride (BM25 + vecteurs + Reciprocal Rank Fusion +
reranking cross-encoder) dont les résultats alimentent soit une réponse de
chat directe (avec citations cliquables vers les passages sources), soit
un agent autonome capable d'enchaîner plusieurs étapes et d'appeler des
outils — y compris des outils exposés par un serveur MCP externe. Toute
cette chaîne peut aussi être orchestrée explicitement via un moteur de
workflows (déclencheurs cron/webhook, blocs LLM/RAG/recherche/HTTP/
condition/base de données/humain). Chaque exécution — recherche, réponse,
run d'agent, run de workflow, run d'évaluation — est tracée (latence,
tokens, coût), et l'Eval Lab permet de mesurer objectivement (Recall@K,
MRR, NDCG, taux d'hallucination) si un changement améliore réellement la
qualité avant de le déployer.

**Composants principaux** :
- `api/` — backend FastAPI, 756 endpoints, 82 modèles de données, 123
  migrations Alembic, ~300 fichiers de tests.
- `frontend/` — Next.js/React, dashboard multi-sections dont l'Eval Lab
  (`/dashboard/eval`), le générateur de workflows visuel (React Flow), et
  le chat (Markdown + coloration syntaxique + citations).
- `sdks/` — clients officiels Python, JavaScript, React et Vue pour l'API
  publique.
- PostgreSQL (Supabase) pour les données, Redis pour le cache applicatif
  et le rate limiting, Celery pour les tâches de fond (ingestion, éval,
  workflows, purge).

---

## 4. Capacités détaillées

| Capacité | Description | Différenciateur | Statut |
|---|---|---|---|
| RAG hybride | BM25 + vecteurs + RRF + reranking cross-encoder | Reranking réel et fonctionnel — supérieur à un concurrent (Onyx) qui l'a retiré comme code mort en 2026 | ✅ Fait, branché |
| Chunking avancé | 7 stratégies codées et testées unitairement (fixed/recursive/semantic/markdown/sentence/paragraph/parent-child) | — | 🟡 1 seule branchée en production, 6 codées mais non sélectionnables par type de document |
| Retrieval avancé | HyDE, multi-query, MMR, query rewriting, compression de contexte, filtrage metadata — tous codés et testés | — | 🟡 Codés, non exposés dans l'API de recherche actuelle |
| Agents & MCP | Agents configurés + agents autonomes multi-étapes (plan → exécution → coût → garde-fous), MCP **client et serveur** | Interopérabilité MCP bidirectionnelle — gap fermé alors qu'il était absent de la plateforme à l'audit du 2026-09-21 | ✅ Fait |
| Workflows | Moteur d'exécution réel (11 types de blocs, cron via Celery Beat, pause/reprise humaine, anti-boucle) + interface visuelle React Flow | — | ✅ Fait (backend + UI) |
| Auth & Multi-tenant | JWT, OAuth Google/GitHub, SSO OIDC générique, 2FA TOTP + WebAuthn, RBAC à 52 permissions granulaires (13 ressources × 4 actions) | SSO OIDC en self-hosted gratuit, alors que la plupart des concurrents le réservent à leur édition Enterprise payante | ✅ Fait |
| Billing | Stripe + Paystack derrière une interface fournisseur commune, plans, quotas, factures | Deux fournisseurs de paiement réels, pas un seul | ✅ Fait |
| White label | Marque, domaines personnalisés, certificats SSL, branding email | — | ✅ Fait |
| Notifications | In-app + email, préférences par utilisateur, index dédié pour le compteur non-lu | — | ✅ Fait |
| API Platform & SDKs | Clés API par organisation (hachées, jamais en clair), scopes, rotation, rate limit/quotas par clé, 4 SDKs officiels | — | ✅ Fait |
| Observabilité | Traces d'agent, audit logs, coût/tokens par requête, diagnostics de retrieval en direct, cache applicatif Redis, index DB mesurés | — | ✅ Fait |
| Eval Lab | Datasets, test cases, runs, métriques (Recall@K, MRR, NDCG, précision), comparaisons, seuils de régression, **analyse d'échecs réelle** (retrieval/génération/hallucination suspectée, depuis des signaux réels, jamais une catégorie fabriquée), UI dédiée | Analyse d'échecs catégorisée avec preuve — la plupart des concurrents s'appuient sur un outil tiers (Langfuse/Langsmith) ou n'ont rien | ✅ Fait |
| Chat UX | Streaming SSE, Markdown + coloration syntaxique, citations cliquables, historique, partage, feedback | — | ✅ Fait |
| Sandbox Environment | Environnement isolé (TTL, données séparées) pour développeurs/tests | Décision explicite de ne PAS livrer une isolation partielle trompeuse — voir Section 12 | ⬜ Tracé, non construit |
| Sécurité | RBAC, chiffrement, audit logs, isolation multi-tenant applicative | SSRF/PII masking/scan antimalware encore absents (voir Section 12) | 🟡 Fait pour l'essentiel, gaps documentés |

---

## 5. Architecture technique

| Couche | Choix |
|---|---|
| API | FastAPI, SQLAlchemy 2.0 async, PostgreSQL (Supabase), Alembic |
| Tâches de fond | Celery + Redis |
| Accès LLM | LiteLLM — une seule abstraction sur Anthropic, OpenAI, Mistral et d'autres, avec fallback automatique de fournisseur |
| Frontend | Next.js, React, TypeScript |
| Stockage objet | Compatible S3 |
| Vision/média | YOLOv8 (inférence locale), CLIP + faiss-cpu |

```
                    frontend/ (Next.js, dashboard multi-sections)
                                   │ REST + streaming SSE
                                   v
        api/ (FastAPI, 756 endpoints — auth, orgs, documents, chat,
        agents, workflows, eval lab, billing, admin, sécurité, MCP)
    ┌───────────────┬──────────────────┬──────────────┬─────────────┐
    v               v                  v              v
PostgreSQL     Celery + Redis      S3 storage    MCP externe
(Supabase)     (ingestion, évals,  (documents,   (client MCP
+ pgvector     workflows, purge)   médias)       de la plateforme)
```

**Flux type (question → réponse citée)** : upload document → chunking →
embeddings → index → requête utilisateur → recherche hybride
(BM25 + vecteurs + RRF) → reranking cross-encoder → passages sélectionnés
→ appel LLM (via LiteLLM) avec le contexte → réponse + citations vers les
passages exacts → trace (latence, tokens, coût) persistée.

---

## 6. Sécurité

- **RBAC** : 52 permissions granulaires réelles (13 ressources × 4
  actions read/write/delete/manage), vérifiées sur 73 routers via des
  dépendances FastAPI dédiées.
- **Chiffrement** : clés API hachées (jamais stockées en clair), secrets
  jamais exposés dans les logs/traces.
- **Audit logs** : table dédiée, indexée sur (utilisateur, horodatage).
- **Isolation multi-tenant** : appliquée au niveau applicatif
  (`organization_id` sur la quasi-totalité des tables), Row-Level
  Security Postgres activée mais actuellement contournée en pratique —
  limite documentée, pas cachée (voir Section 12).
- **Gaps documentés, non résolus** : protection SSRF, détection/masquage
  PII, scan antimalware sur les documents uploadés — absents, tracés au
  ROADMAP, pas fabriqués comme "faits".

---

## 7. Performance

- **Cache applicatif Redis** — `CacheService` générique (`get_or_set`/
  `invalidate`), fail-open (une panne Redis dégrade la latence, ne casse
  jamais une requête), câblé sur la configuration d'organisation
  (lue à chaque traitement de document/recherche/run d'agent).
- **Index DB mesurés, pas ajoutés à l'aveugle** — audité colonne par
  colonne contre le code réel des modèles avant d'ajouter les 5 index
  effectivement manquants (`conversations.organization_id`,
  `workflow_runs.status`, `agent_runs.status`,
  `evaluation_jobs.status`, `notifications(user_id, read_at)`).
- **Discipline explicite** : aucune optimisation n'est déclarée sans
  preuve — quand un benchmark réel n'était pas possible dans
  l'environnement de développement, l'optimisation a été tracée comme
  gap plutôt que déclarée "faite" sans mesure (voir ROADMAP, Étape 13).

---

## 8. Déploiement

- Docker (self-hosted et SaaS), documenté dans
  [`docs/install/SELF_HOSTED.md`](install/SELF_HOSTED.md) et
  [`docs/install/SAAS.md`](install/SAAS.md).
- CI/CD : GitHub Actions (build backend/frontend, tests, `pip-audit`
  sécurité dépendances).
- Monitoring : `/health`, `/health/ready` (dépendances réelles — DB,
  Redis rate-limit, Redis cache — jamais un simple "200 OK" de façade),
  métriques Prometheus.
- Sauvegardes : documentées dans `docs/install/`.

---

## 9. Écosystème

- **SDKs officiels** : Python, JavaScript, React, Vue — un client par
  écosystème frontend/backend courant, pas un seul SDK générique.
- **API Platform** : clés par organisation, scopes, rotation, rate
  limiting et quotas par clé — pas une clé API plate sans granularité.
- **MCP** : la plateforme est à la fois serveur MCP (expose son propre
  registre d'outils à des clients MCP externes) et client MCP
  (enregistre et appelle des serveurs MCP tiers) — les deux rôles étaient
  absents à l'audit concurrentiel du 2026-09-21, les deux sont
  aujourd'hui réels.
- **Intégrations** : Google Drive, Notion, Confluence, OneDrive, GitHub,
  Slack, Teams, Discord, sitemap/crawl web — connecteurs documentaires
  réels. Les connecteurs CRM/ticketing d'entreprise (Salesforce, Zendesk,
  Jira, Linear, HubSpot) restent absents (voir Section 12).

---

## 10. Évaluation et qualité

**Eval Lab** — le module qui distingue le plus ce projet des alternatives
open source à ce niveau de maturité : datasets d'évaluation versionnés,
jeux de questions, runs automatiques, métriques de retrieval (Recall@1/3/
5/10, MRR, NDCG, précision) et de génération (latence, tokens, coût,
taux d'hallucination — calculé, pas déclaratif), comparaisons de runs,
seuils de régression configurables, et une **analyse d'échecs réelle** :
chaque question qui échoue dans un run est désormais persistée (pas
seulement loguée) et catégorisée à la source exacte de l'échec
(retrieval vs génération), combinée à un second signal indépendant déjà
existant dans le pipeline (score de fidélité/hallucination) pour repérer
les réponses qui ont ABOUTI mais de façon non fondée — sans jamais
fabriquer une catégorie qui n'a pas de preuve derrière elle. Une interface
frontend dédiée (`/dashboard/eval`) expose tout cela sans passer par
l'API brute.

---

## 11. Différenciateurs concurrentiels

Comparaison basée sur un audit concurrentiel direct (5 agents de
recherche indépendants, sources citées) contre Dify, RAGFlow, Flowise,
Onyx et AnythingLLM ([`docs/COMPETITIVE_AUDIT_KNOWFLOW.md`](COMPETITIVE_AUDIT_KNOWFLOW.md),
2026-09-21), mis à jour ici avec l'état réel actuel (les gaps MCP,
Markdown chat, workflow UI, OIDC et Eval Lab UI relevés dans cet audit
ont depuis été fermés) :

| Fonctionnalité | Dify | RAGFlow | Flowise | Onyx | AnythingLLM | **Ce projet** |
|---|---|---|---|---|---|---|
| MCP client | ✅ natif | ✅ | ✅ | ✅ natif | ✅ natif | ✅ **fermé depuis l'audit** |
| MCP serveur | ✅ | ✅ | 🔌 communautaire | ✅ | ❌ absent | ✅ **fermé depuis l'audit** |
| SSO OIDC en self-hosted gratuit | 🔒 Enterprise | ❓ | 🔒 Enterprise | 🔒 Enterprise | ❌ | ✅ |
| RBAC granulaire en self-hosted gratuit | 🔒 Enterprise | ✅ (3 couches) | 🔒 Enterprise | 🔒 Enterprise | ❌ | ✅ (52 permissions) |
| Workflow builder visuel | ✅✅ | ✅ | ✅✅ | ❌ | ✅ | ✅ **fermé depuis l'audit** (React Flow) |
| Markdown + coloration code dans le chat | ✅ | ❓ | ✅ | ✅ | ❓ | ✅ **fermé depuis l'audit** |
| Eval Lab avec analyse d'échecs catégorisée | 🟡 (via Langfuse externe) | ❓ | 🔌 externe | ❓ | ❌ | ✅ (interne, réel) |
| Reranking cross-encoder | ✅ | ✅ | ✅ | ⚰️ retiré en 2026 | ❌ | ✅ |
| Billing multi-fournisseur intégré | N/A (pas facturable) | N/A | 🔒 interne Cloud | N/A | N/A | ✅ (Stripe + Paystack) |
| 4 SDKs officiels (Python/JS/React/Vue) | ✅ (Python/Node) | ✅ (Python) | ✅ (TS/Python) | ❌ | ❌ (CLI seul.) | ✅ |

**Gaps honnêtes restants face aux références** (non maquillés, voir
Section 12) : GraphRAG, connecteurs CRM/entreprise, permission sync,
export de conversation, allowlist de domaine widget, SCIM.

---

## 12. Roadmap

**Fait (vérifié, testé)** : auth complète, multi-tenant, ingestion
documentaire multi-format + connecteurs collaboratifs, retrieval hybride
+ reranking, multi-LLM avec fallback, agents autonomes, moteur de
workflows + UI visuelle, MCP client + serveur, Eval Lab + UI + analyse
d'échecs, billing double-fournisseur, marque blanche, notifications, API
Platform + 4 SDKs, cache applicatif + index DB mesurés, monitoring réel.

**Tracé, priorisé, avec plan** (extrait — liste complète dans
[`ROADMAP.md`](../ROADMAP.md), chaque entrée classifiée CORRIGÉE/TRACÉE/
ACCEPTÉE, jamais laissée ambiguë) :

| Priorité | Élément | Statut |
|---|---|---|
| P1 | Bump sécurité `transformers`/`weasyprint` (CVE connues) | Tracé — bloqué par l'accès réseau PyPI de l'environnement de build actuel, pas par une incompatibilité de code |
| P2 | Sandbox Environment (isolation dev/test) | Tracé avec plan en 6 phases — refusé de livrer une isolation partielle trompeuse |
| P2 | Comparaison de runs Eval Lab + agrégats par run | Tracé, endpoint manquant identifié précisément |
| P2 | Branchement des 6 stratégies de chunking codées | Tracé |
| P2 | Techniques de retrieval avancées (HyDE/MMR/multi-query) exposées dans l'API | Tracé — code déjà écrit et testé |
| P2 | Connecteurs CRM/ticketing (Salesforce, Zendesk, Jira...) | Tracé |
| P2 | Agent Builder UI complet | Tracé |
| P3 | Boucle de function-calling agent réelle (au-delà de la sélection textuelle) | Tracé |
| P3 | RLS Postgres réelle (rôle dédié, sans bypass) | Tracé |
| P3 | SSRF/PII/antimalware | Tracé |

---

## 13. Cas d'usage

- **Entreprise** : déployer un assistant RAG interne multi-département
  (une organisation par département/filiale), avec SSO OIDC pour
  l'authentification et RBAC pour limiter qui peut voir quoi.
- **Développeur** : consommer l'API publique et les SDKs pour intégrer la
  recherche/génération dans un produit existant, sans opérer soi-même le
  pipeline RAG.
- **Chercheur/équipe qualité** : utiliser l'Eval Lab pour comparer
  objectivement deux configurations de retrieval ou deux modèles avant un
  déploiement, avec une analyse d'échecs catégorisée plutôt qu'une
  impression qualitative.
- **Intégrateur/revendeur** : partir d'une base self-hosted avec marque
  blanche et facturation déjà réelles, plutôt que de reconstruire ces
  couches pour chaque client.

---

## 14. Modèle économique

Codebase commerciale (licence MIT présente dans le dépôt), dépôt GitHub
public par décision explicite pour ce concours — le jury doit pouvoir
consulter le code directement. La stratégie de licence à long terme
(100% ouvert vs. open core avec des modules commerciaux fermés) est une
décision produit distincte, non tranchée à ce jour — voir
[`ROADMAP.md`](../ROADMAP.md) pour le suivi de cette décision, tracée
plutôt que laissée implicite.

---

## 15. Vision

Le projet vise à combler, un gap vérifié à la fois, l'écart entre ce que
proposent les plateformes RAG/agents open source de référence et ce
qu'une entreprise attend réellement d'un produit self-hosted : pas
seulement un pipeline RAG qui fonctionne, mais l'ensemble de ce qui
l'entoure — auth d'entreprise sans mur de licence Enterprise,
interopérabilité MCP pour ne pas isoler les agents de l'écosystème
d'outils déjà en place, et une preuve mesurable de qualité (Eval Lab)
plutôt qu'une confiance aveugle dans le prompt. La discipline du projet —
auditer avant de coder, ne jamais déclarer "fait" sans preuve, tracer
chaque limite plutôt que la cacher — est elle-même une partie de la
proposition de valeur pour une entreprise qui doit pouvoir auditer ce
qu'elle déploie.

---

## Annexe — Thème IBM Bob 2.0

**Thème principal recommandé** :
> "AI Agents for the Enterprise: A Multi-Tenant RAG SaaS Platform with
> MCP, Eval Lab, and Full Observability"

**Justification** : ce thème combine trois axes que le concours met en
avant (agents autonomes génératifs, IA d'entreprise, innovation) avec
trois capacités réellement construites et vérifiables dans ce dépôt :
l'interopérabilité MCP bidirectionnelle (un gap concurrentiel documenté
et fermé), l'Eval Lab avec analyse d'échecs réelle (preuve de qualité,
pas de promesse), et une architecture multi-tenant avec SSO/RBAC de
niveau entreprise disponible en self-hosted gratuit.

**Sous-thèmes possibles** : MCP for Enterprise · Eval Lab (mesure de la
qualité RAG) · Observability (traces/coût/latence) · Security (RBAC,
isolation multi-tenant) · Multi-tenant SaaS architecture.

### Pitch de soumission (résumé)

1. **Problème** — Construire une IA d'entreprise réelle exige d'assembler
   soi-même des systèmes que peu de plateformes open source réunissent
   (auth d'entreprise, agents, workflows, éval, facturation), le reste
   étant verrouillé derrière des licences Enterprise commerciales.
2. **Solution** — Une plateforme RAG SaaS multi-tenant self-hosted qui
   réunit ces systèmes dans un seul produit, avec SSO/RBAC de niveau
   entreprise disponibles sans licence séparée.
3. **Différenciateurs** — MCP bidirectionnel (client + serveur), Eval Lab
   avec analyse d'échecs catégorisée et prouvée, discipline d'ingénierie
   documentée (chaque limite tracée, jamais cachée).
4. **Impact** — Réduit le coût d'entrée pour une entreprise qui veut
   déployer une IA générative avec les garanties (auth, mesure de
   qualité, observabilité) qu'elle attend déjà de ses autres outils
   internes.
5. **Vision** — Combler méthodiquement, gap vérifié après gap vérifié,
   l'écart entre les plateformes RAG open source existantes et les
   attentes réelles d'une entreprise.

---

**Description du projet RAG SaaS Platform — TERMINÉE — sections : 15/15 — thème IBM Bob 2.0 : IDENTIFIÉ — pitch : PRÊT — honnêteté : OUI — survente : NON**
