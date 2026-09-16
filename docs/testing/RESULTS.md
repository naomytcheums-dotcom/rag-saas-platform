# Résultats — campagne de tests par personas IA + régression

## 1. Performance de l'inscription (`POST /auth/register`)

| Étape | Temps mesuré | Commentaire |
|---|---|---|
| Avant correction | 22 s à 59 s | `httpx.post()` synchrone bloquant la boucle d'événements + aucun timeout Redis (voir [BUGS_FOUND.md](BUGS_FOUND.md) #3) |
| Après correction (email async + timeouts Redis) | 18,7 s | -62 % vs. le pire cas mesuré avant correction |
| Après migration DB appliquée (mesure finale, 2 essais réels) | 10,7 s et 16,4 s | `curl` chronométré contre le backend réel, requêtes `201 Created` |

**Ce qui reste et pourquoi ce n'est pas un bug de code** : une requête d'inscription
déclenche 7 à 9 allers-retours séquentiels vers la base Postgres. Cette base réelle
(Supabase) est hébergée dans une autre région que cet environnement de développement — la
latence réseau inter-région mesurée en isolation est d'environ 9,6 s cumulés sur ces
allers-retours à elle seule. Ce n'est pas fixable par du code : c'est une caractéristique de
distance réseau propre à cet environnement de développement précis, et un déploiement réel
avec l'API et la base de données co-localisées dans la même région n'aurait vraisemblablement
pas ce coût.

## 2. Suite de régression (pytest)

La suite complète est découpée en 4 lots séquentiels (voir `.circleci/config.yml`) pour
éviter l'OOM d'un unique processus chargeant de nombreux modèles ML.

### Lot 4/4 — celui qui contenait le test intermittent à corriger

```
858 passed, 9 skipped, 0 failed in 2197.19s (0:36:37)
```

