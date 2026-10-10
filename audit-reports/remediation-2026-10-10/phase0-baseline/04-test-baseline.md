# Phase 0 — Base de référence des tests

Les résultats mesurés (tests ciblés, Alembic, sauvegarde/restauration, suite complète en cours) sont dans `../10-test-results.md`. Échec préexistant connu : `test_detect_user_language_falls_back_to_accept_language_header` (langue `de`), non traité. Test préexistant échouant sur `main` avec Redis réel : `test_partner_registration_is_rate_limited_per_ip` (hors périmètre ici, non vérifié).
