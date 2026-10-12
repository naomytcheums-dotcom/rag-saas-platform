# Mise en production : procédure ordonnée (2026-10-11)

Ce document dit dans quel ordre mettre en ligne la branche `bob/auto-fix-20261010-gaps` (PR #25) et pourquoi l'ordre compte. Rien de ce qui suit n'a été exécuté sur la
production : l'assistant n'a pas accès à la base de production et les tests ne doivent jamais la toucher. Les commandes se lancent dans **votre** terminal.

## Pourquoi l'ordre est obligatoire
Le code de la PR #25 lit des colonnes et des tables qui n'existent pas encore en production (par exemple `users.job_title`, table `connector_credentials`).
**Code déployé avant les migrations = erreurs 500 sur toute lecture d'utilisateur, y compris la connexion.** Les migrations, elles, sont additives et compatibles avec
l'ancien code : on peut donc migrer AVANT de déployer sans rien casser.

```
1. sauvegarde  ->  2. répétition à blanc  ->  3. migration  ->  4. variables d'environnement  ->  5. fusion + déploiement  ->  6. vérification
```

## 0. Ce qui est en attente
La production est déclarée en révision 0130 (non vérifiée, `docs/audit/PRODUCTION_MIGRATION_PLAN.md`). La tête du code est 0144. Il faut donc 0131 à 0144 :

| Révision | Effet | Point d'attention |
|---|---|---|
| 0131 | active la sécurité par ligne (RLS) sur 11 tables | les autres tables l'ont déjà depuis 0014 : même comportement, risque faible |
| 0132 | description des espaces de travail | additive |
| 0133 | révisions du corpus BM25 (déclencheurs) | crée des déclencheurs d'instruction sur `documents`, `document_chunks`, `media_assets` qui incrémentent `organizations.bm25_corpus_revision`. **Mesuré en base jetable (2026-10-12)** : deux transactions qui écrivent pour la même organisation s'attendaient (4 s). **Corrigé par 0144**, appliquée dans la même montée : ne pas s'arrêter à 0133 |
| 0134 | **SSO entreprise : propriété du domaine à prouver** | une connexion SSO créée par un client doit **repasser la vérification DNS TXT** ; avant, ses utilisateurs ne passent plus par ce SSO |
| 0135 | propriétaire des appels Twilio | colonne nullable |
| 0136 | crée `notification_templates` | la table n'existait pas (les routes répondaient 500) |
| 0137-0139 | séparation tuning/held-out, SLA et notes d'escalade, correction de feedback | additives |
| 0140-0141 | codes promo, jetons SCIM | nouvelles tables |
| 0142 | `users.job_title` | colonne nullable |
| 0143 | identifiants de connecteurs par organisation | nouvelle table |
| 0144 | révision BM25 incrémentée à la validation, une fois par transaction et organisation | remplace les déclencheurs de 0133 par des déclencheurs de contrainte différés : plus d'attente entre écritures concurrentes d'une même organisation (mesuré : 0 s au lieu de 4 s), surcoût de l'ordre de 0,3 à 0,5 s pour 50 000 lignes écrites d'un coup ; retour arrière testé |

## 1. Sauvegarde (obligatoire)
`scripts/backup.sh` sauvegarde la base **auto-hébergée** de `docker-compose.selfhosted.yml`, PAS la base de production (Supabase). Pour la production, faites un vrai `pg_dump`
distant. Aucune installation : le client PostgreSQL passe par Docker. Depuis le dossier de ce dépôt, dans PowerShell (adresse de connexion DIRECTE de Supabase, port 5432, sans `+asyncpg` ;
ne la collez jamais dans un chat) :
```
New-Item -ItemType Directory -Force backups | Out-Null
$env:PGURL = "postgresql://postgres:<mot-de-passe>@db.<ref>.supabase.co:5432/postgres"
docker run --rm -e PGURL -v "${PWD}\backups:/out" postgres:17 sh -c 'pg_dump "$PGURL" --no-owner --format=custom -f /out/prod_backup.dump'
# (corrigé le 2026-10-12 : l'ancienne ligne contenait un caractère de contrôle à la place de "\b" ; son reste, ignoré, suit) ackups:/out" postgres:17 sh -c 'pg_dump "$PGURL" --no-owner --format=custom -f /out/prod_backup.dump'
Get-Item backups\prod_backup.dump
```
Vérifiez que la taille n'est pas nulle et gardez une copie hors de la machine. (Ne redirigez pas la sortie avec `>` sous PowerShell : cela corrompt un fichier binaire.)
Option complémentaire : la sauvegarde du tableau de bord Supabase (Database > Backups) si votre offre en inclut.

## 2. Répétition à blanc (ne modifie rien)
Dans un terminal PowerShell, avec l'adresse de la base de production dans la variable (ne la collez jamais dans un chat) :
```
$env:DATABASE_URL = "<adresse de la base de production, driver asyncpg>"
python scripts/migrate.py
```
Les migrations en attente s'exécutent dans UNE transaction toujours annulée. Si une migration échoue, rien n'est modifié : relevez le message.

## 3. Migration réelle
```
python scripts/migrate.py --apply
```
Elle refait la répétition puis applique `alembic upgrade head`. Contrôle : `python -m alembic current` doit afficher `0144`.

## 4. Variables à régler sur l'hébergeur (Render) avant le déploiement
| Variable | Valeur | Pourquoi |
|---|---|---|
| `ENCRYPTION_MASTER_KEY` | une clé neuve (voir ci-dessous) | sans elle, les identifiants de connecteurs ne peuvent pas être enregistrés (503) |
| `CONNECTORS_ALLOW_PLATFORM_CREDENTIALS` | `false` (défaut) | chaque organisation utilise ses propres identifiants |
| `*_ENABLED` des connecteurs que vous proposez (`JIRA_ENABLED=true`...) | `true` pour ceux voulus | ne mettez AUCUN jeton serveur : chaque client apporte le sien |
| `GMAIL_*`, `GOOGLE_CALENDAR_*`, `OUTLOOK_*`, `AGENT_SMTP_*`, `GITHUB_API_TOKEN` | **vides** | ces outils d'agents utilisent encore un compte du serveur pour toutes les organisations (D17) |
| `COOKIE_SECURE` | `true` | cookies de session |
| `CREDITS_ALLOW_UNPAID_TOPUP` | `false` | pas de crédits offerts sans paiement |
| `METRICS_AUTH_TOKEN` | un secret long | protège `/metrics` |
| `PROMPT_INJECTION_LLM_CONFIRM` | `true` (défaut) et un fournisseur de modèle configuré | le second avis du détecteur d'injection |

Générer la clé de chiffrement (à conserver dans un coffre : la perdre rend les identifiants stockés illisibles) :
```
python -c "from api.security.encryption import generate_encryption_key; print(generate_encryption_key())"
```

## 5. Fusion et déploiement
1. Attendre que la CI de la PR #25 soit verte (le job `bandit` est non bloquant et reste rouge : 5 alertes HuggingFace connues).
2. Fusionner la PR (jamais de poussée directe sur `main`).
3. Vérifier dans Render si le déploiement est automatique ; sinon le lancer.
4. Le fichier `render.yaml` **à la racine décrit encore l'ancien prototype Streamlit** : si un Blueprint est relié, Render peut le lire. Le bon plan est `deploy/render/render.api.yaml` (API + worker Celery + beat). Décidez avant la fusion si vous remplacez le fichier racine.
5. Il faut un **worker Celery** en production (traitement des documents, purge des comptes, rétention, imports) : sans lui ces fonctions n'ont aucun effet.

## 6. Vérification après déploiement
```
python scripts/post_deploy_smoke.py --api https://<votre-api> --frontend https://<votre-site>
```
puis : inscription d'un compte de test, connexion, envoi d'un document, une question dans le chat, page *Paramètres > Comptes connectés*. Supprimez le compte de test ensuite.

## 7. Si ça se passe mal
- Application en erreur après déploiement : redéployer la version précédente. Les migrations étant additives, l'ancien code fonctionne avec le nouveau schéma.
- Une migration qui échoue en `--apply` : PostgreSQL annule la transaction ; relevez l'erreur, ne modifiez pas une migration existante (créez-en une nouvelle).
- Retour arrière de schéma : `python -m alembic downgrade -1` seulement après avoir lu la migration concernée ; ne jamais supprimer de données sans la sauvegarde de l'étape 1.

## Ce qui reste hors de cette procédure
Paiements réels (CinetPay ou autre : non implémenté, voir D16), remboursements (BILL-016), nom de domaine et certificats, sauvegardes hébergées automatiques, supervision (Sentry, traçage),
et les décisions listées dans `audit-reports/functional-audit-2026-10-10/10-final-status-2026-10-11.md`.
