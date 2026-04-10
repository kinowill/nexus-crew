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
| **Phase 1** | Refactor protocole + contrats de sortie | 🔄 EN COURS (§0 ✅ tool use NIM, §1 ✅ contrats de sortie) |
| Phase 2 | Cooperation multi-agent reelle | ⏳ a venir |
| Phase 3 | Intelligence depot lourd | ⏳ a venir |
| Phase 4 | Qualite produit | ⏳ a venir |
| Phase 5 | Vers autonomie plus elevee | ⏳ a venir |

**Dette runtime connue (en cours de fix Phase 1 §0)** : sur certains modeles
NIM (Qwen 3 Coder 480B, Kimi K2 Thinking, etc.), l'integration CrewAI ne
declenche pas correctement le format `tool_calls` natif. Les agents
Coder/Critic produisent alors des "intentions vides" ou du `<tool_call>` XML
casse au lieu d'appeler reellement les outils. Cause racine identifiee
(strict mode + params required avec defaults), fix en cours d'implementation.

**Cible v1** : assistant local multi-agent cooperatif, supervise par
protocole. Priorite qualite/fiabilite avant vitesse. Reference
architecture/produit : `DOCUMENT_MAITRE_PROJET.md`.

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
| Architect | Qwen 3.5 397B | DeepSeek V3.2 | Llama 3.3 70B |
| Coder | Qwen 3 Coder 480B | Devstral 2 123B | Kimi K2 Instruct |
| Critic | Kimi K2 Thinking | Qwen 3 Next 80B Thinking | Nemotron Super 49B |
| Scanner | Llama 3.3 70B | GPT-OSS 120B | Gemma 3 27B |

> Les chaines sont calibrees a partir de la matrice tool use NIM
> (`scripts/tool_use_matrix.md`) qui mesure la capacite reelle de chaque
> modele a appeler des outils au format OpenAI standard.

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
| `--write`, `-w` | Active l'ecriture reelle de fichiers |
| `--allow-shell`, `-s` | Donne au Coder l'outil shell (shell=False, allowlist stricte) |
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
├── crew/
│   ├── crew.py              # Systeme multi-agents actuel
│   └── contracts.py         # Contrats de sortie + validation (Phase 1 §1)
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

- **Dette tool use NIM (en cours de fix Phase 1 §0)** : sur certains modeles
  (Qwen 3 Coder 480B, Kimi K2 Thinking), CrewAI ne declenche pas
  correctement le format `tool_calls` natif et les agents emettent du XML
  Hermes casse au lieu d'appeler les outils. Cause racine identifiee
  (interaction `strict mode` x params required avec defaults). Voir
  `DOCUMENT_MAITRE_PROJET.md` §19 (journal Phase 1 §0).
- Le prototype actuel reste trop sequentiel.
- Les contrats de sortie des agents ne sont pas encore assez stricts
  (Phase 1).
- `planning` et `memory` CrewAI restent desactives sur NIM (incompat).
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
