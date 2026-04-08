# AGENTIQUE — NEXUS Crew

Système multi-agents autonome basé sur **CrewAI** et les modèles **NVIDIA NIM**
gratuits. Chaque agent dispose d'un vrai poste de travail : lecture/écriture de
fichiers, shell, recherche, grep. L'objectif est de rivaliser avec des outils
frontier payants sur des projets complexes, sans aucun coût d'inférence.

---

## Architecture

```
    [Researcher]        <--- carte mentale du projet (lit, grep, explore)
          |
          v
    [Architect]         <--- plan d'execution numerote
          |
          v
    [Coder]             <--- implemente (read/write/shell)
          |
          v
    [Critic]            <--- review, bugs, securite
          |
          v
    [Coder (rework)]    <--- applique les corrections du Critic
          |
          v
    [Architect (synth)] <--- rapport final utilisateur
```

En mode `--deep`, un **Scanner** (Llama 3.3 70B) fait un inventaire large
avant le Researcher pour les très gros repos.

### Modèles + chaîne de fallback

Chaque rôle a 3 modèles. Si le primaire tombe (429, timeout, erreur), le
suivant prend le relais automatiquement, tu vois `[fallback actif : <id>]`.

| Rôle | Primaire | Fallback 1 | Fallback 2 |
|---|---|---|---|
| Researcher | Qwen 3.5 397B | DeepSeek V3.2 | Llama 3.3 70B |
| Architect | DeepSeek V3.2 | Qwen 3.5 397B | Llama 3.3 70B |
| Coder | Qwen 3 Coder 480B | Devstral 2 123B | Kimi K2 Instruct |
| Critic | Kimi K2 Thinking | Qwen 3 Next 80B Thinking | Nemotron Super 49B |
| Scanner | Llama 3.3 70B | GPT-OSS 120B | Gemma 3 27B |

### Collaboration

- **`allow_delegation=True`** sur tous les agents → ils peuvent s'interroger
  en cours d'exécution (le Coder peut demander au Researcher, le Critic
  peut renvoyer au Coder).
- **`planning=True`** → une phase de planning globale (pilotée par un LLM
  Architect) coordonne les tâches avant exécution.
- **`memory=True`** + embedder `nvidia/nv-embed-v1` → mémoire court/long
  terme partagée entre agents, même hors du contexte explicite des tâches.
- **Cache LiteLLM disk** — `.crew_cache/` — sert les appels identiques depuis
  le disque pendant la session (retries, délégations, fallbacks). **Vidé à
  chaque démarrage** pour éviter des réponses obsolètes quand le code du
  projet a changé entre deux runs.
- **Boucle Critic → Coder** via `rework_task` : après la review, le Coder
  applique les corrections du Critic avant la synthèse finale. Si tout est
  `APPROVED`, le rework est un no-op.

### Sécurité

- **`_safe_path()`** empêche toute évasion hors du projet et des dossiers
  `--allow` explicites.
- **`run_shell`** bloque les commandes destructives en dry-run (`rm`,
  `rmdir`, `Remove-Item`, `dd`, `shutdown`, `mkfs`, fork bomb).
- **Aucun `write_file` réel sans `--write`**.
- **Tracing + télémétrie CrewAI forcés OFF** dès l'import → aucun prompt
  ni output ne part vers le cloud CrewAI.

---

## Installation

### 1. Clé API NVIDIA NIM

Gratuite : https://build.nvidia.com/ → récupère `nvapi-...`.

```bash
cp .env.example .env
# editer .env et renseigner NVIDIA_API_KEY
```

### 2. Dépendances Python

**Option A — env isolé (recommandé)** :

```bash
uv tool install crewai --with crewai-tools --with litellm
```

**Option B — Python système** :

```bash
pip install -r requirements.txt
```

CrewAI tire automatiquement `chromadb` et `litellm` comme dépendances
transitives (requis pour la mémoire et le cache).

### 3. Test de santé

```bash
python scripts/test_connection.py
```

Vérifie clé API, catalogue NIM, existence des modèles primaires, endpoint
embedder, fichiers clés, dépendances Python. Tout doit être `[OK]`.

---

## Usage

### Lanceur interactif (Windows)

