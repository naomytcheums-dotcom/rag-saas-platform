# Audit autonome 06 — résultats de validation

Date : 2026-10-03. Pas de DB production, ni de credentials live réutilisés.

## Environnement isolé

Les sous-processus utilisent `RAG_ENV_FILE=.env.staging`, DATABASE_URL
factice loopback port 1 pour suites locales, aucun transaction pooler
hérité, JWT/HMAC éphémères et aucun provider de production. Les nouveaux
tests staging exigent opt-in et host exact; ne remplacent pas PG par SQLite.

## Résultats finalisés

| Commande / périmètre | Résultat | Portée |
|---|---|---|
| Guard/config/loader + collection staging ciblés | 18 passed, 11 skipped | 11 skips = live PostgreSQL non exécuté |
| Frontend `npm test -- --maxWorkers=1` avant correctif | 112 passed, 13 files | 144.28s |
| Frontend même commande après correctif | 112 passed, 13 files | 118.26s |
| Frontend `npm run type-check` | exit 0 | TypeScript local |
| Frontend `npm run lint` initial | 3 errors, 33 warnings | deux surfaces corrigées |
| Frontend lint rejoué | 0 errors, 32 warnings, exit 0 | warnings non filtrés |
| Ruff nouvelles commandes/tests | All checks passed | pas un PASS de tout `api/` |
| `ruff check api/` initial | 3 253 diagnostics, exit 1 | 2 065 B008, 393 UP007, 276 I001, etc. |
| `pip check` après restauration des imports | No broken requirements found | ne garantit pas que tous les paquets manifest sont installés |
| Pytest complet première tentative | exit 2, six erreurs collection | ChromaDB/googleapiclient/mem0/Streamlit absents |
| Collection après restauration | 5 335 node IDs sélectionnés | cas paramétrés, pas fonctions AST |
| Sous-ensemble média diagnostique | 5 failed, 7 passed | imports ultralytics/faiss absents |

## Run backend complet

Deuxième tentative lancée avec `pytest tests/ -q --tb=short --junitxml=...`
après restauration des quatre packages de collection aux versions
déclarées. Résultat final : **125 failed, 4 993 passed, 208 skipped,
23 deselected en 2 970.15 s (49 min 30 s), exit 1**.
JUnit : 5 326 cas, 125 failures, zéro error. Ce run n'est pas vert.

## Rejeux après diagnostic

| Périmètre | Résultat | Interprétation |
|---|---|---|
| Chiffrement, SSL, domaines, webhooks, chat, SSO, auth et guards | 307 passed, 4 failed, 13 skipped / 324 | Clés éphémères de chiffrement; cookies non-secure uniquement pour clients HTTP locaux. Deux tests Resend live et deux readiness DB/Redis restent rouges. |
| Guard/config/loader, staging, média, Sentry, lineage | 40 passed, 11 skipped / 51 | Dépendances déclarées restaurées. Les 11 skips sont PostgreSQL staging. YOLO/CLIP ont passé leurs exemples réels; Hugging Face offline pour éviter de gros téléchargements implicites. |
| Email unit, appels HTTP mockés | 23 passed / 23 | Clé Resend volontairement invalide uniquement dans ce sous-processus; aucun credential provider réel. |
| Guard/config/loader, BeeAI et Graph RAG | 34 passed / 34 | SDK déclarés restaurés; désactivation prouvée du chargement dotenv tiers. |

Les runs se chevauchent : **ne pas additionner leurs totaux** pour annoncer
un nouveau résultat complet. Parmi les 125 échecs initiaux, 104 ont un
rejeu ciblé passant; 4 restent échouants dans leurs rejeux et 17 n'ont pas
été rejoués avec une cause résolue. Aucun nouveau run complet vert.

Les 17 cas non résolus concernent admin dashboard (2), OAuth live (2),
sitemap réseau (1), DeepEval (3), Docling (2), Presidio (4) et prompt
optimization (3). Un échec de configuration/dépendance n'est pas à lui
seul une preuve de bug métier ou de vulnérabilité.

Les journaux sont conservés dans les artefacts de session :
`autonomous-pytest.log`, `autonomous-pytest.xml`,
`autonomous-pytest-02.log`, `autonomous-pytest-02.xml`,
`autonomous-media-targeted.log`, `autonomous-ruff.json`,
`autonomous-config-retest.log/xml`, `autonomous-final-targeted.log/xml`,
`autonomous-email-unit.log/xml`, `autonomous-framework-retest.log/xml`.
Un XML du deuxième run n'est exploitable comme résultat complet qu'après
fin de processus. Pas de somme artificielle de runs chevauchants.

## Dépendances observées

Rétablies : ChromaDB 1.5.9, google-api-python-client 2.198.0,
mem0ai 2.2.1, Streamlit 1.61.1, déjà déclarées dans les manifests.
Aucun manifest modifié, aucune version majeure arbitrairement augmentée.

Après fin du run complet : ultralytics 8.4.106, faiss-cpu 1.15.0,
sentry-sdk 2.40.0, openlineage-python 1.53.0, beeai-framework 0.1.85 et
lightrag-hku 1.5.7 restaurés. PyTorch 2.13.0+cpu conservé; torchvision
0.28.0 compatible. `pip check` final vert.

