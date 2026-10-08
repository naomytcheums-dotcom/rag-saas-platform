# Tenant Isolation Matrix — Generated from current ORM metadata

Generated: 2026-10-03 from the current working tree. This is a **static discovery aid**, not proof of deployed schema, runtime authorization, or policy behavior. ORM metadata contains 177 tables. It does not include a live DB catalog. An `organization_id` / FK path is only a candidate tenant path; endpoint checks still require code/test review.

Classification is conservative: `DIRECT_TENANT` means a direct `organization_id`; `INDIRECT_TENANT` means an FK-parent path to a direct-tenant table; `USER_SCOPED` means a user path; `GLOBAL` is limited to explicit catalog/config candidates; `SYSTEM` is a security/system-name candidate; unresolved tables are `UNKNOWN`. Router/task file counts only indicate symbol references, not validated reads, writes or authorization. The RLS column is a coarse local-source heuristic: a source mention is not proof that a migration reaches the target table or that it ran.

| Classification | Tables |
|---|---:|
| `DIRECT_TENANT` | 79 |
| `INDIRECT_TENANT` | 63 |
| `USER_SCOPED` | 24 |
| `GLOBAL` (candidate) | 3 |
| `SYSTEM` (candidate) | 6 |
| `UNKNOWN` | 2 |

