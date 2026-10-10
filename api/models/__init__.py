"""
Import every model module here so Base.metadata is fully populated as soon
as `api.models` is imported once -- Alembic's env.py and the test DB
fixture both rely on that (a model class that's never imported never
registers its table).

Hardening Mission, Phase 4 -- a real, confirmed, systemic audit finding:
this file was missing 38 of its own model modules (everything from
`acme_account` through `widget`), not just the 2 (`rag_experiment`,
`flight_recording`) an earlier pass of this same audit had already
found and fixed the SYMPTOM of (the "no such table: rag_experiments"
crash when test_rag_evolution_engine.py ran in isolation). The crash
only ever happened to NOT reproduce for most of these 38 in the full
test suite because `api.main` (imported once by every test via
conftest.py) transitively imports most routers, which transitively
import most of these models anyway BEFORE `Base.metadata.create_all()`
runs -- a real, fragile, import-ORDER-dependent accident, not a correct
design. Every model below is now imported directly, unconditionally,
here -- the single, real, authoritative source of truth this module's
own docstring already claimed to be.
"""

from api.database import Base
from api.models.acme_account import AcmeAccount
from api.models.admin import Plan, Subscription, SystemLog
from api.models.agent import Agent
from api.models.agent_api_key import AgentAPIKey
from api.models.agent_long_term_memory import AgentLongTermMemoryItem
from api.models.agent_memory import AgentMemoryItem, AgentSession
from api.models.agent_run import AgentRunRecord
from api.models.agent_trace import AgentTrace
from api.models.alerting import AlertChannel, AlertHistory, AlertRule, Incident
from api.models.analytics import AnalyticsAggregate, AnalyticsDashboard, AnalyticsEvent
from api.models.audit_log import AuditLog
from api.models.autonomous_agent import AgentCollaboration, AgentPlan, AgentStep, AutonomousAgent
from api.models.autonomous_agent import AgentMemory as AutonomousAgentMemory
from api.models.batch_job import BatchJob, BatchJobItem
from api.models.billing import Credit, CreditTransaction, Invoice, InvoiceLine, PaymentCustomer, PaymentEvent, UsageAlert
from api.models.chat_integrations import DiscordIntegration, DiscordMessage, SlackIntegration, SlackMessage, TeamsIntegration, TeamsMessage
from api.models.citation import Citation
from api.models.compliance import ConsentRecord, DataBreach, DataRequest
from api.models.consent_reactivation_token import ConsentReactivationToken
from api.models.conversation import Conversation, ConversationMessage
from api.models.conversation_share import ConversationShare
from api.models.custom_domain import CustomDomain
from api.models.custom_tool import CustomTool
from api.models.document import Document, DocumentAuditLog, DocumentChunk, DocumentTag, DocumentTagAssignment, DocumentVersion
import api.models.bm25_revision  # noqa: F401 -- registers SQLite corpus revision triggers
from api.models.document_image import DocumentImage
from api.models.encryption_audit import EncryptionAudit, EncryptionKeyRecord
from api.models.enterprise_sso import EnterpriseSSOAccount, EnterpriseSSOConnection
from api.models.escalation import Escalation, EscalationNote
from api.models.evaluation import (
    ABTest, ABTestAssignment, ABTestResult, BenchmarkVersion, ComparisonJob, DeploymentEvaluation, EvaluationDataset,
    EvaluationFailure, EvaluationJob, EvaluationQuestion, EvaluationResult, ManualEvaluation, QuestionSet,
    QuestionSetItem, RegressionDetection, RegressionThreshold,
)
from api.models.external_source import ExternalSource
from api.models.fine_tuning import FineTunedModel, FineTuningDataset, FineTuningEvaluation, FineTuningJob
from api.models.flight_recording import FlightRecording
from api.models.follow_up_question import FollowUpQuestion
from api.models.human_approval import HumanApproval
from api.models.integrations import AirbyteConnection, IntegrationConnection, IntegrationLog, IntegrationMapping
from api.models.invitation import Invitation
from api.models.jwt_signing_key import JWTSigningKey
from api.models.lockout_recovery_token import TwoFactorLockoutRecoveryToken
from api.models.mcp_server import MCPServerConfig, MCPToolCache
from api.models.media import MediaAsset, MediaFrame, MediaTranscript
from api.models.message_actions import MessageEditHistory, MessageFeedback, RegenerationHistory
from api.models.metadata_enrichment import DocumentEntity, DocumentKeyword
from api.models.oauth import OAuthAccount
from api.models.organization import Organization, OrganizationMember
from api.models.organization_api_key import KeyRotationHistory, OrganizationAPIKey
from api.models.organization_branding import OrganizationBranding
from api.models.organization_llm_config import OrganizationLLMConfig
from api.models.organization_quota import OrganizationQuota
from api.models.organization_settings import OrganizationSettings
from api.models.organization_usage import OrganizationUsage, OrganizationUsageDetail
from api.models.password_history import PasswordHistory
from api.models.plugins import Plugin, PluginExecution, PluginInstallation, PluginReview, PluginVersion
from api.models.rag_experiment import RagExperiment
from api.models.rbac import CustomRole, Permission, PermissionGroup, RolePermission, UserCustomRole
from api.models.recovery_code import TwoFactorRecoveryCode
from api.models.reindex_schedule import ReindexSchedule
from api.models.resource_permission import ResourcePermission
from api.models.response import Response
from api.models.retrieval_diagnostic import RetrievalDiagnostic
from api.models.restore_token import AccountRestoreToken
from api.models.revoked_token import RevokedAccessToken
from api.models.sales import License, PartnerCommission, Reseller, SubClient, SupportTicket, TicketResponse
from api.models.sandbox import SandboxEnvironment
from api.models.security_scan import SecurityAlert, SecurityPolicy, SecurityScan, Vulnerability
from api.models.session import Session
from api.models.sms import SmsMessage
from api.models.ssl_certificate import SSLCertificate
from api.models.team import Team, TeamMember
from api.models.token import EmailVerificationToken, PasswordResetToken
from api.models.task_plan import TaskPlan, TaskStep
from api.models.tool_config import ToolBudget, ToolTimeoutOverride
from api.models.tool_fallback import LlmFallback, ToolFallback
from api.models.tool_permission import ToolPermission
from api.models.user import User
from api.models.voice import CallRecord, VoiceMessage, VoiceSettings
from api.models.webauthn_credential import WebAuthnCredential
from api.models.webhook import Webhook, WebhookDelivery
from api.models.widget import WidgetConfig, WidgetSuggestedQuestion
from api.models.workflow import Workflow
from api.models.workflow_human_input import WorkflowHumanInput
from api.models.workflow_node_execution import WorkflowNodeExecution
from api.models.workflow_run import WorkflowRun, WorkflowTrigger
from api.models.workflow_version import WorkflowVersion
from api.models.workspace import Workspace
from api.models.notification import Notification, NotificationPreference
from api.models.notification_template import NotificationTemplate

