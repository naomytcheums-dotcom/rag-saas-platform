# Audit concurrentiel exhaustif — KnowFlow vs Dify / RAGFlow / Flowise / Onyx / AnythingLLM

**Date** : 2026-09-21
**Objectif** : cartographier, fonctionnalité par fonctionnalité, ce que proposent aujourd'hui (état réel, pas historique) les 5 plateformes open source de référence, puis comparer chaque fonctionnalité au code réel de KnowFlow pour produire une feuille de route qui ne refait jamais ce qui existe déjà.

**Méthode** : 5 agents de recherche indépendants (un par plateforme), consultant en priorité les dépôts GitHub officiels, la documentation officielle, les changelogs/releases 2026, avec citation systématique des sources. Le résultat brut de chaque agent est reproduit intégralement dans les Parties A à E (aucune fonctionnalité n'a été supprimée pour raccourcir). La Partie G est construite à partir d'un audit direct du code source de KnowFlow (grep/lecture de fichiers réels, pas une supposition).

**Note d'honnêteté** : certaines fonctionnalités marquées `[Unverified]` par les agents de recherche n'ont pas pu être confirmées avec une source primaire — elles sont conservées telles quelles plutôt que d'être présentées comme certaines. Ne pas les utiliser pour une décision commerciale/juridique sans re-vérification directe.

---

## PARTIE A — Dify (langgenius/dify)

### 0. Licence (à lire en premier)

- **Nom exact** : "Dify Open Source License" — Apache 2.0 modifiée.
- **Clause de restriction multi-tenant (la plus importante)** : interdiction d'utiliser le code Dify pour opérer un environnement multi-tenant ("un tenant = un workspace") sans autorisation écrite de l'éditeur (LangGenius) — nécessite une licence commerciale pour héberger Dify en SaaS revendu à des tiers.
- **Clause de branding** : interdiction de retirer/modifier le logo/copyright dans la console et le frontend web.
- **Ce qui reste permis** : usage commercial interne, usage comme backend de son propre produit, self-hosting pour une seule organisation, modification/redistribution sinon conforme à Apache 2.0.
- **Statut OSI** : considéré comme "source-available", pas open source au sens OSI (débat communautaire actif, cf. issue #17109).
- **Éditions** : Community (self-hosted) / Dify Cloud (SaaS payant) / Dify Enterprise (SSO/SAML/OIDC, RBAC, audit logs, SCIM, support dédié — licence commerciale séparée).

### 1. Platform / SaaS
- Workspace = unité tenant ; utilisateur multi-workspace.
- Rôles Community (toujours actifs) : **Owner** (unique, facturation, suppression workspace), **Admin** (gestion membres/apps/providers, pas les rôles/facturation), **Editor** (CRUD apps + KB), **Member** (accès aux apps publiées uniquement).
- **RBAC Enterprise** (flag `RBAC_ENABLED`) : permissions nommées fines (`workspace.member.manage`, `workspace.role.manage`...), en plus de : SSO SAML/OIDC/OAuth2, SCIM, MFA/2FA, audit logs infalsifiables vers SIEM, RBAC au niveau workflow.
- Contrôle d'accès par app plus fin ("moi seul / toute l'équipe / membres sélectionnés") : demandé en issue, **statut de livraison non confirmé**.
- Gestion centralisée des providers de modèles, credentials par workspace ou par outil/nœud.
- **Marketplace** (marketplace.dify.ai) : plugins de providers de modèles, d'outils, de stratégies d'agent, d'extensions/webhooks.
- Chaque app génère automatiquement une API REST (chat/completion/workflow-run).
- Cycle Draft → Publish ; une fois publiée, une app est exposée simultanément en web app, iframe, widget JS embarquable et API REST.
- Quotas Cloud par volume de messages/appels API, sièges, stockage KB (chiffres variables, ne pas citer sans vérifier `dify.ai/pricing` à la date).

### 2. Types d'application
| Type | Nature | Notes |
|---|---|---|
| Chatbot | Conversationnel simple | Interface simplifiée, même moteur que Chatflow |
| Chatflow | Workflow multi-tour avec état de conversation | ID de conversation, compteur de tours, variables de conversation, mémoire dans les nœuds LLM, streaming progressif texte/image/fichier |
| Workflow | Orchestration mono-tour/batch | Pas de notion de conversation ; utilisable comme backend d'app ou job batch ; `/workflows/run` |
| Agent | Assistant autonome conversationnel | Décomposition de tâches, raisonnement, appel d'outils, mémoire multi-tour |
| Text Generator / Completion | Formulaire → résultat, un coup | `/completion-messages`, sans historique |
- Pas de type d'app "RAG-only" dédié : le RAG est une ressource (Knowledge Base) attachable à n'importe quel type d'app ci-dessus.
- App API-only : choix de déploiement (ne pas publier le lien web app), pas un type distinct.

### 3. Workflow Builder — inventaire complet des nœuds
| Nœud | Configure |
|---|---|
| Start (User Input) | Point d'entrée manuel/API, champs de formulaire d'entrée |
| Trigger | Point d'entrée automatique (cron/webhook/plugin) — voir 3.2 |
| LLM | Modèle, prompt système/utilisateur, mémoire/contexte, détail vision, sortie structurée (JSON Schema), function/tool calling, paramètres (température, top_p, presets Créatif/Équilibré/Précis) |
| Knowledge Retrieval | KB ciblée(s), mode (vecteur/full-text/hybride), top-k, seuil, filtres metadata, modèle de reranking |
| Question Classifier | Classification d'intention par LLM → branches |
| IF/ELSE | Branchement conditionnel booléen/comparaison |
| Iteration | Boucle sur un tableau, sous-graphe par élément, collecte en tableau |
| Loop | Boucle générale à condition de sortie + variables de boucle |
| Code | Exécution Python/Node.js sandboxée (DifySandbox) |
| Template Transform | Templating Jinja2 |
| HTTP Request | Méthode/URL/headers/params/body/auth vers API externe |
| Variable Aggregator | Fusionne les sorties de branches parallèles/conditionnelles (même type de donnée requis) |
| Variable Assigner | Écrit/met à jour variables de conversation/environnement |
| Parameter Extractor | Extraction de paramètres structurés depuis texte libre par LLM |
| Document Extractor | Extraction de texte d'un fichier uploadé en cours de workflow |
| List Operator | Filtre/tri/transforme des tableaux |
| Tool | Invoque un plugin d'outil marketplace en étape autonome |
| Agent (nœud) | Sous-boucle de raisonnement/appel d'outils autonome dans un canvas Workflow/Chatflow |
| Human Input (v1.13.0+) | Pause l'exécution, UI de revue humaine, branche selon l'action choisie (Approve/Reject/Escalate...) |
| Answer | Réponse streamée en cours de conversation (Chatflow) |
| End / Output | Nœud terminal, variables de sortie finales |

- **Triggers** : Schedule (cron Unix, variable `$current_time`), Webhook (URL unique par trigger, aucune vérification HMAC native — recommandée via nœud Code), Plugin Trigger (événements de plugins type GitHub/Gmail).
- **Variables** : système, entrée du Start node, variables de conversation (Chatflow), variables d'environnement (secrets workspace), pool de variables adressable par nœud.
- **Parallélisme** (depuis v0.8.0) : ordonnancement concurrent des nœuds sans dépendance non résolue, réglable via `GRAPH_ENGINE_MIN_WORKERS`/`MAX_WORKERS` ; Variable Aggregator requis pour fusionner. Régression communautaire signalée en v1.9.0 (à vérifier sur la version actuelle).
- **Erreurs/retry/timeout** : "Retry on Failure" par nœud (LLM/HTTP/Tool/Code) avec nombre max + intervalle ; après épuisement : échec total, valeur par défaut prédéfinie, ou branche d'erreur dédiée. Chemins d'erreur surlignés en jaune dans la visualisation.
- **Versioning/publish/import-export** : Draft vs Versions publiées nommées/datées, restauration/diff ; export/import DSL (YAML) de l'app entière, versionné avec avertissement de compatibilité.
- **Debug/logs** : exécution pas-à-pas d'un nœud isolé, "Variable Inspector" (cache les sorties pour retester en aval sans tout relancer), logs d'exécution complets par nœud (entrées/sorties/timing/erreurs).

### 4. Agents
- Stratégies : **Function Calling** et **ReAct**, plus stratégies communautaires (plugins Marketplace "Agent Strategies").
- **MCP bidirectionnel natif depuis v1.6.0** : Dify client MCP (appelle des serveurs MCP externes) ET serveur MCP (expose une app/workflow Dify comme outil MCP).
- Outils intégrés (~50+ historiquement) désormais livrés via le marketplace de plugins plutôt que codés en dur.
- Outils personnalisés : définition OpenAPI/Swagger, ou plugin complet via le SDK de plugins Dify.
- Mémoire d'agent : par conversation, fenêtre configurable.
- **Sandboxing** : exécution de code/outils via **DifySandbox** dédié (bloque accès fichiers, réseau, commandes système).
- **Human-in-the-loop natif** : nœud Human Input (v1.13.0+).

### 5. RAG
- KB = ressource workspace indépendante, attachable à plusieurs apps.
- Formats : PDF, Word, Excel, PowerPoint, texte, Markdown, images + extension via plugins marketplace (TextIn XParse, Mistral OCR, parsing basé sur "Unstructured" avec stratégies auto/hi_res/fast/OCR-only et chunking by_title/by_page/by_similarity). **OCR/tables largement dépendant de plugins, pas uniforme en natif.**
- **Knowledge Pipeline** (architecture récente) : orchestration d'ingestion avec choix de parseur par type de fichier, plusieurs parseurs en parallèle, puis chunk/embed/index.
- Chunking : **Général** (taille fixe), **Parent-Child** (hiérarchique), **Q&A** (extraction structurée question/réponse).
- Embeddings : pluggables par provider/coût/langue/dimension via le système de plugins.
- Indexation : index vectoriel "haute qualité" ou index mot-clé "économique" au choix.
- Retrieval : vecteur, full-text, hybride pondéré.
- Reranking optionnel, modèles pluggables.
- Filtrage metadata (tags personnalisés, manuel ou automatique) depuis v1.1.0.
- Citations : outil "Retrieval Test" (segment source, numéro, score de correspondance) + citations visibles côté utilisateur final.
- Réglages exposés : top-k, seuil de score, pondération hybride sémantique/mot-clé, reranking on/off + choix modèle, règles de filtre metadata.

### 6. LLM
- Architecture de providers migrée en plugins marketplace depuis v1.0 (fév. 2025) — liste ouverte et extensible, pas figée en dur.
- Providers notables : OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Gemini/Vertex, NVIDIA NIM, OpenRouter, Cohere, plugin générique "OpenAI-API-compatible" (Ollama, vLLM, etc.).
- Multimodal : vision avec niveau de détail configurable (High/Low), entrées fichiers/documents en contexte multimodal.
- Streaming : `response_mode: streaming` vs `blocking` côté API, streaming token par token + streaming de fichiers/images en Chatflow.
- **Structured Outputs** (v1.3.0) : éditeur JSON Schema visuel ou brut sur le nœud LLM.
- Function/tool calling natif sur nœud LLM et nœud/app Agent.
- **Fallback de modèles** : **non confirmé comme fonctionnalité native documentée** — probablement absent ou dépendant de plugins.
- Paramètres exposés : température, top_p, max tokens, format de réponse, presets Créatif/Équilibré/Précis.

### 7. Prompt management
- Le nœud LLM sert d'IDE de prompt (templates système/utilisateur/assistant, interpolation de variables, preview live).
- Nœud Template Transform (Jinja) pour du templating plus complexe hors nœud LLM.
- Versioning des prompts implicite via le versioning d'app entière (pas de versioning de prompt isolé confirmé).
- Test/debug via l'exécution pas-à-pas du nœud LLM ; pas de "prompt playground" comparatif multi-modèles confirmé actuellement.

### 8. Observability / LLMOps
- Logs natifs par app (conversations, messages, annotations bonnes/mauvaises réponses → jeu de données d'évaluation).
- Intégrations tierces configurables : **Langfuse** (officiel), et historiquement d'autres (LangSmith-like) — à vérifier en app pour la liste actuelle.
- Coût/tokens/latence : disponibles a minima par message dans les logs natifs, plus riches via Langfuse.
- Évaluation : boucle légère via annotations ; évaluation offline systématique mieux couverte par des outils externes (Langfuse) que par le cœur Dify — écart potentiel à vérifier vs KnowFlow.

### 9. API / SDK / intégrations
- Endpoints par app : `POST /chat-messages`, `POST /completion-messages`, `POST /workflows/run`, pattern asynchrone pour workflows longs (poll sur `workflow_run_id`).
- API de gestion des datasets/KB séparée.
- SDKs officiels/communautaires (Python, Node.js) en wrappers REST légers.
- Webhooks entrants (nœud Webhook Trigger, URL unique) et sortants (nœud HTTP Request).
- Intégrations tierces via marketplace : Slack, GitHub, Gmail confirmés, + intégration OpenAPI générique pour le reste.
- Widget embarquable : web app hébergée, iframe, widget JS, API REST — tout depuis la même surface "Publish".

### Écarts/points à re-vérifier avant usage externe
1. Fallback de modèles natif — non confirmé.
2. Pas de type d'app "RAG-only" — le RAG est une ressource, pas un type d'app (différenciateur potentiel pour KnowFlow si pertinent).
3. Partage fin par app (only-me/sélection) — statut de livraison incertain.
4. Régression du parallélisme signalée en v1.9.0 — à vérifier sur la version actuelle.
5. Nommage des nœuds incohérent entre versions de doc — vérifier la barre latérale live avant publication externe.
6. Frontières Enterprise/Cloud/Community pour RBAC/SSO/audit à reconfirmer sur `dify.ai/pricing/dify-enterprise`.

---

## PARTIE B — RAGFlow (infiniflow/ragflow)

*(Version stable de référence : v0.27.x / v0.27.2, sept. 2026)*

### 0. Licence
- **Apache License 2.0 pure, non modifiée.** Aucune clause de restriction SaaS/multi-tenant, aucun champ d'application restreint. Confirmé sur le fichier LICENSE du dépôt.
- Pas d'édition "Enterprise" séparée du code self-hosted — la différenciation commerciale se fait uniquement via le **cloud hébergé** d'InfiniFlow (cloud.ragflow.io : gratuit 5 apps/500 crédits mensuels, payant ~29$ et ~129$/mois, tarif entreprise sur devis) — un modèle d'hébergement/support, pas un fork à fonctionnalités verrouillées.
- Redistribution pleinement permise (usage commercial, modification, usage privé) avec attribution standard Apache 2.0.

### 1. Knowledge Base
- **Import** : upload direct (UI drag-drop avec gestion des échecs partiels), API HTTP/SDK Python, **Sitemap** (crawl sitemap.xml), **WebDAV** (avec certificat CA custom), connecteurs tiers avec sync (parfois incrémentale) : S3 (incrémental via ETag), Confluence, Notion, Discord, Google Drive, Google BigQuery (incrémental), Outlook, OneDrive, Microsoft Teams, Slack, SharePoint, Salesforce, Azure Blob Storage, Azure DevOps.
- **Formats** (8 catégories, 23+) : PDF, DOC, DOCX, TXT, MD, MDX, EPUB ; CSV, XLSX, XLS ; PPT, PPTX ; JPEG/JPG/PNG/TIF/GIF ; + audio, vidéo, email, HTML.
- **Pipeline de parsing "DeepDoc" (moteur propriétaire RAGFlow)** :
  - OCR maison (pas un wrapper Tesseract), CLI testable.
  - Reconnaissance de mise en page : 10 régions structurelles (Texte, Titre, Figure, Légende figure, Tableau, Légende tableau, En-tête, Pied de page, Référence, Équation).
  - Reconnaissance de structure de tableau (TSR) : 5 labels (Colonne, Ligne, En-tête colonne, En-tête ligne projeté, Cellule fusionnée) + **correction automatique de rotation** (teste 0/90/180/270°, choisit la confiance OCR la plus haute).
  - Figures : recadrées avec légendes extraites et texte OCR intégré ; tableaux : image recadrée + traduction tableau→texte naturel.
  - **Parseurs alternatifs sélectionnables par dataset** : DeepDoc (défaut), Naive (rapide, sans OCR), MinerU (formules mathématiques), Docling, TCADPParser (Tencent), parsing par **VLM** (n'importe quel LLM multimodal configuré), MonkeyOCRv2, PaddleOCR-VL self-hosted, SoMark (layout-aware, non totalement vérifié).
- **Métadonnées** : auto-génération, extraction de mots-clés configurable, génération automatique de questions par chunk, champs personnalisés typés, filtres poussés jusqu'à l'index (v0.27.1).
- **10 méthodes de chunking nommées** (sélectionnables par dataset) :
  | Méthode | Mécanisme |
  |---|---|
  | General (naive) | Découpage généraliste + extraction mots-clés + "TOCEnhance" (table des matières) |
  | Q&A | Chaque paire Q/R devient un chunk |
  | Manual | Respecte la structure hiérarchique des manuels/docs produit |
  | Table | Une ligne = un chunk (XLSX/CSV/TXT) |
  | Paper | Chunking par structure abstract/section |
  | Book | Chunking par chapitre |
  | Laws | Chunking par structure/numérotation légale |
  | Presentation | Une slide = un chunk |
  | Picture | Documents centrés image |
  | One | Document entier = un seul chunk |
  | Tag (non-retrieval) | Construit un jeu de tags pour auto-tagger d'autres datasets |
  - **Nouveauté v0.27.0 — "compilation de connaissance"** au-delà du chunking plat : représentations structurelles **Wiki, Graph, Tree, Page Index, Mind Map, Timeline**.
  - Paramètres : taille cible, délimiteurs personnalisés, % de recouvrement, retrieval enfant-parent.
- **Indexation** : Elasticsearch (défaut) ou Infinity (moteur propriétaire InfiniFlow, v0.7.3).

### 2. RAG / Retrieval
- Recherche vectorielle (cosinus dense) + recherche mot-clé/full-text (pondération type BM25).
- **Fusion hybride** : par défaut similarité mot-clé pondérée + cosinus vectoriel pondéré ; si reranker configuré, la similarité vectorielle est remplacée par le score de reranking dans le score final.
- Rerankers pluggables (style cross-encoder, ex. famille BGE-rerank), avec nombre de candidats et paramètres KNN configurables (v0.27.1).
- Query rewrite basé LLM dans les pipelines agent/chat (détail public limité).
- **Knowledge Graph (GraphRAG) optionnel** : extraction d'entités/relations par LLM à l'ingestion, **déduplication/résolution d'entités par LLM** (comparaison de paires candidates par lot, fusion par composantes connexes, recalcul de PageRank après fusion) — amélioration vs GraphRAG vanilla de Microsoft. Recherche itérative sur chunks entité/relation/**rapport de communauté**, explicitement plus lent, opt-in.
- **PageRank au niveau dataset** pour pondérer certains datasets/documents en recherche cross-dataset.
- Filtrage metadata accéléré par index (v0.27.1).
- Top-k / seuil configurables par composant Retrieval ou appel API.
- **Modes de raisonnement agentique (nouveauté v0.27.0)** : 4 profondeurs sélectionnables — **Low, Medium, High, Ultra**.
- Compression de contexte : pas documentée comme étape nommée distincte — probablement absente en tant que fonctionnalité isolée.

### 3-4. Agents / Canvas de workflow (système unifié chez RAGFlow)
- **Composants de base** : Begin (entrée, déclencheurs Conversationnel/Tâche/**Webhook**, variables globales typées : texte/paragraphe/dropdown/fichier/nombre/booléen/JSON, message d'accueil) ; Agent (raisonnement/génération/appel d'outils, prompts configurables, appel de sous-agents/outils, **sortie structurée via JSON Schema**) ; Retrieval (KB ou "mémoires") ; Message/Await response (pause pour réponse utilisateur).
- **Contrôle de flux / manipulation de données** : Switch (branchement par règles), Categorize (classification LLM), Iteration (boucle sur tableau), Loop (répétition avec variables et condition d'arrêt + plafond anti-boucle-infinie), Code (Python/JS), Text processing, Execute SQL, HTTP Request, VariableAssigner, ListOperations.
- **Outils attachables aux nœuds Agent** : Recherche web (Tavily Search/Extract, Google via SerpApi, DuckDuckGo, SearXNG, Keenable, Sofya, You.com, Serply) ; Référence (Wikipedia, GitHub) ; Académique (Google Scholar, ArXiv, PubMed, BGPT) ; Finance (Yahoo Finance, WenCai) ; Intégration (Execute SQL, HTTP Request, Email SMTP/HTML/CC, Générateur de documents Markdown→PDF/DOCX/TXT/MD/HTML, Browser piloté par LLM).
- **MCP bidirectionnel** : RAGFlow client MCP (appelle des serveurs externes) ET serveur MCP (expose la recherche KB via DeepDoc, mode self-host mono-tenant ou mode host multi-tenant par client MCP).
- **Mémoire** : peu documentée, probablement stade précoce (Retrieval peut sourcer depuis des "mémoires" en plus des KB).
- Providers modèles en expansion rapide 2026 : DeepSeek v4, Gemini 3 Pro, Qwen 3.8, Kimi K3, AWS Bedrock, etc.

### 5. Chat
- Assistants liés à un ou plusieurs datasets, historique de session conservé.
- **Citations traçables** (toggle), aperçu rapide du texte source, citations sources Excel dans la prévisualisation (v0.27.2).
- Streaming activé par défaut (assistants et agents).
- Feedback pouces haut/bas : évoqué en communauté, **non confirmé en documentation officielle**.
- Partage/embed : génération iframe/JS pour site externe.
- **Déploiement multi-canal 2026** : Discord, Feishu, Telegram, Line, Slack (couverture par plateforme non vérifiée individuellement).
- API compatible OpenAI (chat-completion) pour assistants et agents.

### 6. Administration
- Multi-tenant : un utilisateur peut appartenir à plusieurs tenants, chaque tenant isolé (config/accès).
- Deux couches de permission : **rôle d'équipe** (adhésion, seul le owner invite par défaut) et **rôle Enterprise** (couche RBAC administrative séparée — non confirmé si OSS ou réservé au cloud).
- Modèle de partage de ressources à 3 niveaux : appartenance équipe, portée de partage, permissions au niveau ressource (être membre ne donne pas accès automatiquement).
- API complète (dataset, fichier, chunk, assistant, session, agent, retrieval).
- **Aucun tableau de bord de monitoring/observabilité natif trouvé** dans la doc officielle — probablement absent en OSS.

### 7. Connecteurs de synchronisation
Web (Sitemap, WebDAV), stockage cloud (S3 incrémental, Azure Blob, Google Drive, OneDrive, SharePoint), collaboration (Confluence, Notion, Teams, Slack, Discord), dev (Azure DevOps), CRM (Salesforce), data warehouse (BigQuery incrémental), email (Outlook). Comportement de sync (complet vs incrémental) non vérifié individuellement pour chaque connecteur au-delà de S3/BigQuery.

### Écarts à re-vérifier
Feedback pouces haut/bas non confirmé · rôle Enterprise RBAC (portée exacte, OSS ou cloud) · absence de dashboard monitoring natif · compression de contexte absente en tant que feature nommée · maturité réelle du sous-système mémoire · sémantique de sync exacte par connecteur au-delà de S3/BigQuery.

---

## PARTIE C — Flowise (FlowiseAI/Flowise)

### 0. Statut critique — projet arrêté

**Le dépôt `FlowiseAI/Flowise` a été archivé (lecture seule) le 13 août 2026.** Chronologie officielle : gel du code le 29 juillet 2026, archivage le 13 août 2026, fin du support de l'équipe cœur le 31 août 2026. Raison donnée par les mainteneurs : les développeurs s'appuient de plus en plus sur des agents de codage généralistes, et l'approche low-code visuelle "rigide" atteint vite ses limites en complexité. Packages npm et images Docker marqués dépréciés (toujours installables, plus aucun correctif de sécurité). Forks communautaires connus : `dblagbro/flow-wiser` ("Flow-Wiser"), `YardiSystems/FlowiseArchive`.

**Implication pour KnowFlow** : cible figée, jamais évolutive — utile comme référence de fonctionnalités passées, dangereux comme fondation technique (aucun correctif de sécurité futur, dépendances LangChain figées qui vieilliront).

### Licence
- **Double licence** : Apache 2.0 pour le cœur (Community : moteur de flux, bibliothèque de nœuds, UI, serveur API) ; **licence commerciale/Enterprise séparée** pour `packages/server/src/enterprise/` et fichiers à copyright explicite (SSO, RBAC, workspaces Enterprise, audit logs). La présence de code Enterprise dans le dépôt ne contamine pas le statut Apache 2.0 du reste.

### 1. Visual Builder — catégories de nœuds (canvas "Chatflow")
- **LLMs** : AWS Bedrock, Azure OpenAI, Cohere, Google Vertex AI, HuggingFace Inference, Ollama, OpenAI, Replicate, etc.
- **Chat Models** : AWS ChatBedrock, Azure ChatOpenAI, ChatAnthropic, ChatCohere, Chat Fireworks, ChatGoogleGenerativeAI/PaLM, ChatOpenAI, ChatOllama, ChatLocalAI, ChatMistralAI, ChatTogetherAI, etc.
- **Embeddings** : Azure OpenAI, Cohere, Google GenerativeAI/VertexAI, HuggingFace Inference, LocalAI, MistralAI, Ollama, OpenAI (+ variante custom), TogetherAI, VoyageAI, AWS Bedrock.
- **Vector Stores** : AstraDB, Chroma, Couchbase, Elastic, Faiss, In-Memory, Milvus, MongoDB Atlas, OpenSearch, Pinecone, Postgres, Qdrant, Redis, SingleStore, Supabase, Upstash Vector, Vectara, Weaviate, Zep Collection.
- **Document Loaders** (très large) : Airtable, API Loader, Apify, BraveSearch Loader, Cheerio Web Scraper, Confluence, CSV, Custom, Document Store, Docx, Epub, Figma, File, FireCrawl, Folder, GitBook, Github, Google Drive, Google Sheets, Jira, JSON/JSONL, Excel/PPT/Word Microsoft, Notion (Database/Page/Folder), Oxylabs, PDF, Plain Text, Playwright/Puppeteer Web Scraper, S3, SearchApi/SerpApi web search, Spider, Text File, Unstructured File/Folder Loader.
- **Text Splitters** : Character, Code, Html-To-Markdown, Markdown, Recursive Character, Token.
- **Retrievers** : Cohere Rerank, Custom, Embeddings Filter, Extract Metadata, HyDE, LLM Filter, Multi Query, Prompt, Reciprocal Rank Fusion, Similarity Score Threshold, Vector Store, Voyage AI Rerank.
- **Memory** : Buffer, Buffer Window, Conversation Summary, Conversation Summary Buffer, DynamoDB, MongoDB Atlas, Redis-Backed, Upstash Redis-Backed, Zep (self-host ou cloud).
- **Chains** : GET/POST API Chain, OpenAPI Chain, Conversation Chain, Conversational Retrieval QA, LLM Chain, Multi Prompt Chain, Multi Retrieval QA, Retrieval QA, SQL Database Chain, Vectara QA, VectorDB QA.
- **Agents (classiques)** : Airtable Agent, AutoGPT, BabyAGI, CSV Agent, Conversational Agent, Conversational Retrieval Agent, MistralAI Tool Agent, OpenAI Assistant (wrap Assistants API), OpenAI Function Agent (**deprecating**), OpenAI Tool Agent, ReAct Agent Chat/LLM, Tool Agent, XML Agent.
- **Tools intégrés** : BraveSearch, Browserless, Calculator, Chain Tool, Chatflow Tool (appeler un autre chatflow comme outil), Custom Tool (JS), Exa Search, Google Custom Search, Google Drive, OpenAPI Toolkit, Python Interpreter, Read/Write File, Request Get/Post, Retriever Tool, SearchApi/SearXNG/SerpApi/Serper, Web Browser, **Code Interpreter by E2B** (sandboxé).
- **Output Parsers** : Advanced Structured (Zod), Structured (JSON), CSV, Custom List.
- **Prompts** : Prompt Template, Chat Prompt Template, Few Shot Prompt Template.
- **MCP** : nœud MCP personnalisé (stdio/SSE/HTTP) comme outil Chatflow ou nœud natif Agentflow V2.

### 2. Agent Builder / Agentflow (V1 → V2)
- **Agentflow V1 ("Sequential Agents")** : marqué **"(Deprecating)"** — pattern supervisor/worker type LangGraph.
- **Agentflow V2** (génération actuelle) : "superset de Chatflow et Assistant" — chat, agent unique, multi-agent, orchestration générale.
  - Architecture multi-agent : un Supervisor délègue à des Workers, historique de conversation complet partagé à chaque étape.
  - Moteur d'exécution à file d'attente + dépendances de nœuds permettant **boucles, branchement conditionnel, et human-in-the-loop** — impossible sur le canvas Chatflow linéaire.
  - MCP comme nœud de premier niveau (pas seulement un outil d'agent).
  - Limitation connue non résolue (figée par l'archivage) : intégrations d'observabilité (Langfuse/Lunary) rapportées cassées pour les traces Agentflow V2.

### 3. Chatflow vs Agentflow vs Assistant
| Concept | Usage | Plafond de complexité |
|---|---|---|
| Assistant | Bot FAQ simple : instructions + outils + RAG sur fichiers uploadés | Bas |
| Chatflow | Agent unique, chatbot, pipeline LLM modéré | Moyen — pas de boucle/branchement natifs |
| Agentflow (V1→V2) | Multi-agent, branchement conditionnel, boucles, human-in-the-loop | Haut — cible long terme |

### 4. RAG
- RAG ad hoc sur canvas (Loader → Splitter → Embeddings → Vector Store → Retriever) ou **Document Store** dédié (UI centralisée réutilisable entre flows) avec **prévisualisation des chunks** avant validation et **Record Manager** optionnel (dédup/incrémental évitant les doublons à la ré-ingestion).
- Boîte à outils retrieval mature : reranking (Cohere/Voyage), expansion de requête (Multi Query, HyDE), fusion (Reciprocal Rank Fusion).

### 5. Memory
Buffer / Buffer Window / Conversation Summary / Conversation Summary Buffer / Redis / Upstash Redis / MongoDB Atlas / DynamoDB / Zep (self-host ou cloud) ; `sessionId` passable via `overrideConfig` pour isoler des conversations concurrentes.

### 6. Tools & Intégrations
Custom Tool en JS avec accès `$vars`, whitelist npm via `TOOL_FUNCTION_EXTERNAL_DEP` ; intégrations tierces (Open WebUI, Zapier) ; MCP (voir §1/§2) ; **Analytics/Observabilité configurables** : LunaryAI, Langsmith, Langfuse, LangWatch, Arize, Phoenix, Opik (tracing Agentflow V2 rapporté cassé, non corrigé — projet gelé).

### 7. API
- `POST /api/v1/prediction/{chatflowid}` (+ `overrideConfig` pour sessionId/modèle) ; Swagger/OpenAPI auto-généré ; SDKs TypeScript/Python officiels ; auth par clé API (Bearer) liable à un chatflow spécifique (sinon invocation publique par défaut si l'ID est connu) ; widget embarquable JS officiel thémable ; API dédiée Document Store.

### 8. Multi-user / Auth / Workspaces (ligne de fracture Community vs Cloud/Enterprise la plus nette)
| Fonctionnalité | Community (self-host gratuit) | Cloud | Enterprise |
|---|---|---|---|
| Instance mono-utilisateur | Oui | — | — |
| Workspaces | **Non** | Oui | Oui |
| RBAC | Non | Oui | Oui |
| SSO (OIDC) | Non | Limité/incertain | Oui |
| LDAP | Non | Non | Oui |
| Audit logs | Non | Limité | Oui |
| Versioning formel de flow (UI) | Non | Limité | Oui |
| SLA uptime | Aucun | Non précisé | 99.99% |
| Credentials chiffrées | Oui (`FLOWISE_SECRETKEY_OVERWRITE` à épingler manuellement) | Oui | Oui |
| Variables d'environnement | Oui | Oui | Oui |
- **Piège opérationnel signalé** : clé de chiffrement auto-générée aléatoirement au démarrage si non épinglée — perte/rotation silencieuse casse le déchiffrement des credentials stockées.

### 9. Developer Experience
- Variables `{{var}}` (statiques/runtime), accessibles en Custom Tool via `$vars.nom`.
- **Marketplace de templates** : flows JSON pré-construits (RAG Q&A, SQL, orchestration multi-agent), simple fichier JSON déposé dans `server/marketplaces`.
- Import/export JSON (credentials exclues volontairement de l'export, à reconnecter manuellement après import).
- **Mode queue documenté** (`MODE=queue`, Redis/BullMQ) séparant tiers HTTP et workers d'exécution, scalable indépendamment, guide Docker et Kubernetes (autoscaling par profondeur de queue via KEDA plutôt que CPU).
- Versioning formel de flow = fonctionnalité Enterprise ; JSON export/import manuel = Community.

---

## PARTIE D — Onyx (ex-Danswer, onyx-dot-app/onyx)

*(Synthèse — rapport complet et sourcé dans [`reports/Onyx feature inventory 2026.md`](../reports/Onyx feature inventory 2026.md))*

### 0. Licence — split net dans un seul dépôt
- **MIT** pour tout ce qui est hors des dossiers `ee/` (`backend/ee/`, `web/src/app/ee/`, `web/src/ee/`).
- Ces dossiers `ee/` sont sous une **licence Enterprise Onyx séparée, non-OSI, "source-available"** : code visible publiquement mais **usage en production interdit sans licence payante** par siège, aucune clause de conversion type BUSL (pas de passage automatique en open source après N années) — restriction propriétaire permanente.
- Un mirroir potentiellement 100% FOSS existe (`onyx-dot-app/onyx-foss`), relation exacte avec le dépôt principal non vérifiée.
- **Distinction cruciale** : "Enterprise Edition" (concept de licence de code) ≠ "tier Enterprise" (nom commercial) — le tier payant "Business" ($20/utilisateur/mois) inclut déjà commercialement du code sous licence EE (RBAC, historique de requêtes) sans que ce soit le tier "Enterprise" complet.

### 1. Recherche d'entreprise
- Hybride BM25 + similarité vectorielle sur **OpenSearch** (Vespa entièrement retiré en v4.0.0, mai 2026 — toute source mentionnant Vespa comme actuel est obsolète).
- Scoping via **Document Sets** (filtres de recherche gérés par admin), filtres par type de source, tags/metadata clé-valeur, **filtrage temporel** (v4.4.0).
- Citations : requêtes parallèles (reformulation sémantique + variantes mot-clé), fusion par Reciprocal Rank Fusion pondérée, fusion des chunks adjacents, sélection/expansion des chunks les plus pertinents par le LLM avant assemblage de la réponse citée.
- v4.3.0 : "conversation-aware scoping" (sélection dynamique des sources à interroger par requête). v4.6.0 : endpoint `POST /api/search` public + CLI, "Incognito Mode".
- **Tier** : recherche hybride/doc sets/filtres/citations = **Community (MIT)**. **La recherche permission-aware (ACL au niveau document, miroir des permissions source) est réservée à l'Enterprise Edition** — en CE, aucune application automatique des permissions source, seulement une gestion manuelle par utilisateur/groupe.

### 2. Connecteurs — ~56 sources, sync par poll, permission-sync EE-only
- Liste confirmée (dossier `backend/onyx/connectors/`) : Airtable, Asana, Axero, Bitbucket, Blob storage (S3/GCS/R2/Oracle unifié), BookStack, Box, Braintrust, Canvas, Bitbucket, ClickUp, Coda, Confluence, Discord, Discourse, Document360, Dropbox, Drupal Wiki, Egnyte, File, Fireflies, Freshdesk, GitBook, GitHub, GitLab, Gmail, Gong, Google Drive, Google Sites, Guru, Highspot, HubSpot, IMAP, Jira, Linear, Loopio, LumApps, MediaWiki, Notion, Outline, Outlook, ProductBoard, Salesforce, SharePoint, Slab, Slack, Teams, TestRail, Web (crawler), Wikipedia, XenForo, Zendesk, Zoom, Zulip.
- **4 patterns de sync** : Load (réindexation complète point-in-time), Poll (rafraîchissement incrémental par plage de temps — mécanisme principal), Slim (fetch léger ID-only pour purge/cohérence), **Event-Based explicitement "conçu pour une implémentation future"** — donc **aucun connecteur actuel n'utilise de push webhook temps réel**, tout est en polling planifié (30 min par défaut, purge 30 jours).
- **Permission sync (ACL automatique) EE-only**, confirmé sur au moins 8 à 11 sources (Confluence, Jira, GitHub, Google Drive, Gmail, Slack, Salesforce, SharePoint + Box/Canvas/Outlook selon la source) — implémenté via un module dédié `onyx.external_permissions.sync_params` réservé EE, frontière de module réelle, pas juste UI.
- Chaque connecteur a 3 modes d'accès : Private, Public, **Auto Sync Permissions (EE)**.

### 3. Chat
- Édition/régénération de message, sélection de modèle par session, contrôles effort de raisonnement + température par session (v4.5.0).
- Citations en note de bas de page numérotées `[[n]](url)`, panneau de sources dédié, "Copy with references".
- Feedback pouces haut/bas (visible admin au survol), partage par lien.
- v4.6.0 : comparaison multi-modèles dans les chats partagés, "Incognito Mode" (rétention configurable), exécution des runs (chat + Deep Research) jusqu'au bout côté serveur même si le client se déconnecte.
- **"Persona", "Assistant" et "Agent" sont le même concept** chez Onyx. 4 agents intégrés : Search Agent, General Agent, Paraphrase Agent, Art Agent (génération d'image). Agents personnalisés : nom/description/icône, prompt système, questions de démarrage, scoping via Document Sets, LLM par défaut ; partage org-wide/groupe/"Featured" (pas de marketplace public cross-organisation).
- Pas d'export complet de transcript (PDF/Markdown/JSON) confirmé au-delà de "Copy with references".
- **Tier** : tout ceci = **Community (MIT)**.

### 4. Agents / Actions / MCP
- "Actions" (= Tools) définissables par import de spec OpenAPI. Intégrées : Knowledge (recherche interne), Image Generation (DALL-E 3), Web Search (Serper/Google PSE/Brave/SearXNG/crawler maison/Firecrawl/Exa), **Coding Agent** opt-in (bash + téléchargement de fichiers, désactivé par défaut, v4.0.0).
- **MCP bidirectionnel** : Onyx client MCP (transport HTTP/Streamable-HTTP uniquement, **pas de stdio**), auth No Auth/API Key/OAuth/Pass-Through OAuth ; Onyx serveur MCP (connecte Claude, Cursor, etc. à la base de connaissance Onyx). Itération rapide 2026 : contrôle d'accès par groupe (v4.4.0), pré-approbation d'outils pour tâches planifiées (v4.5.0), correctifs OAuth (v4.6.0), timeout dédié configurable (v4.7.0).
- **Tier : Community (MIT)** pour Actions, agents personnalisés et MCP (client+serveur) — non listés comme EE.

### 5. Deep Research
- Mode de chat activable par bascule (icône sablier), non automatique, **non supporté dans les "project chats"**.
- Hiérarchie multi-agent à 2 niveaux : Clarification Agent → Planning Agent → Orchestrator Agent (délègue à des sous-agents, peut rediriger en cours de route) → Research Agents (recherche avec accès outils) → Report Agents (rapports intermédiaires/finaux avec citations numérotées) — conçue pour éviter la dégradation d'info par sur-empilement d'agents.
- Exécution jusqu'au bout côté serveur indépendamment de la déconnexion client (v4.6.0).
- **Tier : Community (MIT), explicitement gratuit** — cœur du positionnement open source d'Onyx.

### 6. RAG / Search internals
- Chunking sensible aux tokens (dimensionné à la fenêtre de contexte du modèle d'embedding), mode "Multipass Indexing" optionnel (plusieurs tailles de chunk par document).
- **Contextual RAG** (`enable_contextual_rag`) : le LLM génère des résumés document/chunk à l'indexation, injectés dans le texte avant embedding (technique proche du "contextual retrieval" d'Anthropic) — maintenue activement (ré-indexation forward-only ajoutée en v4.6.0).
- **Reranking supprimé comme code mort en 2026** (PR #14781) : la classe `RerankingModel` et ses clients cross-encoder (Cohere, LiteLLM, AWS) ont été retirés faute d'appel runtime détecté par analyse statique — vestiges DB/frontend non fonctionnels restants. La pertinence repose désormais sur fusion hybride BM25+vecteur pondérée, enrichissement contextuel des chunks, et sélection de chunks par le LLM à la génération — **écart architectural réel vs pattern "hybride + reranker cross-encoder"** répandu ailleurs (dont KnowFlow).
- Expansion de requête via "Multilingual Expansion" (reformulation multi-langue) et pattern multi-requête (sémantique + mot-clé).
- Cache d'embedding de requêtes (v4.1.0). Taille/recouvrement de chunk par défaut non divulgués dans les sources primaires.

### 7. Traitement de documents
- Connecteur File générique : `.txt .pdf .docx .pptx .xlsx .csv .md .mdx .conf .log .json .tsv .xml .yml .yaml .eml .epub`.
- Chunking section-based pour XLSX/CSV (v3.3.0), étendu en "Tabular Indexing" (v4.5.0) ; extraction d'images intégrées des PDF (v4.0.0) ; durcissement gros fichiers (streaming ligne à ligne, extraction PDF en sous-process, v4.3.0) ; **retrait du parsing local "unstructured" en v4.7.0 au profit de l'API hébergée** — un déploiement self-hosted peut désormais dépendre d'un service externe pour le parsing de formats complexes.
- Images traitées par **résumé via modèle de vision** (description texte générée par LLM), **pas d'OCR classique confirmé** (pas de pipeline type Tesseract identifié).

### 8. Permissions / groupes / utilisateurs / admin
- Modèle de rôles en transition mi-2026 : ancien schéma (Admin, Basic, Curator, Global Curator) remplacé par un modèle de groupes avec "Group Managers" à partir de v4.7 (migration automatique, sans blocage).
- Types de compte : Standard, Service Account, Slack Bot, External User, Anonymous. Les groupes conditionnent l'accès aux connecteurs privés/Document Sets/Agents et peuvent porter des limites de tokens LLM par groupe ; **un compte sans groupe n'a aucune permission**.
- **Groupes personnalisés au-delà des 2 par défaut (Admin/Basic) = Enterprise Edition uniquement**, de même que le RBAC fin par groupe et le contrôle d'accès documentaire (auto-sync ET assignation manuelle).

### 9. Analytics / feedback
- Feedback pouces haut/bas = Community.
- Analytics d'usage (par équipe/LLM/agent), historique de requêtes, audit logging = **code sous licence Enterprise Edition** — mais commercialement inclus dans le tier payant "Business" (20$/utilisateur/mois) sans nécessiter la licence Enterprise complète pour les clients du cloud Onyx (nuance licence de code vs tier commercial).

### 10. API
- API REST couvrant quasiment toutes les fonctionnalités (Chat, Search, Document Management, Agents), explorateur OpenAPI/Swagger intégré (`/api/docs`).
- Auth par **API Keys** (comptes de service, accès dérivé des groupes) et **Personal Access Tokens** (expiration configurable, scopes granulaires : Search-Read, Chat-Read/Write, LLM Gateway-Use).
- Pas de SDK officiel Python/JS confirmé ; pas de politique de rate-limiting publique confirmée.
- **Tier** : API cœur = Community ; "Enterprise Edition APIs à accès étendu" listées séparément comme fonctionnalité EE.

### 11. Auth / SSO
- Email/password toujours actif sans configuration ; premier utilisateur inscrit = admin automatique.
- Google OAuth = tier payant bas (Business), **SAML 2.0 et OIDC spécifiquement réservés à l'Enterprise Edition**, à la fois commercialement et au niveau code (dossiers `ee/`).
- **SCIM 2.0** : provisioning/déprovisioning utilisateur, sync de groupe, mise à jour de profil, configuré via Admin Panel, guides Okta/Entra — **très probablement EE-only** (inféré, pas de source primaire unique explicite).

### 12. Liste des fonctionnalités Enterprise Edition (consolidée)
SSO OIDC/SAML 2.0 · SCIM (groupes/provisioning) · Permission Sync Connectors (8-11 sources) · Group-Based Permissions fines (v4.7+) · User Groups & RBAC personnalisés · Usage Analytics · Encrypted Secrets · Whitelabeling · Hook Extensions (logique custom injectée dans le pipeline sans modifier le code source) · Enterprise Edition APIs · Priority Support. Le tier commercial "Enterprise" ajoute aussi : déploiement on-premise, déploiement régional, accès anticipé aux fonctionnalités, intégrations sur mesure, exports de données, facturation par facture, remises volume, tarifs éducation, SLA — ces derniers sont des conditions commerciales/contractuelles, pas du code verrouillé.

---

## PARTIE E — AnythingLLM (Mintplex-Labs/anything-llm)

*(Synthèse — rapport complet et sourcé dans [`reports/AnythingLLM feature inventory.md`](../reports/AnythingLLM feature inventory.md))*

### 0. Licence
- **MIT pur, monorepo unique, aucun split open-core**, depuis le tout premier commit (juin 2023). Seule exception : sous-dossier expérimental non intégré `open-computer` (bureau virtuel, hérité d'un submodule QEMU) sous **AGPLv3**, isolé du produit principal.
- **AnythingLLM Cloud** (Basic 50$/mois, Pro 99$/mois, Enterprise sur devis) est, fait notable, un **sous-ensemble fonctionnel**, pas un sur-ensemble, du build Docker gratuit : le Cloud désactive explicitement les Agent Skills personnalisées et le support MCP, et ne fournit aucun LLM local embarqué — pour des raisons de sécurité multi-tenant et de contraintes matérielles.

### 1. Workspaces
- Unité d'isolation de **configuration**, pas seulement de documents : température, longueur d'historique (défaut 20), prompt système override, seuil de similarité (défaut 0.25), provider/modèle de chat override, `topN` (nombre de snippets de contexte, défaut 4), mode de chat, **et un provider/modèle séparé spécifiquement pour le mode Agent** — permet de faire tourner le chat normal sur un modèle local bon marché tout en réservant un modèle plus fort aux sessions agent.
- 3 modes de chat : **Agent Mode** (appel d'outils natif automatique), **Chat Mode** (mélange contexte récupéré + connaissances générales du modèle), **Query Mode** (répond strictement depuis les documents uploadés, seuil de similarité configurable No restriction/Low ≥.25/Medium ≥.50/High ≥.75, réponse de refus personnalisable).
- Isolation vectorielle exacte au niveau DB non totalement vérifiée (champ `vectorTag` suggérant un filtrage par tag metadata) ; un mode "Accuracy Optimized" alternatif est mentionné (Cloud) sans détail complet.

### 2. RAG — ingestion large, chunking peu sophistiqué
- Formats : texte/markup (.txt .md .org .adoc .rst .csv .json .html), Office (.docx .pptx .xlsx .odt .odp), .pdf, .mbox, .epub, audio (.wav .mp3 .ogg .oga .opus .m4a .webm, transcrit via Whisper), quelques images/vidéos (.png .jpg .webp .mp4 .mpeg) ; **.doc legacy binaire non supporté**.
- Connecteurs : loader Git/GitHub générique avec awareness de branche, transcription YouTube (préférant les sous-titres humains aux auto-générés), crawler récursif "Website Depth", Confluence, Drupal Wiki, Obsidian Vault, Paperless-NGX ; GitLab traité dans le loader repo générique (issues/discussions/wiki inclus) ; **pas de connecteur Sitemap XML autonome confirmé**.
- **10 vector DB** : LanceDB (embarqué par défaut), Astra DB, Chroma, Chroma Cloud, Milvus, PGVector, Pinecone, Qdrant, Weaviate, Zilliz — tous MIT.
- **14 moteurs d'embedding** : Azure OpenAI, Cohere, Gemini, Generic OpenAI, Lemonade, LiteLLM, LM Studio, Local AI, Mistral, **Native** (25MB CPU embarqué, sans clé API), Ollama, OpenAI, OpenRouter, Voyage AI.
- **Chunking : `RecursiveCharacterTextSplitter` plat, défaut 1000 caractères / 20 de recouvrement**, exposé en UI comme deux simples champs — **pas de chunking sensible à la structure/aux titres** (feature request ouverte #6364 confirmant l'absence) — point faible confirmé vs des stacks RAG plus sophistiquées.
- Mécanique de citation en chat **non confirmée** dans les sources atteintes (question ouverte, pas une lacune confirmée).

### 3. Agents — 3 mécanismes d'extension, dont 2 coupés en Cloud
- Invocation automatique (LLM à tool-calling natif) ou manuelle (`@agent`), fin sur complétion ou `/exit`.
- **~10 skills intégrées** : RAG Search, Web Browsing, Web Scraping, Save Files, List Documents, Summarize Documents, Chart Generation, SQL Agent, File System Agent, Create Scheduled Jobs (statut Gmail/Calendar/Outlook/Document-Generation comme built-in vs Hub add-on non tranché).
- **Custom Agent Skills** : plugins NodeJS (`plugin.json` + `handler.js`), capables d'invocations système, disponibles Docker (depuis v1.2.2) et Desktop (v1.6.5) mais **explicitement exclues du Cloud** (raison de sécurité multi-tenant).
- **Community Hub** (hub.anythingllm.com, bêta) : publication/partage de skills, prompts système, slash commands via CLI dédiée.
- **Agent Flows** : constructeur visuel no-code (chaînage d'appels API/étapes LLM/opérations fichiers), déclenchable à la demande ou via cron, compatible MCP — Docker et Desktop, **support Cloud incertain mais probablement absent** (même pattern que Custom Skills).
- **MCP client natif depuis v1.8.0** (stdio, SSE, Streamable), configuré via `anythingllm_mcp_servers.json`, intégration Docker Model Runner (v1.10.0). **Cloud désactive explicitement le MCP** — même raison de sécurité. AnythingLLM comme **serveur** MCP reste communautaire uniquement (feature request officielle ouverte #6403).

### 4. Modèles
- **~38-40 providers LLM** intégrés (majors + agrégateurs OpenRouter/LiteLLM/APIpie + long tail Cerebras/DeepSeek/Fireworks/Groq/Moonshot/Novita/NVIDIA NIM/SambaNova/xAI/Zai...), tous MIT, aucun verrouillé en self-hosted.
- Inférence locale traitée en 1ère classe : Ollama, LM Studio, Local AI, KoboldCPP, oMLX, Text-Generation-WebUI, Lemonade, llmman + **"AnythingLLM Default"** (LLM et embedder embarqués, 25MB CPU, aucune clé API, fonctionnement 100% offline).
- Override de modèle par workspace au niveau provider ET modèle, séparément pour le mode Agent.
- **Cloud ne fournit aucun LLM local embarqué** ("doit se connecter à des providers cloud externes ou faire tourner son propre LLM local").
- TTS : 6 options (Native système, navigateur, Piper local, Kokoro self-hosted, OpenAI, ElevenLabs, générique compatible OpenAI) ; STT : Native navigateur et OpenAI seulement confirmés, **entrée vocale absente sur Desktop**.

### 5. Chat — multi-utilisateur via bascule irréversible
- Regenerate, Edit (tronque et resoumet, pas de branchement confirmé), Feedback pouces (qualitatif, pensé pour export type RLHF), Copy, Speak.
- **Threads** multiples par workspace (`WorkspaceThread`), documents uploadés isolés par thread, documents du workspace visibles dans tous les threads (bug documenté d'incohérence API vs UI principale sur les endpoints de thread).
- **Pinning de document** : injecte le texte intégral dans chaque prompt du workspace, contournant le retrieval par chunks — manuel uniquement, pas de promotion automatique.
- Export d'historique en **CSV uniquement** par workspace/utilisateur (≥10 logs), désactivable globalement par admin (désactive aussi l'export/suppression) — demande de format JSONL toujours ouverte.
- **Streaming token par token non confirmé** — écart à vérifier directement.
- **3 rôles exactement** : Admin (contrôle total), Manager (large gestion workspace/utilisateurs mais pas d'accès config LLM/Embedder/Vector DB/clé API), Default (accès restreint aux workspaces explicitement assignés, style allow-list, pas de notion de "groupes" séparée) — débat mainteneur actif sur le périmètre trop large de Manager (issue #5857).
- **Mode multi-utilisateur = bascule à sens unique, irréversible** depuis Settings → Security, **Docker uniquement** (absent de Desktop, architecturalement mono-utilisateur).
- **Aucun SSO (SAML/OIDC) trouvé dans la documentation officielle** — absence probable mais non confirmée en OSS ; le tier Cloud Enterprise annonce "SSO, RBAC, et plus" comme différenciateur payant, suggérant un SSO potentiellement livré uniquement en service géré, pas en OSS.

### 6. API
- API REST complète (~58 endpoints rapportés, non vérifié sur la spec brute), OpenAPI 3.0, Swagger UI interactif sur `/api/docs` (désactivable via `DISABLE_SWAGGER_DOCS`) — entièrement MIT, non payant.
- **Clés API non scopées** (pas de portée par workspace/rôle/endpoint) — modèle plus grossier qu'un système de clés SaaS typique.
- Pas de SDK officiel JS/Python de premier niveau — CLI officielle (`@mintplex-labs/anything-llm-cli`) et CLI Hub séparée pour la publication de skills ; les développeurs sont censés générer un client depuis la spec OpenAPI eux-mêmes.

### 7. Widget embarquable + Admin
- Widget **Docker uniquement** (absent de Desktop, probablement absent de Cloud aussi — non vérifié spécifiquement).
- Un embed = un workspace (`data-embed-id`), personnalisation riche via `data-*` : position (4 coins), 5 styles d'icône, couleur hex, image de marque, texte d'accueil, nom de l'assistant, taille de fenêtre, langue, retrait du footer sponsor, overrides modèle/température/prompt système par embed.
- **Allowlist de domaine existe mais est ouverte par défaut** (n'importe quelle origine peut interroger un embed sans allowlist configurée), sauf activation explicite de `EMBED_REQUIRE_ALLOWLIST` — **risque d'exposition réel** que l'opérateur doit corriger activement.
- Gouvernance d'usage : plafonds max-chats/jour et max-chats/session par embed (0 = illimité).
- Le widget **retire les snippets de contexte/citations pour les utilisateurs anonymes** (sessions randomisées) — parité streaming/citation avec l'app principale non confirmée.
- **Event Logs** admin toujours actif (connexions, messages envoyés, changements de config, uploads de documents), stockage local, **pas de politique de rétention/export confirmée** — lacune réelle pour un acheteur enterprise/conformité.
- Télémétrie PostHog activée par défaut (exclut PII/contenu documents/logs de chat), désactivable (`DISABLE_TELEMETRY`) — opt-out historiquement incomplet selon une issue ouverte.
- **White-labeling (logo login, messages d'accueil, liens/icônes footer) exclusif au self-hosted Docker** — absent de Desktop **ET du Cloud payant** (les clients Cloud ne peuvent pas rebrander leur instance).

### 8. Formes de déploiement
- **Docker self-host** = build de référence complet : RBAC multi-utilisateur, embeds, white-labeling, agents, MCP, matrice complète de providers — gratuit, MIT. Déployable via Compose, bare metal, boutons one-click (Railway/Render/DigitalOcean/AWS/GCP/RepoCloud), chart Helm officiel Kubernetes.
- **Desktop** (Mac/Windows/Linux) : mono-utilisateur volontairement restreint, installeur one-click avec LLM local embarqué, embedder CPU, LanceDB — sans multi-utilisateur, embeds, white-labeling, agents, entrée vocale.
- **AnythingLLM Cloud** : instances mono-tenant isolées sur AWS, positionné comme plus simple à essayer plutôt que plus capable — **sous-ensemble fonctionnel** du Docker gratuit (pas d'agents custom, pas de MCP, pas de LLM local, pas de white-label).

### Ce que cela signifie pour un concurrent (synthèse de l'agent de recherche)
Le signal stratégique le plus net : le tier Cloud payant d'AnythingLLM n'est pas "plus de fonctionnalités pour plus d'argent" — c'est une version *contrainte pour la sécurité* du logiciel gratuit, privée précisément de l'extensibilité (agents custom, MCP) et du contrôle de marque (white-label) que les acheteurs enterprise veulent le plus. Un produit hébergé multi-tenant qui supporte ces trois choses en toute sécurité serait une différenciation durable plutôt qu'une course à la parité.

---

## PARTIE F — Matrice comparative globale

Légende : ✅ disponible · 🟡 partiel/limité · ❌ absent · 🔒 Enterprise/commercial uniquement · 🔌 plugin/intégration tierce · 🧪 expérimental/beta · ⚰️ mort/non maintenu (Flowise) · ❓ non vérifié avec certitude

| Domaine | Fonctionnalité | Dify | RAGFlow | Flowise | Onyx | AnythingLLM | **KnowFlow** |
|---|---|---|---|---|---|---|---|
| **Auth** | Email/mdp | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| | OAuth Google | ✅🔌 | ❓ | ✅🔌 | ✅ | ❓ | ✅ |
| | OAuth GitHub | ✅🔌 | ❓ | ✅🔌 | ❓ | ❓ | ✅ |
| | 2FA TOTP | ❓ | ❓ | ❓ | ❓ | ❓ | ✅ |
| | 2FA WebAuthn/FIDO2 | ❓ | ❓ | ❓ | ❓ | ❓ | ✅ |
| | SSO OIDC | 🔒 Enterprise | ❓ | 🔒 Enterprise | 🔒 EE | ❌ non confirmé | ✅ |
| | SSO SAML | 🔒 Enterprise | ❓ | ❓ | 🔒 EE | ❌ | ❌ (décision documentée) |
| | SCIM | 🔒 Enterprise | ❓ | ❓ | 🔒 EE (inféré) | ❌ | ❌ |
| | Sessions actives + révocation | ❓ | ❓ | ❓ | ❓ | ❓ | ✅ |
| **Multi-tenant** | Organizations/Workspaces | ✅ | ✅ (tenant) | 🔒 Cloud/Ent | ✅ | ✅ | ✅ |
| | Rôles multiples (Owner/Admin/Member...) | ✅ (4 rôles) | ✅ (2 couches) | 🔒 Ent | ✅ (transition v4.7) | ✅ (3 rôles) | ✅ (6 rôles) |
| | Groupes personnalisés + RBAC fin | 🔒 Enterprise | ❓ | 🔒 Enterprise | 🔒 EE | ❌ (pas de notion groupe) | 🟡 (Casbin construit, non branché) |
| | Permissions granulaires par ressource | 🔒 Enterprise | ✅ (3 couches) | 🔒 Enterprise | 🔒 EE (doc-level) | ❌ | 🟡 (branché workspaces seulement) |
| | RLS base de données | ❓ | ❓ | ❓ | ❓ | ❓ | 🟡 (activée mais bypassée) |
| | Quotas d'usage | ✅ Cloud | ❓ | 🔒 Ent | ❓ | ❌ | ✅ (10 dimensions) |
| | White-label | ❓ | ❓ | 🔒 Ent | 🔒 EE | ✅ Docker seul. (❌ Cloud) | ✅ |
| | Domaines personnalisés | ❓ | ❓ | ❓ | ❓ | ❌ | ✅ |
| **Ingestion documents** | PDF/DOCX/TXT/MD/HTML/CSV/JSON/XML | ✅ (+plugins pour OCR avancé) | ✅ (DeepDoc natif) | ✅ (loaders) | ✅ | ✅ | ✅ |
| | EPUB | 🔌 | ✅ | 🔌 | ✅ | ✅ | ✅ |
| | OCR natif (pas juste plugin) | 🔌 | ✅ (moteur propre) | 🔌 (Unstructured) | ❌ (résumé vision, pas OCR) | ❓ | 🟡 (via fallback OCR) |
| | Extraction tableaux avec structure | 🔌 | ✅ (TSR, 5 labels) | 🔌 | 🟡 (Tabular Indexing) | ❌ | 🟡 |
| | Google Drive / Docs | 🔌 | ✅ | ✅ (loader) | ✅ (+ perm-sync EE) | ❌ (pas confirmé) | ✅ (réel) |
| | Slack / Teams / Discord (import) | 🔌 | ✅ | ❌ | ✅ (Slack/Teams) | ❌ | ✅ (réel) |
| | Confluence / Notion / OneDrive | 🔌 | ✅ | ✅ (loaders) | ✅ | ✅ (Confluence) | ✅ (réel) |
| | GitHub repos/issues | 🔌 | ✅ | ✅ (loader) | ✅ | ✅ (repo+issues) | ✅ (réel) |
| | Sitemap / crawl web | 🔌 | ✅ | ✅ (loader) | ✅ (Web connector) | 🟡 (Website Depth, pas sitemap dédié) | ✅ |
| | ZIP fan-out | ❓ | ❓ | ❓ | ❓ | ❓ | ✅ |
| | Connecteurs "entreprise" (Salesforce, Zendesk, Jira, Linear...) | 🔌 | ✅ (Salesforce, BigQuery, Azure DevOps) | ❌ | ✅✅ (~56 connecteurs, le plus large) | ❌ | ❌ |
| | Permission sync (ACL miroir source) | ❓ | ❓ | ❓ | 🔒 EE (8-11 sources) | ❌ | ❌ |
| **Chunking** | Fixed-size | ✅ | ✅ | ✅ (Text Splitters) | ✅ | ✅ (défaut, seul dispo) | ✅ (seul branché) |
| | Recursive/Semantic/Markdown-aware/Sentence/Paragraph/Parent-Child/Code-aware | ✅ (Parent-Child, Q&A) | ✅✅ (10 méthodes nommées + "compilation" Wiki/Graph/Tree/Mind Map/Timeline) | ✅ (Recursive/Code/Markdown/Token splitters) | 🟡 (token-aware, multipass) | ❌ (feature request ouverte) | 🟡 (6 stratégies codées, **non branchées en prod**) |
| **Retrieval** | Vector + BM25 + RRF | ✅ | ✅ | ✅ (retrievers dédiés) | ✅ | 🟡 | ✅ |
| | Reranking cross-encoder | ✅ | ✅ | ✅ (Cohere/Voyage Rerank) | ⚰️ **supprimé comme code mort en 2026** | ❌ | ✅ |
| | Query rewriting / HyDE / Multi-query | 🟡 | 🟡 | ✅ (nœuds dédiés) | ✅ (Multilingual Expansion) | ❌ | 🟡 (codé, **non branché à l'API**) |
| | MMR / déduplication / compression contexte | ❓ | ❌ | ❓ | ❌ | ❌ | ❌ (codé, non branché) |
| | Filtrage metadata | ✅ | ✅ (accéléré index) | ❓ | ✅ | ❓ | ❌ (absent du schéma de requête) |
| | GraphRAG / Knowledge Graph | ❌ | ✅✅ (avec dédup d'entités LLM) | ❌ | ❌ | ❌ | ❌ |
| | Modes de raisonnement (Low/Med/High/Ultra) | ❌ | ✅ | ❌ | 🟡 (Deep Research) | ❌ | ❌ |
| **Multi-LLM** | Anthropic/OpenAI/Gemini/Mistral/Ollama | ✅ (marketplace) | ✅ | ✅ (nœuds dédiés) | ✅ | ✅✅ (~38-40 providers) | ✅ (via LiteLLM) |
| | Fallback automatique de provider | ❓ non confirmé | ❓ | ❓ | ❓ | ❓ | ✅ (réel) |
| | Structured output / JSON mode | ✅ | ❓ | 🟡 (Output Parsers) | ❓ | ❓ | ❓ à vérifier |
| **Embeddings** | OpenAI/Cohere/Voyage/HF/SentenceTransformers | ✅ | ✅ | ✅ | ✅ | ✅✅ (14 moteurs) | ✅ |
| **Agent — architecture** | Function calling / ReAct | ✅ | ✅ | ✅ (Tool/ReAct/XML Agents) | ✅ | ✅ | 🟡 (sélection textuelle, pas de vraie boucle function-calling) |
| | Mémoire court terme / cross-session | ✅ | 🟡 (peu documenté) | ✅ (9 types Memory) | ❓ | ✅ | ✅ |
| | Sandboxing exécution code | ✅ (DifySandbox) | ❓ | ✅ (E2B Code Interpreter) | ✅ (Coding Agent opt-in) | 🟡 (skills = code Node non sandboxé documenté) | ✅ (AST whitelist, pas d'exec réel) |
| | Human-in-the-loop | ✅ (nœud Human Input) | 🟡 | ✅ (Agentflow V2) | ❌ non confirmé en agent simple | ❌ | ✅ (réel, autonomous agents) |
| | Exécution parallèle d'outils | ✅ | ❓ | ❓ | ❓ | ❓ | ❌ (codé, orphelin) |
| | Validation de résultat d'outil | ❓ | ❓ | ❓ | ❓ | ❓ | ❌ (codé, orphelin) |
| **Agent — outils** | Web search | 🔌 | ✅ (Tavily+8 autres) | ✅ (10+ providers) | ✅ (6 providers) | ✅ | ✅ (Tavily) |
| | SQL / base de données | ✅ (nœud) | ✅ (Execute SQL) | ✅ (SQL Chain/Agent) | ❓ | ✅ (SQL Agent) | ✅ (réel, lecture seule) |
| | Email | 🔌 | ✅ (SMTP) | ❓ | ❓ | 🔒 Hub? | ✅ (réel) |
| | Calendrier | 🔌 | ❓ | ❓ | ❓ | ❓ | ✅ (réel) |
| | Génération de documents | 🔌 | ✅ (Markdown→PDF/DOCX) | ❓ | ❓ | ✅ | ❌ |
| | **MCP (client)** | ✅✅ (natif v1.6.0) | ✅ | ✅ (nœud dédié) | ✅✅ (natif) | ✅ (natif v1.8.0) | ❌ **absent** |
| | **MCP (serveur)** | ✅ | ✅ | 🔌 (communautaire) | ✅ | ❌ (feature request ouverte) | ❌ **absent** |
| **Agent Builder (UI)** | ✅ complet (modèle/KB/outils/mémoire/perms/garde-fous) | N/A (pas d'agent "builder" séparé — c'est le canvas) | N/A | ✅ (Personas/Custom Agents complet) | 🟡 | 🟡 très limité (nom/desc/prompt seulement) |
| **Workflow Builder** | UI visuelle | ✅✅ complet | ✅ (canvas Agent unifié) | ✅✅ (référence historique du genre) | ❌ (pas de concept workflow visuel) | ✅ (Agent Flows no-code) | ❌ **aucune UI** |
| | Moteur d'exécution (triggers/boucles/conditions/parallélisme/erreurs/retry) | ✅✅ très complet | ✅ | ✅✅ | N/A | 🟡 (Agent Flows plus simple) | ✅ (backend, **construit dans cette session** : condition, boucle via cycles, retry non générique, pas de parallélisme) |
| | Versioning de workflow | ✅ (Draft/Publish + diff) | ❓ | 🔒 Enterprise | N/A | ❓ | ✅ (réel : versions + diff + restore) |
| | Import/export (DSL/JSON) | ✅ (YAML DSL) | ❓ | ✅ (JSON) | N/A | ❓ | ❌ |
| | Marketplace de templates | ✅ | ❓ | ✅ | N/A | 🟡 (Community Hub, skills seulement) | ❌ |
| **Citations** | Cliquables + score + passage exact | ✅ | ✅ | 🟡 | ✅✅ (panneau sources + expansion LLM) | ❓ non confirmé | 🟡 |
| **Anti-hallucination** | Détection/score de fidélité | 🟡 (via Langfuse externe) | ❓ | ❓ | ❓ | ❓ | ✅ (scoring déterministe réel) |
| **Evaluation Lab** | Métriques retrieval/génération, comparaison modèles | 🟡 (annotations + Langfuse) | ❓ | 🔌 (via Langfuse/Langsmith externes) | ❓ | ❌ | ✅ (réel, jobs + comparaisons) |
| **Chat UI** | Streaming | ✅ | ✅ | ✅ | ✅ | ❓ non confirmé | ✅ |
| | Markdown + coloration code | ✅ | ❓ | ✅ | ✅ | ❓ | ❌ **absent** (trou confirmé) |
| | Regenerate/Edit/Retry/Feedback | ✅ | 🟡 | ✅ | ✅ | ✅ (sauf branching) | ✅ |
| | Historique + recherche + rename + delete | ✅ | ✅ | ✅ | 🟡 (pas d'export complet) | ✅ (CSV seulement) | ✅ |
| | Partage de conversation | ✅ | ✅ (embed) | ✅ | ✅ | ❓ | ✅ |
| | Export (PDF/DOCX/JSON) | ❓ | ❓ | ❓ | ❌ (pas confirmé) | 🟡 (CSV seulement) | ❌ |
| **Voice** | STT/TTS intégré | ❓ | ❓ | ❓ | ❓ | ✅ (6 TTS, STT limité) | 🟡 (composants réels, non intégrés au chat) |
| **Widget embarquable** | Script + branding + position + langue | ✅ | ✅ | ✅ (officiel, thémable) | ❓ | ✅ | ✅ |
| | Allowlist de domaine | ❓ | ❓ | ❓ | ❓ | 🟡 (existe, ouvert par défaut) | ❌ **absent** |
| **API publique** | REST versionnée + clés API + scopes | ✅ | ✅ | ✅ | ✅✅ (PAT scopés) | ✅ (clés non scopées) | ✅ |
| | SDK officiels | ✅ (Python/Node) | ✅ (Python) | ✅ (TS/Python) | ❌ non confirmé | ❌ (CLI seulement) | ✅ (Python/JS/React/Vue) |
| | Webhooks entrants/sortants | ✅ | ❓ | ❓ | ❓ | ❓ | ✅ (workflows) |
| **Intégrations chat** | Slack/Teams/Discord (bot de chat) | 🔌 | ✅ (2026) | ❓ | 🟡 (Slack Bot = type de compte) | ❌ | ✅ (réel) |
| **Billing** | Stripe/Paystack intégré et configuré | N/A (produit, pas plateforme facturable) | N/A | 🔒 Cloud (interne) | N/A (SaaS propriétaire) | N/A (SaaS propriétaire) | 🟡 (Stripe réel mais **non configuré par défaut**) |
| **Monitoring** | /health, /metrics Prometheus | ❓ | ❌ non confirmé | ❓ | ❓ | ❓ | ✅ |
| **Sécurité IA** | Prompt injection / jailbreak filtrant en direct | ❓ | ❓ | ❓ | ❓ | ❓ | 🟡 (écrit, non branché en filtre live) |
| | PII detection/masking | ❓ | ❓ | ❓ | ❓ | ❓ | ❌ |
| | SSRF protection | ❓ | ❓ | ❓ | ❓ | ❓ | ❌ |
| **Marketplace plugins** | ✅ (modèles/outils/stratégies) | ❌ | ❓ | ❌ | ❌ (Community Hub = skills seulement) | ✅ (réel, sandboxé Docker) |

*Note méthodologique : les colonnes concurrentes reflètent fidèlement les rapports sourcés des Parties A-E, y compris leurs propres `❓`/`non confirmé` — ne pas les convertir en "absent" sans re-vérification. La colonne KnowFlow reflète l'audit direct du code effectué dans cette conversation (voir Partie G).*

---

## PARTIE G — KnowFlow actuel (audit direct du code, pas une supposition)

Cette partie résume ce qui a été vérifié **en lisant le code réel** (pas la documentation interne du projet, qui a un historique de sur-estimation) au fil de cette conversation et des vérifications ciblées faites pour ce rapport.

### G.1 — Ce qui est réellement fait et testé (✅)
- **Auth complet** : email/mdp, OAuth Google/GitHub, 2FA TOTP + WebAuthn, reset mdp, sessions, rate limiting Redis réel. 45/45 tests réels passés sur rôles/permissions/organisations.
- **Ingestion** : PDF(+OCR)/DOCX/TXT/MD/HTML/CSV/JSON/XML/EPUB, + connecteurs réels Google Drive/Notion/Confluence/OneDrive/GitHub/Slack/Teams/Discord/sitemap/ZIP (`api/tasks/*_import.py`).
- **Retrieval hybride** : BM25 + vecteurs + RRF + reranking cross-encoder, branché sur `POST /organizations/{org_id}/search`.
- **Multi-LLM/embeddings** : LiteLLM (Anthropic/OpenAI/Gemini/Mistral/Ollama) avec fallback réel, 5 providers d'embedding.
- **Anti-hallucination** : scoring déterministe à 5 facteurs, branché sur chaque réponse.
- **Agents autonomes** : boucle multi-étapes réelle (plan → exécution → coût → garde-fous) — `api/services/autonomous_agents.py`.
- **Workflow Builder (backend)** : **construit dans cette session** — `api/services/workflow_engine.py` exécute réellement le graphe nœud par nœud (llm/rag/search/http/condition/code/email/calendar/database), pause/reprise sur bloc humain, cap anti-boucle, déclenchement cron réellement fonctionnel via Celery Beat. 17 nouveaux tests, 77/77 passés.
- **Frontend** : build propre (0 erreur TS/lint), chat avec streaming SSE réel, citations, historique, partage, feedback ; dashboard réellement branché à l'API (billing, sécurité, marketplace...).
- **Widget embarquable** : script JS autonome réel.
- **API publique v1** : 9 endpoints réels + gestion de clés (rotation/scopes/quotas) + SDK Python/JS/React/Vue réellement écrits et testés.
- **Marketplace de plugins** : sandboxing Docker réel (`--network none`, `--read-only`, `--cap-drop ALL`).
- **Monitoring** : `/health`, `/ready`, `/metrics` Prometheus réels.
- **Evaluation Lab** : jobs réels, comparaisons de déploiement, seuils de régression.

### G.2 — Ce qui existe mais est mal branché (🟡)
- **RBAC Casbin** : moteur complet et testé, jamais appelé par les routes réelles.
- **6 stratégies de chunking sur 7** : écrites, testées unitairement, jamais appelées en production (seul le chunking taille fixe tourne).
- **HyDE, multi-query, MMR, query rewriting, context compression, filtrage metadata** : code réel non trivial, zéro appelant, absents du schéma de requête `/search`.
- **Sélection d'outils par l'agent** : textuelle seulement (ajoutée au prompt), pas de vraie boucle de function-calling qui exécute.
- **Exécution parallèle d'outils + validation des résultats d'outils** : code écrit, jamais appelé.
- **Agent Builder (UI)** : backend riche, interface limitée à nom/description/prompt.
- **Voice AI** : composants réels (STT/TTS, push-to-talk, VAD), page démo isolée, jamais intégrée au chat.
- **RLS Postgres** : activée mais contournée (`BYPASSRLS`), isolation 100% applicative.
- **Sécurité IA (guardrails)** : détection prompt injection/jailbreak écrite, pas branchée en filtre actif.
- **Facturation** : code Stripe réel, mais livré non configuré par défaut (pas de Paystack, contrairement à ce qu'annonçait le cahier des charges).

### G.3 — Ce qui est complètement absent (❌) — confirmé par cette nouvelle recherche
- **MCP (Model Context Protocol)** — client ET serveur — **absent alors que les 5 plateformes concurrentes l'ont toutes**, dont 3 en natif bidirectionnel (Dify, Onyx, RAGFlow) et 1 en client natif (AnythingLLM). C'est le plus gros écart de standard d'interopérabilité 2026.
- **Connecteurs "entreprise"** au niveau d'Onyx : Salesforce, Zendesk, Jira, Linear, Asana, HubSpot, etc. — KnowFlow n'a que les connecteurs "documentaires" de base (Drive/Notion/Confluence/OneDrive/GitHub/Slack/Teams/Discord), pas les CRM/ticketing/PM.
- **Permission sync (ACL miroir depuis la source)** — absent, alors qu'Onyx en a fait sa killer feature Enterprise sur 8-11 connecteurs.
- **GraphRAG / Knowledge Graph** — RAGFlow a une implémentation avancée avec déduplication d'entités par LLM ; KnowFlow n'a rien.
- **Interface visuelle du Workflow Builder** — aucune (React Flow ou équivalent), alors que Dify/Flowise/AnythingLLM en ont une mature, et que le moteur backend vient d'être construit sans interface pour le piloter.
- **Markdown + coloration syntaxique dans le chat** — absent, alors que la quasi-totalité des concurrents l'ont.
- **Allowlist de domaine sur le widget** — absente (même AnythingLLM en a une, bien qu'ouverte par défaut).
- **Export de conversation** (PDF/DOCX/JSON) — absent.
- **Marketplace de templates de workflows/agents** — absent.
- **SCIM** — absent (comme AnythingLLM, mais Dify/Onyx l'ont en Enterprise).
- **PII detection/masking, SSRF protection, scan antimalware** — absents.

---

## PARTIE H — Gap Analysis

### H.A — Déjà terminé (confirmé fonctionnel, pas besoin d'y retoucher)
Auth, multi-tenant de base, ingestion documentaire (formats + connecteurs collaboratifs), retrieval hybride + reranking, multi-LLM/embeddings avec fallback, anti-hallucination, agents autonomes, moteur d'exécution de workflow (backend), frontend chat/dashboard, widget, API publique + SDKs, marketplace de plugins sandboxée, monitoring, evaluation lab.

### H.B — Partiellement terminé (fondation réelle, à finir de brancher — pas à recoder)
RBAC Casbin (brancher, `asgi-lifespan` sur les tests) · 6 stratégies de chunking (sélectionner par type de document) · techniques de retrieval avancées (exposer comme options de `SearchRequest`) · function-calling agent réel · exécution parallèle d'outils · Agent Builder UI · Voice AI (intégrer au chat) · RLS réelle (rôle Postgres dédié) · guardrails IA en filtre actif · configuration Stripe de bout en bout.

### H.C — Manquant (à développer, priorité fixée en Partie J)
MCP client + serveur · connecteurs CRM/ticketing (Salesforce, Zendesk, Jira, Linear, HubSpot) · permission sync · interface visuelle du Workflow Builder (React Flow) · GraphRAG · Markdown/coloration dans le chat · allowlist de domaine widget · export de conversation · marketplace de templates · SCIM · PII/SSRF/antimalware.

### H.D — À améliorer (KnowFlow a une version inférieure aux références)
- **Reranking** : KnowFlow a un reranking cross-encoder classique fonctionnel — c'est en fait **supérieur à Onyx**, qui l'a retiré en 2026. Rien à faire ici, juste le noter comme un vrai avantage compétitif à ne pas perdre.
- **Chunking** : n'a qu'une stratégie active contre 10 méthodes nommées + 6 représentations structurelles chez RAGFlow. Écart important sur la sophistication d'ingestion documentaire.
- **Agent Builder UI** : très en retrait face à Onyx (Personas complets) ou AnythingLLM.
- **Widget** : fonctionnel mais sans allowlist de sécurité, contrairement à AnythingLLM.

### H.E — Redondant (plusieurs façons de faire la même chose ailleurs, à choisir une approche unique pour KnowFlow)
- Recherche avancée : query rewriting/HyDE/multi-query/MMR existent déjà en code chez KnowFlow — il ne s'agit pas d'un choix entre plusieurs implémentations concurrentes mais de brancher l'existant plutôt que de regarder ailleurs.
- Chunking : RAGFlow a 10 méthodes nommées, KnowFlow en a déjà codé 7 en interne — pas besoin d'en importer une 11e, juste de finir le branchement + éventuellement adapter la "compilation de connaissance" (Wiki/Graph/Tree/Mind Map) comme inspiration future, pas comme urgence.

---

## PARTIE I — Fonctionnalités à améliorer pour atteindre un niveau comparable

| Fonctionnalité KnowFlow | Niveau actuel | Niveau de référence | Écart |
|---|---|---|---|
| Chunking | 1 stratégie active / 7 codées | RAGFlow : 10 méthodes nommées + compilation structurelle | Brancher les 6 existantes par type de document avant d'en coder de nouvelles |
| Retrieval avancé | Codé, non exposé | Dify/RAGFlow/Onyx : exposé et configurable par l'utilisateur | Exposer `use_query_rewriting`/`use_hyde`/`use_multi_query`/`use_mmr` dans `SearchRequest` |
| Agent tool-calling | Textuel (prompt uniquement) | Dify/Flowise/Onyx/AnythingLLM : vraie boucle de function-calling | Implémenter une vraie boucle qui parse `tool_calls` et ré-invoque |
| Agent Builder UI | Nom/description/prompt seulement | Onyx (Personas complets), AnythingLLM (skills+MCP) | Exposer modèle/KB/outils/mémoire/garde-fous dans l'UI existante |
| Workflow Builder UI | Aucune | Dify/Flowise/AnythingLLM : React Flow/no-code mature | Construire l'UI par-dessus le moteur déjà fonctionnel |
| Widget sécurité | Pas d'allowlist | AnythingLLM : allowlist (même imparfaite) | Ajouter un champ `allowed_domains` + vérification `Origin`/`Referer` |
| Chat UI | Pas de markdown/code | Quasi tous les concurrents | Intégrer `react-markdown` + coloration syntaxique |

---

## PARTIE J — Nouvelle roadmap KnowFlow

Organisée en modules, avec priorité (P0=critique, P1=important, P2=différenciant, P3=confort), dépendances, difficulté estimée (S/M/L/XL), partie technique concernée, ce qui est réutilisable vs à développer, et tests nécessaires.

### Module 1 — Core SaaS / Auth / Multi-tenancy
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Brancher RBAC Casbin sur les routes | P1 | `asgi-lifespan` dans les fixtures de test | M | Backend | Moteur Casbin déjà construit (`api/security/rbac.py`) | Migration progressive route par route + fix fixture tests | Suite complète RBAC existante à ne pas casser (~450 tests) |
| RLS Postgres réelle (rôle dédié) | P2 | Aucune | L | Backend/Infra | Structure de tables déjà prête | Rôle Postgres sans BYPASSRLS, policies par organisation, migration connexion app | `test_postgres_integration.py` à étendre |
| Permissions granulaires étendues à `organizations.py` | P2 | Décision produit (risque de sécurité documenté) | S | Backend | `resource_permissions.py` déjà branché sur workspaces | Étendre avec garde-fous adaptés | Tests de non-régression sécurité |

### Module 2 — Knowledge Base / Document Processing
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Brancher les 6 stratégies de chunking existantes | P0 | Aucune | M | Backend | Code déjà écrit et testé unitairement | Sélection automatique/manuelle par type de document dans `process_document` | Tests d'intégration bout en bout par type de doc |
| Connecteurs CRM/ticketing (Salesforce, Zendesk, Jira, Linear, HubSpot) | P2 | Framework de connecteur existant | L (par connecteur) | Backend | Pattern déjà établi (`api/tasks/*_import.py`) | Un module par connecteur, OAuth par service | Tests par connecteur |
| Permission sync (ACL miroir) | P3 | Connecteurs entreprise | XL | Backend | — | Nouveau sous-système complet | Tests de sécurité approfondis |
| GraphRAG (inspiration RAGFlow) | P3 | Aucune | XL | Backend | — | Extraction entités/relations + dédup LLM | Tests qualité retrieval |

### Module 3 — RAG / Search
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Exposer HyDE/multi-query/MMR/query rewriting dans l'API | P0 | Aucune | S | Backend | Code déjà écrit (`api/services/hyde.py`, `multi_query.py`, `mmr.py`, `query_rewriting.py`) | Champs optionnels sur `SearchRequest` + branchement | Tests API + non-régression appelants existants |
| Filtrage metadata en retrieval | P1 | Aucune | S | Backend | — | Champ filtre sur `SearchRequest` | Tests retrieval filtré |
| Context compression / déduplication | P2 | Aucune | M | Backend | `context_compression.py` déjà écrit | Branchement | Tests qualité |

### Module 4 — Agents / Tools / MCP
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| **MCP client** (le plus gros écart standard 2026) | P0 | Aucune | L | Backend | Registre d'outils existant (`api/services/agent_tools.py`) | Client MCP (HTTP/SSE), découverte dynamique d'outils, auth (API key/OAuth) | Tests d'intégration avec un serveur MCP de test |
| **MCP serveur** | P1 | MCP client (partage de code) | M | Backend | Recherche KB déjà réelle | Exposer recherche KB + agents comme outils MCP | Tests avec client MCP externe (Claude Desktop) |
| Vraie boucle de function-calling agent | P1 | Aucune | M | Backend | Sélection textuelle existante comme base | Parser `tool_calls`, ré-invoquer, boucler | Tests agent end-to-end |
| Exécution parallèle d'outils | P2 | Function-calling réel | S | Backend | `parallel_tools.py` déjà écrit | Branchement dans l'orchestrateur | Tests de concurrence |
| Validation de résultat d'outil | P2 | Function-calling réel | S | Backend | `tool_validation.py` déjà écrit | Branchement | Tests |
| Agent Builder UI complet | P1 | Aucune | M | Frontend | Page existante (nom/desc/prompt) | Ajouter sélection modèle/KB/outils/mémoire/garde-fous | Tests E2E frontend |

### Module 5 — Workflow Builder
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Interface visuelle (React Flow) | P0 | Moteur backend (✅ fait) | L | Frontend | Endpoints CRUD déjà réels (`api/routers/workflows.py`) | Canvas complet : nœuds, édition, validation, sauvegarde | Tests E2E frontend + tests d'intégration avec le moteur |
| Exécution parallèle de branches | P2 | Interface visuelle | L | Backend | Moteur séquentiel existant comme base | Étendre le moteur pour un vrai fan-out/fan-in | Tests de concurrence |
| Import/export (JSON/YAML) | P2 | Interface visuelle | S | Backend | `export_workflow` déjà écrit | Ajouter import + validation | Tests round-trip |
| Marketplace de templates de workflow | P3 | Import/export | M | Backend/Frontend | Marketplace de plugins existant comme pattern | Nouvelle catégorie de ressource partageable | Tests |

### Module 6 — Chat / UX
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Markdown + coloration syntaxique | P0 | Aucune | S | Frontend | `MessageContent.tsx` existant | Intégrer `react-markdown` + `highlight.js`/`shiki` | Tests visuels/snapshot |
| Export de conversation (PDF/DOCX/JSON) | P1 | Aucune | M | Backend/Frontend | Historique déjà réel | Génération de fichier + endpoint | Tests |
| Intégrer Voice AI au chat principal | P2 | Aucune | M | Frontend | Composants déjà réels (page démo) | Câblage dans `/chat` | Tests E2E |

### Module 7 — Widget / Sécurité
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Allowlist de domaine sur le widget | P0 | Aucune | S | Backend | `WidgetConfig` existant | Champ `allowed_domains` + vérification `Origin` | Tests de sécurité (domaine autorisé/refusé) |
| Guardrails IA en filtre actif (prompt injection/jailbreak) | P1 | Aucune | M | Backend | Détection déjà écrite | Brancher en filtre pré-génération | Tests d'attaque |
| PII detection/masking | P2 | Aucune | M | Backend | — | Nouveau (ex. Presidio) | Tests |
| SSRF protection | P1 | Aucune | S | Backend | — | Guard sur les fetchers sortants (`url_reader.py`, `http_call`) | Tests de sécurité |

### Module 8 — Facturation
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| Configuration Stripe de bout en bout | P0 (si objectif commercial) | Aucune | M | Backend/Infra | Code Stripe déjà réel | Clés API réelles, webhooks testés en conditions réelles | Tests d'intégration Stripe (mode test) |

### Module 9 — Enterprise / Connecteurs / Standards
| Item | Priorité | Dépend de | Difficulté | Backend/Frontend | Réutilisable | À développer | Tests |
|---|---|---|---|---|---|---|---|
| SCIM | P3 | SSO SAML (si décidé) | L | Backend | — | Nouveau | Tests avec IdP de test (Okta) |
| SAML (actuellement refusé par choix documenté OIDC-only) | P3 | Décision produit | L | Backend | — | Nouveau + dépendance `python3-saml`/`xmlsec1` | Tests |

---

## Résumé exécutif — les 5 priorités absolues (P0)

1. **Brancher les 6 stratégies de chunking déjà codées** — gain énorme pour un coût quasi nul (le code existe).
2. **Exposer les techniques de retrieval avancées déjà codées** (HyDE/multi-query/MMR/query rewriting) — même logique.
3. **MCP client** — écart de standard le plus visible face aux 5 concurrents en 2026, absent à 100% chez KnowFlow.
4. **Interface visuelle du Workflow Builder** — le moteur vient d'être construit cette session, il ne sert à rien sans UI.
5. **Markdown + coloration syntaxique dans le chat** — attendu par défaut par tout utilisateur de 2026, absent chez KnowFlow alors que quasi tous les concurrents l'ont.

Ces 5 points partagent un point commun : **aucun ne nécessite de repartir de zéro**. Les 3 premiers ont déjà tout ou partie du code écrit et orphelin ; les 2 derniers sont des ajouts ciblés sur une base déjà solide.
