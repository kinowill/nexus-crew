# AGENTIQUE / NEXUS Crew

> ⚠️ **PROJET EN COURS DE DEVELOPPEMENT — PROTOTYPE EXPERIMENTAL**
>
> Ce repo n'est PAS un outil pret a l'emploi. C'est un terrain de R&D actif
> pour valider une architecture multi-agent locale type Codex / Claude Code,
> sur les modeles NVIDIA NIM gratuits. Les chantiers (fondations, integration
> tool use, contrats de sortie, gouvernance multi-agent) sont en cours et
> documentes phase par phase dans `DOCUMENT_MAITRE_PROJET.md`.
>
> Si tu cherches un outil de coding agent fonctionnel maintenant, regarde
> Claude Code, Codex, Aider, Continue. Ce repo te servira surtout si tu veux
> comprendre comment monter un systeme equivalent a partir de modeles
> open-weights gratuits.

Prototype d'assistant local de developpement base sur **CrewAI** et les
modeles **NVIDIA NIM** gratuits.

L'objectif cible n'est pas une simple suite d'actions d'agents. La direction
produit vise un outil de travail type Codex / Claude Code : capable de lire,
comprendre, interpreter, modifier, relire et valider proprement du code sur
des projets reels, avec supervision utilisateur, permissions explicites et
contraintes de securite.

---

## Statut

**Etat global** : prototype, en developpement actif, NON utilisable en production.

**Avancement par phase** (detail dans `DOCUMENT_MAITRE_PROJET.md` §15) :

| Phase | Sujet | Etat |
|---|---|---|
| **Phase 0** | Hardening fondations (shell, permissions, install determ.) | ✅ CLOTUREE |
| **Phase 1** | Refactor protocole + contrats de sortie | 🔄 EN COURS (§0 ✅ tool use NIM, §1 ✅ contrats de sortie, §2 slice A ✅ modes CLI, §3 ✅ resilience NIM) |
| Phase 2 | Cooperation multi-agent reelle | ⏳ a venir |
| Phase 3 | Intelligence depot lourd | ⏳ a venir |
| Phase 4 | Qualite produit | ⏳ a venir |
| Phase 5 | Vers autonomie plus elevee | ⏳ a venir |

**Dettes resolues en Phase 1** :

- **§0 tool use NIM** : `FallbackLLM._strip_strict_tools()` retire `strict` +
  `additionalProperties` et sort du `required` les params avec `default`
  Python. Qwen Coder 480B et Kimi K2 Thinking emettent maintenant du
  `tool_calls` natif.