Double-clic sur `nexus.bat`. Affiche un folder picker, un aperçu du dossier,
puis demande la tâche, `--write`, `--deep`. Détecte Python automatiquement
(env `uv tool` ou PATH système).

### Ligne de commande

```bash
python crew/crew.py "ta tache" --project C:/chemin/projet [options]
```

| Flag | Effet |
|---|---|
| `--project`, `-p` | Dossier de travail principal (requis) |
| `--write`, `-w` | Active l'écriture réelle de fichiers (sinon dry-run) |
| `--deep`, `-d` | Ajoute le Scanner pour les gros projets |
| `--allow`, `-a` | Dossier supplémentaire accessible (répétable) |

### Exemples

```bash
# Analyse sans rien ecrire
python crew/crew.py "liste les fichiers Python et explique chacun" -p .

# Refactor avec ecriture
python crew/crew.py "refactore l'auth en JWT" -p C:/mon-app --write

# Gros projet avec scan large
python crew/crew.py "audit securite complet" -p C:/gros-repo --deep

# Acces a une lib externe
python crew/crew.py "adapte le pattern X de cette lib dans mon projet" \
  -p C:/mon-app --allow C:/libs/lib-x --write
```

---

## Structure du projet

```
AGENTIQUE/
├── crew/crew.py          # Systeme multi-agents principal
├── scripts/
│   ├── test_connection.py    # Sante : API, modeles, deps
│   └── discover_models.py    # Liste les 189 modeles NIM
├── nexus.bat             # Lanceur interactif Windows
├── requirements.txt      # Deps Python (crewai, litellm, etc.)
├── .env.example          # Template cle API
├── .env                  # [gitignore] ta cle reelle
├── .gitignore
├── .crew_cache/          # [gitignore] cache LiteLLM (vide a chaque run)
├── .crew_memory/         # [gitignore] memoire CrewAI
└── README.md
```

---

## Troubleshooting

**`ValueError: Model must be a non-empty string`** → version de `crewai`
trop ancienne. Mets à jour : `uv tool upgrade crewai`.

**`chromadb` ou `litellm` manquant** → `pip install crewai[tools]` ou
réinstalle via `uv tool install crewai --with crewai-tools --with litellm`.

**`UnicodeEncodeError` sur Windows** → déjà géré : `crew.py` force
`sys.stdout.reconfigure(encoding="utf-8")` et `nexus.bat` force
`PYTHONIOENCODING=utf-8` + `chcp 65001`.

**Le crew utilise un modèle qui n'existe plus** → lance
`python scripts/discover_models.py` pour lister les 189 modèles NIM
courants et mets à jour `MODEL_CHAINS` dans `crew/crew.py`.

**Un agent délire et ne trouve rien** → vérifie le fallback dans le log
(`[modele X a echoue]`). Si les 3 modèles d'une chaîne tombent, c'est
souvent un souci de rate-limit NIM (40 req/min gratuit) — relance.

**Le cache rend des réponses bizarres** → purge manuelle :
`rm -rf .crew_cache/` (déjà fait automatiquement à chaque démarrage).

---

## Limites connues

- **Le binaire `grep`** est utilisé en chemin rapide (via Git Bash sur
  Windows). S'il est absent, fallback Python pur activé automatiquement
  (plus lent sur gros repos).
- **Pas de vraie boucle illimitée** Critic↔Coder : la boucle est un
  single-shot rework. Pour itérer jusqu'à `APPROVED`, il faudrait passer
  en `Process.hierarchical` avec un manager agent (plus cher en tokens).
- **Rate-limits NVIDIA NIM** : le tier gratuit est à 40 req/min. Un run
  complet sur un gros projet peut saturer — les fallbacks aident mais
  parfois un retry humain est nécessaire.
- **Sur un Windows neuf sans Git**, `grep` natif absent → fallback Python.
  Pas de crash, juste plus lent.

---

## Sécurité avant push public

- `.env` : jamais committé (déjà dans `.gitignore`).
- `.claude/` : jamais committé (contient parfois la clé dans les règles de permission).
- `.old/` : jamais committé (archives locales de l'ancien NEXUS).
- `.crew_cache/` / `.crew_memory/` : jamais committés.
- Scan des fichiers trackés : aucun `nvapi-*` réel, seul `.env.example`
  contient un placeholder.

---

## Licence

Usage personnel.
