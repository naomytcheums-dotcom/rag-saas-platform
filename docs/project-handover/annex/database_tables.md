# Database tables (generated from SQLAlchemy metadata)

182 tables.

## ab_test_assignments
- columns (5): id:CHAR(32)*, ab_test_id:CHAR(32), request_id:VARCHAR(200), variant:VARCHAR(1), assigned_at:DATETIME
- foreign keys: ab_test_id->ab_tests.id
- indexes: ix_ab_test_assignments_ab_test_id

## ab_test_results
- columns (12): id:CHAR(32)*, ab_test_id:CHAR(32), variant:VARCHAR(1), metric_value:NUMERIC(20, 6), sample_count:INTEGER, mean:NUMERIC(20, 6), std_dev:NUMERIC(20, 6), confidence_interval_lower:NUMERIC(20, 6), confidence_interval_upper:NUMERIC(20, 6), p_value:NUMERIC(10, 8), is_significant:BOOLEAN, created_at:DATETIME
- foreign keys: ab_test_id->ab_tests.id
- indexes: ix_ab_test_results_ab_test_id

## ab_tests
- columns (19): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, variant_a:JSON, variant_b:JSON, traffic_split:INTEGER, status:VARCHAR(20), metrics:JSON, start_date:DATETIME, end_date:DATETIME, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, test_type:VARCHAR(20), target_metric:VARCHAR(50), min_sample_size:INTEGER, confidence_level:FLOAT, winner:VARCHAR(10)
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_ab_tests_organization_id

## account_restore_tokens
- columns (6): id:CHAR(32)*, user_id:CHAR(32), token_hash:VARCHAR(64), created_at:DATETIME, expires_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_account_restore_tokens_token_hash

## acme_accounts
- columns (6): id:CHAR(32)*, directory_url:VARCHAR(500), account_key_pem_encrypted:TEXT, account_url:VARCHAR(500), created_at:DATETIME, updated_at:DATETIME
- foreign keys: none
- indexes: none

## agent_api_keys
- columns (11): id:CHAR(32)*, agent_id:CHAR(32), name:VARCHAR(200), key_hash:VARCHAR(64), key_prefix:VARCHAR(10), scopes:JSON, expires_at:DATETIME, last_used_at:DATETIME, created_by:CHAR(32), created_at:DATETIME, revoked_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id
- indexes: ix_agent_api_keys_agent_id, ix_agent_api_keys_key_hash

## agent_collaborations
- columns (7): id:CHAR(32)*, initiator_agent_id:CHAR(32), collaborator_agent_id:CHAR(32), task:TEXT, status:VARCHAR(20), result:JSON, created_at:DATETIME
- foreign keys: collaborator_agent_id->autonomous_agents.id, initiator_agent_id->autonomous_agents.id
- indexes: ix_agent_collaborations_collaborator_agent_id, ix_agent_collaborations_initiator_agent_id

## agent_long_term_memory_items
- columns (8): id:CHAR(32)*, agent_id:CHAR(32), user_id:CHAR(32), key:VARCHAR(200), value:JSON, created_at:DATETIME, updated_at:DATETIME, expires_at:DATETIME
- foreign keys: agent_id->agents.id, user_id->users.id
- indexes: ix_agent_long_term_memory_agent_id

## agent_memories
- columns (7): id:CHAR(32)*, agent_id:CHAR(32), memory_type:VARCHAR(20), content:TEXT, embedding:JSON, importance:NUMERIC(3, 2), created_at:DATETIME
- foreign keys: agent_id->autonomous_agents.id
- indexes: ix_agent_memories_agent_id

## agent_memory_items
- columns (6): id:CHAR(32)*, session_id:CHAR(32), key:VARCHAR(200), value:JSON, created_at:DATETIME, expires_at:DATETIME
- foreign keys: session_id->agent_sessions.id
- indexes: none

## agent_plans
- columns (6): id:CHAR(32)*, agent_id:CHAR(32), goal:TEXT, steps:JSON, status:VARCHAR(20), created_at:DATETIME
- foreign keys: agent_id->autonomous_agents.id
- indexes: ix_agent_plans_agent_id

## agent_runs
- columns (14): id:CHAR(32)*, agent_id:VARCHAR(200), organization_id:CHAR(32), status:VARCHAR(20), input:JSON, context:JSON, result:JSON, error:TEXT, started_at:DATETIME, completed_at:DATETIME, trace:JSON, created_by:CHAR(32), stop_requested:BOOLEAN, response_id:CHAR(32)
- foreign keys: created_by->users.id, organization_id->organizations.id, response_id->responses.id
- indexes: ix_agent_runs_agent_id, ix_agent_runs_organization_id, ix_agent_runs_status

## agent_sessions
- columns (7): id:CHAR(32)*, agent_id:VARCHAR(200), user_id:CHAR(32), created_at:DATETIME, updated_at:DATETIME, expires_at:DATETIME, metadata_json:JSON
- foreign keys: user_id->users.id
- indexes: ix_agent_sessions_agent_id

## agent_steps
- columns (11): id:CHAR(32)*, plan_id:CHAR(32), step_number:INTEGER, action:VARCHAR(100), parameters:JSON, result:JSON, status:VARCHAR(20), error:TEXT, total_cost:NUMERIC(12, 6), started_at:DATETIME, completed_at:DATETIME
- foreign keys: plan_id->agent_plans.id
- indexes: ix_agent_steps_plan_id

## agent_traces
- columns (12): id:CHAR(32)*, agent_run_id:CHAR(32), step_number:INTEGER, step_type:VARCHAR(20), description:TEXT, input:JSON, output:JSON, duration_ms:INTEGER, status:VARCHAR(20), error:TEXT, metadata_json:JSON, created_at:DATETIME
- foreign keys: agent_run_id->agent_runs.id
- indexes: ix_agent_traces_agent_run_id

## agents
- columns (38): id:CHAR(32)*, organization_id:CHAR(32), workspace_id:CHAR(32), name:VARCHAR(200), description:TEXT, system_prompt:TEXT, system_prompt_template:TEXT, model_config_json:JSON, tools:JSON, memory_enabled:BOOLEAN, memory_window_size:INTEGER, memory_ttl:INTEGER, memory_max_items:INTEGER, memory_retention_policy:VARCHAR(10), guardrails_enabled:BOOLEAN, human_approval_required:BOOLEAN, knowledge_base_id:CHAR(32), knowledge_base_config:JSON, allowed_users:JSON, allowed_roles:JSON, is_public:BOOLEAN, guardrails_config:JSON, blocked_topics:JSON, allowed_domains:JSON, max_tokens_per_response:INTEGER, content_filter_level:VARCHAR(10), prompt_injection_detection_enabled:BOOLEAN, citation_required:BOOLEAN, citation_required_message:TEXT, answer_only_from_context:BOOLEAN, context_only_message:TEXT, idk_threshold:FLOAT, idk_message:TEXT, status:VARCHAR(10), created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, deleted_at:DATETIME
- foreign keys: created_by->users.id, knowledge_base_id->workspaces.id, organization_id->organizations.id, workspace_id->workspaces.id
- indexes: ix_agents_organization_id, ix_agents_workspace_id

## airbyte_connections
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), airbyte_source_id:VARCHAR(100), airbyte_connection_id:VARCHAR(100), source_type:VARCHAR(100), created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_airbyte_connections_organization_id

## alert_channels
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(100), type:VARCHAR(7), config:JSON, enabled:BOOLEAN, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_alert_channels_organization_id

## alert_history
- columns (6): id:CHAR(32)*, rule_id:CHAR(32), triggered_at:DATETIME, value_at_trigger:FLOAT, message:TEXT, notified:BOOLEAN
- foreign keys: rule_id->alert_rules.id
- indexes: ix_alert_history_rule_id, ix_alert_history_triggered_at

## alert_rules
- columns (11): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(100), metric:VARCHAR(64), operator:VARCHAR(3), threshold:FLOAT, severity:VARCHAR(8), channel_id:CHAR(32), enabled:BOOLEAN, created_by:CHAR(32), created_at:DATETIME
- foreign keys: channel_id->alert_channels.id, created_by->users.id, organization_id->organizations.id
- indexes: ix_alert_rules_organization_id

## analytics_aggregates
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), metric_name:VARCHAR(100), metric_value:NUMERIC(20, 4), period:VARCHAR(10), period_start:DATETIME, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_analytics_aggregates_organization_id, uq_analytics_aggregates_identity

## analytics_dashboards
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), widgets:JSON, is_default:BOOLEAN, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_analytics_dashboards_organization_id

