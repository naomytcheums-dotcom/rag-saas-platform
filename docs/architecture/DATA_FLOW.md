# Data Flow

Flux end-to-end des 4 pipelines principaux.
Pour les composants, voir OVERVIEW.md.
Pour le RAG detaille, voir docs/advanced/RAG_PIPELINE.md.

## 1. Ingestion de documents

Upload (API)
  -> stockage S3/R2 + row Document (status=pending)
  -> tache Celery dispatchee
  -> extraction (PDF/DOCX/HTML/... via parseurs dedies)
  -> nettoyage (markdown, normalisation)
  -> chunking (semantique, markdown, code, paragraphe...)
  -> embedding (provider configure par org)
  -> insertion pgvector (chunks + metadonnees)
  -> Document.status = completed
  -> notification user (in-app + email)

Idempotence : reindex possible via Document.modification_check.

Points d entree : api/tasks/document_processing.py,
api/services/document_extraction.py, api/services/chunking.py.

## 2. Chat RAG

User query (API ou SSE)
  -> auth + permission check
  -> resolution config (LLM provider, modele, temperature)
  -> retrieval hybride (BM25 + vecteur pgvector)
  -> rerank (cross-encoder ou MMR)
  -> assemblage contexte + citations candidates
  -> LLM call (streaming ou non)
  -> post-traitement : citations persistees, confidence, groundedness
  -> stream tokens au client (SSE)
  -> debit credits (tokens_input + tokens_output)

Points d entree : api/services/rag.py, api/services/generation.py,
api/services/streaming.py, api/services/citations.py.

## 3. Agents

Agent run (API)
  -> creation AgentRunRecord (status=running)
  -> chargement short-term memory (session)
  -> chargement long-term memory (cross-run, par agent+user)
  -> selection tools (permission + pertinence)
  -> boucle LLM : LLM repond (texte ou tool_calls)
  -> si tool_calls : validation, execution, feedback role:tool, reprise
  -> si reponse finale : break
  -> guardrails (validation finale)
  -> write-back long-term memory (best-effort, LLM extraction)
  -> AgentRunRecord (status=completed, result, trace)

Non-streaming : AgentOrchestrator.run_agent (boucle complete).
Streaming : AgentOrchestrator.stream_response
ATTENTION : tools non executes aujourd hui (selection uniquement, voir ROADMAP P2 #4).

Points d entree : api/services/agent_orchestrator.py,
api/services/agent_tools.py, api/services/agent_long_term_memory.py.

## 4. Workflows

Trigger (webhook / schedule / manual)
  -> WorkflowRun cree (status=pending)
  -> tache Celery dispatchee
  -> execution sequentielle des blocs :
    - code (expression AST eval)
    - http (requete externe)
    - llm (appel LLM)
    - rag (retrieval + generation)
    - condition (branchement)
    - human (approbation)
    - email, calendar, database...
  -> WorkflowRun.status = completed + output

Points d entree : api/services/workflow_engine.py,
api/tasks/workflow_runs.py, api/services/workflow_blocks/.

## Flux transverses

### Notifications

Evenement (billing, workflow, member, quota...)
  -> api/services/notifications.py
  -> NotificationTemplate (DB override ou code default)
  -> Notification (in-app)
  -> NotificationDelivery (email, si configure)
  -> envoi Twilio (SMS/WhatsApp) si active

### Billing

Evenement provider (Stripe/Paystack webhook)
  -> verification signature
  -> handle_stripe_webhook / handle_paystack_webhook
  -> PaymentEvent (idempotent)
  -> mise a jour Subscription
  -> notification (payment_failed, payment_succeeded...)
  -> debit/credit credits (AI Pack)

### Multi-tenancy

Chaque requete porte un org_id. Les checks sont doubles :
- Applicatif : require_permission("resource:action")
- DB : RLS PostgreSQL (org_id = current_setting(...))

Voir SECURITY.md.
