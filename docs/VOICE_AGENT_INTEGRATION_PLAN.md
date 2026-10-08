# Plan vocal temps réel — non intégré

Date : 2026-10-03. Choix : LiveKit Agents, worker séparé. Source :
[évaluation](./VOICE_AGENT_EVALUATION.md). Aucun déploiement ni package ajouté.

## Architecture cible

Navigateur → API FastAPI authentifiée → autorisation org/agent/budget →
token RTC à room imposée → LiveKit serveur/cloud → worker vocal →
API retrieval interne authentifiée tenant → LLM → TTS → room.

L'API reste autorité sur tenant, agent, permissions, crédits et sources.
Le worker n'accepte pas de tenant transmis librement dans un prompt/audio
ou des métadonnées non authentifiées. La voix round-trip reste disponible.

## Étapes

1. Valider staging et tests A/B avant tout RTC.
2. Choisir serveur self-hosted ou cloud et budget; aucun choix implicite
   de fournisseur payant et aucune clé cloud dans les rapports.
3. Worker avec dépendances séparées et versions compatibles vérifiées.
4. Ajouter route de création de session après `require_permission`,
   rate-limit, scope de l'agent, réservation de budget et audit.
5. Tokens room-scoped courts, identity non devinable, pas de join d'une
   autre room; mapping session→org stocké côté serveur.
6. Adapter le retrieval existant; ne pas dupliquer les vecteurs/permissions.
7. Ajouter STT/TTS en streaming, VAD, barge-in et cancellation de génération.
8. Débit mesuré/idempotent, plafond de durée et arrêt lorsque quota épuisé.
9. UI derrière feature flag, permissions micro et fallback explicite.
10. Tests de bout en bout audio, isolation, latence et coûts en staging.
11. Revue sécurité/privacité, canary et plan de désactivation.
12. Production seulement après autorisation de release séparée.

## Fichiers futurs (aucun créé pour l'intégration)

- `voice-worker/` : manifest, entrée worker, adaptateur RAG.
- `api/routers/voice_sessions.py` : session/token, permissions/quota.
- `api/services/voice_sessions.py` : lifecycle et budget.
- Nouvelle migration après 0132 si persistance nécessaire; ne pas
  modifier les migrations historiques.
- `frontend/components/RealtimeVoiceSession.tsx` : UI RTC et fallback.
- Compose optionnel worker/LiveKit/TURN, documentation d'exploitation.
- Tests backend, frontend et audio dans suites existantes.

## Dépendances envisagées

Worker : livekit-agents, livekit-api, plugins STT/LLM/TTS/VAD nécessaires
uniquement. Frontend : SDK LiveKit JS et éventuellement composants React.
Versions exactes : à résoudre/pinner lors de la phase d'intégration.
Aucune dépendance n'est ajoutée à `requirements-api.txt` dans ce plan.

## Variables requises

`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, feature flag,
plafond durée/coût/session, providers audio choisis et credentials via
secret manager. Jamais dans le frontend, les logs ou un fichier suivi.

## Tests attendus

- Token demandé par A pour un agent/room de B refusé.
- Worker ne peut demander retrieval d'un tenant non autorisé.
- Sources et mémoire n'exposent aucune donnée de B en room A.
- Audio silencieux, bruit, français/anglais, interruption et reconnexion.
- Expiration des tokens; arrêt de session après budget ou déconnexion.
- Double callback/retry ne double pas le débit.
- p95 bout-en-bout et time-to-first-audio sur charge représentative.
- Permissions microphone refusées : fallback texte sans fausse réussite.
- Désactivation du feature flag conserve le tour audio existant.

## Effort et risques

Prototype estimé 3–5 jours, parcours durci estimé 10–20 jours;
infrastructure/provider peuvent allonger ce délai. Estimation non mesurée.
Risques : dépendances natives, modèle de contexte RLS non encore validé,
réseau WebRTC/TURN, coût API et données audio sensibles.
Mitigations : worker distinct, scope serveur, budgets, minimisation/rétention,
tests adversariaux et versionnage de prompts/providers.