## analytics_events
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), user_id:CHAR(32), event_type:VARCHAR(100), event_data:JSON, created_at:DATETIME
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_analytics_events_created_at, ix_analytics_events_event_type, ix_analytics_events_org_type_created, ix_analytics_events_organization_id

## audit_logs
- columns (13): id:CHAR(32)*, user_id:CHAR(32), organization_id:CHAR(32), resource_type:VARCHAR(50), resource_id:VARCHAR(64), action:VARCHAR(100), ip:VARCHAR(45), user_agent:VARCHAR(500), timestamp:DATETIME, metadata_json:TEXT, success:BOOLEAN, failure_reason:VARCHAR(500), checksum:VARCHAR(64)
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_audit_logs_action, ix_audit_logs_organization_id, ix_audit_logs_resource_type, ix_audit_logs_timestamp, ix_audit_logs_user_id, ix_audit_logs_user_id_timestamp

## audit_logs_archive
- columns (15): id:CHAR(32)*, original_id:CHAR(32), user_id:CHAR(32), organization_id:CHAR(32), resource_type:VARCHAR(50), resource_id:VARCHAR(64), action:VARCHAR(100), ip:VARCHAR(45), user_agent:VARCHAR(500), timestamp:DATETIME, metadata_json:TEXT, success:BOOLEAN, failure_reason:VARCHAR(500), checksum:VARCHAR(64), archived_at:DATETIME
- foreign keys: none
- indexes: ix_audit_logs_archive_original_id

## autonomous_agents
- columns (16): id:CHAR(32)*, organization_id:CHAR(32), created_by:CHAR(32), name:VARCHAR(200), description:TEXT, goal:TEXT, status:VARCHAR(20), max_steps:INTEGER, current_step:INTEGER, tools_enabled:JSON, guardrails:JSON, memory_config:JSON, total_cost:NUMERIC(12, 6), error:TEXT, created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_autonomous_agents_organization_id

## batch_job_items
- columns (7): id:CHAR(32)*, batch_job_id:CHAR(32), sequence:INTEGER, item_id:CHAR(32), status:VARCHAR(20), error:TEXT, processed_at:DATETIME
- foreign keys: batch_job_id->batch_jobs.id
- indexes: ix_batch_job_items_batch_job_id

## batch_jobs
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), job_type:VARCHAR(20), status:VARCHAR(20), total_items:INTEGER, processed_items:INTEGER, failed_items:INTEGER, config:JSON, created_by:CHAR(32), created_at:DATETIME, started_at:DATETIME, completed_at:DATETIME, error:TEXT
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_batch_jobs_organization_id

## benchmark_versions
- columns (9): id:CHAR(32)*, dataset_id:CHAR(32), version_number:INTEGER, question_set_id:CHAR(32), description:TEXT, snapshot:JSON, metadata_json:JSON, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, dataset_id->evaluation_datasets.id, question_set_id->question_sets.id
- indexes: ix_benchmark_versions_dataset_id

## call_records
- columns (14): id:CHAR(32)*, call_sid:VARCHAR(64), conversation_id:CHAR(32), agent_id:CHAR(32), organization_id:CHAR(32), from_number:VARCHAR(32), to_number:VARCHAR(32), status:VARCHAR(20), duration_seconds:INTEGER, recording_url:VARCHAR(500), transcription:TEXT, started_at:DATETIME, ended_at:DATETIME, created_at:DATETIME
- foreign keys: agent_id->agents.id, conversation_id->conversations.id, organization_id->organizations.id
- indexes: ix_call_records_call_sid, ix_call_records_organization_id

## citations
- columns (22): id:CHAR(32)*, response_id:CHAR(32), document_id:CHAR(32), chunk_id:CHAR(32), source_url:VARCHAR(2048), source_page:INTEGER, source_title:VARCHAR(500), text:TEXT, relevance_score:FLOAT, citation_number:INTEGER, position_start:INTEGER, position_end:INTEGER, metadata_json:JSON, created_at:DATETIME, document_name:VARCHAR(500), document_type:VARCHAR(127), source_section:VARCHAR(500), source_heading:VARCHAR(500), chunk_index:INTEGER, relevance_label:VARCHAR(10), text_preview:VARCHAR(500), is_primary:BOOLEAN
- foreign keys: chunk_id->document_chunks.id, document_id->documents.id, response_id->responses.id
- indexes: ix_citations_document_id, ix_citations_response_id

## comparison_jobs
- columns (9): id:CHAR(32)*, dataset_id:CHAR(32), comparison_type:VARCHAR(20), name:VARCHAR(200), variants:JSON, results:JSON, created_by:CHAR(32), created_at:DATETIME, completed_at:DATETIME
- foreign keys: created_by->users.id, dataset_id->evaluation_datasets.id
- indexes: ix_comparison_jobs_dataset_id

## connector_credentials
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), provider:VARCHAR(40), encrypted_payload:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_connector_credentials_organization_id

## consent_reactivation_tokens
- columns (6): id:CHAR(32)*, user_id:CHAR(32), token_hash:VARCHAR(64), created_at:DATETIME, expires_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_consent_reactivation_tokens_token_hash

## consent_records
- columns (6): id:CHAR(32)*, user_id:CHAR(32), consent_type:VARCHAR(50), granted:BOOLEAN, ip:VARCHAR(45), created_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_consent_records_created_at, ix_consent_records_user_id

## conversation_messages
- columns (9): id:CHAR(32)*, conversation_id:CHAR(32), role:VARCHAR(20), content:TEXT, tool_calls:JSON, tool_call_id:VARCHAR(200), created_at:DATETIME, metadata_json:JSON, retry_count:INTEGER
- foreign keys: conversation_id->conversations.id
- indexes: ix_conversation_messages_conversation_id

## conversation_shares
- columns (8): id:CHAR(32)*, conversation_id:CHAR(32), token:VARCHAR(64), shared_by:CHAR(32), expires_at:DATETIME, max_views:INTEGER, views:INTEGER, created_at:DATETIME
- foreign keys: conversation_id->conversations.id, shared_by->users.id
- indexes: ix_conversation_shares_conversation_id, ix_conversation_shares_token

## conversations
- columns (11): id:CHAR(32)*, agent_id:VARCHAR(200), user_id:CHAR(32), organization_id:CHAR(32), title:VARCHAR(300), created_at:DATETIME, updated_at:DATETIME, archived:BOOLEAN, metadata_json:JSON, deleted_at:DATETIME, is_public:BOOLEAN
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_conversations_agent_id, ix_conversations_deleted_at, ix_conversations_organization_id, ix_conversations_user_id

## coupon_redemptions
- columns (5): id:CHAR(32)*, coupon_id:CHAR(32), organization_id:CHAR(32), user_id:CHAR(32), created_at:DATETIME
- foreign keys: coupon_id->coupons.id, organization_id->organizations.id, user_id->users.id
- indexes: ix_coupon_redemptions_coupon_id, ix_coupon_redemptions_organization_id

## coupons
- columns (11): id:CHAR(32)*, code:VARCHAR(64), kind:VARCHAR(20), bonus_credits:INTEGER, percent_off:INTEGER, max_redemptions:INTEGER, redeemed_count:INTEGER, expires_at:DATETIME, active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id
- indexes: ix_coupons_code

## credit_transactions
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), type:VARCHAR(8), amount:INTEGER, balance_after:INTEGER, reason:VARCHAR(200), user_id:CHAR(32), created_at:DATETIME
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_credit_transactions_created_at, ix_credit_transactions_organization_id

## credits
- columns (5): id:CHAR(32)*, organization_id:CHAR(32), balance:INTEGER, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## custom_domains
- columns (20): id:CHAR(32)*, organization_id:CHAR(32), domain:VARCHAR(255), status:VARCHAR(20), verification_token:VARCHAR(64), ssl_cert:TEXT, ssl_key:TEXT, verification_attempts:INTEGER, last_verification_attempt_at:DATETIME, email_verified:BOOLEAN, dkim_selector:VARCHAR(63), dkim_private_key:TEXT, dkim_public_key:TEXT, email_verification_token:VARCHAR(64), email_verification_attempts:INTEGER, email_verified_at:DATETIME, email_verification_started_at:DATETIME, resend_domain_id:VARCHAR(64), created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_custom_domains_organization_id

## custom_roles
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(100), description:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_custom_roles_organization_id

## custom_tools
- columns (14): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, webhook_url:VARCHAR(2000), method:VARCHAR(10), headers:JSON, timeout:INTEGER, retry_count:INTEGER, schema:JSON, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, deleted_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_custom_tools_organization_id

