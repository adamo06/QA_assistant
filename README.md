# QA Assistant

Assistant Python pour ingérer un corpus de PDF métier, générer des embeddings OpenAI, indexer les chunks dans Chroma, exposer une API métier FastAPI, puis interroger le corpus via un agent LangChain.

## Ce que fait le projet

Le projet couvre 3 étapes:

1. Charger des PDF déposés dans `data/`.
2. Découper le contenu en chunks, créer des embeddings OpenAI, puis indexer le tout dans une base vectorielle Chroma persistante.
3. Exposer une API métier FastAPI pour la recherche documentaire et les résumés de corpus.
4. Interroger le corpus avec un agent RAG LangChain qui récupère le contexte pertinent avant de répondre.

Le point d’entrée `main.py` indexe le corpus puis passe en mode interactif dans le terminal pour poser librement des questions métier.

## Architecture

```text
QA_Assistant/
├── main.py
├── config.py
├── llm.py
├── api/
│   ├── client.py
│   └── server.py
├── agents/
│   └── rag.py
├── tools/
│   ├── search.py
│   └── database.py
├── memory/
│   ├── store.py
│   └── vectorstore.py
├── data/
├── chroma_db/
├── .env
├── pyproject.toml
└── requirements.txt
```

## Rôle des fichiers

- `main.py`: point d’entrée. Lance l’ingestion, indexe le corpus, exécute l’agent RAG et affiche un résumé lisible en français.
- `config.py`: paramètres globaux, chargement du `.env` et prompt système général.
- `llm.py`: création du modèle OpenAI utilisé par l’agent.
- `api/server.py`: API FastAPI métier, avec auth par clé API ou OAuth client credentials.
- `api/client.py`: client local utilisé par l’agent pour appeler l’API métier.
- `agents/rag.py`: agent LangChain RAG et tool de retrieval sur Chroma.
- `tools/search.py`: ingestion des PDF, parsing, découpage, embeddings et indexation.
- `memory/store.py`: stockage mémoire local des chunks et de leurs embeddings.
- `memory/vectorstore.py`: création et gestion du stockage vectoriel Chroma.
- `tools/database.py`: emplacement réservé pour de futurs outils liés à une base métier.

## Ce que tu dois déposer dans `data/`

Place ici les PDF métier à traiter:

- procédures internes
- fiches produits
- modes opératoires
- documents de référence

Le projet lit automatiquement le dossier `data/` par défaut.

## Configuration

Crée ou modifie le fichier `.env` à la racine du projet.

Variables utiles:

```env
OPENAI_API_KEY="ta_cle_openai"
PDF_CORPUS_PATHS="D:\YASSINE\Objectware\Formations\IA\Module 3\QA_Assistant\data"
BUSINESS_API_AUTH_METHOD="api_key"
BUSINESS_API_KEY="dev-business-key"
BUSINESS_OAUTH_CLIENT_ID="qa-assistant"
BUSINESS_OAUTH_CLIENT_SECRET="dev-oauth-secret"
```

Notes:

- `OPENAI_API_KEY` est indispensable pour les embeddings et les réponses du modèle.
- `PDF_CORPUS_PATHS` est optionnelle. Si elle n’est pas définie, le projet utilise automatiquement `data/`.
- Tu peux mettre plusieurs chemins séparés par `;`.
- `BUSINESS_API_AUTH_METHOD` accepte `api_key` ou `oauth`.
- L’agent utilise l’API métier via le client local `TestClient`, donc tu peux la tester sans lancer un serveur séparé.

## Dépendances principales

- `langchain`
- `langchain-openai`
- `langchain-chroma`
- `langchain-community`
- `pypdf`
- `chromadb`

## Exécution

```bash
uv run .\main.py
```

Au lancement, le script:

1. charge les PDF
2. génère les embeddings
3. indexe les chunks dans Chroma
4. démarre une session interactive dans le terminal
5. permet de poser des questions métier librement

### Lancer l'API FastAPI séparément

Si tu veux exposer l’API métier en HTTP, lance:

```bash
uv run uvicorn api.server:app --reload
```

Endpoints utiles:

- `GET /health`
- `POST /oauth/token`
- `GET /v1/business/summary`
- `GET /v1/business/search?q=...`

### Lancer les tests PowerShell

Un script dédié est disponible pour vérifier l’API et le chemin agent:

```powershell
.\test_api.ps1
```

## Stockage généré

L’index Chroma est persisté localement dans:

```text
chroma_db/
```

Tu peux supprimer ce dossier si tu veux repartir d’un index vide.

## Métadonnées indexées

Chaque chunk indexé dans Chroma contient des métadonnées stables:

- `source`
- `source_name`
- `source_type`
- `page`
- `chunk_index`
- `chunk_id`
- `chunk_chars`
- `embedding_model`

Ces champs permettent de retracer l’origine d’une réponse et de filtrer les résultats si besoin.

## Format de réponse

Le projet affiche:

- un résumé d’ingestion en français
- les informations Chroma
- les réponses de l’API métier quand l’agent s’en sert
- les réponses de l’agent à chaque question saisie

Pour quitter la session interactive, tape `exit`, `quit` ou `q`.

## Limites actuelles

- Le projet est orienté ingestion et RAG; ce n’est pas encore une application complète de production avec UI.
- Si le corpus contient des PDF scannés ou sans texte extractible, l’extraction peut être incomplète.

## Améliorations possibles

- ajouter une vraie métrique d’évaluation
- exposer un outil de recherche métier plus riche
- ajouter une interface CLI ou web
- permettre l’ajout incrémental de nouveaux PDF sans réindexer tout le corpus
- brancher plusieurs collections Chroma par type de document
- connecter l’API métier à une source externe réelle plutôt qu’au corpus local
