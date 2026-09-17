# Inventaire complet du dashboard client (2026-09-17)

Méthode : chaque page (`frontend/app/dashboard/**/page.tsx`, 30 fichiers)
lue intégralement, chaque appel `api.get/post/patch/delete/postFile`
tracé jusqu'à son endpoint réel, chaque endpoint vérifié comme existant
dans le routeur backend correspondant (fichier + ligne cités). Complété
par des tests en direct dans un vrai navigateur pour les points signalés
comme cassés par l'utilisateur (traduction, i18n).

**Résultat global de l'analyse statique : les 30 pages sont
FONCTIONNELLES** — chaque appel frontend correspond à une route
backend réelle et existante, avec les bonnes permissions (`require_org_member`/
`_admin`/`_owner`/`require_superadmin` cohérentes entre frontend et
backend). Aucun appel à un endpoint inexistant trouvé.

Ceci ne veut PAS dire "tout marche parfaitement" — voir
`DASHBOARD_BROKEN.md` pour les vrais bugs trouvés en testant en direct
(pas détectables par une simple vérification de câblage d'endpoints).

## 1. Pages principales

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 1 | Accueil dashboard | `/dashboard` | ✅ | Grille de liens statiques vers les 8 sections |
| 2 | Agents | `/dashboard/agents` | ✅ | Liste, créer, supprimer, activer/pause |
| 3 | Documents | `/dashboard/documents` | ✅ | Liste, upload, suppression (couverture partielle du routeur — voir notes) |
| 4 | Facturation | `/dashboard/billing` | ✅ | 6 onglets : Overview, Plans, Usage, Credits, Invoices, Payment |
| 5 | Profil | `/dashboard/profile` | ✅ | 4 onglets : Info, Security, Preferences, Danger zone |
| 6 | Sécurité | `/dashboard/security` | ✅ | 7 onglets, ~20 endpoints (score, rôles, audit log, chiffrement, conformité, scans, politiques) |

## 2. Réglages (Settings)

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 7 | Widget | `/dashboard/settings/widget` | ✅ | Config nom/message/position/thème/couleurs, upload logo, aperçu live |
| 8 | Clés API | `/dashboard/settings/api-keys` | ✅ | Créer, révoquer, renouveler, voir quota |
| 9 | Webhooks | `/dashboard/settings/webhooks` | ✅ | CRUD, activer/désactiver, tester, historique de livraison |
| 10 | Organisation | `/dashboard/settings/organization` | ✅ | Renommer, inviter/retirer membres |
| 11 | Intégrations | `/dashboard/settings/integrations` | ✅ | Slack/Teams/Discord + connexions Zapier/Make/n8n génériques |
| 12 | Configuration IA (BYOK) | `/dashboard/settings/llm-config` | ✅ | Ajouter/supprimer une clé LLM propre (nouveau, ajouté cette session) |

## 3. Analytique

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 13 | Vue d'ensemble | `/dashboard/analytics` | ✅ | 5 onglets + export CSV/JSON + dashboards personnalisés |
| 14 | Business | `/dashboard/analytics/business` | ✅ | MRR/ARR/ARPU/churn/retention/LTV (superadmin) |
| 15 | Produit | `/dashboard/analytics/product` | ✅ | Usage, adoption, engagement (DAU) |
| 16 | Technique | `/dashboard/analytics/technical` | ✅ | Perf HTTP, usage LLM, usage API (org admin) |

## 4. Tests A/B

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 17 | Liste | `/dashboard/ab-tests` | ✅ | Créer, lister, filtrer |
| 18 | Détail | `/dashboard/ab-tests/[id]` | ✅ | Start/pause/resume/complete, décision auto/manuelle, export, résultats |

## 5. Médias

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 19 | Médiathèque | `/dashboard/media` | ✅ | Upload, liste+filtre, recherche texte, recherche visuelle (CLIP) |
| 20 | Détail média | `/dashboard/media/[id]` | ✅ | Statut/polling, transcript, frames vidéo, lecture |

## 6. Agents autonomes

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 21 | Liste | `/dashboard/autonomous-agents` | ✅ | Créer, lister |
| 22 | Détail | `/dashboard/autonomous-agents/[id]` | ✅ | Run/pause/resume/stop, Plan, Mémoire, Collaboration, Garde-fous |

## 7. Marketplace de plugins

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 23 | Marketplace | `/dashboard/marketplace` | ✅ | 3 onglets (Browse/My plugins/Installed) — 14 actions au total (publier, installer, avis, exécuter, configurer...) |

## 8. Fine-tuning

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 24 | Vue d'ensemble | `/dashboard/fine-tuning` | ✅ | 3 cartes-résumé (datasets/jobs/modèles) |
| 25 | Datasets | `/dashboard/fine-tuning/datasets` | ✅ | Upload, re-validation, suppression |
| 26 | Jobs | `/dashboard/fine-tuning/jobs` | ✅ | Créer, lister avec polling auto |
| 27 | Détail job | `/dashboard/fine-tuning/jobs/[id]` | ✅ | Suivi + annulation |
| 28 | Modèles | `/dashboard/fine-tuning/models` | ✅ | Déployer/retirer, supprimer, évaluer |

## 9. Programme partenaire & marque blanche

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| 29 | Partenaires | `/dashboard/partners` | ✅ | Profil partenaire, lien de parrainage, commissions |
| 30 | Marque blanche | `/dashboard/whitelabel` | ✅ | 12 actions (logo, favicon, couleurs, domaine, email, aperçu, reset) |

## 10. Documentation API

| # | Page | URL | Statut | Fonctionnalités clés |
|---|---|---|---|---|
| — | API Docs | `/dashboard/api-docs` | ✅ | Page de liens statiques vers Swagger UI (`/docs`), pas d'appel API propre |

## Note sur les "4 forfaits" (SaaS / self-hosted / parrainage / marque blanche)

Clarification importante : ces 4 modèles de vente existent bien
(voir `docs/CAHIER_DES_CHARGES.md`, PARTIE 18) mais **jamais sous forme
d'une page publique unique listant les 4 côte à côte** — ils sont
répartis en fonctionnalités distinctes :
- **SaaS** : page Pricing publique (`/` section Tarifs) + `/dashboard/billing`
- **Self-hosted (licence)** : scripts d'installation + validation de
  licence (backend, pas de page dashboard dédiée dans l'inventaire ci-dessus)
- **Parrainage/revendeur** : `/dashboard/partners` (ci-dessus, #29)
- **Marque blanche** : `/dashboard/whitelabel` (ci-dessus, #30)

Rien n'a donc été "supprimé" de la page d'accueil — ces 4 offres
n'ont jamais coexisté sur une seule page publique dans le code de ce
projet. Si tu veux une page publique dédiée les présentant les 4 côte
à côte, c'est une fonctionnalité à construire, pas une régression à corriger.