## data_breaches
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), description:TEXT, affected_user_count:INTEGER, declared_by:CHAR(32), created_at:DATETIME, notified_at:DATETIME
- foreign keys: declared_by->users.id, organization_id->organizations.id
- indexes: ix_data_breaches_organization_id

## data_requests
- columns (9): id:CHAR(32)*, user_id:CHAR(32), request_type:VARCHAR(13), status:VARCHAR(11), details:TEXT, resolution_note:TEXT, processed_by:CHAR(32), created_at:DATETIME, processed_at:DATETIME
- foreign keys: processed_by->users.id, user_id->users.id
- indexes: ix_data_requests_user_id

## deployment_evaluations
- columns (11): id:CHAR(32)*, agent_id:CHAR(32), dataset_id:CHAR(32), evaluation_job_id:CHAR(32), version:VARCHAR(50), status:VARCHAR(20), results:JSON, thresholds:JSON, created_by:CHAR(32), created_at:DATETIME, completed_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id, dataset_id->evaluation_datasets.id, evaluation_job_id->evaluation_jobs.id
- indexes: ix_deployment_evaluations_agent_id

## discord_integrations
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), guild_id:VARCHAR(32), guild_name:VARCHAR(255), bot_token:TEXT, bot_id:VARCHAR(32), default_channel_id:VARCHAR(32), default_channel_name:VARCHAR(255), agent_id:CHAR(32), created_by:CHAR(32), is_active:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id, organization_id->organizations.id
- indexes: ix_discord_integrations_organization_id

## discord_messages
- columns (14): id:CHAR(32)*, integration_id:CHAR(32), conversation_id:CHAR(32), discord_message_id:VARCHAR(32), discord_channel_id:VARCHAR(32), discord_user_id:VARCHAR(32), discord_user_name:VARCHAR(255), content:TEXT, response:TEXT, is_thread:BOOLEAN, parent_message_id:VARCHAR(32), status:VARCHAR(16), created_at:DATETIME, processed_at:DATETIME
- foreign keys: conversation_id->conversations.id, integration_id->discord_integrations.id
- indexes: ix_discord_messages_integration_id

## document_audit_logs
- columns (7): id:CHAR(32)*, document_id:CHAR(32), action:VARCHAR(50), user_id:CHAR(32), changes:JSON, metadata_json:JSON, timestamp:DATETIME
- foreign keys: document_id->documents.id, user_id->users.id
- indexes: ix_document_audit_logs_document_id

## document_chunks
- columns (14): id:CHAR(32)*, document_id:CHAR(32), media_asset_id:CHAR(32), organization_id:CHAR(32), content:TEXT, metadata_json:JSON, embedding:JSON, embedding_model:VARCHAR(200), embedding_dim:INTEGER, embedding_vector:VECTOR(384), created_at:DATETIME, chunk_index:INTEGER, parent_chunk_id:CHAR(32), chunk_role:VARCHAR(10)
- foreign keys: document_id->documents.id, media_asset_id->media_assets.id, organization_id->organizations.id, parent_chunk_id->document_chunks.id
- indexes: ix_document_chunks_document_id, ix_document_chunks_media_asset_id, ix_document_chunks_organization_id, ix_document_chunks_parent_chunk_id

## document_entities
- columns (7): id:CHAR(32)*, document_id:CHAR(32), entity_type:VARCHAR(20), entity_value:VARCHAR(500), confidence:FLOAT, position:INTEGER, created_at:DATETIME
- foreign keys: document_id->documents.id
- indexes: ix_document_entities_document_id

## document_images
- columns (11): id:CHAR(32)*, document_id:CHAR(32), file_key:VARCHAR(1024), file_size:INTEGER, width:INTEGER, height:INTEGER, format:VARCHAR(20), metadata_json:JSON, description:TEXT, objects_json:JSON, created_at:DATETIME
- foreign keys: document_id->documents.id
- indexes: ix_document_images_document_id

## document_keywords
- columns (5): id:CHAR(32)*, document_id:CHAR(32), keyword:VARCHAR(200), score:FLOAT, created_at:DATETIME
- foreign keys: document_id->documents.id
- indexes: ix_document_keywords_document_id

## document_tag_assignments
- columns (5): id:CHAR(32)*, document_id:CHAR(32), tag_id:CHAR(32), assigned_at:DATETIME, assigned_by:CHAR(32)
- foreign keys: assigned_by->users.id, document_id->documents.id, tag_id->document_tags.id
- indexes: ix_document_tag_assignments_document_id, ix_document_tag_assignments_tag_id

## document_tags
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(100), color:VARCHAR(20), created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_document_tags_organization_id

## document_versions
- columns (8): id:CHAR(32)*, document_id:CHAR(32), version_number:INTEGER, file_key:VARCHAR(1024), file_size:INTEGER, metadata_json:JSON, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, document_id->documents.id
- indexes: ix_document_versions_document_id

## documents
- columns (23): id:CHAR(32)*, organization_id:CHAR(32), workspace_id:CHAR(32), name:VARCHAR(500), source_url:VARCHAR(2048), file_key:VARCHAR(1024), file_size:INTEGER, file_type:VARCHAR(127), status:VARCHAR(20), metadata_json:JSON, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, processed_at:DATETIME, current_version_id:CHAR(32), deleted_at:DATETIME, deleted_by:CHAR(32), indexing_started_at:DATETIME, indexing_error:TEXT, content_hash:VARCHAR(64), last_modified:DATETIME, last_checked:DATETIME, reindex_schedule:VARCHAR(100)
- foreign keys: created_by->users.id, current_version_id->document_versions.id, deleted_by->users.id, organization_id->organizations.id, workspace_id->workspaces.id
- indexes: ix_documents_organization_content_hash_file_type, ix_documents_organization_id, ix_documents_workspace_id

## email_verification_tokens
- columns (7): id:CHAR(32)*, user_id:CHAR(32), code_hash:VARCHAR(64), attempts:INTEGER, created_at:DATETIME, expires_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: none

## encryption_audit
- columns (7): id:CHAR(32)*, operation:VARCHAR(50), rows_affected:INTEGER, success:BOOLEAN, detail:VARCHAR(500), performed_by:CHAR(32), created_at:DATETIME
- foreign keys: performed_by->users.id
- indexes: none

## encryption_key_records
- columns (5): id:CHAR(32)*, label:VARCHAR(200), is_active:BOOLEAN, created_at:DATETIME, retired_at:DATETIME
- foreign keys: none
- indexes: none

## enterprise_sso_accounts
- columns (6): id:CHAR(32)*, user_id:CHAR(32), connection_id:CHAR(32), provider_subject:VARCHAR(255), provider_email:VARCHAR(320), created_at:DATETIME
- foreign keys: connection_id->enterprise_sso_connections.id, user_id->users.id
- indexes: ix_enterprise_sso_accounts_connection_id, ix_enterprise_sso_accounts_user_id

## enterprise_sso_connections
- columns (13): id:CHAR(32)*, email_domain:VARCHAR(255), display_name:VARCHAR(200), issuer:VARCHAR(500), client_id:VARCHAR(255), client_secret_encrypted:VARCHAR(1000), is_enabled:BOOLEAN, domain_verified:BOOLEAN, domain_verified_at:DATETIME, domain_verification_token:VARCHAR(64), created_by_admin_id:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by_admin_id->users.id
- indexes: none

## escalation_notes
- columns (5): id:CHAR(32)*, escalation_id:CHAR(32), author_id:CHAR(32), body:TEXT, created_at:DATETIME
- foreign keys: author_id->users.id, escalation_id->escalations.id
- indexes: ix_escalation_notes_escalation_id

## escalations
- columns (12): id:CHAR(32)*, agent_run_id:CHAR(32), organization_id:CHAR(32), issue:TEXT, context:JSON, priority:VARCHAR(10), status:VARCHAR(10), resolution:TEXT, assignee_id:CHAR(32), created_at:DATETIME, resolved_at:DATETIME, sla_due_at:DATETIME
- foreign keys: agent_run_id->agent_runs.id, assignee_id->users.id, organization_id->organizations.id
- indexes: none

## evaluation_datasets
- columns (10): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, version:INTEGER, is_active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, deleted_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_evaluation_datasets_organization_id

## evaluation_failures
- columns (6): id:CHAR(32)*, evaluation_job_id:CHAR(32), question_id:CHAR(32), category:VARCHAR(20), error:TEXT, created_at:DATETIME
- foreign keys: evaluation_job_id->evaluation_jobs.id, question_id->evaluation_questions.id
- indexes: ix_evaluation_failures_evaluation_job_id

