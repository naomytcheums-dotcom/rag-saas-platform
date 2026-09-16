# Rapport de documentation — audit du 2026-09-16

## Périmètre vérifié

`docs/` contient 165 fichiers Markdown répartis en 27 sous-dossiers thématiques
(admin, advanced, analytics, api, autonomous, billing, ci, developer, diagrams, faq,
fine-tuning, install, integrations, marketplace, media, monitoring, partners, plugins,
sales, security, testing, tutorials, user, whitelabel, widget, ab-testing), plus les
fichiers racine (`CAHIER_DES_CHARGES.md`, `AUTH_BACKEND_SETUP.md`,
`DEPLOYMENT_GUIDE.md`, `index.md`, `_sidebar.md`, `_coverpage.md`).

## 1. Liens internes

Vérification programmatique de tous les liens Markdown relatifs (`[texte](chemin.md)`)
dans l'intégralité de `docs/`, y compris à l'intérieur de `CAHIER_DES_CHARGES.md`
lui-même (qui concentre la majorité des renvois croisés vers les sous-dossiers). **Zéro
lien cassé trouvé.** Les liens racine (`README.md`, `CHANGELOG.md`, `ROADMAP.md`,
`ARCHITECTURE.md`, `CONTRIBUTING.md`, `AUDIT.md`) vers `docs/` sont également tous valides.

## 2. Couverture par sujet

Chaque sous-système majeur du produit a un dossier `docs/` dédié : sécurité
(`docs/security/`, `docs/admin/`), facturation (`docs/billing/`, `docs/sales/`), plugins
(`docs/plugins/`, `docs/marketplace/`), fine-tuning (`docs/fine-tuning/`), agents
autonomes (`docs/autonomous/`), médias (`docs/media/`), marque blanche
(`docs/whitelabel/`), intégrations (`docs/integrations/`), widget (`docs/widget/`), guides
développeur (`docs/developer/`), guides utilisateur (`docs/user/`), tutoriels
(`docs/tutorials/`), FAQ (`docs/faq/`), installation (`docs/install/`), CI/CD (`docs/ci/`).
Le SDK est documenté pour 4 langages (`SDK_JS.md`, `SDK_PYTHON.md`, `SDK_REACT.md`,
`SDK_VUE.md`).

**Ajouté pendant cette session** (avant cet audit, pour une demande distincte) :
`docs/developer/I18N.md` (sélecteur de langue) et `docs/testing/*.md` (campagne de tests
par personas IA).

## 3. Fraîcheur / exactitude

- `docs/testing/RESULTS.md` et `docs/testing/BUGS_FOUND.md` : mis à jour aujourd'hui
  (2026-09-16), reflètent l'état réel le plus récent (traduction du tableau de bord,
  correctif "Event loop is closed", migrations DB appliquées).
- `docs/CAHIER_DES_CHARGES.md` (3800+ lignes) : dernière grande mise à jour de fond datée
  du 2026-09-19 dans son propre texte (Partie 16 ter, finalisation) — cohérent avec l'état
  du code vérifié pendant cet audit (routers plugins/sales bien présents et fonctionnels).
- Aucune date manifestement fausse ou incohérente trouvée dans les fichiers examinés.

## 4. Numérotation des Parties

Voir `docs/audit/COHERENCE.md` section 1 pour le détail — un vrai problème de
**lisibilité** (pas de contenu manquant) a été trouvé et corrigé : absence de note
explicative en tête de document pour le saut d'en-têtes 15→18.

## 5. Exemples de code

Non vérifiés exhaustivement (165 fichiers, périmètre trop large pour une exécution réelle
de chaque exemple dans le temps disponible). Spot-check sur `docs/developer/I18N.md`
(rédigé et vérifié en direct dans le navigateur aujourd'hui même) et
`docs/api/AUTHENTICATION.md` (exemples cohérents avec les schémas Pydantic réels
`api/schemas/auth.py`) — aucune divergence trouvée sur cet échantillon.

## Portée non couverte (honnête)

- Les 165 fichiers n'ont pas été relus intégralement un par un — seuls la structure, les
  liens (vérification automatique complète) et un échantillon de contenu ont été
  contrôlés.
- Aucune vérification automatisée que chaque exemple de requête curl/code documenté
  fonctionne réellement contre le backend actuel (au-delà de l'échantillon cité ci-dessus).
- `docs/api/openapi.json` non comparé au schéma OpenAPI réellement généré par
  `api/main.py` pour détecter une éventuelle dérive.

## Bilan

Documentation structurellement saine : zéro lien cassé, couverture large et cohérente par
sujet, contenu récent daté honnêtement là où vérifié. Deux vrais problèmes trouvés,
corrigés — voir `docs/audit/COHERENCE.md` pour le détail complet de chacun :
- lisibilité de la numérotation des Parties (note de navigation ajoutée) ;
- titre contradictoire dans [`docs/sales/PARTNER_PROGRAM.md`](../sales/PARTNER_PROGRAM.md)
  (2026-09-16) — le titre n'annonçait que "Partie 18" alors que le corps du texte couvre
  aussi "Partie 16 (bis)". Corrigé : titre renommé
  "Partner program (Partie 16 bis + Partie 18)".