- **§3 resilience NIM** : backoff 429 (3 retries 1/2/4s), retry-1 sur sortie
  XML Hermes cassee, retry-1 sur variance "0 tools courte" (heuristique
  marqueur d'intention + sortie < 300 chars), logs payload via
  `NEXUS_DEBUG_LLM=1`. Retry XML Hermes observe en runtime reel (2
  declenchements sur un run mode=read, les deux ont abouti).

**Cible v1** : assistant local multi-agent cooperatif, supervise par
protocole. Priorite qualite/fiabilite avant vitesse. Reference
architecture/produit : `DOCUMENT_MAITRE_PROJET.md`.

Le code actuel sert a valider les fondations, les contraintes NVIDIA NIM et la
mechanique locale. Il ne faut pas le confondre avec la cible produit finale.

---

## Architecture Actuelle

Le pipeline s'adapte au mode d'usage choisi via `--mode` (defaut : `edit`) :

**Mode `edit` / `debug`** (pipeline complet, pour modifier du code) :

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

**Mode `read`** (comprendre / auditer, pas de modification) :

```text
    [Researcher]  <- rapport direct
```

**Mode `review`** (relire l'existant, pas de Coder) :

```text
    [Researcher]  -->  [Critic (review)]  -->  [Architect (synth)]
```

En mode `--deep`, un **Scanner** fait un inventaire large avant le
Researcher pour les tres gros repos, quel que soit le mode.

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
| Researcher | Qwen 3.5 397B | GPT-OSS 120B | Nemotron Super 49B |
| Architect | Qwen 3.5 397B | GPT-OSS 120B | Nemotron Super 49B |
| Coder | Qwen 3 Coder 480B | Devstral 2 123B | Kimi K2 Instruct |
| Critic | Kimi K2 Thinking | Qwen 3 Next 80B Thinking | Nemotron Super 49B |
| Scanner | Llama 3.3 70B | GPT-OSS 120B | Gemma 3 27B |

> Les chaines sont calibrees a partir de la matrice tool use NIM et des observations runtime bornees
> (`scripts/tool_use_matrix.md`) qui mesure la capacite simple-tool; les fallbacks Researcher/Architect ont ete ajustes apres observations runtime multi-outils. Cette matrice doit etre regeneree.
> Elle mesure la capacite reelle de chaque
> modele a appeler des outils au format OpenAI standard.

---

## Collaboration Actuelle

- `allow_delegation=False` sur tous les agents tant que la gouvernance Phase 2 n'existe pas.
- Cache LiteLLM disk sur `.crew_cache/` quand l'environnement le supporte.
- Boucle `Critic -> Coder` via `rework_task` en modes `edit` / `debug`.
- **Contrats de sortie par task** (`crew/contracts.py`, Phase 1 §1) : chaque
  task a une contrainte minimale (outils requis, longueur output, patterns
  de sortie type `APPROVED|CHANGES_NEEDED` pour le Critic). Violations
  loguees via `ContractTracker`, pas de retry auto (prevu Phase 2).
- **Modes d'usage CLI** (Phase 1 §2 slice A) : `--mode read/edit/review/debug`
  adapte la composition du crew a la demande, evitant la sur-utilisation
  systematique du pipeline complet. Classifier automatique de mode prevu
  Phase 2.
- `planning=True` et `memory=True` desactives pour rester compatibles avec
  certaines limites NVIDIA NIM.

Important : cette collaboration reste aujourd'hui insuffisamment gouvernee
pour une vraie v1 pro. La Phase 2 introduira une couche de gouvernance,
des interactions typees entre agents, et la validation technique integree
avant reponse finale.

---

## Compat NIM

Les modeles NIM gratuits ont chacun leurs contraintes. `FallbackLLM.call()`
normalise les appels avant passage a LiteLLM.

| Modele | Symptome | Patch |
|---|---|---|
| Qwen 3.5 397B | `System message must be at the beginning` | fusion des system messages en position 0 |
| DeepSeek V3.2 | `Invalid grammar request` | `response_model=None` force |
| Llama 3.3 70B | `single tool-calls at once` | `parallel_tool_calls=False` |
| Qwen Coder 480B, Kimi K2 | XML Hermes au lieu de `tool_calls` | `_strip_strict_tools()` + retry-1 |
| Tous | 429 NIM free tier (~40 req/min) | backoff 1s / 2s / 4s avant fallback |
| Tous | variance "0 tools au tour 1" (texte nu) | retry-1 si marqueur d'intention + sortie courte |

---

## Securite

- `_safe_path()` borne les acces fichiers au projet et aux dossiers `--allow`.
- Aucun `write_file` reel sans `--write`.
- Tracing et telemetrie CrewAI forces OFF.

`run_shell` (Phase 0 #1) :

- OFF par defaut, active explicitement avec `--allow-shell`.
- `shell=False`, pas d'interpretation shell donc pas d'injection.
- Allowlist stricte de binaires (python, pytest, git, npm, cargo, etc.).
- Chainage et redirection shell (`|`, `;`, `&&`, `>`, etc.) refuses.
- Toujours reserve au Coder (Critic est en lecture seule).

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
| `--mode`, `-m` | Mode d'usage : `read` / `edit` / `review` / `debug` (defaut : `edit`) |
| `--write`, `-w` | Active l'ecriture reelle de fichiers (ignore en `read` / `review`) |
| `--allow-shell`, `-s` | Donne au Coder l'outil shell (shell=False, allowlist stricte) |
| `--deep`, `-d` | Ajoute le Scanner |
| `--allow`, `-a` | Dossier supplementaire accessible |

### Validation runtime bornee

Pour eviter qu'un run NIM long bloque la session Codex, borner les appels LLM :

```bash
NEXUS_LLM_TIMEOUT_SECONDS=30 NEXUS_DEBUG_LLM=1 python crew/crew.py "Relis crew/crew.py" --project . --mode review
```

Le defaut reste 90s par appel modele. Pour une validation courte, utiliser 30-45s,
puis conserver le log dans un fichier local gitignore si le run doit etre analyse.

### Exemples

```bash
# Comprendre / auditer sans modification (2 agents, pas de Coder)
python crew/crew.py "explique ce projet" -p . --mode read

# Modification avec validation (pipeline complet, defaut)
python crew/crew.py "refactore l'auth en JWT" -p C:/mon-app --mode edit --write

# Relire un etat existant sans y toucher
python crew/crew.py "relis crew/crew.py et cherche les risques" -p . --mode review

# Scanner + pipeline complet sur gros repo
python crew/crew.py "audit securite complet" -p C:/gros-repo --deep --write

# Acces a une dep locale supplementaire
python crew/crew.py "adapte le pattern X" -p C:/mon-app --allow C:/libs/lib-x --write
```

---

## Structure du projet

```text
AGENTIQUE/
├── crew/
│   ├── crew.py              # Systeme multi-agents + FallbackLLM + routing modes
│   └── contracts.py         # Contrats de sortie + validation (Phase 1 §1)
├── scripts/
│   ├── test_connection.py   # Sante : API, modeles, deps
│   ├── discover_models.py   # Inventaire modele NIM
│   ├── test_phase0.py       # Validation statique Phase 0 (20/20)
│   ├── test_resilience.py   # Tests unitaires resilience NIM §3/§3bis (31/31)
│   ├── test_modes.py        # Tests unitaires modes d'usage Phase 1 §2 (31/31)
│   ├── test_tool_use.py     # Matrice tool use par modele NIM
│   ├── tool_use_matrix.md   # Resultats de la matrice
│   └── test_crewai_schema.py # Preuve du fix schemas CrewAI -> NIM (§0.c)
├── DOCUMENT_MAITRE_PROJET.md # Cible produit/architecture v1 + journal §19
├── nexus.bat                # Lanceur interactif Windows
├── test_phase0.bat          # Lanceur validation Phase 0
├── requirements.txt         # Dependances Python
├── .env.example             # Template cle API
├── .gitignore
└── README.md
```

---

## Limites connues

- Le prototype reste sequentiel (`Process.sequential`). La cooperation
  multi-agent reelle et les boucles gouvernees sont prevues Phase 2.
- Pas de retry automatique sur violation de contrat de sortie : les
  violations sont loguees par `ContractTracker` mais la task suivante part
  quand meme. Retry auto prevu Phase 2.
- `planning=True` et `memory=True` CrewAI restent desactives sur NIM
  (incompat documentee).
- Le payload CrewAI gonfle tour apres tour (bytes x44 sur 5 tours ReAct du
  Researcher mesures en debug). Resume / troncature prevue Phase 2.
- Les rate-limits NVIDIA NIM free tier (~40 req/min) restent un risque
  malgre le backoff automatique sur gros runs prolonges.
- Mode `debug` est aujourd'hui un alias de `edit` cote composition. La
  differentiation produit (orientation diagnostic) est prevue Phase 2.

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