## evaluation_jobs
- columns (16): id:CHAR(32)*, dataset_id:CHAR(32), question_set_id:CHAR(32), agent_id:CHAR(32), model_config_json:JSON, split:VARCHAR(10), status:VARCHAR(20), progress:INTEGER, total_questions:INTEGER, completed_questions:INTEGER, results:JSON, error:TEXT, created_by:CHAR(32), created_at:DATETIME, started_at:DATETIME, completed_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id, dataset_id->evaluation_datasets.id, question_set_id->question_sets.id
- indexes: ix_evaluation_jobs_dataset_id, ix_evaluation_jobs_status

## evaluation_questions
- columns (13): id:CHAR(32)*, dataset_id:CHAR(32), question:TEXT, expected_answer:TEXT, expected_documents:JSON, difficulty:VARCHAR(10), category:VARCHAR(100), metadata_json:JSON, created_at:DATETIME, updated_at:DATETIME, expected_answer_type:VARCHAR(10), expected_answer_metadata:JSON, split:VARCHAR(10)
- foreign keys: dataset_id->evaluation_datasets.id
- indexes: ix_evaluation_questions_dataset_id

## evaluation_results
- columns (11): id:CHAR(32)*, question_id:CHAR(32), agent_id:CHAR(32), evaluation_job_id:CHAR(32), model_config_json:JSON, retrieved_documents:JSON, retrieved_chunks:JSON, actual_answer:TEXT, metrics:JSON, latency_ms:INTEGER, created_at:DATETIME
- foreign keys: agent_id->agents.id, evaluation_job_id->evaluation_jobs.id, question_id->evaluation_questions.id
- indexes: ix_evaluation_results_evaluation_job_id, ix_evaluation_results_question_id

## external_sources
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), workspace_id:CHAR(32), source_type:VARCHAR(20), source_id:VARCHAR(2048), config_encrypted:TEXT, enabled:BOOLEAN, last_sync_at:DATETIME, sync_status:VARCHAR(20), sync_error:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id, workspace_id->workspaces.id
- indexes: ix_external_sources_organization_id

## fine_tuned_models
- columns (11): id:CHAR(32)*, organization_id:CHAR(32), job_id:CHAR(32), name:VARCHAR(200), provider:VARCHAR(20), provider_model_id:VARCHAR(300), base_model:VARCHAR(200), status:VARCHAR(20), deployed:BOOLEAN, metrics:JSON, created_at:DATETIME
- foreign keys: job_id->fine_tuning_jobs.id, organization_id->organizations.id
- indexes: ix_fine_tuned_models_job_id, ix_fine_tuned_models_organization_id

## fine_tuning_datasets
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), created_by:CHAR(32), name:VARCHAR(200), description:TEXT, dataset_type:VARCHAR(20), format:VARCHAR(20), file_key:VARCHAR(1024), size:INTEGER, status:VARCHAR(20), validation_errors:JSON, example_count:INTEGER, created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_fine_tuning_datasets_organization_id

## fine_tuning_evaluations
- columns (7): id:CHAR(32)*, model_id:CHAR(32), dataset_id:CHAR(32), evaluation_job_id:CHAR(32), metrics:JSON, score:NUMERIC(6, 4), created_at:DATETIME
- foreign keys: dataset_id->evaluation_datasets.id, evaluation_job_id->evaluation_jobs.id, model_id->fine_tuned_models.id
- indexes: ix_fine_tuning_evaluations_dataset_id, ix_fine_tuning_evaluations_model_id

## fine_tuning_jobs
- columns (15): id:CHAR(32)*, organization_id:CHAR(32), dataset_id:CHAR(32), created_by:CHAR(32), name:VARCHAR(200), base_model:VARCHAR(200), provider:VARCHAR(20), status:VARCHAR(20), hyperparameters:JSON, metrics:JSON, provider_job_id:VARCHAR(200), error_message:TEXT, started_at:DATETIME, completed_at:DATETIME, created_at:DATETIME
- foreign keys: created_by->users.id, dataset_id->fine_tuning_datasets.id, organization_id->organizations.id
- indexes: ix_fine_tuning_jobs_dataset_id, ix_fine_tuning_jobs_organization_id

## flight_recordings
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), query:VARCHAR(2000), stages_json:JSON, total_duration_ms:INTEGER, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_flight_recordings_organization_id

## follow_up_questions
- columns (5): id:CHAR(32)*, message_id:CHAR(32), question:TEXT, clicked:BOOLEAN, created_at:DATETIME
- foreign keys: message_id->conversation_messages.id
- indexes: ix_follow_up_questions_message_id

## human_approvals
- columns (12): id:CHAR(32)*, agent_run_id:CHAR(32), organization_id:CHAR(32), tool_name:VARCHAR(200), params:JSON, status:VARCHAR(10), requested_by:CHAR(32), approved_by:CHAR(32), requested_at:DATETIME, approved_at:DATETIME, expires_at:DATETIME, comment:TEXT
- foreign keys: agent_run_id->agent_runs.id, approved_by->users.id, organization_id->organizations.id, requested_by->users.id
- indexes: none

## incidents
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), title:VARCHAR(200), description:TEXT, severity:VARCHAR(8), status:VARCHAR(13), created_by:CHAR(32), created_at:DATETIME, resolved_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_incidents_organization_id

## integration_connections
- columns (10): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), provider:VARCHAR(7), action:VARCHAR(19), token:VARCHAR(64), is_active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_integration_connections_organization_id

## integration_logs
- columns (6): id:CHAR(32)*, connection_id:CHAR(32), status:VARCHAR(8), payload:JSON, detail:TEXT, created_at:DATETIME
- foreign keys: connection_id->integration_connections.id
- indexes: ix_integration_logs_connection_id, ix_integration_logs_created_at

## integration_mappings
- columns (5): id:CHAR(32)*, connection_id:CHAR(32), source_field:VARCHAR(200), target_field:VARCHAR(200), transform:VARCHAR(50)
- foreign keys: connection_id->integration_connections.id
- indexes: ix_integration_mappings_connection_id

## invitations
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), email:VARCHAR(320), role:VARCHAR(7), invited_by:CHAR(32), token_hash:VARCHAR(64), expires_at:DATETIME, accepted_at:DATETIME, created_at:DATETIME
- foreign keys: invited_by->users.id, organization_id->organizations.id
- indexes: ix_invitations_email, ix_invitations_organization_id, ix_invitations_token_hash

## invoice_lines
- columns (6): id:CHAR(32)*, invoice_id:CHAR(32), description:VARCHAR(300), quantity:INTEGER, unit_price_cents:INTEGER, total_cents:INTEGER
- foreign keys: invoice_id->invoices.id
- indexes: ix_invoice_lines_invoice_id

## invoices
- columns (17): id:CHAR(32)*, organization_id:CHAR(32), number:VARCHAR(40), status:VARCHAR(8), currency:VARCHAR(3), subtotal_cents:INTEGER, vat_rate:NUMERIC(5, 2), vat_cents:INTEGER, total_cents:INTEGER, period_start:DATE, period_end:DATE, due_date:DATE, paid_at:DATETIME, voided_at:DATETIME, void_reason:VARCHAR(500), created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_invoices_created_at, ix_invoices_organization_id

## jwt_signing_keys
- columns (5): id:CHAR(32)*, secret:VARCHAR(500), is_active:BOOLEAN, created_at:DATETIME, retired_at:DATETIME
- foreign keys: none
- indexes: none

## key_rotation_history
- columns (8): id:CHAR(32)*, key_id:CHAR(32), rotated_from:CHAR(32), rotated_to:CHAR(32), rotated_by:CHAR(32), rotated_at:DATETIME, reason:TEXT, metadata_json:JSON
- foreign keys: key_id->organization_api_keys.id, rotated_by->users.id, rotated_from->organization_api_keys.id, rotated_to->organization_api_keys.id
- indexes: ix_key_rotation_history_key_id

## licenses
- columns (11): id:CHAR(32)*, key:VARCHAR(64), organization_id:CHAR(32), plan_key:VARCHAR(50), status:VARCHAR(7), max_activations:INTEGER, activation_count:INTEGER, expires_at:DATETIME, activated_at:DATETIME, last_validated_at:DATETIME, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## llm_fallbacks
- columns (4): provider:VARCHAR(50)*, fallback_provider:VARCHAR(50), updated_by:CHAR(32), updated_at:DATETIME
- foreign keys: updated_by->users.id
- indexes: none