| Table | PK | Org col | Workspace col | User col | Owner col | Agent col | Document col | Conversation col | Workflow col | Evaluation col | Candidate tenant path | RLS source | Router refs (files) | Task refs (files) | Class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ab_test_assignments | id | - | - | - | - | - | - | - | - | - | ab_test_assignments -> ab_tests.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| ab_test_results | id | - | - | - | - | - | - | - | - | - | ab_test_results -> ab_tests.organization_id | YES (source migration) | 1: ab_tests.py | 1: ab_tests.py | INDIRECT_TENANT |
| ab_tests | id | organization_id | - | - | - | - | - | - | - | - | ab_tests.organization_id | YES (source migration) | 2: ab_tests.py, rag_control_plane.py | 2: ab_tests.py, celery_app.py | DIRECT_TENANT |
| account_restore_tokens | id | - | - | user_id | - | - | - | - | - | - | account_restore_tokens -> users | YES (source migration) | 1: account.py | 0:  | USER_SCOPED |
| acme_accounts | id | - | - | - | - | - | - | - | - | - | deployment-wide ACME credential/configuration | YES (source migration) | 0:  | 0:  | SYSTEM |
| agent_api_keys | id | - | - | - | - | agent_id | - | - | - | - | agent_api_keys -> agents.organization_id | YES (source migration) | 1: agent_api_keys.py | 0:  | INDIRECT_TENANT |
| agent_collaborations | id | - | - | - | - | initiator_agent_id, collaborator_agent_id | - | - | - | - | agent_collaborations -> autonomous_agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| agent_long_term_memory_items | id | - | - | user_id | - | agent_id | - | - | - | - | agent_long_term_memory_items -> agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| agent_memories | id | - | - | - | - | agent_id | - | - | - | - | agent_memories -> autonomous_agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| agent_memory_items | id | - | - | - | - | - | - | - | - | - | agent_memory_items -> agent_sessions -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| agent_plans | id | - | - | - | - | agent_id | - | - | - | - | agent_plans -> autonomous_agents.organization_id | YES (source migration) | 0:  | 1: autonomous_agents.py | INDIRECT_TENANT |
| agent_runs | id | organization_id | - | - | - | agent_id | - | - | - | - | agent_runs.organization_id | YES (source migration) | 1: agent_traces.py | 0:  | DIRECT_TENANT |
| agent_sessions | id | - | - | user_id | - | agent_id | - | - | - | - | agent_sessions -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| agent_steps | id | - | - | - | - | - | - | - | - | - | agent_steps -> agent_plans -> autonomous_agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| agent_traces | id | - | - | - | - | - | - | - | - | - | agent_traces -> agent_runs.organization_id | YES (source migration) | 1: agent_traces.py | 0:  | INDIRECT_TENANT |
| agents | id | organization_id | workspace_id | - | - | - | - | - | - | - | agents.organization_id | YES (source migration) | 17: agents.py, agent_api_keys.py, agent_factory.py | 3: autonomous_agents.py, celery_app.py, sales.py | DIRECT_TENANT |
| airbyte_connections | id | organization_id | - | - | - | - | - | - | - | - | airbyte_connections.organization_id | YES (source migration) | 1: integrations_universal.py | 1: integrations.py | DIRECT_TENANT |
| alert_channels | id | organization_id | - | - | - | - | - | - | - | - | alert_channels.organization_id | YES (source migration) | 1: quality_alerts.py | 1: alerting.py | DIRECT_TENANT |
| alert_history | id | - | - | - | - | - | - | - | - | - | alert_history -> alert_rules.organization_id | YES (source migration) | 0:  | 1: alerting.py | INDIRECT_TENANT |
| alert_rules | id | organization_id | - | - | - | - | - | - | - | - | alert_rules.organization_id | YES (source migration) | 1: quality_alerts.py | 1: alerting.py | DIRECT_TENANT |
| analytics_aggregates | id | organization_id | - | - | - | - | - | - | - | - | analytics_aggregates.organization_id | YES (source migration) | 0:  | 1: analytics.py | DIRECT_TENANT |
| analytics_dashboards | id | organization_id | - | - | - | - | - | - | - | - | analytics_dashboards.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| analytics_events | id | organization_id | - | user_id | - | - | - | - | - | - | analytics_events.organization_id | YES (source migration) | 0:  | 1: analytics.py | DIRECT_TENANT |
| audit_logs | id | organization_id | - | user_id | - | - | - | - | - | - | audit_logs.organization_id | YES (source migration) | 3: admin_users_management.py, analytics.py, audit.py | 2: analytics.py, audit.py | DIRECT_TENANT |
| audit_logs_archive | id | organization_id | - | user_id | - | - | - | - | - | - | audit_logs_archive.organization_id | YES (source migration) | 0:  | 1: audit.py | DIRECT_TENANT |
| autonomous_agents | id | organization_id | - | - | - | - | - | - | - | - | autonomous_agents.organization_id | YES (source migration) | 1: autonomous_agents.py | 4: autonomous_agents.py, celery_app.py, fine_tuning.py | DIRECT_TENANT |
| batch_job_items | id | - | - | - | - | - | - | - | - | - | batch_job_items -> batch_jobs.organization_id | YES (source migration) | 1: batch_jobs.py | 0:  | INDIRECT_TENANT |
| batch_jobs | id | organization_id | - | - | - | - | - | - | - | - | batch_jobs.organization_id | YES (source migration) | 1: batch_jobs.py | 3: batch_jobs.py, celery_app.py, evaluation_jobs.py | DIRECT_TENANT |
| benchmark_versions | id | - | - | - | - | - | - | - | - | - | benchmark_versions -> evaluation_datasets.organization_id | YES (source migration) | 1: benchmark_versions.py | 0:  | INDIRECT_TENANT |
| call_records | id | - | - | - | - | agent_id | - | conversation_id | - | - | call_records -> agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| citations | id | - | - | - | - | - | document_id | - | - | - | citations -> document_chunks.organization_id | YES (source migration) | 2: chat_stream.py, citations.py | 0:  | INDIRECT_TENANT |
| comparison_jobs | id | - | - | - | - | - | - | - | - | - | comparison_jobs -> evaluation_datasets.organization_id | YES (source migration) | 1: comparison_jobs.py | 2: celery_app.py, comparison_jobs.py | INDIRECT_TENANT |
| consent_reactivation_tokens | id | - | - | user_id | - | - | - | - | - | - | consent_reactivation_tokens -> users | YES (source migration) | 1: account.py | 0:  | USER_SCOPED |
| consent_records | id | - | - | user_id | - | - | - | - | - | - | consent_records -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| conversation_messages | id | - | - | - | - | - | - | conversation_id | - | - | conversation_messages -> conversations.organization_id | YES (source migration) | 2: feedback.py, questions.py | 0:  | INDIRECT_TENANT |
| conversation_shares | id | - | - | - | - | - | - | conversation_id | - | - | conversation_shares -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| conversations | id | organization_id | - | user_id | - | agent_id | - | - | - | - | conversations.organization_id | YES (source migration) | 9: admin_dashboard.py, audit.py, conversations.py | 2: celery_app.py, conversation_cleanup.py | DIRECT_TENANT |
| credit_transactions | id | organization_id | - | user_id | - | - | - | - | - | - | credit_transactions.organization_id | YES (source migration) | 0:  | 1: billing.py | DIRECT_TENANT |
| credits | id | organization_id | - | - | - | - | - | - | - | - | credits.organization_id | YES (source migration) | 5: a2a.py, agent_factory.py, billing.py | 2: billing.py, celery_app.py | DIRECT_TENANT |
| custom_domains | id | organization_id | - | - | - | - | - | - | - | - | custom_domains.organization_id | YES (source migration) | 4: custom_domains.py, email_domains.py, mcp_servers.py | 1: domain_verification.py | DIRECT_TENANT |
| custom_roles | id | organization_id | - | - | - | - | - | - | - | - | custom_roles.organization_id | YES (source migration) | 2: search.py, webhooks.py | 0:  | DIRECT_TENANT |
| custom_tools | id | organization_id | - | - | - | - | - | - | - | - | custom_tools.organization_id | YES (source migration) | 2: custom_tools.py, mcp_server.py | 0:  | DIRECT_TENANT |
| data_breaches | id | organization_id | - | - | - | - | - | - | - | - | data_breaches.organization_id | YES (source migration) | 0:  | 1: compliance.py | DIRECT_TENANT |
| data_requests | id | - | - | user_id | - | - | - | - | - | - | data_requests -> users | YES (source migration) | 1: compliance.py | 1: compliance.py | USER_SCOPED |
| deployment_evaluations | id | - | - | - | - | agent_id | - | - | - | - | deployment_evaluations -> agents.organization_id | YES (source migration) | 1: deployment_evaluations.py | 2: celery_app.py, deployment_evaluations.py | INDIRECT_TENANT |
| discord_integrations | id | organization_id | - | - | - | agent_id | - | - | - | - | discord_integrations.organization_id | YES (source migration) | 1: chat_integrations_discord.py | 0:  | DIRECT_TENANT |
| discord_messages | id | - | - | discord_user_id | - | - | - | conversation_id | - | - | discord_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| document_audit_logs | id | - | - | user_id | - | - | document_id | - | - | - | document_audit_logs -> documents.organization_id | YES (source migration) | 0:  | 1: reindex.py | INDIRECT_TENANT |
| document_chunks | id | organization_id | - | - | - | - | document_id | - | - | - | document_chunks.organization_id | YES (source migration) | 0:  | 1: media.py | DIRECT_TENANT |
| document_entities | id | - | - | - | - | - | document_id | - | - | - | document_entities -> documents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| document_images | id | - | - | - | - | - | document_id | - | - | - | document_images -> documents.organization_id | YES (source migration) | 1: documents.py | 0:  | INDIRECT_TENANT |
| document_keywords | id | - | - | - | - | - | document_id | - | - | - | document_keywords -> documents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| document_tag_assignments | id | - | - | - | - | - | document_id | - | - | - | document_tag_assignments -> document_tags.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| document_tags | id | organization_id | - | - | - | - | - | - | - | - | document_tags.organization_id | YES (source migration) | 1: documents.py | 0:  | DIRECT_TENANT |
| document_versions | id | - | - | - | - | - | document_id | - | - | - | document_versions -> documents.organization_id | YES (source migration) | 1: documents.py | 0:  | INDIRECT_TENANT |
| documents | id | organization_id | workspace_id | - | - | - | - | - | - | - | documents.organization_id | YES (source migration) | 19: admin_dashboard.py, audit.py, batch_jobs.py | 19: autonomous_agents.py, celery_app.py, confluence_import.py | DIRECT_TENANT |
| email_verification_tokens | id | - | - | user_id | - | - | - | - | - | - | email_verification_tokens -> users | YES (source migration) | 1: verify.py | 0:  | USER_SCOPED |
| encryption_audit | id | - | - | - | - | - | - | - | - | - | encryption_audit -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| encryption_key_records | id | - | - | - | - | - | - | - | - | - | deployment-wide key-rotation metadata | YES (source migration) | 0:  | 0:  | SYSTEM |
| enterprise_sso_accounts | id | - | - | user_id | - | - | - | - | - | - | enterprise_sso_accounts -> users | YES (source migration) | 1: enterprise_sso.py | 0:  | USER_SCOPED |
| enterprise_sso_connections | id | - | - | - | - | - | - | - | - | - | enterprise_sso_connections -> users | YES (source migration) | 1: enterprise_sso.py | 0:  | USER_SCOPED |
| escalations | id | organization_id | - | - | - | - | - | - | - | - | escalations.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| evaluation_datasets | id | organization_id | - | - | - | - | - | - | - | - | evaluation_datasets.organization_id | YES (source migration) | 9: benchmark_versions.py, comparison_jobs.py, evaluation_datasets.py | 0:  | DIRECT_TENANT |
| evaluation_failures | id | - | - | - | - | - | - | - | - | - | evaluation_failures -> evaluation_jobs -> agents.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| evaluation_jobs | id | - | - | - | - | agent_id | - | - | - | - | evaluation_jobs -> agents.organization_id | YES (source migration) | 2: evaluation_jobs.py, rag_control_plane.py | 3: celery_app.py, comparison_jobs.py, evaluation_jobs.py | INDIRECT_TENANT |
| evaluation_questions | id | - | - | - | - | - | - | - | - | - | evaluation_questions -> evaluation_datasets.organization_id | YES (source migration) | 3: evaluation_datasets.py, evaluation_results.py, manual_evaluations.py | 0:  | INDIRECT_TENANT |
| evaluation_results | id | - | - | - | - | agent_id | - | - | - | - | evaluation_results -> agents.organization_id | YES (source migration) | 1: evaluation_results.py | 0:  | INDIRECT_TENANT |
| external_sources | id | organization_id | workspace_id | - | - | - | - | - | - | - | external_sources.organization_id | YES (source migration) | 3: batch_jobs.py, external_sources.py, reindex_schedules.py | 1: external_source_sync.py | DIRECT_TENANT |
| fine_tuned_models | id | organization_id | - | - | - | - | - | - | - | - | fine_tuned_models.organization_id | YES (source migration) | 1: fine_tuning.py | 0:  | DIRECT_TENANT |
| fine_tuning_datasets | id | organization_id | - | - | - | - | - | - | - | - | fine_tuning_datasets.organization_id | YES (source migration) | 1: fine_tuning.py | 0:  | DIRECT_TENANT |
| fine_tuning_evaluations | id | - | - | - | - | - | - | - | - | - | fine_tuning_evaluations -> evaluation_datasets.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| fine_tuning_jobs | id | organization_id | - | - | - | - | - | - | - | - | fine_tuning_jobs.organization_id | YES (source migration) | 1: fine_tuning.py | 1: fine_tuning.py | DIRECT_TENANT |
| flight_recordings | id | organization_id | - | - | - | - | - | - | - | - | flight_recordings.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| follow_up_questions | id | - | - | - | - | - | - | - | - | - | follow_up_questions -> conversation_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| human_approvals | id | organization_id | - | - | - | - | - | - | - | - | human_approvals.organization_id | YES (source migration) | 1: human_approval.py | 0:  | DIRECT_TENANT |
| incidents | id | organization_id | - | - | - | - | - | - | - | - | incidents.organization_id | YES (source migration) | 1: observability.py | 0:  | DIRECT_TENANT |
| integration_connections | id | organization_id | - | - | - | - | - | - | - | - | integration_connections.organization_id | YES (source migration) | 0:  | 1: integrations.py | DIRECT_TENANT |
| integration_logs | id | - | - | - | - | - | - | - | - | - | integration_logs -> integration_connections.organization_id | YES (source migration) | 0:  | 1: integrations.py | INDIRECT_TENANT |
| integration_mappings | id | - | - | - | - | - | - | - | - | - | integration_mappings -> integration_connections.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| invitations | id | organization_id | - | - | - | - | - | - | - | - | invitations.organization_id | YES (source migration) | 2: invitations.py, organization_members.py | 0:  | DIRECT_TENANT |
| invoice_lines | id | - | - | - | - | - | - | - | - | - | invoice_lines -> invoices.organization_id | YES (source migration) | 0:  | 1: billing.py | INDIRECT_TENANT |
| invoices | id | organization_id | - | - | - | - | - | - | - | - | invoices.organization_id | YES (source migration) | 1: billing.py | 2: billing.py, celery_app.py | DIRECT_TENANT |
| jwt_signing_keys | id | - | - | - | - | - | - | - | - | - | system/security table; ownership/tenant use needs review | YES (source migration) | 1: audit.py | 1: jwt_key_rotation.py | SYSTEM |
| key_rotation_history | id | - | - | - | - | - | - | - | - | - | key_rotation_history -> organization_api_keys.organization_id | YES (source migration) | 0:  | 1: api_key_maintenance.py | INDIRECT_TENANT |
| licenses | id | organization_id | - | - | - | - | - | - | - | - | licenses.organization_id | YES (source migration) | 0:  | 2: celery_app.py, sales.py | DIRECT_TENANT |
| llm_fallbacks | provider | - | - | - | - | - | - | - | - | - | llm_fallbacks -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| manual_evaluations | id | - | - | - | - | agent_id | - | - | - | - | manual_evaluations -> agents.organization_id | YES (source migration) | 1: manual_evaluations.py | 0:  | INDIRECT_TENANT |
| mcp_server_configs | id | organization_id | - | - | - | - | - | - | - | - | mcp_server_configs.organization_id | YES (source migration) | 1: mcp_servers.py | 0:  | DIRECT_TENANT |
| mcp_tool_cache | id | - | - | - | - | - | - | - | - | - | mcp_tool_cache -> mcp_server_configs.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| media_assets | id | organization_id | - | - | - | - | - | - | - | - | media_assets.organization_id | YES (source migration) | 1: media.py | 1: media.py | DIRECT_TENANT |
| media_frames | id | - | - | - | - | - | - | - | - | - | media_frames -> media_assets.organization_id | YES (source migration) | 0:  | 1: media.py | INDIRECT_TENANT |
| media_transcripts | id | - | - | - | - | - | - | - | - | - | media_transcripts -> media_assets.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| message_edit_history | id | - | - | - | - | - | - | - | - | - | message_edit_history -> conversation_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| message_feedback | id | - | - | user_id | - | - | - | - | - | - | message_feedback -> conversation_messages -> conversations.organization_id | YES (source migration) | 1: feedback.py | 0:  | INDIRECT_TENANT |
| notification_preferences | id | organization_id | - | user_id | - | - | - | - | - | - | notification_preferences.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| notification_templates | id | organization_id | - | - | - | - | - | - | - | - | notification_templates.organization_id | NOT FOUND (static source) | 1: notification_templates.py | 0:  | DIRECT_TENANT |
| notifications | id | organization_id | - | user_id | - | - | - | - | - | - | notifications.organization_id | YES (source migration) | 7: a2a.py, account.py, invitations.py | 4: celery_app.py, document_processing.py, notifications.py | DIRECT_TENANT |
| oauth_accounts | id | - | - | user_id | - | - | - | - | - | - | oauth_accounts -> users | YES (source migration) | 1: oauth.py | 1: account_purge.py | USER_SCOPED |
| organization_api_keys | id | organization_id | - | - | - | - | - | - | - | - | organization_api_keys.organization_id | YES (source migration) | 3: a2a.py, mcp_server.py, public_api.py | 1: api_key_maintenance.py | DIRECT_TENANT |
| organization_branding | id | organization_id | - | - | - | - | - | - | - | - | organization_branding.organization_id | YES (source migration) | 2: organization_branding.py, white_label.py | 0:  | DIRECT_TENANT |
| organization_llm_configs | id | organization_id | - | - | - | - | - | - | - | - | organization_llm_configs.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| organization_members | id | organization_id | - | user_id | - | - | - | - | - | - | organization_members.organization_id | YES (source migration) | 68: ab_tests.py, agents.py, agent_api_keys.py | 6: account_purge.py, analytics.py, billing.py | DIRECT_TENANT |
| organization_quotas | id | organization_id | - | - | - | - | - | - | - | - | organization_quotas.organization_id | YES (source migration) | 1: quotas.py | 0:  | DIRECT_TENANT |
| organization_settings | id | organization_id | - | - | - | - | - | - | - | - | organization_settings.organization_id | YES (source migration) | 8: a2a.py, agent_factory.py, chat_stream.py | 0:  | DIRECT_TENANT |
| organization_usage | id | organization_id | - | - | - | - | - | - | - | - | organization_usage.organization_id | YES (source migration) | 2: usage.py, workspaces.py | 0:  | DIRECT_TENANT |
| organization_usage_details | id | organization_id | - | user_id | - | - | - | - | - | - | organization_usage_details.organization_id | YES (source migration) | 1: usage.py | 0:  | DIRECT_TENANT |
| organizations | id | - | - | - | - | - | - | - | - | - | tenant root/control-plane entity | YES (source migration) | 64: a2a.py, ab_tests.py, admin_dashboard.py | 5: account_purge.py, analytics.py, plugins.py | SYSTEM |
| partner_commissions | id | - | - | - | - | - | - | - | - | - | partner_commissions -> resellers.organization_id | YES (source migration) | 0:  | 1: sales.py | INDIRECT_TENANT |
| password_history | id | - | - | user_id | - | - | - | - | - | - | password_history -> users | YES (source migration) | 4: account.py, auth.py, invitations.py | 0:  | USER_SCOPED |
| password_reset_tokens | id | - | - | user_id | - | - | - | - | - | - | password_reset_tokens -> users | YES (source migration) | 1: password.py | 0:  | USER_SCOPED |
| payment_customers | id | organization_id | - | - | - | - | - | - | - | - | payment_customers.organization_id | NOT FOUND (static source) | 1: billing.py | 0:  | DIRECT_TENANT |
| payment_events | provider, id | - | - | - | - | - | - | - | - | - | provider webhook idempotency ledger; payload must remain non-sensitive | NOT FOUND (static source) | 0:  | 0:  | SYSTEM |
| permission_groups | id | - | - | - | - | - | - | - | - | - | global catalog/config | YES (source migration) | 0:  | 0:  | GLOBAL |
| permissions | id | - | - | - | - | - | - | - | - | - | global catalog/config | YES (source migration) | 55: ab_tests.py, agents.py, agent_factory.py | 0:  | GLOBAL |
| plans | id | - | - | - | - | - | - | - | - | - | global catalog/config | YES (source migration) | 3: admin_subscriptions.py, autonomous_agents.py, billing.py | 2: billing.py, sales.py | GLOBAL |
| plugin_executions | id | organization_id | - | - | - | - | - | - | - | - | plugin_executions.organization_id | YES (source migration) | 0:  | 1: plugins.py | DIRECT_TENANT |
| plugin_installations | id | organization_id | - | - | - | - | - | - | - | - | plugin_installations.organization_id | YES (source migration) | 0:  | 1: plugins.py | DIRECT_TENANT |
| plugin_reviews | id | organization_id | - | user_id | - | - | - | - | - | - | plugin_reviews.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| plugin_versions | id | - | - | - | - | - | - | - | - | - | plugin_versions -> plugins.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| plugins | id | organization_id | - | - | - | - | - | - | - | - | plugins.organization_id | YES (source migration) | 2: conversations.py, plugins.py | 2: celery_app.py, plugins.py | DIRECT_TENANT |
| question_set_items | id | - | - | - | - | - | - | - | - | - | question_set_items -> evaluation_questions -> evaluation_datasets.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| question_sets | id | - | - | - | - | - | - | - | - | - | question_sets -> evaluation_datasets.organization_id | YES (source migration) | 2: evaluation_comparisons.py, question_sets.py | 0:  | INDIRECT_TENANT |
| rag_experiments | id | organization_id | - | - | - | - | - | - | - | - | rag_experiments.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| regeneration_history | id | - | - | - | - | - | - | - | - | - | regeneration_history -> conversation_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| regression_detections | id | - | - | - | - | - | - | - | - | - | regression_detections -> evaluation_jobs -> agents.organization_id | YES (source migration) | 1: regression_detection.py | 0:  | INDIRECT_TENANT |
| regression_thresholds | id | organization_id | - | - | - | - | - | - | - | - | regression_thresholds.organization_id | YES (source migration) | 1: regression_thresholds.py | 0:  | DIRECT_TENANT |
| reindex_schedules | id | organization_id | - | - | - | - | - | - | - | - | reindex_schedules.organization_id | YES (source migration) | 1: reindex_schedules.py | 1: reindex_schedule.py | DIRECT_TENANT |
| resellers | id | organization_id | - | - | - | - | - | - | - | - | resellers.organization_id | YES (source migration) | 1: sales.py | 1: sales.py | DIRECT_TENANT |
| resource_permissions | id | organization_id | - | user_id | - | - | - | - | - | - | resource_permissions.organization_id | YES (source migration) | 2: resource_permissions.py, workspaces.py | 0:  | DIRECT_TENANT |
| responses | id | organization_id | workspace_id | - | - | - | - | - | - | - | responses.organization_id | YES (source migration) | 32: ab_tests.py, account.py, admin_dashboard.py | 0:  | DIRECT_TENANT |
| retrieval_diagnostics | id | organization_id | - | - | - | - | - | - | - | - | retrieval_diagnostics.organization_id | YES (source migration) | 1: retrieval_diagnostics.py | 0:  | DIRECT_TENANT |
| revoked_access_tokens | id | - | - | user_id | - | - | - | - | - | - | revoked_access_tokens -> users | YES (source migration) | 0:  | 1: token_blacklist_cleanup.py | USER_SCOPED |
| role_permissions | id | - | - | - | - | - | - | - | - | - | role_permissions -> custom_roles.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| sandbox_environments | id | organization_id | - | - | - | - | - | - | - | - | sandbox_environments.organization_id | YES (source migration) | 1: sandbox.py | 0:  | DIRECT_TENANT |
| security_alerts | id | organization_id | - | - | - | - | - | - | - | - | security_alerts.organization_id | YES (source migration) | 3: admin_dashboard.py, audit.py, auth.py | 1: security_scan.py | DIRECT_TENANT |
| security_policies | id | organization_id | - | - | - | - | - | - | - | - | security_policies.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| security_scans | id | organization_id | - | - | - | - | - | - | - | - | security_scans.organization_id | YES (source migration) | 0:  | 1: security_scan.py | DIRECT_TENANT |
| sessions | id | - | - | user_id | - | - | - | - | - | - | sessions -> users | YES (source migration) | 12: account.py, admin_users_management.py, auth.py | 18: ab_tests.py, account_deletion_reminder.py, account_purge.py | USER_SCOPED |
| slack_integrations | id | organization_id | - | - | - | agent_id | - | - | - | - | slack_integrations.organization_id | YES (source migration) | 1: chat_integrations_slack.py | 0:  | DIRECT_TENANT |
| slack_messages | id | - | - | slack_user_id | - | - | - | conversation_id | - | - | slack_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| sms_messages | id | organization_id | - | - | - | - | - | - | - | - | sms_messages.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| ssl_certificates | id | - | - | - | - | - | - | - | - | - | ssl_certificates -> custom_domains.organization_id | YES (source migration) | 1: ssl_certificates.py | 1: ssl_certificate_renewal.py | INDIRECT_TENANT |
| sub_clients | id | organization_id | - | - | - | - | - | - | - | - | sub_clients.organization_id | YES (source migration) | 0:  | 1: sales.py | DIRECT_TENANT |
| subscriptions | id | organization_id | - | - | - | - | - | - | - | - | subscriptions.organization_id | YES (source migration) | 2: admin_subscriptions.py, billing.py | 2: billing.py, sales.py | DIRECT_TENANT |
| support_ticket_responses | id | - | - | - | - | - | - | - | - | - | support_ticket_responses -> support_tickets.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| support_tickets | id | organization_id | - | - | - | - | - | - | - | - | support_tickets.organization_id | YES (source migration) | 0:  | 0:  | DIRECT_TENANT |
| system_logs | id | - | - | - | - | - | - | - | - | - | system/security table; ownership/tenant use needs review | YES (source migration) | 0:  | 0:  | SYSTEM |
| task_plans | id | - | - | - | - | - | - | - | - | - | no direct organization/user ancestry found | YES (source migration) | 0:  | 0:  | UNKNOWN |
| task_steps | id | - | - | - | - | - | - | - | - | - | no direct organization/user ancestry found | YES (source migration) | 0:  | 0:  | UNKNOWN |
| team_members | id | - | - | user_id | - | - | - | - | - | - | team_members -> teams.organization_id | YES (source migration) | 2: organization_members.py, teams.py | 0:  | INDIRECT_TENANT |
| teams | id | organization_id | - | - | - | - | - | - | - | - | teams.organization_id | YES (source migration) | 4: chat_integrations_teams.py, organization_members.py, quotas.py | 0:  | DIRECT_TENANT |
| teams_integrations | id | organization_id | - | - | - | agent_id | - | - | - | - | teams_integrations.organization_id | YES (source migration) | 1: chat_integrations_teams.py | 0:  | DIRECT_TENANT |
| teams_messages | id | - | - | teams_user_id | - | - | - | conversation_id | - | - | teams_messages -> conversations.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| tool_budgets | tool_name | - | - | - | - | - | - | - | - | - | tool_budgets -> users | YES (source migration) | 1: tool_config.py | 0:  | USER_SCOPED |
| tool_fallbacks | id | - | - | - | - | - | - | - | - | - | tool_fallbacks -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| tool_permissions | id | organization_id | - | user_id | - | agent_id | - | - | - | - | tool_permissions.organization_id | YES (source migration) | 1: tool_permissions.py | 0:  | DIRECT_TENANT |
| tool_timeout_overrides | tool_name | - | - | - | - | - | - | - | - | - | tool_timeout_overrides -> users | YES (source migration) | 0:  | 0:  | USER_SCOPED |
| two_factor_lockout_recovery_tokens | id | - | - | user_id | - | - | - | - | - | - | two_factor_lockout_recovery_tokens -> users | YES (source migration) | 2: two_factor.py, webauthn.py | 0:  | USER_SCOPED |
| two_factor_recovery_codes | id | - | - | user_id | - | - | - | - | - | - | two_factor_recovery_codes -> users | YES (source migration) | 1: two_factor.py | 0:  | USER_SCOPED |
| usage_alerts | id | organization_id | - | - | - | - | - | - | - | - | usage_alerts.organization_id | YES (source migration) | 0:  | 1: sales.py | DIRECT_TENANT |
| user_custom_roles | id | - | - | user_id | - | - | - | - | - | - | user_custom_roles -> custom_roles.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| users | id | - | - | - | - | - | - | - | - | - | users | YES (source migration) | 65: ab_tests.py, account.py, admin_dashboard.py | 7: ab_tests.py, account_deletion_reminder.py, account_purge.py | USER_SCOPED |
| voice_messages | id | - | - | user_id | - | - | - | conversation_id | - | - | voice_messages -> conversations.organization_id | YES (source migration) | 1: voice_messages.py | 1: voice_message_cleanup.py | INDIRECT_TENANT |
| voice_settings | id | - | - | user_id | - | - | - | - | - | - | voice_settings -> users | YES (source migration) | 1: voice_settings.py | 0:  | USER_SCOPED |
| vulnerabilities | id | - | - | - | - | - | - | - | - | - | vulnerabilities -> security_scans.organization_id | YES (source migration) | 1: security_scan.py | 1: security_scan.py | INDIRECT_TENANT |
| webauthn_credentials | id | - | - | user_id | - | - | - | - | - | - | webauthn_credentials -> users | YES (source migration) | 4: auth.py, enterprise_sso.py, oauth.py | 0:  | USER_SCOPED |
| webhook_deliveries | id | - | - | - | - | - | - | - | - | - | webhook_deliveries -> webhooks.organization_id | YES (source migration) | 0:  | 1: webhooks.py | INDIRECT_TENANT |
| webhooks | id | organization_id | - | - | - | - | - | - | - | - | webhooks.organization_id | YES (source migration) | 7: audit.py, compliance.py, encryption.py | 5: celery_app.py, integrations.py, security_scan.py | DIRECT_TENANT |
| widget_configs | id | organization_id | - | - | - | agent_id | - | - | - | - | widget_configs.organization_id | YES (source migration) | 1: widget.py | 0:  | DIRECT_TENANT |
| widget_suggested_questions | id | - | - | - | - | - | - | - | - | - | widget_suggested_questions -> widget_configs.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| workflow_human_inputs | id | - | - | - | - | - | - | - | - | - | workflow_human_inputs -> workflow_runs -> workflows.organization_id | YES (source migration) | 0:  | 1: workflows.py | INDIRECT_TENANT |
| workflow_node_executions | id | - | - | - | - | - | - | - | - | - | workflow_node_executions -> workflow_runs -> workflows.organization_id | YES (source migration) | 0:  | 0:  | INDIRECT_TENANT |
| workflow_runs | id | - | - | - | - | - | - | - | workflow_id | - | workflow_runs -> workflows.organization_id | YES (source migration) | 1: workflows.py | 1: workflows.py | INDIRECT_TENANT |
| workflow_triggers | id | - | - | - | - | - | - | - | workflow_id | - | workflow_triggers -> workflows.organization_id | YES (source migration) | 1: workflows.py | 1: workflows.py | INDIRECT_TENANT |
| workflow_versions | id | - | - | - | - | - | - | - | workflow_id | - | workflow_versions -> workflows.organization_id | YES (source migration) | 1: workflows.py | 0:  | INDIRECT_TENANT |
| workflows | id | organization_id | workspace_id | - | - | - | - | - | - | - | workflows.organization_id | YES (source migration) | 1: workflows.py | 3: celery_app.py, notifications.py, workflows.py | DIRECT_TENANT |
| workspaces | id | organization_id | - | - | - | - | - | - | - | - | workspaces.organization_id | YES (source migration) | 6: agents.py, organization_members.py, quotas.py | 0:  | DIRECT_TENANT |

## Limits

- RLS source status was inferred heuristically from local migration source text only. A table name merely appearing in a migration containing an enable statement can be a false positive. `NOT FOUND` is not proof that RLS is disabled in a DB; migrations may be unapplied, hand-adjusted, or use constructs the static scan misses.
- This generated matrix reflects ORM declarations loaded from this worktree, including untracked code. It is not necessarily the schema at Git HEAD or the live database.
- FK path graph follows child-to-parent foreign keys only; it can miss tenant ownership through JSON, polymorphic IDs, caches, composite conventions, or runtime joins.
- Router/task file references are name occurrence counts, not call graphs and not evidence of an authorization guard.
- Tables classified `UNKNOWN`, and all ID-bearing access paths, require manual review and explicit IDOR tests before any security claim.
