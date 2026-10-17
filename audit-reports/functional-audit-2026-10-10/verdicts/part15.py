# Part 15 - Human-in-the-loop. Facts read: api/models/escalation.py (Escalation: id, agent_run_id, organization_id, issue, context JSON, priority, status, resolution, assignee_id, created_at, resolved_at);
# the only code using it is api/tools/human_escalation.py and api/security/agents.py: NO router, no frontend page, no SLA column, no internal-notes column. api/routers/feedback.py offers POST/GET/PATCH/DELETE message feedback and org stats.
# No code that turns feedback into evaluation cases was found (grep for feedback-to-dataset conversion returned nothing).
VC, PI, NI, IU, BE, BR, AM = ("VERIFIED_COMPLETE", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "IMPLEMENTED_UNVERIFIED",
                              "BLOCKED_EXTERNAL", "BROKEN", "AMBIGUOUS_REQUIREMENT")
ESC = "api/models/escalation.py + api/tools/human_escalation.py"
ET = "tests/test_human_escalation.py"
NOAPI = "no API route or screen lets a human list, assign or resolve tickets"
V = {
"15.1.1": (PI, "HIGH", ESC + " (escalations.id UUID)", ET, "org column present", NOAPI, "none", "MEDIUM", "add ticket API"),
"15.1.2": (PI, "HIGH", ESC + " (priority column and enum)", ET, "none", NOAPI, "none", "MEDIUM", "add ticket API"),
"15.1.3": (PI, "HIGH", ESC + " (assignee_id column)", ET, "none", NOAPI + "; no assignment action", "none", "MEDIUM", "add assignment endpoint"),
"15.1.4": (NI, "HIGH", "none: no SLA or due-date column in api/models/escalation.py", "none", "n/a", "SLA absent", "none", "MEDIUM", "add SLA field and timers"),
"15.1.5": (PI, "HIGH", ESC + " (status column and enum, resolved_at)", ET, "none", NOAPI, "none", "MEDIUM", "add ticket API"),
"15.1.6": (NI, "HIGH", "none: no notes column or table related to escalations", "none", "n/a", "internal notes absent", "none", "LOW", "add notes"),
"15.1.7": (PI, "HIGH", ESC + " (context JSON column)", ET, "none", NOAPI, "none", "LOW", "expose in the ticket view"),
"15.1.8": (PI, "HIGH", ESC + " (resolution column)", ET, "none", NOAPI, "none", "MEDIUM", "add resolve endpoint"),
"15.1.9": (NI, "HIGH", "none: no router and no frontend page mention escalations (grep of api/routers and frontend/app)", "none", "n/a", "no human-agent dashboard", "none", "MEDIUM", "build the dashboard"),
"15.2.1": (PI, "HIGH", "api/routers/feedback.py (POST/GET/PATCH/DELETE /messages/{id}/feedback, GET /organizations/{id}/feedback/stats); frontend/components/FeedbackButtons.tsx used in MessageBubble.tsx", "feedback tests partial", "org-scoped", "thumbs up/down works in the chat UI; see 8.1.9 for field coverage", "none", "LOW", "none"),
"15.2.2": (PI, "MEDIUM", "feedback payload carries a reason (api/routers/feedback.py update_feedback takes reason)", "feedback tests partial", "none", "UI capture of reason categories not confirmed", "none", "LOW", "confirm UI"),
"15.2.3": (PI, "MEDIUM", "feedback comment field in the same router", "feedback tests partial", "none", "UI capture not confirmed", "none", "LOW", "confirm UI"),
"15.2.4": (NI, "MEDIUM", "none: no proposed-correction field found in feedback models/routes", "none", "n/a", "absent", "none", "LOW", "add field"),
"15.2.5": (PI, "MEDIUM", "failure analysis exists for evaluation runs (frontend/components/eval/FailureAnalysis.tsx, failure categories) but not applied to live user feedback", "Eval Lab tests", "none", "not connected to user feedback", "none", "LOW", "connect feedback to failure analysis"),
"15.2.6": (NI, "HIGH", "none: no code converts negative feedback into evaluation cases", "none", "n/a", "absent", "none", "MEDIUM", "implement feedback-to-dataset"),
"15.2.7": (PI, "LOW", "the pieces exist (Eval Lab, rag_evolution_engine.py, rag_control_plane.py) but the loop 'benchmark -> improvement' has never been run end to end on real data", "tests/test_rag_evolution_engine_retrieval.py, tests/test_rag_control_plane.py", "none", "never executed on real data", "LLM provider, dataset", "LOW", "run once with SQuAD"),
}