## manual_evaluations
- columns (9): id:CHAR(32)*, question_id:CHAR(32), agent_id:CHAR(32), evaluator_id:CHAR(32), score:INTEGER, feedback:TEXT, criteria:JSON, created_at:DATETIME, updated_at:DATETIME
- foreign keys: agent_id->agents.id, evaluator_id->users.id, question_id->evaluation_questions.id
- indexes: ix_manual_evaluations_evaluator_id, ix_manual_evaluations_question_id

## mcp_server_configs
- columns (17): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, transport:VARCHAR(20), url:VARCHAR(2048), command:VARCHAR(500), args:JSON, env:JSON, auth_type:VARCHAR(20), auth_credential_encrypted:TEXT, is_active:BOOLEAN, last_sync_at:DATETIME, last_sync_error:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_mcp_server_configs_organization_id

## mcp_tool_cache
- columns (6): id:CHAR(32)*, server_id:CHAR(32), name:VARCHAR(200), description:TEXT, input_schema:JSON, discovered_at:DATETIME
- foreign keys: server_id->mcp_server_configs.id
- indexes: ix_mcp_tool_cache_server_id

## media_assets
- columns (18): id:CHAR(32)*, organization_id:CHAR(32), uploaded_by:CHAR(32), media_type:VARCHAR(5), status:VARCHAR(10), filename:VARCHAR(500), file_key:VARCHAR(1024), file_size:INTEGER, mime_type:VARCHAR(100), duration_ms:INTEGER, description:TEXT, ocr_text:TEXT, objects_json:JSON, tags_json:JSON, clip_embedding:JSON, error:TEXT, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id, uploaded_by->users.id
- indexes: ix_media_assets_organization_id

## media_frames
- columns (8): id:CHAR(32)*, media_asset_id:CHAR(32), frame_index:INTEGER, timestamp_ms:INTEGER, file_key:VARCHAR(1024), description:TEXT, objects_json:JSON, created_at:DATETIME
- foreign keys: media_asset_id->media_assets.id
- indexes: ix_media_frames_media_asset_id

## media_transcripts
- columns (7): id:CHAR(32)*, media_asset_id:CHAR(32), text:TEXT, segments_json:JSON, language:VARCHAR(10), provider:VARCHAR(50), created_at:DATETIME
- foreign keys: media_asset_id->media_assets.id
- indexes: ix_media_transcripts_media_asset_id

## message_edit_history
- columns (6): id:CHAR(32)*, message_id:CHAR(32), version:INTEGER, content:TEXT, edited_at:DATETIME, edited_by:CHAR(32)
- foreign keys: edited_by->users.id, message_id->conversation_messages.id
- indexes: ix_message_edit_history_message_id

## message_feedback
- columns (8): id:CHAR(32)*, message_id:CHAR(32), user_id:CHAR(32), rating:VARCHAR(20), reason:TEXT, comment:TEXT, correction:TEXT, created_at:DATETIME
- foreign keys: message_id->conversation_messages.id, user_id->users.id
- indexes: ix_message_feedback_message_id, ix_message_feedback_message_user_unique

## notification_preferences
- columns (8): id:CHAR(32)*, user_id:CHAR(32), organization_id:CHAR(32), notification_type:VARCHAR(100), in_app_enabled:BOOLEAN, email_enabled:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_notification_preferences_organization_id, ix_notification_preferences_user_id

## notification_templates
- columns (10): id:CHAR(32)*, organization_id:CHAR(32), notification_type:VARCHAR(64), title:VARCHAR(500), body:TEXT, email_subject:VARCHAR(500), is_active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_notification_templates_notification_type, ix_notification_templates_organization_id

## notifications
- columns (16): id:CHAR(32)*, organization_id:CHAR(32), user_id:CHAR(32), type:VARCHAR(100), title:VARCHAR(300), body:TEXT, data:JSON, priority:VARCHAR(10), channel:VARCHAR(10), read_at:DATETIME, created_at:DATETIME, expires_at:DATETIME, email_status:VARCHAR(20), email_error:TEXT, email_sent_at:DATETIME, email_retry_count:INTEGER
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_notifications_created_at, ix_notifications_organization_id, ix_notifications_type, ix_notifications_user_id, ix_notifications_user_id_read_at

## oauth_accounts
- columns (6): id:CHAR(32)*, user_id:CHAR(32), provider:VARCHAR(6), provider_account_id:VARCHAR(255), provider_email:VARCHAR(320), created_at:DATETIME
- foreign keys: user_id->users.id
- indexes: none

## organization_api_keys
- columns (19): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), key_hash:VARCHAR(64), key_prefix:VARCHAR(10), scopes:JSON, expires_at:DATETIME, last_used_at:DATETIME, is_active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, revoked_at:DATETIME, rate_limit:INTEGER, rate_limit_period:VARCHAR(20), quota_limit:INTEGER, quota_period:VARCHAR(20), quota_used:INTEGER, quota_reset_at:DATETIME, scheduled_rotation_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_organization_api_keys_key_hash, ix_organization_api_keys_organization_id

## organization_branding
- columns (19): id:CHAR(32)*, organization_id:CHAR(32), logo_url:TEXT, favicon_url:TEXT, primary_color:VARCHAR(7), secondary_color:VARCHAR(7), accent_color:VARCHAR(7), font_family:VARCHAR(100), brand_name:VARCHAR(200), custom_css:TEXT, hide_platform_branding:BOOLEAN, company_email:VARCHAR(254), support_email:VARCHAR(254), email_sender_name:VARCHAR(200), email_sender_email:VARCHAR(254), custom_js:TEXT, is_active:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## organization_llm_configs
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), provider:VARCHAR(50), encrypted_api_key:VARCHAR(1000), is_active:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_organization_llm_configs_organization_id

## organization_members
- columns (12): id:CHAR(32)*, organization_id:CHAR(32), user_id:CHAR(32), role:VARCHAR(7), invited_by:CHAR(32), joined_at:DATETIME, daily_request_limit:INTEGER, max_documents:INTEGER, max_conversations:INTEGER, can_create_workspaces:BOOLEAN, can_create_teams:BOOLEAN, can_invite_members:BOOLEAN
- foreign keys: invited_by->users.id, organization_id->organizations.id, user_id->users.id
- indexes: ix_organization_members_organization_id, ix_organization_members_user_id

## organization_quotas
- columns (14): id:CHAR(32)*, organization_id:CHAR(32), max_users:INTEGER, max_workspaces:INTEGER, max_teams:INTEGER, max_documents:INTEGER, max_storage_mb:INTEGER, max_requests_per_month:INTEGER, max_requests_per_day:INTEGER, max_api_calls:INTEGER, max_agents:INTEGER, max_kb_size_mb:INTEGER, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## organization_settings
- columns (5): id:CHAR(32)*, organization_id:CHAR(32), settings:JSON, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## organization_usage
- columns (5): id:CHAR(32)*, organization_id:CHAR(32), date:DATE, metric:VARCHAR(64), value:INTEGER
- foreign keys: organization_id->organizations.id
- indexes: none

## organization_usage_details
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), user_id:CHAR(32), timestamp:DATETIME, metric:VARCHAR(64), value:INTEGER, metadata_json:JSON
- foreign keys: organization_id->organizations.id, user_id->users.id
- indexes: ix_organization_usage_details_org_metric_timestamp

## organizations
- columns (10): id:CHAR(32)*, name:VARCHAR(200), slug:VARCHAR(200), created_at:DATETIME, updated_at:DATETIME, is_suspended:BOOLEAN, suspended_at:DATETIME, suspended_reason:VARCHAR(500), billing_country:VARCHAR(2), bm25_corpus_revision:BIGINT
- foreign keys: none
- indexes: ix_organizations_slug

## partner_commissions
- columns (8): id:CHAR(32)*, reseller_id:CHAR(32), period_start:DATE, period_end:DATE, amount_cents:INTEGER, status:VARCHAR(7), paid_at:DATETIME, created_at:DATETIME
- foreign keys: reseller_id->resellers.id
- indexes: ix_partner_commissions_reseller_id

## password_history
- columns (5): id:CHAR(32)*, user_id:CHAR(32), password_hash:VARCHAR(255), created_at:DATETIME, sequence:BIGINT
- foreign keys: user_id->users.id
- indexes: ix_password_history_created_at, ix_password_history_user_id

## password_reset_tokens
- columns (6): id:CHAR(32)*, user_id:CHAR(32), token_hash:VARCHAR(64), created_at:DATETIME, expires_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_password_reset_tokens_token_hash

## payment_customers
- columns (5): id:CHAR(32)*, organization_id:CHAR(32), provider:VARCHAR(8), external_customer_id:VARCHAR(100), created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_payment_customers_organization_id

