# NEXUS — Document Maître

> Source de vérité unique du système d'orchestration multi-agents NEXUS.
> Architecture : Brain + Workers propulsés par NVIDIA NIM (gratuit).

---

## Objectif

Construire un environnement de développement IA hybride permettant de travailler sur des projets complexes de façon quasi-illimitée :

- **~90 %** du travail → modèles NVIDIA NIM gratuits (40 req/min)
- **~9 %** → Claude Sonnet (abonnement Pro, fallback Brain)
- **< 1 %** → Claude Opus (décisions critiques, à la demande)

---

## Architecture Brain + Workers

```
┌─────────────────────────────────────────────────┐
│  BRAIN — Qwen 3.5 397B (gratuit)                │
│  Fallback : Claude Sonnet (OAuth, Pro)          │
│                                                 │
│  Seul responsable du routage et des décisions.  │
│  Évalue chaque résultat, décide la suite.       │
└──────────┬──────────────────────────────────────┘
           │ DELEGATE / FINAL
    ┌──────┴────────────────────────┐
    ▼              ▼               ▼
┌────────┐   ┌──────────┐   ┌──────────┐
│  Kimi  │   │ Nemotron │   │ GPT-OSS  │
│  K2    │   │  Super   │   │  120B    │
│ [code] │   │ [review] │   │ [synth.] │
└────────┘   └──────────┘   └──────────┘
```

**Les workers exécutent et retournent. Ils ne décident rien du flux.**

Flux exemple — "implémente l'auth JWT" :
```
Brain/Qwen → Kimi     [génère le code JWT]
Brain/Qwen → Nemotron [review du code]
Brain/Qwen → Kimi     [corrige les 2 bugs trouvés]
Brain/Qwen → FINAL    [code validé]
```

---

## Structure des fichiers

```
AGENTIQUE/
├── MASTER.md                   ← ce fichier (source de vérité)
├── .env                        ← clé API (gitignored, ne jamais committer)
├── .env.example                ← template sans clé réelle
│
├── nexus_chat.py               ← INTERFACE PRINCIPALE (chat interactif)
├── nexus.py                    ← orchestrateur batch (tâches one-shot)
├── nexus.bat                   ← lanceur Windows
│
├── mcp-servers/nexus/
│   ├── server.py               ← serveur MCP (intégration Claude Code)
│   ├── models.json             ← configuration des modèles NVIDIA NIM
│   └── requirements.txt
│
└── scripts/
    ├── install.bat             ← installation complète
    ├── discover_models.py      ← liste les modèles disponibles sur ton compte
    └── test_connection.py      ← vérifie que tout fonctionne
```

---

## Deux modes d'utilisation

### Mode 1 — Claude Code normal
Ouvrir Claude Code et travailler comme d'habitude. NEXUS n'intervient pas.
Utile pour : questions, debug interactif, décisions architecturales.

### Mode 2 — NEXUS Chat (interface agentique)
```bash
python nexus_chat.py --project <chemin-du-projet>
python nexus_chat.py --project <chemin-du-projet> --write   # écrit les fichiers
python nexus_chat.py --brain claude                         # force Claude comme Brain
```
Utile pour : implémentation, refactoring, review, audit de projet.

---

## Modèles NVIDIA NIM configurés

| Alias | Modèle | Rôle | Statut |
|-------|--------|------|--------|
| `qwen` | `qwen/qwen3.5-397b-a17b` | Brain / Orchestrateur | ✅ |
| `kimi` | `moonshotai/kimi-k2-instruct-0905` | Worker — code | ✅ |
| `nemotron` | `nvidia/nemotron-3-super-120b-a12b` | Worker — review | ✅ |
| `gpt_oss` | `openai/gpt-oss-120b` | Worker — synthèse | ✅ |
| `minimax` | `minimaxai/minimax-m2.5` | Contexte long | ✅ |
| `glm` | `z-ai/glm5` | Fallback | ✅ |

Modèles bonus disponibles (non actifs par défaut) :

| Modèle | Intérêt |
|--------|---------|
| `qwen/qwen3-coder-480b-a35b-instruct` | Qwen3 Coder 480B — code très complexe |
| `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Nemotron Ultra — alternative à Opus |
| `moonshotai/kimi-k2-thinking` | Kimi Thinking — bugs difficiles |
| `deepseek-ai/deepseek-v3.2` | DeepSeek V3.2 — généraliste puissant |

---

## Fallbacks automatiques

```
Brain Qwen échoue    → Claude Sonnet (CLI OAuth)
Worker Kimi échoue   → Qwen → GLM-5
Worker Nemotron échoue → Qwen → GLM-5
Rate limit NIM       → attente automatique 15s, retry
Max 8 itérations     → réponse du dernier worker disponible
```

---

## Installation

```bash
# 1. Copier la configuration de clé
cp .env.example .env
# Éditer .env et renseigner NVIDIA_API_KEY

# 2. Installer les dépendances
pip install mcp httpx

# 3. Enregistrer le MCP dans Claude Code
claude mcp add -s user -e "NVIDIA_API_KEY=<ta-cle>" nexus -- python mcp-servers/nexus/server.py

# 4. Vérifier
python -X utf8 scripts/test_connection.py

# 5. Découvrir les modèles disponibles sur ton compte
python -X utf8 scripts/discover_models.py
```

Ou sous Windows : double-cliquer sur `scripts/install.bat` (après avoir rempli `.env`).

---

## Journal des décisions d'architecture

### 2026-04-07 — Installation initiale
- Création de la structure AGENTIQUE
- 189 modèles NVIDIA NIM disponibles découverts
- MCP server enregistré dans Claude Code (scope user, Connected ✅)

### 2026-04-07 — v1 → v2 : pipeline fixe abandonné
Problème : ordre Qwen→Kimi→Nemotron toujours identique, non adaptatif.

### 2026-04-07 — v2 → v3 : Brain + Workers
Problème v2 : chaque agent décidait du routage, y compris les moins intelligents (GLM, Kimi).
Solution : un seul Brain (Qwen) centralise toutes les décisions. Les workers exécutent sans réfléchir au flux.

### 2026-04-07 — Premier commit public
Nettoyage sécurité : clé API retirée du code, chemins personnels anonymisés, `.gitignore` créé.
