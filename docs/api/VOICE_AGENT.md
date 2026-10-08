# Agent vocal (voix → RAG → réponse)

`POST /voice/organizations/{org_id}/agent` — multipart, champ `file` (audio), permission `documents:read`.

Un tour de conversation : **audio → transcription (STT) → pipeline RAG de l'organisation → réponse + sources**, avec synthèse vocale optionnelle.

| Paramètre (query) | Rôle |
|---|---|
| `stt_provider` | `local_whisper` (open source, auto-hébergé), `whisper`, `deepgram`. Défaut : `STT_PROVIDER`. |
| `language` | ex. `fr`, `fr-FR` (réduit au code court pour Whisper local). |
| `speak` | `true` → la réponse est aussi synthétisée (ElevenLabs, clé requise) et renvoyée en base64. Sinon le client peut lire `answer_text` lui-même (Web Speech, gratuit). |

Réponse : `transcript`, `answer_text`, `answer_audio_base64` (ou `null`), `response_id`, `sources[]` (citations), `credits_charged`.

## Brique open source : `local_whisper`

[faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), exécuté dans le processus API : pas de clé, l'audio ne quitte pas le serveur.
Dépendance **optionnelle** (non ajoutée à `requirements-api.txt`, volontairement) :

```bash
pip install faster-whisper
```

Le modèle est téléchargé au premier usage (`LOCAL_WHISPER_MODEL`, défaut `base`, `LOCAL_WHISPER_COMPUTE_TYPE=int8`, `LOCAL_WHISPER_DEVICE=cpu`).
Sans le paquet, l'endpoint répond **400** avec la commande d'installation — jamais de faux résultat.

## Garde-fous (identiques aux autres points d'entrée payants)

- Rate limit par organisation (`VOICE_AGENT_RATE_LIMIT_*`).
- Pré-vérification solde + plafonds journalier/mensuel (402 / 429), BYOK exempté ; coût forfaitaire par tour `VOICE_AGENT_TURN_CREDIT_COST`.
- Audio borné (`VOICE_AGENT_MAX_AUDIO_BYTES`), transcription bornée (`VOICE_AGENT_MAX_TRANSCRIPT_CHARS`).
- Anti-injection : une phrase prononcée bloquée par les guardrails répond 400 (comme le chat texte).
- Isolation multi-tenant : la récupération est limitée à `org_id`, le membre doit appartenir à l'organisation.

## Limites assumées

- **Tour par tour**, pas de streaming temps réel (micro continu / transcription partielle / réponse parlée en flux). Un pipeline temps réel (WebRTC : LiveKit Agents, Pipecat) apporte une empreinte de dépendances disproportionnée pour le backend ; il reste une évolution possible, derrière cette même interface.
- L'inférence Whisper locale n'a pas été exécutée sur un vrai audio dans la suite de tests (modèle à télécharger) : les tests couvrent le routage, la dégradation honnête et les garde-fous ; l'inférence réelle dépend du paquet et du modèle installés sur le déploiement.