## payment_events
- columns (5): provider:VARCHAR(8)*, id:VARCHAR(100)*, type:VARCHAR(100), processed_at:DATETIME, payload_summary:TEXT
- foreign keys: none
- indexes: none

## permission_groups
- columns (4): id:CHAR(32)*, key:VARCHAR(50), label:VARCHAR(100), sort_order:INTEGER
- foreign keys: none
- indexes: none

## permissions
- columns (6): id:CHAR(32)*, key:VARCHAR(100), resource:VARCHAR(50), action:VARCHAR(20), description:VARCHAR(255), group_id:CHAR(32)
- foreign keys: group_id->permission_groups.id
- indexes: ix_permissions_key, ix_permissions_resource

## plans
- columns (22): id:CHAR(32)*, key:VARCHAR(50), name:VARCHAR(100), monthly_price_cents:INTEGER, yearly_price_cents:INTEGER, max_documents:INTEGER, max_agents:INTEGER, max_members:INTEGER, max_api_keys:INTEGER, max_webhooks:INTEGER, max_requests_per_month:INTEGER, monthly_credits_included:INTEGER, priority_support:BOOLEAN, advanced_features:BOOLEAN, sla:BOOLEAN, stripe_product_id:VARCHAR(100), stripe_price_id_monthly:VARCHAR(100), stripe_price_id_yearly:VARCHAR(100), paystack_plan_code_monthly:VARCHAR(100), paystack_plan_code_yearly:VARCHAR(100), is_active:BOOLEAN, created_at:DATETIME
- foreign keys: none
- indexes: none

## plugin_executions
- columns (12): id:CHAR(32)*, plugin_id:CHAR(32), organization_id:CHAR(32), installation_id:CHAR(32), hook:VARCHAR(50), status:VARCHAR(7), input_payload:JSON, output_payload:JSON, error_message:TEXT, duration_ms:INTEGER, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, installation_id->plugin_installations.id, organization_id->organizations.id, plugin_id->plugins.id
- indexes: ix_plugin_executions_created_at, ix_plugin_executions_organization_id, ix_plugin_executions_plugin_id

## plugin_installations
- columns (7): id:CHAR(32)*, plugin_id:CHAR(32), organization_id:CHAR(32), enabled:BOOLEAN, config:JSON, installed_by:CHAR(32), installed_at:DATETIME
- foreign keys: installed_by->users.id, organization_id->organizations.id, plugin_id->plugins.id
- indexes: ix_plugin_installations_organization_id, ix_plugin_installations_plugin_id

## plugin_reviews
- columns (8): id:CHAR(32)*, plugin_id:CHAR(32), organization_id:CHAR(32), user_id:CHAR(32), rating:INTEGER, comment:TEXT, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id, plugin_id->plugins.id, user_id->users.id
- indexes: ix_plugin_reviews_plugin_id

## plugin_versions
- columns (9): id:CHAR(32)*, plugin_id:CHAR(32), version:VARCHAR(50), manifest:JSON, code_key:VARCHAR(500), code_size_bytes:INTEGER, changelog:TEXT, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, plugin_id->plugins.id
- indexes: ix_plugin_versions_plugin_id

## plugins
- columns (18): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), slug:VARCHAR(100), description:TEXT, category:VARCHAR(13), pricing:VARCHAR(8), price:NUMERIC(10, 2), manifest:JSON, version:VARCHAR(50), code_key:VARCHAR(500), code_size_bytes:INTEGER, status:VARCHAR(9), rejection_reason:TEXT, install_count:INTEGER, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_plugins_organization_id

## question_set_items
- columns (5): id:CHAR(32)*, question_set_id:CHAR(32), question_id:CHAR(32), position:INTEGER, created_at:DATETIME
- foreign keys: question_id->evaluation_questions.id, question_set_id->question_sets.id
- indexes: ix_question_set_items_question_id, ix_question_set_items_question_set_id

## question_sets
- columns (7): id:CHAR(32)*, dataset_id:CHAR(32), name:VARCHAR(200), description:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, dataset_id->evaluation_datasets.id
- indexes: ix_question_sets_dataset_id

## rag_experiments
- columns (11): id:CHAR(32)*, organization_id:CHAR(32), config_hash:VARCHAR(64), config_json:JSON, source:VARCHAR(50), baseline_job_id:CHAR(32), candidate_job_id:CHAR(32), decision:VARCHAR(30), metrics_json:JSON, created_by:CHAR(32), created_at:DATETIME
- foreign keys: baseline_job_id->evaluation_jobs.id, candidate_job_id->evaluation_jobs.id, created_by->users.id, organization_id->organizations.id
- indexes: ix_rag_experiments_config_hash, ix_rag_experiments_organization_id

## regeneration_history
- columns (5): id:CHAR(32)*, original_message_id:CHAR(32), new_message_id:CHAR(32), version:INTEGER, regenerated_at:DATETIME
- foreign keys: new_message_id->conversation_messages.id, original_message_id->conversation_messages.id
- indexes: ix_regeneration_history_original_message_id

## regression_detections
- columns (10): id:CHAR(32)*, job_id:CHAR(32), metric:VARCHAR(50), previous_value:FLOAT, current_value:FLOAT, change_percentage:FLOAT, severity:VARCHAR(20), detected_at:DATETIME, resolved_at:DATETIME, resolved_by:CHAR(32)
- foreign keys: job_id->evaluation_jobs.id, resolved_by->users.id
- indexes: ix_regression_detections_job_id

## regression_thresholds
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), metric:VARCHAR(50), threshold:FLOAT, severity:VARCHAR(20), enabled:BOOLEAN, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_regression_thresholds_organization_id

## reindex_schedules
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), schedule_name:VARCHAR(200), cron_pattern:VARCHAR(100), enabled:BOOLEAN, last_run_at:DATETIME, next_run_at:DATETIME, created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_reindex_schedules_organization_id

## resellers
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), commission_percent:INTEGER, is_active:BOOLEAN, referral_code:VARCHAR(16), created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## resource_permissions
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), resource_type:VARCHAR(50), resource_id:CHAR(32), user_id:CHAR(32), action:VARCHAR(50), granted_by:CHAR(32), granted_at:DATETIME, expires_at:DATETIME
- foreign keys: granted_by->users.id, organization_id->organizations.id, user_id->users.id
- indexes: ix_resource_permissions_organization_id, ix_resource_permissions_resource, ix_resource_permissions_user_id

## responses
- columns (30): id:CHAR(32)*, organization_id:CHAR(32), workspace_id:CHAR(32), query:TEXT, answer:TEXT, created_by:CHAR(32), created_at:DATETIME, confidence_score:FLOAT, confidence_factors:JSON, confidence_estimation:FLOAT, confidence_estimation_factors:JSON, claim_verification_status:VARCHAR(20), claim_verification_details:JSON, has_contradictions:BOOLEAN, contradictions:JSON, source_consistency_score:FLOAT, source_consistency_details:JSON, hallucination_score:FLOAT, hallucination_factors:JSON, groundedness_score:FLOAT, groundedness_factors:JSON, has_unsupported_claims:BOOLEAN, unsupported_claims:JSON, faithfulness_score:FLOAT, faithfulness_factors:JSON, retrieval_strategy:VARCHAR(20), embedding_model:VARCHAR(200), llm_provider:VARCHAR(50), llm_model:VARCHAR(200), flight_recording_id:CHAR(32)
- foreign keys: created_by->users.id, flight_recording_id->flight_recordings.id, organization_id->organizations.id, workspace_id->workspaces.id
- indexes: ix_responses_organization_id

## retrieval_diagnostics
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), query:TEXT, strategy:VARCHAR(30), final_chunks:JSON, result_count:INTEGER, latency_ms:INTEGER, created_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: ix_retrieval_diagnostics_organization_id

## revoked_access_tokens
- columns (5): id:CHAR(32)*, user_id:CHAR(32), jti:VARCHAR(36), revoked_at:DATETIME, expires_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_revoked_access_tokens_jti

## role_permissions
- columns (3): id:CHAR(32)*, role_id:CHAR(32), permission_id:CHAR(32)
- foreign keys: permission_id->permissions.id, role_id->custom_roles.id
- indexes: ix_role_permissions_permission_id, ix_role_permissions_role_id

## sandbox_environments
- columns (9): id:UUID*, organization_id:UUID, name:VARCHAR(255), api_key_id:UUID, data_ttl_hours:INTEGER, is_active:BOOLEAN, expires_at:DATETIME, created_at:DATETIME, updated_at:DATETIME
- foreign keys: api_key_id->organization_api_keys.id, organization_id->organizations.id
- indexes: ix_sandbox_environments_organization_id

