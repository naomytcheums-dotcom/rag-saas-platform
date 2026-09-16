# Rapport de cohérence — audit du 2026-09-16

## 1. Numérotation des Parties (1 à 25)

**Constat initial (qui s'est révélé partiellement faux)** : `docs/CAHIER_DES_CHARGES.md`
saute de `## PARTIE 15` à `## PARTIE 18` dans ses en-têtes — ressemble à du contenu
manquant pour "Partie 16" et "Partie 17".

**Vérification réelle** : le contenu existe intégralement, mais n'est pas sous un en-tête
`## PARTIE 16`/`## PARTIE 17` dédié — il est imbriqué **à l'intérieur** de la section
`## PARTIE 15`, avec des suffixes `(bis)`/`(ter)` :
- **"Partie 16 (bis)"** = modèles de vente (licences self-hosted, support hybride/SLA,
  programme revendeur/partenaire) — `api/models/sales.py`, `api/routers/sales.py`,
  documenté dans `docs/sales/*.md`.
- **"Partie 16 (ter)"** = marketplace de plugins — `api/models/plugins.py`,
  `api/routers/plugins.py`, documenté dans `docs/marketplace/PARTIE_16_TER_MARKETPLACE.md`
  et `docs/plugins/*.md`.
- **"Partie 17"** n'a jamais été assigné à quoi que ce soit — confirmé par recherche
  exhaustive (`grep -rn "Partie 17"` dans `docs/` et `api/` : zéro résultat).

Le document lui-même explique déjà cette collision en prose, au milieu de la section
Partie 15 (le numéro "16" a été réutilisé deux fois par erreur dans des sessions
antérieures pour deux sujets sans rapport, la discipline du projet étant de documenter la
collision plutôt que de tout renuméroter au risque de casser des renvois existants
ailleurs). **Ce n'est donc pas un trou de documentation, mais un vrai problème de
lisibilité** : un lecteur qui ne fait que parcourir les en-têtes `## PARTIE N` (ce qu'un
audit automatisé ferait aussi) conclut à tort qu'il manque du contenu.

**Corrigé** : ajout d'une note de navigation explicite dans la section "Légende" en tête
de document (`docs/CAHIER_DES_CHARGES.md`, juste après le tableau de confiance),
expliquant le saut 15→18 et où trouver le contenu réel de 16(bis)/16(ter) avant même que
le lecteur n'atteigne la section Partie 15.

**Anomalie mineure relevée, corrigée (2026-09-16)** : `docs/sales/PARTNER_PROGRAM.md`
avait pour titre H1 "Partner program (Partie 18)" alors que son propre corps de texte
disait qu'il étend "Partie 16 (bis)". En relisant le fichier en entier : ce n'était pas
une vraie contradiction de fond — le fichier documente bien les deux (l'infrastructure de
base héritée de 16 bis, et l'ajout réel de 18, le grand livre des commissions) — mais le
titre, à lui seul, n'annonçait que 18. **Corrigé** : titre renommé
"Partner program (Partie 16 bis + Partie 18)", avec une note explicative ajoutée en tête
du fichier pour que cette clarification reste visible.

## 2. Suite de tests non référencée en CI (orphelins)

**Faille de processus réelle trouvée** : comparaison programmatique de chaque fichier
`tests/**/test_*.py` réel contre les 4 lots référencés dans `.circleci/config.yml` — 313
fichiers de test au total, **17 jamais exécutés en CI** (aucun test échoué n'aurait donc
pu être détecté sur ces fichiers, quel que soit leur contenu). C'est une récurrence du même
type de problème déjà corrigé lors d'un audit précédent de cette session (34 fichiers
orphelins alors) — de nouveaux fichiers de test ont été ajoutés depuis sans être câblés en
CI.

Sur les 17 :
- **12 fichiers réels, orphelins par omission**, ajoutés au lot 4 de la CI :
  `test_admin_dashboard.py`, `test_admin_organizations.py`, `test_admin_subscriptions.py`,
  `test_admin_users_management.py`, `test_audit_extensions.py`, `test_billing.py`,
  `test_compliance.py`, `test_deployment.py`, `test_encryption.py`,
  `test_observability.py`, `test_rbac_custom.py`, `test_security_scan.py` — 264 tests au
  total, tous verts en local avant ajout (voir `docs/audit/TESTS.md`).
- **5 fichiers légitimement exclus**, désormais documentés en commentaire dans
  `.circleci/config.yml` pour qu'un futur audit ne les signale plus à tort :
  `test_agent.py`, `test_agent_evaluation.py`, `test_injection_test_set.py`,
  `test_integrations.py` (testent le pipeline legacy `src/`, dépendent du paquet privé
  `agentfixture` que cette CI retire délibérément — confirmé : la collecte échoue
  réellement sans lui) et `test_voice.py` (a besoin d'un vrai navigateur avec accès
  microphone, hors périmètre de cette suite backend par son propre docstring).

## 3. Endpoints et modèles de données

Vérifié dans le cadre de l'audit de sécurité (`docs/audit/SECURITY.md`) : les routers
examinés en profondeur (documents, facturation, webhooks, clés API, sources externes,
tâches par lot, retours, approbations humaines, questions, conformité, intégrations)
suivent tous le même motif de scoping par organisation, sans divergence de nommage ou de
structure notable. Aucune incohérence de modèle de données trouvée dans ce périmètre.

**Non vérifié exhaustivement** : cohérence de nommage à travers l'ensemble des ~45 autres
routers non couverts par l'audit sécurité, et cohérence complète frontend ↔ backend
(chaque appel `api.get`/`api.post` du frontend pointant vers un endpoint réellement
existant) — périmètre trop large pour cette passe, à traiter dans un audit dédié si
nécessaire.

## 4. Composants frontend

Le tableau de bord (24 fichiers) a été intégralement traduit en français lors d'une
session précédente du même jour (voir `docs/testing/BUGS_FOUND.md` #6) après avoir constaté
que la coquille et la quasi-totalité des pages restaient en anglais. Aucune nouvelle
incohérence de langue trouvée lors de cet audit sur les pages vérifiées visuellement
depuis (facturation, administration).

## 5. Bug de propagation de logger révélé par l'ajout du fichier orphelin

**Faille réelle, trouvée en deux temps, par l'exécution réelle de la suite combinée** (pas
en isolation — voir `docs/audit/TESTS.md` pour le détail complet) :
`tests/test_admin_dashboard.py::test_system_log_handler_writes_real_rows` échouait de
façon intermittente **uniquement** quand un autre test, plus tôt dans le même processus
pytest, avait déjà déclenché le vrai cycle de vie (`lifespan`) de l'application FastAPI —
ce qui installe un `SystemLogHandler` global sur le logger racine
(`install_system_log_handler`, `api/security/system_log_handler.py`). Le logger utilisé
par le test (`test.system_log_handler`) propage par défaut vers ce logger racine — donc
`logger.warning(message)` écrivait la ligne **deux fois** : une fois via le handler que le
test attache explicitement, une fois via celui installé globalement. **Corrigé** :
`logger.propagate = False` sur ce logger de test, dédié et jamais réutilisé ailleurs — il
n'atteint plus que le handler que le test attache lui-même, quel que soit l'état du reste
du processus. Reproduit et vérifié directement (handler racine installé manuellement dans
le même processus avant d'exécuter la logique du test) avant et après correction.

## Bilan

4 incohérences réelles trouvées et corrigées (numérotation illisible sans note de
navigation ; 12 fichiers de test orphelins ; bug de propagation de logger révélé par
l'exécution réelle de la suite combinée après ajout du fichier orphelin — la preuve la
plus directe que ce fichier valait la peine d'être câblé en CI ; titre contradictoire
dans `PARTNER_PROGRAM.md`). Un 5e problème (un 13e endpoint de pagination non plafonné,
`questions.py`) a été trouvé pendant la re-vérification du 2026-09-16 et corrigé sur le
champ — voir `docs/audit/LIMITS.md`. Le reste du périmètre (endpoints/modèles hors le
sous-ensemble audité pour la sécurité, cohérence frontend↔backend complète) n'a pas pu
être vérifié exhaustivement dans le temps disponible — voir "Non vérifié" ci-dessus.

## Re-vérification (2026-09-16)

Chacun des 6 points de l'audit précédent a été relu dans le code réel et, pour ceux qui
s'y prêtent, retesté en direct :
1. `human_approval.py` : ordre check-puis-mutation confirmé, 36/36 tests verts.
2. Pagination : les 4 endpoints publics confirmés `maximum: 100` via le schéma OpenAPI
   réel. Un 13e endpoint non plafonné trouvé et corrigé en cours de route (voir LIMITS.md).
3. 12 fichiers de test : confirmés présents dans `.circleci/config.yml`, 5 exclusions
   confirmées documentées.
4. Bug de logger : confirmé corrigé (`logger.propagate = False` sur le logger dédié du
   test, pas dans `install_system_log_handler()` lui-même comme le libellé de la demande
   le laissait entendre — la fonction globale reste inchangée à dessein, c'est le logger
   du TEST qui a été rendu étanche). 0 ligne fantôme restante en base réelle, 7/7 tests
   verts.
5. Note de navigation : confirmée présente, mentionne bien les 3 réutilisations de
   "Partie 16".
6. Titre contradictoire : corrigé (voir plus haut).
