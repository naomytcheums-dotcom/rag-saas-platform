# Tests automatisés par personas IA (Crawlix)

Ce document explique comment ce projet est testé avec [Crawlix](https://www.npmjs.com/package/crawlix),
un outil qui fait naviguer un navigateur réel (Playwright) par un agent IA jouant un persona
utilisateur donné, et comment reproduire ces tests.

## Principe

Crawlix reçoit une URL et un objectif en langage naturel ("inscris-toi et connecte-toi", par
exemple), puis un LLM pilote un vrai navigateur (clics, saisie, lecture de la page) pour essayer
d'atteindre cet objectif, comme le ferait un utilisateur réel. Chaque persona (`--agent`) donne
au LLM une consigne de comportement différente :

| Persona | Comportement simulé |
|---|---|
| `first-timer` | Nouvel utilisateur, ne connaît pas l'interface |
| `impatient` | Clique vite, n'attend pas, cherche des raccourcis |
| `power-user` | Utilisateur avancé, explore les fonctions poussées |
| `adversarial` | Essaie des entrées invalides, des injections, des cas limites |
| `non-native-speaker` | Simule une incompréhension du français |
| `slow-network` | Simule une connexion lente (tolérance aux temps de chargement) |

## Installation

```bash
npm install -g crawlix
```

Configuration du LLM utilisé par Crawlix (`~/.crawlix/crawlix.config.json`, **hors du dépôt
git** — ce fichier contient une clé API) :

```json
{
  "primary": {
    "provider": "groq",
    "apiKey": "VOTRE_CLE_GROQ",
    "model": "openai/gpt-oss-20b"
  }
}
```

Contexte du projet donné à l'agent : [`.crawlix/CONTEXT.md`](../../.crawlix/CONTEXT.md)
(URL de l'app, description, les 12 parcours utilisateurs couverts).

## Lancer un test

```bash
crawlix run --url http://localhost:3011 \
  --goal "Inscris-toi avec un email de test, confirme ton compte, puis connecte-toi" \
  --agent first-timer,impatient,power-user \
  --concurrency 1 \
  --steps 20
```

`--concurrency 1` est recommandé avec un modèle gratuit (voir "Limites rencontrées" ci-dessous).

## Ce qui a été réellement utilisé pour cette campagne de tests (honnête, sans rien cacher)

Cette machine de développement n'a pas d'accès payant à une API LLM. Le chemin réellement
suivi, dans l'ordre :

1. **Ollama (modèle local, gratuit)** — `llama3.2:1b` puis `llama3.2` (3B), en forçant le
   mode CPU (`PARAMETER num_gpu 0` dans un Modelfile) car le pilote GPU de cette machine
   plantait avec les modèles Ollama (`CUDA error: device kernel image is invalid`). Le
   modèle 1B était trop faible : il produisait des réponses qui faisaient planter le parseur
   de Crawlix (`TypeError: Cannot read properties of undefined`) et les 3 premiers personas
   testés (first-timer, impatient, power-user) restaient bloqués sur l'écran d'inscription
   sans jamais progresser dans le reste du parcours.
2. **Groq (API cloud, offre gratuite)** — une fois qu'une clé Groq gratuite a été obtenue,
   le modèle `openai/gpt-oss-20b` a donné des résultats nettement plus fiables et a permis
   de réellement progresser au-delà de l'écran d'inscription.

### Limites rencontrées avec l'offre gratuite Groq

- **Quota par minute (TPM)** : 8000 tokens/minute. Un `--concurrency` supérieur à 1 fait
  dépasser ce quota en quelques secondes (erreur HTTP 429).
- **Quota journalier (TPD)** : 200 000 tokens/jour. Une campagne de tests couvrant les 6
  personas sur les 12 parcours utilisateurs représente largement plus que ce budget — le
  quota journalier a été atteint pendant cette campagne, ce qui a limité le nombre de
  campagnes complètes réalisables dans une seule journée. Voir
  [RESULTS.md](RESULTS.md) pour le détail de ce qui a pu être couvert.

**Conséquence pratique pour qui reprend ce projet** : avec une vraie clé API payante (Groq
payant, Anthropic, OpenAI...), la même commande Crawlix peut tourner avec un `--concurrency`
plus élevé et sans interruption de quota, ce qui permettrait de couvrir les 6 personas x 12
parcours en une seule campagne continue.

## Redis local sans Docker/WSL2 (contournement de cette machine, pas pour la production)

Cette machine ne peut lancer ni Docker Desktop ni WSL2 (échec confirmé des deux : virtualisation
imbriquée indisponible dans ce sandbox). Un vrai serveur Redis étant nécessaire pour tester le
rate limiting, le géo-lookup et les autres fonctions qui en dépendent, un script local
(`run_local_redis.py`, **hors du dépôt git**) démarre `fakeredis.TcpFakeServer` : un vrai
serveur TCP qui parle le vrai protocole RESP sur `localhost:6379`, auquel le vrai client
`redis.asyncio` de l'application se connecte exactement comme il le ferait à un vrai Redis —
ce n'est pas un mock substitué dans le code de l'application elle-même.

**Ce n'est pas destiné à la production.** Un déploiement réel utilise un vrai Redis (voir
`docker-compose.selfhosted.yml`).

## Rapports générés

Chaque run Crawlix écrit un rapport Markdown dans `crawlix-reports/` (dossier local, hors
git — contient des captures d'écran et détails de session qui n'ont pas leur place dans
l'historique du dépôt). Voir [BUGS_FOUND.md](BUGS_FOUND.md) pour la synthèse des bugs
réels qui en ont été extraits.
