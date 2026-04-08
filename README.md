# AGENTIQUE / NEXUS Crew

Prototype d'assistant local de developpement base sur **CrewAI** et les
modeles **NVIDIA NIM** gratuits.

L'objectif cible n'est pas une simple suite d'actions d'agents. La direction
produit vise un outil de travail type Codex / Claude Code : capable de lire,
comprendre, interpreter, modifier, relire et valider proprement du code sur
des projets reels, avec supervision utilisateur, permissions explicites et
contraintes de securite.

---

## Statut

- Implementation actuelle : prototype multi-agent encore largement sequentiel.
- Cible v1 : assistant local multi-agent cooperatif, supervise par protocole.
- Priorite : qualite et fiabilite avant vitesse.
- Reference architecture/produit : `DOCUMENT_MAITRE_PROJET.md`.

Le code actuel sert a valider les fondations, les contraintes NVIDIA NIM et la
mechanique locale. Il ne faut pas le confondre avec la cible produit finale.

---

## Architecture Actuelle

```text
    [Researcher]        <- carte mentale du projet
          |
          v
    [Architect]         <- plan d'execution numerote
          |
          v
    [Coder]             <- implemente (read/write/shell)
          |
          v
    [Critic]            <- review, bugs, securite
          |
          v
    [Coder (rework)]    <- applique les corrections du Critic
          |
          v
    [Architect (synth)] <- rapport final utilisateur
```

En mode `--deep`, un **Scanner** fait un inventaire large avant le
Researcher pour les tres gros repos.

---

## Cible V1

La cible validee pour la v1 n'est ni :

- un pipeline rigide deguisé en "multi-agent" ;
- ni un mesh libre d'agents qui discutent sans garde-fou.

La cible est un **mesh multi-agent supervise par protocole** avec :

- un assistant principal coherent cote utilisateur ;
- plusieurs agents specialises et reels ;
- des echanges typés entre agents ;
- des contrats de sortie stricts ;
- des permissions generales ou specifiques ;
- des validations avant actions sensibles ;
- une vraie boucle `coding -> critique -> validation` avant reponse finale.

Dans ce modele, les agents doivent pouvoir :

- se passer la balle ;
- se relire ;
- se demander des confirmations ;
- se challenger ;
- s'entraider ;
- converger vers un resultat valide.

Le detail de cette cible est documente dans `DOCUMENT_MAITRE_PROJET.md`.

---

## Modeles et Fallback

Chaque role a 3 modeles. Si le primaire tombe (429, timeout, erreur), le
suivant prend le relais automatiquement.

| Role | Primaire | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Researcher | Qwen 3.5 397B | DeepSeek V3.2 | Llama 3.3 70B |
| Architect | DeepSeek V3.2 | Qwen 3.5 397B | Llama 3.3 70B |
| Coder | Qwen 3 Coder 480B | Devstral 2 123B | Kimi K2 Instruct |
| Critic | Kimi K2 Thinking | Qwen 3 Next 80B Thinking | Nemotron Super 49B |
| Scanner | Llama 3.3 70B | GPT-OSS 120B | Gemma 3 27B |

---

## Collaboration Actuelle

- `allow_delegation=True` sur tous les agents.
- Cache LiteLLM disk sur `.crew_cache/` quand l'environnement le supporte.
- Boucle `Critic -> Coder` via `rework_task`.
- `planning=True` et `memory=True` desactives pour rester compatibles avec
  certaines limites NVIDIA NIM.

Important : cette collaboration reste aujourd'hui insuffisamment gouvernee
pour une vraie v1 pro. La cible n'est pas seulement de "laisser deleguer",
mais d'introduire :

- un protocole propre ;
- des contrats de sortie ;
- des permissions tracables ;
- des validations de resultat ;
- une orchestration adaptee au type de demande.

---

## Compat NIM

Les modeles NIM gratuits ont chacun leurs contraintes. `FallbackLLM.call()`
normalise les appels avant passage a LiteLLM.

| Modele | Symptome | Patch |
|---|---|---|
| Qwen 3.5 397B | `System message must be at the beginning` | fusion des system messages en position 0 |
| DeepSeek V3.2 | `Invalid grammar request` | `response_model=None` force |
| Llama 3.3 70B | `single tool-calls at once` | `parallel_tool_calls=False` |

---

## Securite

- `_safe_path()` borne les acces fichiers au projet et aux dossiers `--allow`.
- Aucun `write_file` reel sans `--write`.
- Tracing et telemetrie CrewAI forces OFF.

Limite importante actuelle :

- `run_shell` reste trop permissif pour un outil pro.
- La v1 devra passer d'un controle par blacklist a un vrai modele de
  permissions/actions autorisees.

---

## Installation

### 1. Cle API NVIDIA NIM

Gratuite : https://build.nvidia.com/ puis recuperer `nvapi-...`.

```bash
cp .env.example .env
# editer .env et renseigner NVIDIA_API_KEY
```

### 2. Dependances Python

Option A - env isole :

```bash
uv tool install crewai --with crewai-tools --with 'litellm[caching]' --with httpx --with chromadb
```

Option B - Python systeme :

```bash
pip install -r requirements.txt
```

### 3. Test de sante

```bash
python scripts/test_connection.py
```

---

## Usage

### Lanceur interactif Windows

Double-clic sur `nexus.bat`. Il affiche un picker de dossier, un apercu du
repo, puis demande la tache, `--write` et `--deep`.

### Ligne de commande

```bash
python crew/crew.py "ta tache" --project C:/chemin/projet [options]
```

| Flag | Effet |
|---|---|
| `--project`, `-p` | Dossier de travail principal |
| `--write`, `-w` | Active l'ecriture reelle |
| `--deep`, `-d` | Ajoute le Scanner |
| `--allow`, `-a` | Dossier supplementaire accessible |

### Exemples

```bash
python crew/crew.py "liste les fichiers Python et explique chacun" -p .
python crew/crew.py "refactore l'auth en JWT" -p C:/mon-app --write
python crew/crew.py "audit securite complet" -p C:/gros-repo --deep
python crew/crew.py "adapte le pattern X de cette lib" -p C:/mon-app --allow C:/libs/lib-x --write
```

---

## Structure du projet

```text
AGENTIQUE/
├── crew/crew.py             # Systeme multi-agents actuel
├── scripts/
│   ├── test_connection.py   # Sante : API, modeles, deps
│   └── discover_models.py   # Inventaire modele NIM
├── DOCUMENT_MAITRE_PROJET.md # Cible produit/architecture v1
├── nexus.bat                # Lanceur interactif Windows
├── requirements.txt         # Dependances Python
├── .env.example             # Template cle API
├── .gitignore
└── README.md
```

---

## Limites connues

- Le prototype actuel reste trop sequentiel.
- Les contrats de sortie des agents ne sont pas encore assez stricts.
- Le shell n'est pas encore durci au niveau attendu pour un outil pro.
- `planning` et `memory` CrewAI restent desactives sur NIM.
- Les rate-limits NVIDIA NIM peuvent casser un run complet sur gros projet.

---

## Securite avant push public

- `.env` : jamais committe.
- `.claude/` : jamais committe.
- `.old/` : jamais committe.
- `.crew_cache/` / `.crew_memory/` : jamais committes.
- `Audit Technique ... genere par *.txt` : rapports locaux sensibles, ignores.
- `Utilisation *.txt` : logs locaux pouvant fuiter du contexte projet, ignores.

---

## Licence

Usage personnel pour le moment.
