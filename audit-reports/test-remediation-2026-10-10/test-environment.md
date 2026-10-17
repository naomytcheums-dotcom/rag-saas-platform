# test-environment.md — environnement de test isolé

Dernière mise à jour : 2026-10-11 07:35. Branche locale `bob/auto-fix-20261010-1555`, HEAD `0c4dfcf` (dépôt propre, vérifié). Rien poussé, fusionné ni déployé.

## État réel après l'incident (vérifié le 2026-10-11)
- **Le lecteur `D:` n'existe plus** (`Get-PSDrive` : seuls `C:` et `Temp`). Perdus : `D:\rag-work` (sorties brutes de tous les passages, scripts d'appoint, `tessdata`, anciens dossiers temporaires). Aucun fichier **versionné** n'en dépend (`Select-String` sur `scripts/` et `tests/` : aucune référence à `D:` ni à `rag-work`).
- Ancienne pile (`rag-pr1-disposable-*`, bases sur l'ancien stockage) : après redémarrage de Docker, ses bases `rag_*` n'existaient plus (seules `postgres` et `isolated_tests`). Je ne l'utilise plus.
- **Pile actuelle, créée par `Start-TestStack.ps1` (conteneurs `rag-test-pg`, `rag-test-redis`, `rag-test-minio`)** : liée à 127.0.0.1 (`25432`, `26379`, `29000`), trois bases migrées à `0137`. Vérifié à 07:12 (`phase3-checks.txt`).
- Chemins temporaires : `TEMP`/`TMP` = `C:\Users\NITROV15\AppData\Local\Temp\rag-tests` ; preuves : `C:\Users\NITROV15\rag-test-evidence\2026-10-11\` (hors dépôt).
- Docker : moteur 29.7.2 répondant ; il s'est **bloqué** pendant le passage complet de la nuit (environ 23 h 50), mes redémarrages n'ont pas aidé, il a fallu un redémarrage manuel de la propriétaire. **Cause non établie.** Constat : 237 à 645 Mo de mémoire libre sur 16 Go pendant ces passages (Opera, Edge, Chrome, VS Code, Claude, VM WSL ; pas de `.wslconfig`). Hypothèse non prouvée : pression mémoire. Conséquence retenue : lots séparés et un seul pytest à la fois.
- Conteneurs que je n'ai pas créés (`trusting_napier`, `inspiring_mcclintock`, `local-minio`) : à un autre agent ou à vous ; **non touchés**.

## Pourquoi un environnement dédié
Le premier passage complet (17:42-20:15) s'est fait avec `DATABASE_URL` factice injoignable **et le `.env` réel chargé dans l'environnement du processus** (la conftest le lit). Cela a deux conséquences honnêtes à retenir :
1. 194 tests d'infrastructure ont été ignorés (aucune base / Redis / S3 / worker).
2. Rien ne prouve que ce premier passage n'a contacté aucun service hébergé (variables S3, e-mail ou autres présentes dans `os.environ`). Je n'ai pas relevé de trafic réseau : **NOT_VERIFIED**. Le nouveau lanceur supprime ce risque : il ne charge jamais `.env`.

## Pile jetable (tout sur 127.0.0.1)
| Composant | Version / image | Usage |
|---|---|---|
| PostgreSQL | 17.11 (`pgvector/pgvector:pg17`) | bases `rag_test_integration` (application, migrée `0137`), `rag_test_roundtrip_scratch` (destructif : RLS, concurrence), `pytest_p0` (preuve SQL tenant) |
| Redis | 7.4.11 (`redis:7-alpine`) | broker (db 0), résultats (1), limiteur (2), cache (3) |
| MinIO | `bitnamilegacy/minio:2025.7.23` | buckets `avatars` (lecture publique), `documents`, `voice` |
| Worker Celery | `celery -A api.tasks.celery_app worker -P solo`, démarré par le lanceur, `inspect ping` obligatoire | tests e2e et purge |
| Tesseract | 5.4.0 (installé hors dépôt) ; **les données `fra` étaient sur `D:` et sont perdues** : à retélécharger (`tessdata_fast`) dans un dossier sous `C:`, voir `resume-session.md` ; Poppler 25.07 | tests OCR |
| Python | 3.13.12, pytest 9.1.1, pytest-asyncio 1.4.0, SQLAlchemy 2.0.52, Celery 5.6.3, litellm 1.99.0 ; `rag-saas-sdk` installé en mode éditable dans le venv local (hors dépôt) | |

Reproductibilité : `scripts/test_env/Start-TestStack.ps1` (crée les conteneurs, les 3 bases, applique Alembic, crée les buckets, écrit `.stack.env` git-ignoré avec un mot de passe aléatoire), `Run-IsolatedSuite.ps1`, `Stop-TestStack.ps1`.

## Garde-fous du lanceur (`scripts/run_isolated_tests.py`)
- Environnement enfant **assaini** : seules les variables de plomberie sont héritées (PATH, TEMP…). `.env` n'est jamais chargé (`RAG_ENV_FILE` pointe vers un fichier inexistant). Aucune clé Stripe / Paystack / LLM / Sentry / e-mail réelle : les secrets internes sont aléatoires, les identifiants OAuth sont les marqueurs déjà utilisés par la CI (`...-never-real`).
- Refus (code 2, message sans valeur) si la base, Redis ou S3 n'est pas local (127.0.0.1 / localhost / ::1), si le nom de base n'est pas marqué (`test`, `disposable`, `scratch`...), si la base destructive porte le même nom que la base applicative, si la base `P0` ne commence pas par `pytest_`. `DATABASE_URL_TRANSACTION` est alignée sur la même base locale.
- Dépendance absente (base, Redis, S3 injoignables ; worker muet) : arrêt (code 3), **pas de skip**.
- Mode strict des skips (`RAG_STRICT_SKIPS=1`, activé par le lanceur) : tout test ignoré dont la raison n'est pas une dépendance **externe** documentée (`tests/external_skip_allowlist.py`) est transformé en **échec**.
- Tests unitaires du lanceur : `tests/test_isolated_test_runner.py` (10 cas, sans base).

## Variables d'environnement de test : effet sur la production
Aucune. Le lanceur ne s'applique qu'au processus enfant de pytest ; `LITELLM_LOCAL_MODEL_COST_MAP=True` est désormais aussi le défaut de `tests/conftest.py` (`setdefault`), sans effet hors tests.
