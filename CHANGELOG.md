# Changelog

This project was built incrementally across 25 development parts
("Parties"), each independently audited, tested, and documented. This
file summarizes what each part shipped. For full detail — audit
findings, build-vs-reuse decisions, bugs found and fixed, test counts —
see [`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md), the
authoritative source.

Status markers below reflect `docs/CAHIER_DES_CHARGES.md` as of this
writing: ✅ complete, 🟡 partial.

## Partie 25 — Documentation finale

Complete project documentation: user/admin/developer/install guides,
API reference (including a live OpenAPI export), advanced guides,
tutorials, FAQ, diagrams, a docs site, contribution files, and
documentation tests (link/example/API-reference validation). Root
`README.md` rewritten to describe the actual platform (previously
described only the original `src/` demo, preserved at
[`src/README.md`](src/README.md)).

## Partie 24 — Fine-tuning ✅

Dataset upload/validation (JSONL), job submission to OpenAI and Mistral
via direct REST clients, fine-tuned model deployment, and evaluation of
fine-tuned models through the existing Evaluation Lab. Anthropic
fine-tuning explicitly unsupported and documented as such (no public
fine-tuning API). 34 backend tests, 10 frontend tests.

## Partie 23 — Agents autonomes ✅

Autonomous agents with real multi-step planning and execution (not a
single LLM call), persistent memory, bounded agent-to-agent
collaboration, guardrails, and — added in a follow-up finalization —
real per-step/per-agent USD cost tracking (`AUTONOMOUS_MAX_COST`). 35
backend tests.

## Partie 22 — Multi-modal (images, audio, vidéo) ✅

Image/audio/video media pipeline. Finalized across three follow-up
rounds: local YOLOv8 object detection, vision-in-documents wiring, and
real CLIP-based visual search (image-to-image and text-to-image) with a
faiss index.

## Partie 21 — A/B testing avancé ✅

Experiment configuration and statistical analysis for prompts, models,
and retrieval settings.

## Partie 20 — Analytics avancés ✅

Business, product, and technical analytics dashboards and metrics.

## Partie 19 — White-label complet ✅

Custom domains, DNS-01 SSL via a real ACME client (verified against
Let's Encrypt staging), custom email domains, platform branding removal.

## Partie 18 — Modèles de vente ✅

SaaS, self-hosted, partner, and white-label sales/deployment models.

## Partie 1-17 — Foundation (mixed status)

Multi-tenant structure and RBAC, universal knowledge base, the core RAG
pipeline, multi-LLM/embedding support, the agent and evaluation
subsystems, citations and anti-hallucination checks, the API surface,
security/governance foundations, the admin dashboard, billing, developer
experience tooling, human-in-the-loop approval, plugins, and the
marketplace. Several of these areas were marked partial at the time and
substantially extended by later parts (e.g. security and admin were
foundational here, then built out further in Parties 19-24's own
security/admin touchpoints). See
[`docs/CAHIER_DES_CHARGES.md`](docs/CAHIER_DES_CHARGES.md) for the
itemized per-part status.