## scim_tokens
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), token_hash:VARCHAR(64), created_by:CHAR(32), created_at:DATETIME, last_used_at:DATETIME, revoked_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_scim_tokens_organization_id, ix_scim_tokens_token_hash

## security_alerts
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), vulnerability_id:CHAR(32), message:VARCHAR(500), severity:VARCHAR(8), dismissed_at:DATETIME, dismissed_by:CHAR(32), created_at:DATETIME
- foreign keys: dismissed_by->users.id, organization_id->organizations.id, vulnerability_id->vulnerabilities.id
- indexes: ix_security_alerts_organization_id

## security_policies
- columns (9): id:CHAR(32)*, organization_id:CHAR(32), require_2fa_for_admins:BOOLEAN, session_timeout_minutes:INTEGER, max_login_attempts:INTEGER, ip_allowlist:TEXT, min_password_strength_bits:INTEGER, auto_lock_after_failed_attempts:BOOLEAN, updated_at:DATETIME
- foreign keys: organization_id->organizations.id
- indexes: none

## security_scans
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), scan_type:VARCHAR(14), status:VARCHAR(11), summary:TEXT, triggered_by:CHAR(32), started_at:DATETIME, completed_at:DATETIME
- foreign keys: organization_id->organizations.id, triggered_by->users.id
- indexes: ix_security_scans_organization_id

## sessions
- columns (10): id:CHAR(32)*, user_id:CHAR(32), refresh_token_hash:VARCHAR(64), access_token_jti:VARCHAR(36), device_info:VARCHAR(500), ip_address:VARCHAR(45), created_at:DATETIME, last_seen_at:DATETIME, expires_at:DATETIME, revoked_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_sessions_refresh_token_hash

## slack_integrations
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), team_id:VARCHAR(32), team_name:VARCHAR(255), bot_token:TEXT, user_token:TEXT, webhook_url:VARCHAR(1024), default_channel:VARCHAR(64), agent_id:CHAR(32), created_by:CHAR(32), is_active:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id, organization_id->organizations.id
- indexes: ix_slack_integrations_organization_id

## slack_messages
- columns (13): id:CHAR(32)*, integration_id:CHAR(32), conversation_id:CHAR(32), slack_message_ts:VARCHAR(32), slack_channel:VARCHAR(64), slack_user_id:VARCHAR(32), slack_user_name:VARCHAR(255), content:TEXT, response:TEXT, thread_ts:VARCHAR(32), status:VARCHAR(16), created_at:DATETIME, processed_at:DATETIME
- foreign keys: conversation_id->conversations.id, integration_id->slack_integrations.id
- indexes: ix_slack_messages_integration_id

## sms_messages
- columns (10): id:CHAR(32)*, organization_id:CHAR(32), channel:VARCHAR(8), to_number:VARCHAR(32), body:TEXT, status:VARCHAR(6), provider_message_id:VARCHAR(64), error:TEXT, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_sms_messages_created_at, ix_sms_messages_organization_id

## ssl_certificates
- columns (13): id:CHAR(32)*, domain:VARCHAR(255), status:VARCHAR(20), cert_pem:TEXT, key_pem_encrypted:TEXT, chain_pem:TEXT, expires_at:DATETIME, acme_order_url:VARCHAR(500), acme_challenge_url:VARCHAR(500), dns01_record_name:VARCHAR(300), dns01_record_value:VARCHAR(200), created_at:DATETIME, updated_at:DATETIME
- foreign keys: domain->custom_domains.domain
- indexes: none

## sub_clients
- columns (4): id:CHAR(32)*, reseller_id:CHAR(32), organization_id:CHAR(32), created_at:DATETIME
- foreign keys: organization_id->organizations.id, reseller_id->resellers.id
- indexes: ix_sub_clients_reseller_id

## subscriptions
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), plan_id:CHAR(32), status:VARCHAR(8), billing_period:VARCHAR(10), stripe_subscription_id:VARCHAR(100), paystack_subscription_code:VARCHAR(100), trial_ends_at:DATETIME, current_period_end:DATETIME, canceled_at:DATETIME, cancel_reason:VARCHAR(500), created_at:DATETIME, updated_at:DATETIME
- foreign keys: organization_id->organizations.id, plan_id->plans.id
- indexes: none

## support_ticket_responses
- columns (6): id:CHAR(32)*, ticket_id:CHAR(32), body:TEXT, is_staff:BOOLEAN, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, ticket_id->support_tickets.id
- indexes: ix_support_ticket_responses_ticket_id

## support_tickets
- columns (10): id:CHAR(32)*, organization_id:CHAR(32), subject:VARCHAR(200), description:TEXT, priority:VARCHAR(8), status:VARCHAR(11), created_by:CHAR(32), first_responded_at:DATETIME, created_at:DATETIME, resolved_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_support_tickets_created_at, ix_support_tickets_organization_id

## system_logs
- columns (9): id:CHAR(32)*, level:VARCHAR(10), logger_name:VARCHAR(200), message:TEXT, module:VARCHAR(200), function:VARCHAR(200), line:INTEGER, request_id:VARCHAR(64), created_at:DATETIME
- foreign keys: none
- indexes: ix_system_logs_created_at, ix_system_logs_level, ix_system_logs_logger_name, ix_system_logs_request_id

## task_plans
- columns (6): id:CHAR(32)*, objective:TEXT, status:VARCHAR(20), created_at:DATETIME, updated_at:DATETIME, metadata_json:JSON
- foreign keys: none
- indexes: none

## task_steps
- columns (10): id:CHAR(32)*, plan_id:CHAR(32), description:TEXT, status:VARCHAR(20), sequence:INTEGER, dependencies:JSON, result:TEXT, error:TEXT, created_at:DATETIME, completed_at:DATETIME
- foreign keys: plan_id->task_plans.id
- indexes: none

## team_members
- columns (5): id:CHAR(32)*, team_id:CHAR(32), user_id:CHAR(32), role:VARCHAR(6), joined_at:DATETIME
- foreign keys: team_id->teams.id, user_id->users.id
- indexes: ix_team_members_team_id, ix_team_members_user_id

## teams
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_teams_organization_id

## teams_integrations
- columns (14): id:CHAR(32)*, organization_id:CHAR(32), tenant_id:VARCHAR(64), team_id:VARCHAR(64), team_name:VARCHAR(255), bot_id:VARCHAR(64), bot_token:TEXT, webhook_url:VARCHAR(1024), default_channel:VARCHAR(64), agent_id:CHAR(32), created_by:CHAR(32), is_active:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: agent_id->agents.id, created_by->users.id, organization_id->organizations.id
- indexes: ix_teams_integrations_organization_id

## teams_messages
- columns (13): id:CHAR(32)*, integration_id:CHAR(32), conversation_id:CHAR(32), teams_message_id:VARCHAR(128), teams_channel:VARCHAR(128), teams_user_id:VARCHAR(128), teams_user_name:VARCHAR(255), content:TEXT, response:TEXT, reply_to_id:VARCHAR(128), status:VARCHAR(16), created_at:DATETIME, processed_at:DATETIME
- foreign keys: conversation_id->conversations.id, integration_id->teams_integrations.id
- indexes: ix_teams_messages_integration_id

## tool_budgets
- columns (5): tool_name:VARCHAR(200)*, budget_limit:INTEGER, tokens_used:INTEGER, updated_by:CHAR(32), updated_at:DATETIME
- foreign keys: updated_by->users.id
- indexes: none

## tool_fallbacks
- columns (6): id:CHAR(32)*, tool_name:VARCHAR(200), fallback_tool:VARCHAR(200), priority:INTEGER, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id
- indexes: none

## tool_permissions
- columns (8): id:CHAR(32)*, organization_id:CHAR(32), agent_id:VARCHAR(200), user_id:CHAR(32), tool_name:VARCHAR(200), permission:VARCHAR(10), created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id, user_id->users.id
- indexes: none

## tool_timeout_overrides
- columns (4): tool_name:VARCHAR(200)*, timeout_seconds:FLOAT, updated_by:CHAR(32), updated_at:DATETIME
- foreign keys: updated_by->users.id
- indexes: none

## two_factor_lockout_recovery_tokens
- columns (6): id:CHAR(32)*, user_id:CHAR(32), token_hash:VARCHAR(64), created_at:DATETIME, expires_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_two_factor_lockout_recovery_tokens_token_hash

## two_factor_recovery_codes
- columns (5): id:CHAR(32)*, user_id:CHAR(32), code_hash:VARCHAR(64), created_at:DATETIME, used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: none