Contient notamment :
- `test_geo_adaptive_rate_limit_integration.py::test_spoofing_x_forwarded_for_does_not_grant_the_trusted_ip_bypass`
  — anciennement intermittent ("Event loop is closed"), **passe désormais de façon fiable**
  dans ce contexte combiné (voir [BUGS_FOUND.md](BUGS_FOUND.md) #7).
- `test_documents_integration.py` (29 tests, 26 réussis + 3 ignorés intentionnellement,
  0 échec) — anciennement en échec à cause du désalignement de schéma DB
  (voir [BUGS_FOUND.md](BUGS_FOUND.md) #5), corrigé.
- Les 5 fichiers qui déclenchent les vraies tâches Celery via `asyncio.run()`
  (`test_ssl_certificate_renewal_integration.py`, `test_domain_verification_integration.py`,
  `test_sitemap_integration.py`, `test_github_integration.py`,
  `test_enterprise_sso_integration.py`) — c'est exactement leur cohabitation avec le test
  géo-rate-limit dans le même processus pytest qui déclenchait le bug corrigé.

### Lots 1/4, 2/4, 3/4

Exécutés après le lot 4 pour confirmer qu'aucune régression n'a été introduite ailleurs par
les corrections (client Redis, migrations DB) :

```
Lot 1/4 : 1211 passed, 2 skipped, 0 failed in 1222.31s (0:20:22)
Lot 2/4 : 1077 passed, 0 failed in 337.07s (0:05:37)
Lot 3/4 : 703 passed, 0 failed in 309.51s (0:05:09)
```

Un premier passage du lot 1/4 avait révélé 4 échecs réels dans `tests/test_document_progress.py` :
ces tests patchaient directement l'ancien attribut module-level `_progress_redis`
(`api.security.documents._progress_redis.publish`), qui n'existe plus sous cette forme
après la correction #7 ci-dessous (le client est désormais créé à la demande via
`_get_progress_redis()`). Corrigé en adaptant les 4 tests pour patcher `_get_progress_redis`
elle-même plutôt que l'objet qu'elle retournait auparavant de façon statique — un vrai test
cassé par un vrai changement de code, pas une régression applicative. Vérifié isolément
(9/9 passés) puis dans le lot complet ci-dessus (0 échec).

### Bilan cumulé des 4 lots

```
3849 passed, 11 skipped, 0 failed
```

## 3. Campagne Crawlix (tests par personas IA)

### Contraintes rencontrées (voir [PERSONAS_TESTING.md](PERSONAS_TESTING.md) pour le détail)

- Pas de clé API payante disponible au départ → tentative avec Ollama en local, modèle trop
  faible (1B) pour mener un parcours complet sans planter le parseur de Crawlix.
- Clé Groq gratuite obtenue en cours de session → modèle `openai/gpt-oss-20b`, nettement
  plus fiable, mais soumis à un quota de 8000 tokens/minute et 200 000 tokens/jour — les
  deux ont été atteints au cours de cette campagne, avant que les 6 personas x 12 parcours
  utilisateurs prévus aient pu être couverts intégralement en une seule campagne continue.

### Ce qui a été réellement couvert

- Persona **First-Timer** : parcours d'inscription/connexion, plusieurs itérations avec
  modèles différents (voir rapports dans `crawlix-reports/`). A permis de mettre en évidence
  les bugs UX #1 et #2 (langue anglaise résiduelle, case à cocher non accessible) via
  inspection manuelle déclenchée par les observations de l'agent.
- Personas **Impatient** et **Power User** : lancés en parallèle du First-Timer avec le
  modèle local faible ; sont restés bloqués sur l'écran d'inscription pour la même raison
  technique que First-Timer (modèle local trop faible pour interpréter correctement la page
  après navigation), pas un bug applicatif — confirmé en grepant les logs d'avertissement,
  tous identiques ("stale element reference" après navigation, un artefact de l'outil face à
  un modèle qui hésite, pas un défaut de l'app).
- Personas **Adversarial**, **Non-native-speaker**, **Slow-network** et le reste des 12
  parcours (widget, clés API, facturation, admin, marketplace, analytics, fine-tuning,
  agents autonomes) : **non exécutés aujourd'hui**, faute de quota Groq restant. À reprendre
  avec une clé disposant d'un quota plus large, ou en plusieurs jours pour laisser le
  quota journalier se régénérer.

**Honnêteté sur la portée réelle** : cette campagne a validé le parcours d'inscription et a
directement mené à la découverte et la correction de 2 bugs UX + 4 bugs techniques réels
(dont 2 critiques : performance d'inscription et flakiness CI). Elle n'a pas couvert
l'intégralité des 6 personas x 12 parcours annoncés dans l'objectif initial, pour la raison
de quota documentée ci-dessus, pas par choix.

## 4. Bilan des bugs

Voir [BUGS_FOUND.md](BUGS_FOUND.md) pour le détail complet. Résumé :

| # | Bug | Type | Statut |
|---|---|---|---|
| 1 | Interface partiellement en anglais (4 pages) | UX | Corrigé, vérifié |
| 2 | Case à cocher sans nom accessible | Accessibilité/QA | Corrigé, vérifié |
| 3 | Inscription lente (22-59s) — appels email bloquants + timeouts Redis absents | Technique, critique | Corrigé, vérifié |
| 4 | Redis indisponible en local (Docker/WSL2 cassés sur cette machine) | Infrastructure | Contourné (dev uniquement) |
| 5 | Base Postgres réelle en retard de 5 migrations | Technique, critique | Corrigé, vérifié |
| 6 | Tout le tableau de bord (hors auth) resté en anglais | UX, critique | Corrigé pour les pages principales, vérifié |
| 7 | "Event loop is closed" intermittent en suite combinée | Technique, critique, intermittent | Corrigé, vérifié dans le contexte exact qui le déclenchait |

## 5. Campagne du 2026-09-16 — extension aux 12 parcours utilisateurs

**Objectif demandé** : tester chacun des 12 parcours (upload de document, création d'agent,
conversation, widget, clés API, facturation, admin, marketplace, analytics, fine-tuning,
agents autonomes, médiathèque) un par un avec Crawlix, en utilisant un provider avec plus
de quota si besoin.

**Ce qui a été fait** :
- Compte de test persistant créé (`crawlix.persona@example.com`) pour éviter de payer le
  coût d'inscription à chaque test.
- Premier essai sur le parcours "Upload de document" : Crawlix ne trouvait aucun élément
  correspondant aux libellés attendus. Investigation manuelle (navigateur) a révélé la
  vraie cause : **le tableau de bord entier était resté en anglais** (bug #6 ci-dessus),
  jamais détecté car la campagne précédente n'avait couvert que l'écran de connexion.
- Traduction complète de la coquille du tableau de bord et de 13 pages principales
  (correspondant aux 12 parcours demandés, plus Sécurité/Profil/Organisation/Webhooks).
  Vérifiée par `tsc --noEmit` (0 erreur) et par navigation manuelle réelle (captures
  d'écran : Facturation et Administration confirmées entièrement en français).
- Relance du test Crawlix "Upload de document" après correction : **quota Groq journalier
  épuisé** (199 992 / 200 000 tokens utilisés, fenêtre glissante — pas un simple reset
  minute par minute comme initialement espéré). Aucune clé payante n'a été fournie pour
  prendre le relais.

**Ce qui n'a pas pu être fait aujourd'hui, honnêtement** : aucun des 12 parcours n'a pu
être testé par un agent Crawlix réel après la correction du bug d'interface, faute de
quota. Le bug UX majeur qui aurait bloqué chacun de ces 12 tests (tableau de bord en
anglais) a néanmoins été trouvé et corrigé — la prochaine campagne, avec du quota
disponible, devrait donc se dérouler sans cet obstacle.

**Pour reprendre** : soit attendre la réinitialisation complète du quota Groq gratuit
(fenêtre glissante sur 24h, le compteur affiché était de 199 992/200 000 avant l'arrêt),
soit fournir une clé payante (Groq Dev Tier, OpenAI, ou Anthropic), puis relancer un test
Crawlix par parcours, un par un, comme demandé — voir
[PERSONAS_TESTING.md](PERSONAS_TESTING.md) pour la commande exacte.

