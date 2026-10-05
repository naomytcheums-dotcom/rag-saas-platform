# Évaluation de frameworks vocaux — 2026-10-03

## Périmètre et résultat

Recommandation pour **ce projet** : LiveKit Agents, dans un worker séparé.
Ce n'est pas une preuve qu'il est le « meilleur au monde ». Aucun framework
vocal ne remplace les contrôles multi-tenant de cette application.
**Aucune intégration temps réel ni dépendance LiveKit n'a été ajoutée au projet.**

### Existant réellement trouvé

- `api/services/voice.py` : STT LiteLLM Whisper/Deepgram, Whisper local
  optionnel, TTS et autres fonctions vocales.
- `docs/api/VOICE_AGENT.md` : endpoint existant
  `POST /voice/organizations/{org_id}/agent`, upload multipart, un tour
  audio → texte → RAG → réponse; ce n'est pas un micro WebRTC continu.
- `frontend/app/dashboard/voice-agent/` et `frontend/app/voice-demo/` existent.
- Recherche `livekit|pipecat|vocode|voice-agent|liverag|local-vai` dans sources
  API, frontend, SDK et manifests : aucune intégration LiveKit/Pipecat/Vocode
  trouvée; mention de `voice-agent` dans le schéma local.
- Des worktrees `.claude/worktrees` ont des composants voice_input; ils ne
  prouvent pas un clone upstream LiveKit. Les caches ont été exclus des
  inventaires de code; aucune modification de ces worktrees.
- Le remote du dépôt principal n'est pas un remote vocal selon le contrôle
  de ses noms; URL non imprimée. L'historique contient des commits de voix
  applicative, dont `d40ced5` et `f8480b8`.
- Aucun dépôt vocal tiers cloné dans le projet principal n'a été identifié
  par ces recherches. Un clone **d'évaluation nouveau**, externe au projet,
  a été créé comme décrit plus bas.

## Comparaison vérifiée

Chiffres GitHub observés le 2026-10-03; ils peuvent changer. « Multi-tenant »
ci-dessous signifie autorisation des données d'organisation, pas seulement
séparation de sessions/rooms. Scores : jugement d'ingénierie, pas mesures.

