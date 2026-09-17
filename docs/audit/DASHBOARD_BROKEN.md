# Fonctionnalités cassées — trouvées en testant en direct (2026-09-17)

L'analyse statique (voir `DASHBOARD_INVENTORY.md`) a confirmé que les
30 pages du dashboard appellent toutes des endpoints backend réels et
existants. **Mais le câblage frontend↔backend correct ne garantit pas
que tout fonctionne réellement** — les bugs ci-dessous n'étaient
détectables qu'en testant en direct dans un vrai navigateur contre le
vrai déploiement de production, pas par une simple lecture de code.

## 1. CRITIQUE — Le backend de production servait un dossier incomplet (corrigé)

**Cause** : `Dockerfile.api` ne copiait que `api/`, `alembic.ini` et
`gunicorn.conf.py` dans l'image Docker déployée sur Render — jamais
`locales/` ni `frontend/widget/`, deux dossiers à la racine du dépôt
que le code backend lit à l'exécution (`Path(__file__).resolve().parent.parent.parent`).

**Conséquences réelles, vérifiées en direct sur
`rag-saas-api-sjsm.onrender.com`** :
- `GET /i18n/translations/{langue}` renvoyait `{}` pour **toutes** les
  langues → chaque appel `t(clé)` dans l'app retombait sur la clé brute
  au lieu du texte traduit (ex. le champ de saisie du chat affichait
  littéralement `"ask_placeholder"` au lieu de "Demandez n'importe
  quoi…").
- `GET /widget/script.js`, `/widget/chat.js`, `/widget/styles.css`
  renvoyaient **404** → le widget embarquable, une fonctionnalité
  vitrine du produit, était entièrement cassé en production.

**Corrigé** : `Dockerfile.api` copie maintenant aussi `locales/` et
`frontend/widget/` (commit `e205a23`). Redéployé sur Render, revérifié
en direct : `GET /i18n/translations/en` renvoie maintenant un vrai
dictionnaire de traductions.

## 2. CRITIQUE — Widget Google Translate : gèle la page (désactivé)

**Symptôme signalé** : traduction très lente, ne change parfois pas la
langue, impossible de revenir à la page d'accueil une fois sur une
autre langue.

**Reproduit en direct** :
- La traduction fonctionne réellement mais prend ~8-10 secondes
  (confirmé : `window.google.translate.TranslateElement` s'initialise
  et traduit vraiment le DOM — "Créez un assistant RAG..." devient
  "Crea un asistente RAG...").
- **Mais** naviguer vers une autre page (ou revenir à l'accueil) après
  une traduction **fige complètement l'onglet** — `get_page_text` et
  une capture d'écran expirent toutes les deux (30s+), le renderer ne
  répond plus. Reproduit deux fois de suite, pas un incident isolé.

**Cause** : conflit classique entre les mutations DOM de Google
Translate et la réconciliation React/Next.js — exactement la classe de
bug que ce widget (`next-google-translate-widget`) avait été choisi
pour éviter (remplaçant un composant maison qui avait un bug similaire
de type `removeChild`), mais qui persiste ici sous une autre forme
(gel au lieu d'une erreur visible).

**Corrigé (décision assumée)** : le sélecteur de langue a été retiré
des 3 endroits où il était monté (page d'accueil, `/chat`, layout du
dashboard) — commit `6b57964`. Une page qui se fige est strictement
pire qu'une page non traduite. Le composant
(`components/LanguageSwitcher.tsx`) est laissé en place pour une
réintégration plus prudente plus tard, mais n'est plus utilisé nulle
part actuellement.

**Recommandation pour la suite** : ce projet a déjà son propre système
i18n réel et fonctionnel (`frontend/lib/i18n.tsx` + `GET
/i18n/translations/{lang}`, maintenant réparé par le point 1
ci-dessus) qui ne mute jamais le DOM que React gère — c'est la voie
sûre à privilégier plutôt que de retenter une intégration Google
Translate côté client.

## 3. Lien codé en dur vers localhost (corrigé)

`frontend/app/page.tsx` — le lien "Référence API" du footer pointait
vers `http://localhost:8000/docs` au lieu de la vraie URL du backend
en production. Corrigé pour utiliser `NEXT_PUBLIC_API_URL` (commit `6b57964`).

## 4. Backend de production temporairement indisponible (résolu de lui-même)

Pendant la vérification du déploiement, `rag-saas-api-sjsm.onrender.com`
a répondu `502` de façon consistante pendant plusieurs minutes — cause :
Render traitait encore la file des 3 déploiements déclenchés par les
push successifs de cette session. Revérifié quelques minutes plus tard :
`200 OK`. Pas un bug de code, un délai de traitement normal de
l'hébergeur gratuit.

## Points signalés sans bug confirmé (clarifications)

- **"4 forfaits disparus de la page d'accueil"** — aucune régression :
  ces 4 offres n'ont jamais été affichées ensemble sur une seule page
  publique dans ce projet. Voir la note dans `DASHBOARD_INVENTORY.md`.
- **"Un nom sur /chat mais pas sur l'accueil"** — `/chat` affiche un
  en-tête "RAG SaaS Platform" que la page d'accueil n'a pas dans la
  même position ; incohérence de design mineure, pas un bug fonctionnel.

## Observations mineures (pas des bugs, notées pour référence)

- `frontend/app/dashboard/documents/page.tsx` n'expose que
  upload/liste/suppression, alors que le routeur backend supporte
  aussi l'import URL/GitHub/Google Drive/Notion/Confluence — écart de
  couverture UI, pas un défaut.
- `components/analytics/SegmentSelector.tsx` et `MetricFilters.tsx` :
  code mort (jamais importés).
- `TechnicalMetrics` fait un appel réseau (`getTechnicalErrors`) dont
  le résultat n'est jamais affiché.
- `fine-tuning/jobs/[id]` : `getJobMetrics` (endpoint réel) n'est jamais
  appelé, la page réutilise `job.metrics` déjà chargé.
- `white_label.py` a une ancienne route `GET/PATCH
  /organizations/{org_id}/white-label` (sans "config") plus utilisée
  par aucune page frontend actuelle — laissée en place, sans impact.
- `dashboard/profile/page.tsx` : le chargement des sessions actives
  absorbe silencieusement toute erreur réseau (`catch {}` vide).
- `api/services/security_scan.py`/`api/tasks/security_scan.py`
  attendent l'arborescence complète du dépôt (`parents[2]`) pour les
  scans réels de dépendances/code — non copiée dans l'image Docker
  (contrairement à `locales/`/`frontend/widget/`, corrigés) car ça
  nécessiterait de copier tout le repo pour une fonctionnalité
  secondaire déclenchée par un admin. Gap connu, non corrigé, documenté ici.