__all__ = [
    "Base", "User", "OAuthAccount", "Session", "PasswordResetToken", "EmailVerificationToken",
    "TwoFactorRecoveryCode", "AccountRestoreToken", "TwoFactorLockoutRecoveryToken", "ConsentReactivationToken",
    "RevokedAccessToken", "PasswordHistory", "AuditLog", "JWTSigningKey", "WebAuthnCredential",
    "EnterpriseSSOConnection", "EnterpriseSSOAccount", "Organization", "OrganizationMember", "Workspace",
    "ResourcePermission", "Team", "TeamMember", "Invitation", "OrganizationQuota",
    "AgentRunRecord", "ToolPermission", "ToolTimeoutOverride", "ToolBudget", "ToolFallback", "LlmFallback",
    "HumanApproval", "AgentSession", "AgentMemoryItem", "Conversation", "ConversationMessage",
    "TaskPlan", "TaskStep", "AgentTrace", "Escalation", "Agent", "AgentAPIKey",
    "Workflow", "WorkflowTrigger", "WorkflowRun", "WorkflowHumanInput", "CustomTool", "WorkflowVersion",
    "Response", "Citation",
    # Hardening Mission, Phase 4 -- the 38 real, previously-unregistered modules.
    "AcmeAccount", "Plan", "Subscription", "SystemLog", "AlertChannel", "AlertHistory", "AlertRule", "Incident",
    "AnalyticsAggregate", "AnalyticsDashboard", "AnalyticsEvent", "AgentCollaboration", "AgentPlan", "AgentStep",
    "AutonomousAgent", "AutonomousAgentMemory", "BatchJob", "BatchJobItem", "Credit", "CreditTransaction", "Invoice",
    "InvoiceLine", "PaymentCustomer", "PaymentEvent", "UsageAlert", "DiscordIntegration", "DiscordMessage",
    "SlackIntegration", "SlackMessage", "TeamsIntegration", "TeamsMessage", "ConsentRecord", "DataBreach",
    "DataRequest", "ConversationShare", "CustomDomain", "Document", "DocumentAuditLog", "DocumentChunk",
    "DocumentTag", "DocumentTagAssignment", "DocumentVersion", "DocumentImage", "EncryptionAudit",
    "EncryptionKeyRecord", "ABTest", "ABTestAssignment", "ABTestResult", "BenchmarkVersion", "ComparisonJob",
    "DeploymentEvaluation", "EvaluationDataset", "EvaluationFailure", "EvaluationJob", "EvaluationQuestion",
    "EvaluationResult", "ManualEvaluation", "QuestionSet", "QuestionSetItem", "RegressionDetection",
    "RegressionThreshold", "ExternalSource", "FineTunedModel", "FineTuningDataset", "FineTuningEvaluation",
    "FineTuningJob", "FlightRecording", "FollowUpQuestion", "AirbyteConnection", "IntegrationConnection",
    "IntegrationLog", "IntegrationMapping", "MCPServerConfig", "MCPToolCache", "MediaAsset", "MediaFrame",
    "MediaTranscript", "MessageEditHistory", "MessageFeedback", "RegenerationHistory", "DocumentEntity",
    "DocumentKeyword", "KeyRotationHistory", "OrganizationAPIKey", "OrganizationBranding", "OrganizationLLMConfig",
    "OrganizationSettings", "OrganizationUsage", "OrganizationUsageDetail", "Plugin", "PluginExecution",
    "PluginInstallation", "PluginReview", "PluginVersion", "RagExperiment", "CustomRole", "Permission",
    "PermissionGroup", "RolePermission", "UserCustomRole", "ReindexSchedule", "RetrievalDiagnostic", "License",
    "PartnerCommission", "Reseller", "SubClient", "SupportTicket", "TicketResponse", "SandboxEnvironment",
    "SecurityAlert", "SecurityPolicy", "SecurityScan", "Vulnerability", "SmsMessage", "SSLCertificate",
    "CallRecord", "VoiceMessage", "VoiceSettings", "Webhook", "WebhookDelivery", "WidgetConfig",
    "WidgetSuggestedQuestion", "WorkflowNodeExecution", "Notification", "NotificationPreference",
    "NotificationTemplate",
]