## usage_alerts
- columns (6): id:CHAR(32)*, organization_id:CHAR(32), resource_type:VARCHAR(64), threshold_percent:INTEGER, created_by:CHAR(32), created_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_usage_alerts_organization_id

## user_custom_roles
- columns (5): id:CHAR(32)*, user_id:CHAR(32), role_id:CHAR(32), assigned_by:CHAR(32), assigned_at:DATETIME
- foreign keys: assigned_by->users.id, role_id->custom_roles.id, user_id->users.id
- indexes: ix_user_custom_roles_role_id, ix_user_custom_roles_user_id

## users
- columns (26): id:CHAR(32)*, email:VARCHAR(320), hashed_password:VARCHAR(255), is_active:BOOLEAN, is_email_verified:BOOLEAN, role:VARCHAR(10), suspended_at:DATETIME, suspended_reason:VARCHAR(500), failed_login_attempts:INTEGER, locked_until:DATETIME, totp_secret:VARCHAR(64), totp_enabled:BOOLEAN, full_name:VARCHAR(200), company:VARCHAR(200), job_title:VARCHAR(200), avatar_url:VARCHAR(1000), locale:VARCHAR(10), timezone:VARCHAR(64), consent_given_at:DATETIME, terms_version:VARCHAR(20), consent_withdrawn_at:DATETIME, deleted_at:DATETIME, deletion_scheduled_at:DATETIME, deletion_reminder_sent_at:DATETIME, created_at:DATETIME, updated_at:DATETIME
- foreign keys: none
- indexes: ix_users_email

## voice_messages
- columns (9): id:CHAR(32)*, conversation_id:CHAR(32), user_id:CHAR(32), type:VARCHAR(20), audio_key:VARCHAR(500), transcription:TEXT, duration_ms:INTEGER, language:VARCHAR(10), created_at:DATETIME
- foreign keys: conversation_id->conversations.id, user_id->users.id
- indexes: ix_voice_messages_conversation_id

## voice_settings
- columns (15): id:CHAR(32)*, user_id:CHAR(32), language:VARCHAR(10), tts_provider:VARCHAR(20), tts_voice:VARCHAR(100), tts_speed:FLOAT, tts_pitch:FLOAT, tts_volume:FLOAT, stt_provider:VARCHAR(20), stt_language:VARCHAR(10), vad_enabled:BOOLEAN, vad_threshold:FLOAT, audio_history_enabled:BOOLEAN, push_to_talk_enabled:BOOLEAN, updated_at:DATETIME
- foreign keys: user_id->users.id
- indexes: none

## vulnerabilities
- columns (9): id:CHAR(32)*, scan_id:CHAR(32), severity:VARCHAR(8), status:VARCHAR(14), title:VARCHAR(255), description:TEXT, location:VARCHAR(500), cve_id:VARCHAR(50), created_at:DATETIME
- foreign keys: scan_id->security_scans.id
- indexes: ix_vulnerabilities_scan_id

## webauthn_credentials
- columns (9): id:CHAR(32)*, user_id:CHAR(32), credential_id:BLOB, public_key:BLOB, sign_count:INTEGER, transports:VARCHAR(200), nickname:VARCHAR(100), created_at:DATETIME, last_used_at:DATETIME
- foreign keys: user_id->users.id
- indexes: ix_webauthn_credentials_credential_id, ix_webauthn_credentials_user_id

## webhook_deliveries
- columns (10): id:CHAR(32)*, webhook_id:CHAR(32), event:VARCHAR(50), payload:JSON, status_code:INTEGER, response_body:TEXT, error:TEXT, attempt:INTEGER, delivered_at:DATETIME, created_at:DATETIME
- foreign keys: webhook_id->webhooks.id
- indexes: ix_webhook_deliveries_webhook_id

## webhooks
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), url:VARCHAR(2048), events:JSON, headers:JSON, secret:VARCHAR(200), is_active:BOOLEAN, retry_count:INTEGER, timeout:INTEGER, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_webhooks_organization_id

## widget_configs
- columns (36): id:CHAR(32)*, organization_id:CHAR(32), agent_id:CHAR(32), created_by:CHAR(32), public_key:VARCHAR(64), allowed_domains:JSON, logo_url:VARCHAR(1024), primary_color:VARCHAR(9), secondary_color:VARCHAR(9), text_color:VARCHAR(9), background_color:VARCHAR(9), header_background:VARCHAR(9), border_radius:VARCHAR(16), font_family:VARCHAR(128), widget_name:VARCHAR(50), widget_name_enabled:BOOLEAN, widget_short_name:VARCHAR(12), avatar_url:VARCHAR(1024), avatar_uploaded_at:DATETIME, avatar_updated_by:CHAR(32), use_default_avatar:BOOLEAN, welcome_message:TEXT, welcome_message_enabled:BOOLEAN, welcome_message_updated_at:DATETIME, welcome_message_updated_by:CHAR(32), position:VARCHAR(16), position_mobile:VARCHAR(16), offset_x:INTEGER, offset_y:INTEGER, position_locked:BOOLEAN, language:VARCHAR(8), auto_detect_language:BOOLEAN, theme:VARCHAR(8), theme_custom_css:TEXT, created_at:DATETIME, updated_at:DATETIME
- foreign keys: agent_id->agents.id, avatar_updated_by->users.id, created_by->users.id, organization_id->organizations.id, welcome_message_updated_by->users.id
- indexes: ix_widget_configs_organization_id, ix_widget_configs_public_key

## widget_suggested_questions
- columns (8): id:CHAR(32)*, widget_config_id:CHAR(32), question:TEXT, label:VARCHAR(64), position:INTEGER, is_active:BOOLEAN, created_at:DATETIME, updated_at:DATETIME
- foreign keys: widget_config_id->widget_configs.id
- indexes: ix_widget_suggested_questions_widget_config_id

## workflow_human_inputs
- columns (13): id:CHAR(32)*, workflow_run_id:CHAR(32), node_id:VARCHAR(200), message:TEXT, input_type:VARCHAR(20), options:JSON, required:BOOLEAN, status:VARCHAR(10), value:JSON, submitted_by:CHAR(32), submitted_at:DATETIME, created_at:DATETIME, expires_at:DATETIME
- foreign keys: submitted_by->users.id, workflow_run_id->workflow_runs.id
- indexes: none

## workflow_node_executions
- columns (11): id:CHAR(32)*, workflow_run_id:CHAR(32), step_number:INTEGER, node_id:VARCHAR(64), node_type:VARCHAR(50), input:JSON, output:JSON, duration_ms:INTEGER, status:VARCHAR(20), error:TEXT, created_at:DATETIME
- foreign keys: workflow_run_id->workflow_runs.id
- indexes: ix_workflow_node_executions_workflow_run_id

## workflow_runs
- columns (11): id:CHAR(32)*, workflow_id:CHAR(32), trigger_id:CHAR(32), status:VARCHAR(20), input:JSON, output:JSON, error:TEXT, context:JSON, current_node_id:VARCHAR(64), started_at:DATETIME, completed_at:DATETIME
- foreign keys: trigger_id->workflow_triggers.id, workflow_id->workflows.id
- indexes: ix_workflow_runs_status, ix_workflow_runs_workflow_id

## workflow_triggers
- columns (7): id:CHAR(32)*, workflow_id:CHAR(32), type:VARCHAR(20), config:JSON, webhook_token:VARCHAR(64), created_at:DATETIME, last_run_at:DATETIME
- foreign keys: workflow_id->workflows.id
- indexes: ix_workflow_triggers_workflow_id

## workflow_versions
- columns (8): id:CHAR(32)*, workflow_id:CHAR(32), version_number:INTEGER, nodes:JSON, edges:JSON, created_by:CHAR(32), created_at:DATETIME, comment:TEXT
- foreign keys: created_by->users.id, workflow_id->workflows.id
- indexes: ix_workflow_versions_workflow_id

## workflows
- columns (13): id:CHAR(32)*, organization_id:CHAR(32), workspace_id:CHAR(32), name:VARCHAR(200), description:TEXT, nodes:JSON, edges:JSON, variables:JSON, status:VARCHAR(10), created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME, deleted_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id, workspace_id->workspaces.id
- indexes: ix_workflows_organization_id, ix_workflows_workspace_id

## workspaces
- columns (7): id:CHAR(32)*, organization_id:CHAR(32), name:VARCHAR(200), description:TEXT, created_by:CHAR(32), created_at:DATETIME, updated_at:DATETIME
- foreign keys: created_by->users.id, organization_id->organizations.id
- indexes: ix_workspaces_organization_id