Tentatives de restauration protégées par contraintes des versions déjà
installées, refusées sans installer les groupes incompatibles :

- Presidio 2.2.364 exige NumPy < 2.5, environnement NumPy 2.5.2.
- DeepEval 4.2.6 exige Click < 8.4, environnement Click 8.5.0.
- Docling 2.130.0 exige Typer < 0.27, environnement Typer 0.27.2.
- DSPy est importé par les tests mais absent des deux manifests inspectés.

Pas de rétrogradation arbitraire ni suppression de tests. Un environnement
compatible dédié et une résolution reproductible restent à préparer;
ces incompatibilités locales ne sont pas des blocages réseau externes.

## Limites et tests non effectués

- PostgreSQL staging : réseau inaccessible, 11 nouveaux cas non exécutés.
- Restore/rollback live : aucun, pg_dump/psql et DB jetable indisponibles.
- Providers de paiement/LLM/audio : aucune validation live de cette mission.
- Couverture exhaustive des méthodes/actions tenant : non démontrée.
- Aucun test existant supprimé ou réécrit pour transformer un échec en PASS.

## Point de progression — 2026-10-04

Rejeu demandé pour montrer des preuves fraîches : guard staging, sélection
dotenv, configuration, BeeAI et Graph RAG, **34 passed, zéro failure/error/
skip, exit 0 en 178.14 s**. Ruff des huit nouveaux scripts/fichiers de
tests : PASS. Artefacts de session : `progress-20261004.log` et
`progress-20261004.xml`. Aucun provider ni base production utilisés.

Ce point confirme les correctifs/configurations locaux existants; il
n'ajoute pas 34 corrections et ne résout pas les 21 cas encore ouverts.
Les 104 échecs initiaux devenus passants proviennent principalement de
configuration de test et de restauration de dépendances, pas de 104
bugs produit distincts corrigés.

## Lot SDK et runner — 2026-10-04

- Runner staging : import module/script corrigé; deux tests entrypoint
  nouveaux. Guard/config/loader : **22 passed, zéro skip, 23.39 s**.
- Installation conjointe Docling 2.130.0, Presidio 2.2.364, DeepEval
  4.2.6 et DSPy 3.4.0 réussie après dry-run avec pins Transformers
  5.16.1, sentence-transformers 5.7.0 et Torch 2.13.0+cpu conservés.
  NumPy/Click/Typer/Rich/Hugging Face sont ajustés par le résolveur,
  pas installés avec `--no-deps`. **pip check PASS**.
- Déclaration DSPy ajoutée au manifest pour les installations propres.
- Tests DSPy/DeepEval/Docling, extraction documentaire, sentence chunking
  et guard/config/loader : **63 passed, zéro failure/error/skip, 30.793 s**.
  Les huit échecs initiaux DSPy (3), DeepEval (3), Docling (2) ont
  maintenant un rejeu passant. Pas de nouveau run complet vert.
- Détection PII réelle : processus en cours, aucun résultat présumé.
- DNS staging : 11001 confirmé après réparation du runner, pas de SQL.

Artefacts : `dependency-resolution-20261004.json`,
`sdk-retest-20261004.log/xml`, `pii-retest-20261004.log`.
Les incompatibilités locales signalées au 2026-10-03 pour
NumPy/Click/Typer et l'absence de déclaration DSPy sont donc levées
pour les périmètres testés, pas pour toute la plateforme.

Sitemap réseau : **4 passed, zéro skip, 10.957 s** contre le vrai site.
L'échec initial n'est pas reproduit; pas de correctif code inventé.
Total des échecs initiaux ayant désormais un rejeu passant : 113/125.
Il reste 12 cas sans réussite démontrée; ce n'est pas un nouveau résultat
de suite complète.

PII finalisée : **4 passed, zéro failure/error/skip, 831.040 s**,
incluant installation du modèle officiel en_core_web_lg 3.8.0.
Détection et masquage réels, aucun mock du modèle. Pip check final PASS.
Artefacts : `pii-retest-20261004.log/xml`.
Le bilan actualisé est **117/125 échecs initiaux passants au rejeu**;
huit cas restent non résolus (admin 2, OAuth 2, readiness 2, Resend 2).
Pas de nouveau résultat complet vert.

## CI Celery — validation indépendante du run complet actif

Neuf tests nouveaux du bloc shell du workflow : **9 passed en 1.43 s**,
Ruff PASS. Le workflow ne masque plus les exit codes non attendus;
codes 0/124 acceptés pour le burst, autres codes propagés, arrêt forcé
non accepté. Aucun worker ou broker réel lancé. Les tests remplacent
seulement la commande timeout pour exercer les branches du vrai YAML.

Ce fichier a été ajouté après la collection du run complet actif :
les neuf tests ne sont pas inclus dans son futur résumé.

## Backup/restore — lot indépendant

Six tests shell nouveaux avec Docker substitué. Groupe avec CI worker :
**15 passed, zéro skip, 3.90 s**, Ruff PASS. Dump incomplet non publié,
collision refusée, gzip corrompu refusé avant Docker, SQL erreur
propagée avec ON_ERROR_STOP. Pas de DB/bucket/worker contacté.
Ces six tests ont été ajoutés après collection du run complet actif.
