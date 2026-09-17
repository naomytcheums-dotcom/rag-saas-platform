# BYOK (Bring Your Own Key)

## Principe

Une organisation peut fournir sa propre clé API pour un fournisseur LLM
(Anthropic, OpenAI, Gemini, Mistral, ou un endpoint compatible OpenAI)
au lieu d'utiliser la clé de la plateforme (`.env`). Un appel effectué
avec une clé BYOK est facturé directement par le fournisseur à
l'organisation elle-même -- jamais sur ses crédits IA inclus (voir
`docs/features/AI_CREDITS.md`).

## Stockage et chiffrement

`OrganizationLLMConfig` (`api/models/organization_llm_config.py`,
migration `0109`) -- une ligne par (organisation, fournisseur). La clé
n'est jamais stockée en clair : `encrypted_api_key` contient le
chiffrement Fernet réel de
`api/security/secret_encryption.py` -- **le même mécanisme déjà utilisé
et déjà audité** pour les clés de signature JWT et les secrets SSO
d'entreprise, réutilisé tel quel plutôt qu'un second schéma maison.

Note honnête sur le choix technique : Fernet est un chiffrement
authentifié (AES-128-CBC + HMAC-SHA256), pas littéralement AES-256-GCM.
C'est le mécanisme d'encryption-at-rest déjà en place et déjà éprouvé
dans ce projet pour exactement ce type de secret (clé API sensible) --
réutiliser l'existant plutôt que d'introduire un second schéma de
chiffrement pour un bénéfice de sécurité marginal a été jugé le choix
le plus sûr, pas seulement le plus rapide.

## Endpoints réels

- `GET /organizations/{org_id}/llm-config` -- liste les fournisseurs
  configurés (jamais la clé elle-même, ni son chiffré).
- `POST /organizations/{org_id}/llm-config` -- enregistre ou remplace
  la clé d'un fournisseur (`{"provider": "openai", "api_key": "sk-..."}`).
- `DELETE /organizations/{org_id}/llm-config/{provider}` -- supprime la
  clé BYOK de ce fournisseur (l'organisation revient aux crédits
  inclus).

Réservé aux Owners de l'organisation (`require_org_owner`) -- plus
strict que les autres réglages de `/organizations/{org_id}/settings`
(Admin+ en lecture), parce qu'une clé API tierce est plus sensible que
n'importe quel autre réglage de cette page.

## Comment la clé est réellement utilisée

`api/services/llm_byok.py`'s `resolve_org_api_key` est appelé par
`api/services/agent_orchestrator.py` juste avant chaque appel LLM réel
(les deux chemins, `run_agent` et `stream_response`). Si une clé BYOK
active existe pour le fournisseur résolu, elle est déchiffrée et passée
en `api_key=` -- un override explicite que `chat_completion`/
`chat_completion_with_usage`/`chat_completion_stream` supportaient déjà
tous les trois (`api/services/llm_providers.py`'s own
`_chat_completion_raw`, "a real, explicit caller override always
wins"). Aucune modification de `llm_providers.py` n'a été nécessaire.

## Frontend

`/dashboard/settings/llm-config` -- ajouter/remplacer/supprimer une clé
par fournisseur. La clé n'est jamais réaffichée après enregistrement
(seul le fournisseur et la date de configuration sont visibles).

## Test réalisé en direct

Clé BYOK factice enregistrée pour un compte de test, vérifiée en base
(chiffrée, pas en clair), puis supprimée -- voir le message de session
pour le résultat concret.
