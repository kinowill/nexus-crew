# AGENTIQUE — NEXUS Crew

Système multi-agents autonome basé sur **CrewAI** et les modèles gratuits **NVIDIA NIM**.
Chaque agent dispose d'un poste de travail réel (lecture/écriture de fichiers, shell,
recherche, grep) pour comprendre et intervenir sur des projets complexes.

## Architecture

4 agents en mode normal, 5 en mode `--deep`, chacun avec une chaîne de fallback (3 modèles) :

| Rôle | Modèle primaire | Mission |
|---|---|---|
| **Researcher** | Qwen 3.5 397B | Explore le projet, lit les fichiers, produit une carte |
| **Architect** | DeepSeek V3.2 | Planifie l'intervention |
| **Coder** | Qwen 3 Coder 480B | Implémente les changements |
| **Critic** | Kimi K2 Thinking | Review, bugs, sécurité |
| **Scanner** *(--deep)* | Llama 3.3 70B | Wide scan rapide sur gros repos |

Si un modèle tombe, le suivant de la chaîne prend le relais automatiquement.

## Installation

```bash
# 1. Clone
git clone <repo> AGENTIQUE
cd AGENTIQUE

# 2. Dépendances (env isolé recommandé)
uv tool install crewai --with crewai-tools --with litellm
# ou : pip install -r requirements.txt

# 3. Clé API NVIDIA NIM (gratuite : https://build.nvidia.com/)
cp .env.example .env
# éditer .env et renseigner NVIDIA_API_KEY
```

## Usage

```bash
python crew/crew.py "ta tâche" --project C:/chemin/du/projet
```

Options :

- `--write` : autorise l'écriture réelle des fichiers (sinon dry-run)
- `--deep`  : active le Scanner pour les gros projets

Exemples :

```bash
python crew/crew.py "liste les fichiers Python et explique chacun" --project .
python crew/crew.py "refactore l'auth en JWT" --project C:/mon-app --write
python crew/crew.py "audit sécurité complet" --project C:/gros-repo --deep
```

Sur Windows, le lanceur `nexus.bat` à la racine propose une invite interactive.

## Structure

```
AGENTIQUE/
├── crew/crew.py          # Système multi-agents principal
├── mcp-servers/nexus/    # Serveur MCP (optionnel, pour Claude Code)
├── scripts/              # Utilitaires (discover_models, test_connection)
├── requirements.txt
├── .env.example
├── nexus.bat             # Lanceur interactif Windows
└── README.md
```

## Sécurité

- **`.env` ne doit jamais être committé** — déjà dans `.gitignore`.
- Les outils fichiers sont sandbox : `_safe_path()` empêche toute évasion hors du `--project`.
- Le shell bloque les commandes destructives en dry-run.
- Sans `--write`, aucun fichier n'est modifié.

## Licence

Usage personnel.