| Projet | Stars observées | Dernier commit/push observé | Licence | RAG | Temps réel | Isolation tenant métier | Python/FastAPI | Intégration /10 | Docs /10 |
|---|---:|---|---|---|---|---|---|---:|---:|
| [LiveKit Agents](https://github.com/livekit/agents) | 14 460 | clone `96341b0`, 2026-10-02 14:24:26 -07:00; push API 2026-10-03 01:30:21Z | Apache-2.0 | via outils/adaptateur retrieval | WebRTC, pipelines et realtime APIs | à implémenter dans notre backend; room ≠ permission DB | oui, worker Python distinct | 8 | 9 |
| [Pipecat](https://github.com/pipecat-ai/pipecat) | 16 155 | `327f207`, 2026-10-03 15:45:19Z | BSD-2-Clause | processeurs/adaptateurs | oui, framework voix/multimodal | à implémenter et tester | oui, transport à choisir | 7 | 8 |
| [Vocode Core](https://github.com/vocodedev/vocode-core) | 3 797 | `e054c33`, 2024-11-15 22:16:58Z | MIT | extension applicative; validation détaillée UNKNOWN | framework conversationnel | non démontrée | Python | 5 | 6 |
| [LiveRAG](https://github.com/YS-BW/LiveRAG) | 13 | dernier commit exact UNKNOWN dans cette évaluation | MIT selon API GitHub | LightRAG/knowledge bases annoncé | LiveKit annoncé | séparation kb_id annoncée; protection organisationnelle non auditée | dépôt principal TypeScript; composant Python à examiner | 4 | UNKNOWN |
| Oliva / Olivia | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| local-vai | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| fastapi-langgraph-chatbot-with-vector-store-memory-mcp-tools-and-voice-mode | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Voice-Agent (nom générique) | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Les noms ambigus ne permettent pas d'attribuer une licence ou des promesses
à un dépôt précis. Le candidat
`prompt-engineering/fastapi-langgraph-chatbot-with-vector-store-memory-mcp-tools-and-voice-mode`
a répondu HTTP 404; aucune propriété n'est extrapolée. Un résultat de
recherche web n'est pas considéré comme preuve suffisante.

### Sources publiques de métadonnées

- https://api.github.com/repos/livekit/agents
- https://api.github.com/repos/pipecat-ai/pipecat
- https://api.github.com/repos/pipecat-ai/pipecat/commits?per_page=1
- https://api.github.com/repos/vocodedev/vocode-core
- https://api.github.com/repos/vocodedev/vocode-core/commits?per_page=1
- https://api.github.com/repos/YS-BW/LiveRAG
- https://docs.livekit.io/agents/

Seuls les noms de dépôts publics ont été envoyés aux recherches. Aucun code
privé, document client ou credential du projet n'a été transmis.

## Clone examiné hors projet

Commande : Git `clone --depth 1 https://github.com/livekit/agents.git` vers
le dossier `files/voice-agent-eval` de la session Copilot, pas `vendor/`.
SHA : `96341b0db2d0224403a36612cb04a1e38d60d405`.
Le clone temporaire a ensuite été supprimé; SHA et observations conservés
ici. Aucun fichier upstream copié dans le produit.

Examens : README, manifest racine, manifest `livekit-agents/pyproject.toml`,
structure `examples/`, `tests/`, `livekit-plugins/`, licence/métadonnées.
Ni installation ni exécution d'exemples upstream; aucune clé LiveKit.

- Workspace uv contenant core, nombreux plugins et exemples.
- Core Python compatible déclaré `>=3.10,<3.15`, donc avec Python 3.11
  cible et Python 3.13 actuellement utilisé par le projet.
- Dépendances RTC/API/protocol, PyAV, aiohttp, Pydantic, OpenTelemetry,
  OpenAI et audio; compatibilité complète avec le manifest SaaS non testée.
- Le README décrit dispatch, WebRTC, SIP, STT/LLM/TTS modulaires, turn
  detection, outils MCP et framework de tests.
- Les exemples utilisent un `AgentServer`/`AgentSession` : worker séparé
  préférable à l'import du framework complet dans les workers HTTP.
- Les tests upstream sont présents, mais non exécutés; leur nombre et
  leurs résultats sont UNKNOWN dans cette évaluation.

## Pourquoi LiveKit dans cette architecture

WebRTC et dispatch permettent un service de médias distinct. Le retrieval
pgvector et les permissions existants restent la source de vérité.
Ne pas remplacer PostgreSQL par Qdrant ni ajouter un deuxième graphe RAG
simplement pour copier un exemple vocal.

Le framework orchestre STT/LLM/TTS et ajoute transport média, VAD/turn-taking,
interruptions et session audio. Il ne fournit pas automatiquement nos
memberships, RLS, quotas, billing, rétention ni isolation des citations.

Un room token doit être généré par notre API après authentification,
membership et permission. Il ne doit jamais accepter `organization_id`
fourni par le navigateur comme autorité.

## Coûts et effort

Coût réel UNKNOWN : aucun devis ni tarif fournisseur validé ici.
Formule : minutes × (transport + STT + TTS) + tokens LLM + compute/egress.
Self-hosted supprime une part du coût de cloud, pas les coûts CPU/GPU,
TURN/egress, modèles et exploitation.

Estimation d'ingénierie, pas engagement : prototype 3–5 jours; intégration
multi-tenant avec budget/rate-limit, interruptions, observabilité et
acceptation audio : 10–20 jours selon infrastructure et providers.

## Risques et bénéfices

Bénéfices : conversation fluide, accessibilité, interruptions et évolution
SIP; réemploi du retrieval existant plutôt que duplication.
Risques : confusion room/tenant, audio sensible, budgets non maîtrisés,
concurrence de crédits, dépendances natives et latence sous charge.

Prérequis : staging joignable, migrations/IDOR/RLS et budgets validés.
Le plan détaillé est dans `VOICE_AGENT_INTEGRATION_PLAN.md`.
