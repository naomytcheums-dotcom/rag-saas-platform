# Plan de correction — dashboard (2026-09-17)

## Déjà corrigé dans cette session

| # | Problème | Correction | Commit |
|---|---|---|---|
| 1 | `locales/` absent de l'image Docker → traductions i18n cassées en prod | `Dockerfile.api` copie `locales/` | `e205a23` |
| 2 | `frontend/widget/` absent de l'image Docker → widget embarquable 404 en prod | `Dockerfile.api` copie `frontend/widget/` | `e205a23` |
| 3 | Widget Google Translate gèle la page à la navigation | Retiré des 3 points de montage | `6b57964` |
| 4 | Lien "Référence API" codé en dur sur `localhost:8000` | Utilise `NEXT_PUBLIC_API_URL` | `6b57964` |

## Reste à faire (par priorité)

### Priorité haute
1. **Rebrancher une vraie traduction, sans le bug de gel** — le système
   i18n interne (`frontend/lib/i18n.tsx`) fonctionne déjà et est
   maintenant réparé côté backend (point 1 ci-dessus). Reste à :
   - Vérifier que chaque composant UI utilise bien `t()` (l'app a été
     migrée progressivement — voir si des libellés hardcodés restent
     hors du périmètre déjà couvert par `t()`).
   - Ajouter un vrai sélecteur de langue basé sur ce système interne
     (changer `language` dans `I18nProvider`, pas Google Translate) sur
     la page d'accueil et le dashboard.
2. **Variables d'environnement Redis manquantes sur Render** — le
   backend de production répond actuellement
   `"rate_limit_redis": "unreachable"` alors que Redis (Upstash) est
   configuré et fonctionnel en local. Il faut ajouter
   `RATE_LIMIT_REDIS_URL`/`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`
   dans les variables d'environnement du service Render (Dashboard →
   Environment), avec les mêmes valeurs que le `.env` local.

### Priorité moyenne
3. Nettoyer le code mort identifié (`SegmentSelector.tsx`,
   `MetricFilters.tsx`, l'ancienne route `white-label` sans `/config`).
4. Ajouter un vrai sélecteur de dataset (au lieu d'un champ UUID à
   saisir à la main) dans `fine-tuning/models` → Évaluer.

### Priorité basse / décision produit à prendre
5. **Scans de sécurité réels** (`security_scan.py`) nécessitent
   l'arborescence complète du dépôt dans l'image Docker — décision à
   prendre : soit accepter une image plus lourde pour cette
   fonctionnalité admin, soit la déplacer vers un job CI séparé qui a
   accès au vrai code source (probablement la meilleure option, pas
   traité ici faute de temps).
6. **Page publique unique listant les 4 modèles de vente** (SaaS,
   self-hosted, parrainage, marque blanche) — n'existe pas aujourd'hui
   (voir clarification dans `DASHBOARD_INVENTORY.md`). À construire si
   c'est effectivement ce que tu veux sur la page d'accueil — dis-le
   moi explicitement et je la construis, plutôt que de deviner la maquette.
7. **Couverture documents** — exposer dans l'UI les imports
   URL/GitHub/Google Drive/Notion/Confluence déjà supportés côté
   backend mais absents de `dashboard/documents/page.tsx`.

## Non traité (hors périmètre de cette passe)

- Test live exhaustif bouton-par-bouton des 30 pages (fait par analyse
  statique complète + tests live ciblés sur les points signalés cassés
  — un test live intégral de chaque action nécessiterait plusieurs
  heures supplémentaires, honnêtement hors de la fenêtre "approche la
  plus rapide" demandée).
