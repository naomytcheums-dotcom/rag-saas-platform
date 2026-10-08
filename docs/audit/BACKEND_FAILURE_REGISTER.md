# Backend failure register - 2026-10-04

## Resultat complet courant

JUnit `mission-backend-confirmation.xml`, lance le 2026-10-04 a
20:51:26.534212 +01:00 avec `.venv\Scripts\python.exe` :
**5,408 collectes, 5,354 passees, 54 ignorees, 0 echec,
23 deselectionnees**, 10,680.761 s. Fin calculee depuis les metadonnees
JUnit : 23:49:27.295212 +01:00. Les skips/deselections restent hors des
tests passes. Deux exceptions du destructeur Qdrant sont survenues au
shutdown apres le resume pytest.

## Historique

- Premier run complet le 2026-10-04 : 5,262 passes, 44 echecs,
  65 ignores, 23 deselections, 2,948.90 s.
- Rejeu cible : 77 passes et 2 echecs en 131.686 s.
- Rejeu cible Resend/RLS : 3 passes en 22.09 s.
- Ces runs precedents restent historiques; le resultat courant est en tete.

## Baseline and counting rules

Premier run staging-profile complet : **5262 passed, 44 failed, 65 skipped,
23 deselected**, 2948.90 seconds. Source: session artifact
`mission-backend-full.xml`. Most existing unit fixtures use SQLite;
PostgreSQL integration fixtures target the allowlisted Supabase staging.
This is not 5371 tests executed exclusively against PostgreSQL.

All 44 failures are inventoried below. BLOCKED_EXTERNAL is a documentation
status, not a pytest skip or a passing result. No existing assertion is
removed or changed. The 65 original skips and 23 deselections remain
outside this failure register and are not certified.

## Corrections

**DB**: synchronous consumers previously replaced `+asyncpg` in a string,
leaving `ssl=require`, which libpq rejects. `api/database_url.py` now returns
a SQLAlchemy URL and translates SSL to `sslmode`, preserving credentials,
query parameters and TLS mode. Shared task engine and system logging use it.
Historical test-side engine construction still performs string replacement:
the replay profile supplies `PGSSLMODE=require` with a query-free DATABASE_URL,
which both drivers support. The allowlisted STAGING_DATABASE_URL retains
`ssl=require`. This is not a change to any historical test.

**UNIT**: email and DeepEval unit modules already mock the HTTP/judge boundary,
but some cases implicitly require configured provider keys. The isolated
replay harness supplies synthetic, nonfunctional keys only while those
two modules' test calls execute, and restores settings afterward. No live
integration receives these keys. These are test-profile corrections, not
proof of live email delivery or paid LLM evaluation.

**RESEND**: two real integration tests require a sandbox Resend credential,
which is not supplied in the isolated staging profile. Production credentials
are not reused. Both remain BLOCKED_EXTERNAL.

**DNS**: three sitemap integrations require resolving `www.sitemaps.org`.
The full run observed `getaddrinfo failed` and downstream failed processing.
No fixture replacement or network mock is substituted for this live evidence.
The targeted retry succeeded for all three live sitemap cases. These are
recovered external failures, not code corrections and not current blockers.

## Individual inventory

Names below are relative to `tests/`. REPLAY_PENDING must not be counted as
corrected until the targeted JUnit confirms it.

| # | Module | Test | Correction/status |
|---|---|---|---|
| 1 | test_admin_dashboard.py | test_system_log_handler_writes_real_rows | DB; replay PASS |
| 2 | test_celery_integration.py | test_purge_task_deletes_only_accounts_past_their_grace_window | DB; replay PASS |
| 3 | test_celery_integration.py | test_purge_task_is_idempotent | DB; replay PASS |
| 4 | test_celery_integration.py | test_blacklist_cleanup_removes_only_expired_entries | DB; replay PASS |
| 5 | test_celery_integration.py | test_blacklist_cleanup_is_idempotent | DB; replay PASS |
| 6 | test_celery_integration.py | test_deletion_reminder_sends_only_for_accounts_due_soon_and_not_already_sent | DB; replay PASS |
| 7 | test_celery_integration.py | test_deletion_reminder_is_not_resent_on_a_second_run | DB; replay PASS |
| 8 | test_celery_integration.py | test_deletion_reminder_leaves_the_account_eligible_for_retry_when_the_email_fails | DB; replay PASS |
| 9 | test_deepeval_validation.py | test_cross_validate_answer_skips_ground_truth_dependent_metrics_without_an_expected_answer | UNIT; replay PASS |
| 10 | test_deepeval_validation.py | test_cross_validate_answer_includes_ground_truth_dependent_metrics_when_available | UNIT; replay PASS |
| 11 | test_email_domains_integration.py | test_resend_domain_lifecycle_against_the_real_api | BLOCKED_EXTERNAL: RESEND |
| 12 | test_email_domains_integration.py | test_send_via_custom_email_domain_is_rejected_by_the_real_resend_api_for_an_unverified_domain | BLOCKED_EXTERNAL: RESEND |
| 13 | test_email_service.py | test_send_appends_the_support_email_footer_to_every_email | UNIT; replay PASS |
| 14 | test_email_service.py | test_send_footer_is_appended_after_the_original_body | UNIT; replay PASS |
| 15 | test_email_service.py | test_send_wraps_an_http_error_from_resend | UNIT; replay PASS |
| 16 | test_email_service.py | test_send_wraps_a_timeout_from_resend | UNIT; replay PASS |
| 17 | test_email_service.py | test_send_wraps_a_network_error_from_resend | UNIT; replay PASS |
| 18 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_password_reset_email-args0] | UNIT; replay PASS |
| 19 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_verification_code_email-args1] | UNIT; replay PASS |
| 20 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_account_restore_email-args2] | UNIT; replay PASS |
| 21 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_two_factor_lockout_recovery_requested_email-args3] | UNIT; replay PASS |
| 22 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_two_factor_lockout_recovery_completed_email-args4] | UNIT; replay PASS |
| 23 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_new_login_notification_email-args5] | UNIT; replay PASS |
| 24 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_two_factor_enabled_email-args6] | UNIT; replay PASS |
| 25 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_two_factor_disabled_email-args7] | UNIT; replay PASS |
| 26 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_recovery_codes_regenerated_email-args8] | UNIT; replay PASS |
| 27 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_recovery_code_used_email-args9] | UNIT; replay PASS |
| 28 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_account_deletion_scheduled_email-args10] | UNIT; replay PASS |
| 29 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_account_deletion_reminder_email-args11] | UNIT; replay PASS |
| 30 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_consent_withdrawn_email-args12] | UNIT; replay PASS |
| 31 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_consent_reactivation_email-args13] | UNIT; replay PASS |
| 32 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_password_set_email-args14] | UNIT; replay PASS |
| 33 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_password_changed_email-args15] | UNIT; replay PASS |
| 34 | test_email_service.py | test_every_send_function_builds_a_valid_request_to_resend[send_rate_limit_alert_email-args16] | UNIT; replay PASS |
| 35 | test_jwt_key_rotation_integration.py | test_rotation_bootstraps_the_first_key_when_none_exists | DB; replay PASS |
| 36 | test_jwt_key_rotation_integration.py | test_rotation_is_a_no_op_when_the_current_key_is_not_yet_due | DB; replay PASS |
| 37 | test_jwt_key_rotation_integration.py | test_rotation_retires_the_old_key_and_activates_a_new_one_when_due | DB; replay PASS |
| 38 | test_jwt_key_rotation_integration.py | test_rotation_is_idempotent_within_the_same_interval | DB; replay PASS |
| 39 | test_jwt_key_rotation_integration.py | test_rotation_sends_the_admin_notification_email_only_when_configured | DB; replay PASS |
| 40 | test_jwt_key_rotation_integration.py | test_rotation_leaves_the_key_creatable_even_when_the_admin_email_fails | DB; replay PASS |
| 41 | test_jwt_key_rotation_integration.py | test_a_retired_key_still_verifies_within_its_retention_window | DB; replay PASS |
| 42 | test_sitemap_extraction_integration.py | test_fetch_sitemap_downloads_and_parses_a_real_external_sitemap | DNS recovered; replay PASS |
| 43 | test_sitemap_integration.py | test_process_sitemap_runs_the_real_fetch_and_parse_against_a_real_sitemap | DNS recovered; replay PASS |
| 44 | test_sitemap_integration.py | test_process_sitemap_applies_a_real_filter_before_the_real_cap | DNS recovered; replay PASS |

Replay artifact: `mission-backend-recheck.xml` in the session evidence folder.
It includes the 44 original failures plus new URL and role-guard regression
cases. The replay is not a replacement for a full post-correction run.

Historical targeted replay: **77 passed, 2 failed, 0 skipped, 0 errors**
across 79 tests in 131.686 seconds. At that point, 42 of the original 44
failures passed and two Resend cases were blocked by missing credentials.
The later complete confirmation run is recorded above.

The old zero-policy assertion was subsequently renamed and changed at the
user's explicit request to require at least 77 staging policies. The test is
now skipped outside the explicitly selected staging-policy profile; see
`POSTGRES_TEST_PLAN.md`. This profile distinction does not remove the
staging policy assertion.
