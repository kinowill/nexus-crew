# DOCUMENT MAITRE PROJET

Statut: source de vérité produit/architecture pour la v1  
Projet: AGENTIQUE / NEXUS Crew  
Date: 2026-04-08

---

## 1. Objet du document

Ce document fixe la cible produit et la direction d'architecture de la v1.

Il sert à éviter :

- les décisions contradictoires entre README, code et audits ;
- les refontes guidées uniquement par des symptômes ;
- les choix d'architecture flous autour du multi-agent ;
- la dérive vers une démo "impressionnante" mais peu fiable.

Tant qu'un document plus récent ne le remplace pas explicitement, ce fichier fait foi pour le développeur.

---

## 2. Diagnostic actuel

Le projet actuel est un prototype avancé, pas encore un outil pro fiable.

Ce qui existe déjà de valable :

- une bonne intuition produit ;
- un wrapper `FallbackLLM` pertinent pour NVIDIA NIM ;
- une base de rôles utile : `Researcher`, `Architect`, `Coder`, `Critic`, `Scanner` ;
- une UX locale de départ correcte ;
- une vraie volonté de sécurité et de travail sur dépôt réel.

Ce qui ne va pas encore :

- le pipeline actuel est trop rigide et lance presque toujours toute la chaîne ;
- les agents ne respectent pas toujours leur contrat de sortie ;
- le système accepte comme "succès" des réponses invalides ;
- `run_shell_tool()` casse le périmètre de sécurité logique ;
- `Critic` a trop de privilèges ;
- le projet ne distingue pas encore proprement `analyse`, `édition`, `review`, `validation` ;
- les limites NVIDIA NIM sont contournées localement, mais pas encore absorbées dans un protocole robuste.

Conclusion :

La prochaine étape n'est pas "ajouter plus d'agents".  
La prochaine étape est "rendre le système multi-agent vérifiable, gouverné et exploitable".

---

## 3. Cible produit validee

### 3.1. Positionnement v1

La v1 doit être :

- un assistant local de développeur ;
- comparable dans l'expérience de travail à un outil type Codex / Claude Code ;
- piloté par l'utilisateur ;
- capable de lire, comprendre, expliquer, modifier et relire un projet réel ;
- orienté qualité/fiabilité avant vitesse.

### 3.2. Capacites attendues en v1

La v1 doit être excellente sur les deux boucles suivantes :

- lecture/compréhension/audit de gros projets ;
- modification propre de code existant avec validation.

Elle doit fonctionner proprement sur des dépôts gros et réels :

- code ;
- docs ;
- SQL ;
- scripts ;
- arborescences complexes ;
- plusieurs milliers à dizaines de milliers de fichiers ;
- avec une ambition vers encore plus gros, sans exiger une infra enterprise complète dès la v1.

### 3.3. Ce que la v1 n'est pas

La v1 n'est pas encore :

- un agent autonome long-run qui agit seul pendant des heures ;
- un remplaçant complet d'une équipe d'ingénierie ;
- un orchestrateur d'infrastructure enterprise ;
- un système de PR bot autonome à confiance totale.

L'autonomie longue durée est un objectif ultérieur, pas le coeur de la v1.

---

## 4. Exigences produit non negociables

### 4.1. Qualite avant vitesse

La v1 doit préférer :

- une réponse plus lente mais correcte ;
- un patch plus petit mais propre ;
- une validation explicite plutôt qu'un "ça a l'air bon".

Le système peut prendre 1 à 3 minutes si cela améliore réellement la qualité.

### 4.2. Supervision utilisateur

Le système doit pouvoir :

- demander des confirmations ;
- demander des autorisations spécifiques ;
- mémoriser des autorisations générales accordées pour une session ou une catégorie ;
- distinguer lecture, écriture, shell limité, shell large, actions sensibles.

### 4.3. Multi-agent reel

Objectif explicite :

Le produit ne vise pas une simple suite d'étapes figées jouées par des "agents" décoratifs.

Le produit doit viser un vrai système multi-agents où les agents :

- interagissent entre eux ;
- se demandent des confirmations ;
- se relisent ;
- se passent la balle ;
- se challengent ;
- convergent vers un résultat validé avant la réponse utilisateur.

### 4.4. Multi-agent, mais avec protocole

Le système voulu n'est pas un free-for-all conversationnel.

La coopération doit être :

- réelle ;
- encadrée ;
- traçable ;
- bornée ;
- validable ;
- compréhensible.

Le bon modèle n'est donc ni :

- une chaîne rigide purement séquentielle ;
- ni une conversation anarchique entre agents sans garde-fou.

Le bon modèle est :

un **mesh multi-agent supervisé par protocole**.

---

## 5. Contraintes techniques et operationnelles

### 5.1. Contraintes NVIDIA NIM

Le produit doit rester compatible avec les réalités suivantes :

- support inégal des formats structurés ;
- sensibilité aux messages système ;
- timeouts ;
- rate limits ;
- tool use moins robuste que sur certains modèles frontier ;
- variabilité entre modèles d'une même chaîne ;
- nécessité de fallback.

Conséquence :

Le protocole produit ne doit jamais dépendre d'une seule capacité fragile d'un seul modèle.

### 5.2. Contraintes de securite

Le produit manipulera :

- du code local ;
- des fichiers réels ;
- parfois du shell ;
- potentiellement des secrets présents dans les dépôts.

Le système doit donc être pensé comme un outil à risque réel, pas comme un chatbot.

### 5.3. Contrainte de lisibilite

Le développeur et l'utilisateur doivent pouvoir comprendre :

- quel agent a fait quoi ;
- pourquoi une action a été décidée ;
- pourquoi une demande a été rejetée ou mise en attente ;
- pourquoi le système estime qu'un résultat est valide.

---

## 6. Options d'architecture considerees

### Option A - Crew sequentiel classique

Structure :

`Researcher -> Architect -> Coder -> Critic -> Rework -> Final`

Avantages :

- simple à lire ;
- simple à implémenter ;
- facile à démontrer.

Limites :

- sur-travail pour les tâches simples ;
- trop rigide ;
- mauvaise adaptation à la nature réelle de la tâche ;
- agents souvent "en façade" plus qu'en coopération réelle ;
- fragile face aux réponses hors format ;
- peu proche de l'expérience type Codex.

Verdict :

**Rejeté comme architecture cible v1.**

### Option B - Mesh libre d'agents egaux

Structure :

Tous les agents peuvent se parler librement, s'interrompre, se déléguer des bouts de travail, reboucler sans gouvernance forte.

Avantages :

- coopération maximale en apparence ;
- comportement potentiellement riche ;
- effet "agentique" fort.

Limites :

- explosion de tokens et de latence ;
- risque de boucles inutiles ;
- difficulté énorme à valider le travail ;
- coût cognitif et technique élevé ;
- très mauvais fit avec les limites NVIDIA NIM ;
- débogage presque impossible quand ça échoue.

Verdict :

**Rejeté comme architecture cible v1.**

### Option C - Mesh multi-agent supervise par protocole

Structure :

- plusieurs agents réels, spécialisés ;
- interactions autorisées entre eux ;
- mais sous règles de protocole, contrats de sortie, budgets et validation.

Avantages :

- respecte la vision produit multi-agent ;
- permet une vraie relecture croisée ;
- garde une gouvernance exploitable ;
- réduit le chaos ;
- meilleur compromis entre intelligence collective et fiabilité ;
- compatible avec un futur mode plus autonome.

Limites :

- plus complexe à implémenter qu'un pipeline simple ;
- demande une couche de gouvernance claire ;
- nécessite de formaliser les messages, verdicts et permissions.

Verdict :

**Architecture cible retenue pour la v1.**

---

## 7. Architecture cible recommandee

### 7.1. Principe general

La v1 doit exposer à l'utilisateur un seul assistant cohérent, mais fonctionner en interne comme un système de plusieurs agents spécialisés qui coopèrent.

Ces agents ne sont pas de simples étapes fixes.

Ils doivent pouvoir :

- se poser des questions ;
- demander une confirmation à un pair ;
- demander une synthèse d'un pair ;
- renvoyer un travail pour correction ;
- bloquer la sortie finale tant qu'un contrat n'est pas respecté.

### 7.2. Agents cibles

#### 1. Lead Agent

Responsabilités :

- interface principale avec l'utilisateur ;
- compréhension de la demande ;
- maintien de l'objectif global ;
- synthèse finale ;
- pilotage du ton et de la qualité de la réponse.

Il ne doit pas tout faire lui-même.  
Il pilote et arbitre.

#### 2. Research Agent

Responsabilités :

- explorer le dépôt ;
- cartographier la structure ;
- identifier fichiers, modules, dépendances, conventions ;
- produire des synthèses techniques fiables ;
- répondre aux questions de contexte posées par les autres agents.

#### 3. Planning Agent

Responsabilités :

- transformer la demande utilisateur et le contexte en plan d'action ;
- définir le scope ;
- choisir les fichiers à toucher ;
- découper l'exécution ;
- préciser ce qui devra être validé.

#### 4. Coding Agent

Responsabilités :

- lire avant de modifier ;
- proposer ou exécuter des changements ;
- expliciter les fichiers touchés ;
- justifier la logique du patch ;
- renvoyer un état de modification clair.

#### 5. Critic Agent

Responsabilités :

- challenger le plan ou le patch ;
- chercher bugs, régressions, oublis, violations de conventions ;
- demander des corrections ;
- produire un verdict exploitable.

Important :

Le `Critic` n'est pas un second `Coder`.  
Il doit pouvoir relire et bloquer, pas corriger silencieusement à la place.

#### 6. Validation Agent

Responsabilités :

- exécuter ou demander les vérifications techniques ;
- agréger syntaxe, lint, tests, checks ciblés ;
- rendre un état objectif : validé, partiellement validé, bloqué, non vérifié.

#### 7. Safety / Permission Layer

Ce composant peut être un agent ou une couche système selon l'implémentation.

Responsabilités :

- faire respecter les permissions ;
- demander les confirmations nécessaires ;
- distinguer permissions générales et spécifiques ;
- bloquer les actions sensibles ;
- tracer les autorisations accordées.

#### 8. Context / Index Layer

Ce composant n'est pas forcément un agent.

Responsabilités :

- gérer la compréhension de gros dépôts ;
- stocker des résumés ;
- indexer localement ;
- servir le bon contexte aux agents sans recharger tout le repo à chaque fois.

---

## 8. Protocole multi-agent cible

### 8.1. Regle de base

Chaque agent peut interagir avec d'autres agents, mais uniquement par messages typés et contrats explicites.

Un agent ne doit pas envoyer :

- une vague intention ;
- une pseudo réponse ;
- un faux tool call en texte brut ;
- un message du type "je vais commencer par..." quand un livrable était demandé.

### 8.2. Types d'interactions autorises

Exemples :

- `request_context`
- `request_plan_review`
- `request_code_review`
- `request_patch_revision`
- `request_validation`
- `request_user_confirmation`
- `request_permission`
- `request_scope_clarification`

Chaque interaction doit préciser :

- l'émetteur ;
- le destinataire ;
- l'objectif ;
- le contexte minimum nécessaire ;
- le livrable attendu ;
- la limite de taille ;
- le statut de retour attendu.

### 8.3. Etats de sortie obligatoires

Chaque agent doit répondre dans un format contractuel minimal.

Exemples :

#### Research Agent

Doit produire :

- carte du dépôt ;
- fichiers clés ;
- risques ;
- inconnues restantes.

#### Planning Agent

Doit produire :

- plan ordonné ;
- scope ;
- fichiers probables ;
- validations attendues ;
- risques.

#### Coding Agent

Doit produire :

- actions réalisées ;
- fichiers modifiés ;
- raison des changements ;
- points à relire ;
- état : `done`, `blocked`, `needs_clarification`.

#### Critic Agent

Doit produire :

- findings ;
- sévérité ;
- verdict final strict : `APPROVED`, `CHANGES_NEEDED`, `BLOCKED`.

#### Validation Agent

Doit produire :

- checks lancés ;
- checks non lancés ;
- résultat ;
- blocages éventuels.

### 8.4. Boucles autorisees

Certaines boucles sont souhaitées :

- `Research <-> Planning`
- `Planning <-> Coding`
- `Coding <-> Critic`
- `Critic <-> Validation`
- `Lead <-> User`

Mais elles doivent être :

- bornées ;
- tracées ;
- motivées ;
- arrêtées au-delà d'un budget de tours ou si plus aucune information utile n'est produite.

### 8.5. Regle d'arret

Le système ne doit répondre à l'utilisateur que si :

- la demande a été comprise ;
- les permissions nécessaires sont accordées ;
- les agents critiques ont rendu un vrai livrable ;
- le verdict final est cohérent ;
- les validations ont été exécutées ou explicitement sautées ;
- la réponse finale décrit honnêtement ce qui a été fait, vérifié et non vérifié.

Sinon :

le système doit s'arrêter proprement et l'expliquer, pas improviser une pseudo réussite.

---

## 9. Modes d'usage v1

Le système doit classer une demande avant d'orchestrer les agents.

### Mode 1 - Explain / Read

Usage :

- comprendre un projet ;
- expliquer une architecture ;
- résumer un module ;
- auditer sans modifier.

Agents principaux :

- Lead ;
- Research ;
- éventuellement Planning ;
- éventuellement Critic.

Pas de passage automatique chez `Coder` si aucune modification n'est demandée.

### Mode 2 - Edit / Fix / Refactor

Usage :

- corriger ;
- refactorer ;
- implémenter un changement précis ;
- adapter du code existant.

Agents principaux :

- Lead ;
- Research ;
- Planning ;
- Coding ;
- Critic ;
- Validation.

### Mode 3 - Review

Usage :

- relire un patch ;
- identifier risques et régressions ;
- vérifier un travail existant.

Agents principaux :

- Lead ;
- Research si besoin ;
- Critic ;
- Validation.

### Mode 4 - Investigate / Debug

Usage :

- analyser un bug ;
- reproduire ;
- isoler une cause racine ;
- proposer ou appliquer une correction ensuite.

Agents principaux :

- Lead ;
- Research ;
- Planning ;
- Coding ;
- Critic ;
- Validation.

---

## 10. Strategie gros depots

La v1 doit être capable de gérer des dépôts lourds sans noyer les modèles.

Règles :

- ne jamais charger tout le dépôt dans le contexte ;
- commencer par inventaire + ciblage ;
- utiliser fortement recherche de fichiers et symboles ;
- résumer localement les gros fichiers ;
- réutiliser des résumés intermédiaires ;
- conserver une mémoire de session locale structurée ;
- séparer contexte brut, contexte résumé, contexte validé.

Objectif :

faire de la compréhension incrémentale, pas de l'ingestion brute.

---

## 11. Modele de permissions et securite

### 11.1. Permissions de base

Le système doit distinguer au minimum :

- `read`
- `write`
- `shell_limited`
- `shell_sensitive`
- `network` si un jour activé

### 11.2. Portee des permissions

Deux niveaux doivent exister :

- autorisation spécifique ;
- autorisation générale.

Exemples :

- "autorise ce test précis"
- "autorise tous les tests du projet pour cette session"

### 11.3. Regle produit

Le modèle de sécurité retenu par décision utilisateur est `power-user supervisé`, pas sandbox ultra-stricte.

Mais même dans ce mode :

- les actions sensibles restent confirmées ;
- les permissions sont tracées ;
- les limites du dépôt restent connues ;
- les actions shell ne doivent pas reposer sur une blacklist naïve.

### 11.4. Regle d'implementation

Pour la v1 pro :

- remplacer autant que possible les blacklists par des allowlists et catégories d'actions ;
- borner les commandes shell ;
- séparer nettement commandes de lecture, validation, build, git, package manager ;
- rendre impossible qu'un agent de review se transforme discrètement en agent d'édition.

---

## 12. Regles de qualite

Le produit doit se rapprocher d'un vrai outil pro.

Cela implique :

- un patch propre et expliqué ;
- une relecture indépendante ;
- une validation technique quand possible ;
- une honnêteté stricte sur ce qui a été vérifié ou non ;
- une réponse finale exploitable immédiatement par un développeur.

Le système doit considérer comme échec :

- une réponse d'intention au lieu d'un livrable ;
- un verdict absent ;
- un patch non relu ;
- un résumé final vide ou trompeur ;
- un enchaînement d'agents qui a tourné sans produire d'état actionnable.

---

## 13. Regles specifiques NVIDIA NIM

Le produit doit être conçu autour d'une matrice de capacités réelles des modèles.

Chaque modèle ou chaîne de fallback doit être caractérisé selon :

- stabilité ;
- qualité de raisonnement ;
- qualité de coding ;
- tolérance aux longs contextes ;
- tool use ;
- latence ;
- compatibilité messages système ;
- compatibilité formats structurés.

Décision clé :

Le protocole produit ne doit jamais présumer que tous les agents peuvent faire les mêmes choses avec le même niveau de fiabilité.

Autrement dit :

- certains rôles peuvent rester meilleurs pour la recherche ;
- d'autres pour le planning ;
- d'autres pour le coding ;
- mais tous doivent être intégrés dans un protocole résilient aux limites NIM.

---

## 14. Ecart entre le systeme actuel et la cible

### Aujourd'hui

- crew séquentiel ;
- agents avec rôles clairs mais trop peu gouvernés ;
- validation de sortie insuffisante ;
- permissions incomplètes ;
- shell trop permissif ;
- sur-utilisation du pipeline complet ;
- coopération inter-agents plus déclarée que réellement maîtrisée.

### Cible v1

- mesh multi-agent supervisé ;
- vrais rôles coopératifs ;
- protocoles et contrats de sortie stricts ;
- permissions traçables ;
- modes d'usage distincts ;
- validation technique intégrée ;
- réponse finale bloquée tant que l'état n'est pas cohérent.

---

## 15. Roadmap de mise a niveau pour le developpeur

### Phase 0 - Hardening fondations

- sécuriser `run_shell_tool()` ;
- retirer les privilèges d'édition au `Critic` ;
- rendre l'installation déterministe ;
- corriger incohérences README / batch / code ;
- clarifier les permissions.

### Phase 1 - Refactor protocole

- **PRIORITÉ 0 (ajoutée 2026-04-09 après run réel)** : matrice tool use par modèle NIM. Le run de validation Phase 0 a montré que sur 6 réponses d'agents, 5 étaient des intentions vides parce que les modèles autres que Qwen 3.5 397B (DeepSeek V3.2, Qwen 3 Coder 480B, Kimi K2 Thinking) ne savent pas appeler des outils via le mécanisme CrewAI/LiteLLM. Sans corriger ça, les contrats de sortie ci-dessous rejetteraient 5 sorties sur 6 et le pipeline tournerait à vide. Tester chaque modèle, basculer Architect/Coder/Critic sur des modèles tool-use compatibles (Llama 3.3 70B, Qwen2.5 instruct, etc.) avant tout autre chantier Phase 1.
- introduire des contrats de sortie par agent ;
- ajouter validation des appels d'outils (si un agent est censé lire un fichier et n'a pas appelé `read_file`, c'est un échec) ;
- introduire une couche de gouvernance ;
- arrêter d'accepter les réponses invalides ;
- séparer les modes `read`, `edit`, `review`, `debug`.

### Phase 2 - Coopération multi-agent réelle

- autoriser les interactions inter-agents utiles ;
- les typer proprement ;
- borner les boucles ;
- tracer les échanges ;
- ajouter feedback croisé `Coder <-> Critic <-> Validation`.

### Phase 3 - Intelligence dépôt lourd

- indexation locale légère ;
- résumés persistants de session ;
- meilleure sélection de contexte ;
- optimisation pour gros repos.

### Phase 4 - Qualité produit

- validations automatiques ciblées ;
- amélioration de la réponse utilisateur ;
- meilleure ergonomie des confirmations ;
- meilleurs logs ;
- meilleure observabilité des décisions.

### Phase 5 - Vers autonomie plus élevée

- sessions plus longues ;
- mémoire plus robuste ;
- orchestration plus ouverte ;
- autonomie partielle sur tâches larges ;
- toujours après stabilisation de la v1 locale.

---

## 16. Decisions actees

1. La v1 cible un assistant local type Codex / Claude Code.
2. La v1 doit être bonne à la fois en compréhension et en modification propre.
3. La v1 vise gros dépôts réels.
4. La priorité est la qualité/fiabilité avant la vitesse.
5. Le système doit pouvoir agir avec permissions générales ou spécifiques.
6. L'utilisateur garde la supervision des actions sensibles.
7. Le coeur du produit doit être multi-agent réel.
8. Le bon design n'est pas un pipeline rigide, ni un mesh anarchique.
9. L'architecture cible retenue est un mesh multi-agent supervisé par protocole.
10. L'autonomie longue durée est hors scope v1.

---

## 17. Non-objectifs v1

Ne pas viser en v1 :

- autonomie illimitée ;
- auto-exécution longue sans supervision ;
- support parfait des monorepos enterprise extrêmes ;
- orchestration distribuée complexe ;
- "magie agentique" au détriment de la fiabilité ;
- shell totalement libre sans gouvernance.

---

## 18. Fichiers de reference actuels

Pour le développeur :

- `README.md`
- `crew/crew.py`
- `nexus.bat`
- `requirements.txt`
- `Audit Technique Complet du Projet NEXUS Crew - généré par LLM.txt`
- `Utilisation 08.04.2026 - 15h30.txt`

Ce document maître doit être lu avant toute refonte importante du protocole ou des rôles agents.

---

## 19. Journal de validation

> Trace des modifications apportées au projet, conformément au protocole
> (distinction repo modifié / prod alignée / validation réelle).
> Les entrées les plus récentes sont en haut.

### 2026-04-09 — Phase 0 / Validation runtime + clôture + découverte critique tool use

- **Scope** : exécution réelle de NEXUS sur AGENTIQUE lui-même pour valider Phase 0 en runtime, puis clôture officielle de Phase 0.
- **Demande** : valider Phase 0 par un vrai run NIM (et non plus seulement par les tests statiques) avant d'attaquer Phase 1.
- **Run effectué** :
  - Commande : `python crew/crew.py "Explique en 3 lignes ce que fait ce projet (lis README.md)" --project .`
  - Mode : NORMAL (4 agents), pas de `--write`, pas de `--allow-shell`, pas de `--deep`
  - Durée : ~25 min (lent côté NIM, mais exit code 0)
  - Pipeline : Researcher → Architect → Coder → Critic → Coder rework → Architect synthèse finale
- **Ce qui est validé runtime (Phase 0)** :
  - Bannière de permissions affichée correctement (`read: ON`, `write_file: OFF`, `run_shell: OFF`).
  - **0 appel `write_file`** sur l'ensemble du run, malgré 2 invocations du Coder en dry-run.
  - **0 appel `run_shell`** sur l'ensemble du run.
  - 10 appels d'outils, **100 % en lecture** (`list_files`, `read_file`).
  - Cache LiteLLM actif (vérifié au démarrage).
  - Allowlist shell, Critic en lecture seule, Coder shell conditionnel : tous les chantiers Phase 0 se comportent en pratique comme en statique.
  - Exit code 0.
- **Découverte critique non Phase 0 — dette runtime majeure pour Phase 1** :
  - Sur 6 réponses d'agents (Researcher + Architect + Coder + Critic + Coder rework + Architect synthèse), **seul le Researcher (Qwen 3.5 397B) a produit un livrable réel**. C'est un rapport structuré complet, ~1000 mots, qui a même détecté `scripts/test_phase0.py` créé en début de session.
  - Les 5 autres réponses sont des **intentions vides** ("Je vais d'abord lire le fichier README.md...") qui violent explicitement §4.1, §8.1 et §12 du présent document.
  - Plusieurs réponses contiennent des `<tool_call>` au format XML coupé qui n'ont jamais été parsés par CrewAI/LiteLLM. CrewAI a accepté ces sorties cassées comme "Final Answer" valides au lieu de les rejeter.
  - **Cause racine probable** : tool use natif non supporté de manière fiable par DeepSeek V3.2 (Architect), Qwen 3 Coder 480B (Coder) et Kimi K2 Thinking (Critic) côté NIM. Ils tentent un format XML qui n'est pas reconnu, et CrewAI ne valide pas le contenu.
  - **Résultat final affiché à l'utilisateur** : `"Je vais d'abord lire le fichier README.md pour comprendre le projet et produire un rapport final."` — exactement ce que §12 interdit comme "réponse d'intention au lieu d'un livrable".
  - **Un warning CrewAI confirme l'instabilité** : `Event pairing mismatch. 'crew_kickoff_completed' closed 'llm_call_started'` — un appel LLM était encore en cours quand le crew s'est terminé.
- **Implication directe pour Phase 1** :
  - **Priorité 0 ajoutée à Phase 1** (à insérer avant les contrats de sortie §15 Phase 1) : **matrice tool use par modèle NIM**. Tester chaque modèle de chaque chaîne de fallback pour savoir lequel sait vraiment appeler des outils. Probablement basculer Architect/Coder/Critic vers Llama 3.3 70B ou Qwen2.5 instruct, qui sont annoncés comme tool-use compatibles par NIM.
  - Sans cette priorité 0, les contrats de sortie de Phase 1 ne servent à rien : on rejetterait simplement 5 sorties sur 6, et le pipeline tournerait à vide.
  - Les contrats de sortie restent nécessaires en plus, pour rejeter les "intentions" (sortie qui ne respecte pas le format demandé).
  - **Validation des appels d'outils** : si un agent est censé lire un fichier et n'a appelé `read_file` 0 fois, c'est un échec, pas un succès. À ajouter aux contrats Phase 1.
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée).
- **Fichiers NON committés (volontairement ignorés)** : `run_phase0.log` (~1389 lignes, déjà ignoré par `*.log` du `.gitignore`).
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation réelle (statique)** : OUI (entrée précédente, 20/20).
- **Validation réelle (runtime LLM)** : OUI sur le périmètre Phase 0 (permissions, dry-run, bannière, allowlist). Le pipeline a tourné de bout en bout, exit code 0, et toutes les invariants Phase 0 sont respectés en pratique.
- **Phase 0 — STATUT** : **CLÔTURÉE**. Code-complete + validée statiquement (20/20) + validée runtime sur le périmètre Phase 0. La dette tool use découverte n'est PAS une dette Phase 0 (les permissions sont respectées) — c'est une dette qualité produit qui devient priorité 0 de Phase 1.
- **Commit** : `8457f88` (poussé sur `origin/main`).

### 2026-04-09 — Phase 0 / Validation statique complète

- **Scope** : ajout d'une suite de tests statiques couvrant les 5 chantiers Phase 0 + remise à niveau de l'environnement `uv tool`.
- **Demande** : valider proprement Phase 0 avant d'ouvrir Phase 1, sans dépendre d'un run LLM réel (rate limits NIM).
- **Changements code** :
  - `scripts/test_phase0.py` : nouveau script de validation statique. 20 assertions sans appel réseau ni LLM.
    - Imports : `httpx`, `chromadb`, `crewai`, `litellm`.
    - Import de `crew.crew` (pose `CREW_PROJECT` et `CREW_SHELL_ENABLED` avant l'import).
    - Shell durci : `rm -rf foo` refusé (allowlist), `git log | head` refusé (chainage), `git status` autorisé, `python --version` autorisé, commande vide refusée, `curl` refusé.
    - Critic : pas de `write_file`, pas de `run_shell`, `read_file` présent.
    - Coder : `run_shell` présent ssi `CREW_SHELL_ENABLED`, `write_file` toujours présent.
    - Bannière : mentions `run_shell` et `write_file` dans le source.
  - `test_phase0.bat` : raccourci Windows qui réutilise la détection Python de `nexus.bat` et lance le script.
- **Découverte importante (dette cachée)** : l'environnement `uv tool` du poste tournait en `crewai 0.95.0` alors que `requirements.txt` réclame `>=1.14.0`. Le chantier Phase 0 §3 (install déterministe, commit `9770045`) avait corrigé `requirements.txt` mais l'env `uv tool` existant n'avait jamais été réinstallé. Tous les runs précédents s'appuyaient donc sur un env obsolète où `BaseLLM` n'existe pas (le code aurait crashé au premier vrai import si ça n'avait pas été masqué par un cache d'import quelconque).
- **Action prise sur l'env (hors repo)** : `uv tool install "crewai>=1.14.0" --with crewai-tools --with "litellm[caching]" --with httpx --with chromadb --force`. Env passé en `crewai 1.14.1` + `litellm` présent + cache LiteLLM actif (vérifié au lancement du test : `[cache LiteLLM actif - session uniquement]`).
- **Résultat tests** : `20/20` verts.
- **Fichiers touchés** : `scripts/test_phase0.py` (nouveau), `test_phase0.bat` (nouveau), `DOCUMENT_MAITRE_PROJET.md` (cette entrée).
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation réelle (statique)** : OUI — `python scripts/test_phase0.py` → 20/20.
- **Validation réelle (runtime LLM)** : NON. Le test ne couvre pas le comportement réel des agents face à NIM (respect des contrats Critic/Coder en pratique, fallback chain, rate limits). Cette dette reste explicite jusqu'au premier run NIM exploitable.
- **Dette résiduelle Phase 0 documentée** :
  - Allowlist binaire seulement (pas de catégories `git_read` vs `git_write`). `git push` passe si shell activé.
  - `shlex.split(posix=True)` mange les `\` des chemins Windows absolus dans une commande shell.
  - **Nouvelle** : la cohérence de l'env `uv tool` n'est pas vérifiée automatiquement. Si `requirements.txt` change, il faut relancer manuellement `uv tool install ... --force`. À surveiller au prochain bump de dépendance.
- **Commit** : `28a121c` (poussé sur `origin/main`).

### 2026-04-08 — Phase 0 / Relecture post-#1

- **Scope** : `crew/crew.py` — résidus détectés lors de la relecture finale Phase 0.
- **Changements** :
  - Critic backstory : suppression du passage "tu lances les tests quand c'est pertinent" qui contredisait la lecture seule de #2. Remplacé par une consigne explicite de mentionner les tests nécessaires dans le feedback sans les lancer.
  - Epilog CLI : ajout d'un exemple `--allow-shell`.
  - Journal : dette `shlex.split` posix documentée.
- **Fichiers touchés** : `crew/crew.py`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : non.
- **Commit** : `12b6a63` (poussé sur `origin/main`).

### 2026-04-08 — Phase 0 / Shell durci (fin Phase 0)

- **Scope** : `crew/crew.py` (`run_shell_tool`, `make_coder`, CLI), `nexus.bat`, `README.md`.
- **Demande** : Phase 0 §1 — sécuriser réellement `run_shell_tool()`, le point le plus critique de l'audit.
- **Changements** :
  - `run_shell_tool` : passe de `shell=True` + blacklist à `shell=False` + **allowlist stricte** de binaires (`python`, `pytest`, `node`, `npm`, `pnpm`, `yarn`, `git`, `grep`, `rg`, `find`, `where`, `ls`, `cat`, `head`, `tail`, `cargo`, `go`, `make`, `echo`, etc.).
  - Parsing via `shlex.split`, normalisation du binaire (basename + sans `.exe` + lowercase).
  - Refus explicite des métacaractères shell : `|`, `;`, `&&`, `||`, `>`, `<`, `` ` ``, `$(`, `>>`, `<<`. Message clair à l'agent ("lance une seule commande à la fois").
  - Nouveau flag CLI `--allow-shell` / `-s`, **OFF par défaut**. Sans ce flag, `run_shell_tool` n'est tout simplement pas ajouté aux tools du Coder → zéro shell possible.
  - `make_coder` choisit ses tools dynamiquement selon `CREW_SHELL_ENABLED`.
  - Bannière CLI mise à jour : `run_shell : ON / OFF` indépendant de `--write`.
  - **Amalgame `--write` / shell dissous** : `--write` ne concerne plus que `write_file`. Dette Phase 0 §5 résolue.
  - Suppression de la blacklist naïve (`rm`, `rmdir`, etc.) — l'allowlist la remplace intégralement.
  - `nexus.bat` interactif : ajout de la question `Activer le shell des agents ? [o/N]`.
  - `README.md` : table des flags à jour, section sécurité réécrite pour refléter le nouveau modèle.
- **Fichiers touchés** : `crew/crew.py`, `nexus.bat`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : non. Points à tester manuellement :
  1. Sans `--allow-shell`, le Coder ne doit pas avoir `run_shell` dans ses tools (observable via verbose CrewAI ou en demandant à l'agent "quels tools as-tu ?").
  2. Avec `--allow-shell`, une commande `git status` doit passer.
  3. Avec `--allow-shell`, une commande `rm -rf foo` doit être refusée avec message "hors allowlist".
  4. Avec `--allow-shell`, `git log | head` doit être refusé avec message "chainage non autorisé".
  5. Avec `--allow-shell`, `python --version` doit passer.
- **Commit** : `d4591d3` (poussé sur `origin/main`).
- **Limites Phase 0 connues** :
  - Allowlist binaire (autorisé / pas autorisé). Pas encore de catégories fines (`git_read` vs `git_write` vs `package_install`). Une commande comme `git push` passe si shell est activé, sans gate supplémentaire. Le modèle de catégories §11 du doc maître reste à faire dans une phase ultérieure.
  - `shlex.split(..., posix=True)` mange les `\` des chemins Windows absolus (ex : `python C:\foo.py` devient `['python', 'C:foo.py']`). Le cas normal fonctionne (chemins relatifs au projet, forward slashes), mais les chemins Windows absolus dans une commande doivent utiliser `/` ou être quotés. Dette mineure, à ré-évaluer si gênante.

### 2026-04-08 — Phase 0 / Permissions : lisibilité

- **Scope** : `crew/crew.py` — docstring module + bannière de démarrage CLI.
- **Demande** : Phase 0 §5 — clarifier les permissions (pas encore les refondre).
- **Changements** :
  - Bannière de démarrage : affiche désormais explicitement l'état de chaque catégorie de permission (`read`, `write_file`, `run_shell`, `shell destr.`) au lieu d'une simple ligne `Écriture: ACTIVÉE/DRY-RUN`.
  - Docstring module : section `Permissions (Phase 0)` qui documente l'état réel des capacités par agent et la dette connue.
- **Dette documentée** : le flag `--write` pilote actuellement à la fois `write_file` **et** les commandes shell destructives. Cet amalgame historique sera séparé dans le chantier Phase 0 §1 (Shell), pas avant — garder `--write` comme porte unique jusque-là pour ne pas casser l'UX.
- **Fichiers touchés** : `crew/crew.py`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : non. À tester : lancer `python crew/crew.py "x" -p .` (sans `--write`) puis avec `--write` et `--allow`, vérifier que la bannière reflète bien chaque cas.
- **Commit** : `812b538` (poussé sur `origin/main`).

### 2026-04-08 — Phase 0 / Installation déterministe

- **Scope** : `requirements.txt`, `README.md`, `nexus.bat`.
- **Demande** : Phase 0 §3 — rendre l'installation déterministe, réconcilier les promesses runtime et l'environnement réellement installé.
- **Diagnostic** :
  - `httpx` utilisé par `scripts/test_connection.py` et `scripts/discover_models.py` mais absent de `requirements.txt`.
  - `chromadb` listé dans `REQUIRED_IMPORTS` du test de santé mais absent de `requirements.txt` (dépendait du transitif CrewAI — fragile).
  - Cause racine du `cache LiteLLM désactivé` observé dans le run du 8 avril : la commande alternative `uv tool install crewai --with crewai-tools --with litellm` n'incluait pas l'extra `[caching]`, donc `diskcache` n'était pas résolu dans l'env `uv tool`. `requirements.txt` était correct depuis le début, mais la voie `uv tool` (celle utilisée par l'auteur et recommandée en premier) ne l'était pas.
- **Changements** :
  - `requirements.txt` : ajout de `httpx>=0.27` et `chromadb>=0.5`.
  - `README.md` et `nexus.bat` : commande `uv tool` corrigée pour inclure `litellm[caching]`, `httpx` et `chromadb`.
- **Fichiers touchés** : `requirements.txt`, `README.md`, `nexus.bat`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : non. À tester : réinstaller via la commande `uv tool` corrigée, puis lancer `python scripts/test_connection.py` (tous les imports doivent passer) et `python crew/crew.py "test" -p .` — le log doit afficher `[cache LiteLLM actif]` et non plus `[cache LiteLLM désactivé]`.
- **Commit** : `9770045` (poussé sur `origin/main`).

### 2026-04-08 — Phase 0 / Incohérences doc-code

- **Scope** : `nexus.bat`, `scripts/discover_models.py`.
- **Demande** : Phase 0 §4 — corriger les incohérences entre doc, batch et code réel.
- **Changements** :
  - `nexus.bat` : la bannière annonçait `memoire partagee` alors que `memory=True` est désactivé dans `crew.py` (incompat NIM). Mention retirée.
  - `scripts/discover_models.py` : suppression du bloc mort qui écrivait vers `mcp-servers/nexus/models.json` (chemin fantôme inexistant dans le repo, `if exists():` toujours faux). Docstring corrigée : le script redevient purement informatif, le report vers `MODEL_CHAINS` est manuel. Import `json` retiré (plus utilisé).
- **Fichiers touchés** : `nexus.bat`, `scripts/discover_models.py`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : non. À tester : `python scripts/discover_models.py` doit toujours lister les modèles sans erreur d'import et sans tenter d'écrire un fichier. `nexus.bat` doit afficher la bannière corrigée.
- **Commit** : `a6cd042` (local, non poussé).

### 2026-04-08 — Phase 0 / Critic : retrait écriture et shell

- **Scope** : `crew/crew.py` — `make_critic()` et `review_task`.
- **Demande** : Phase 0 §2 — retirer les privilèges d'édition et de shell au Critic.
- **Changement** :
  - `make_critic()` passe de `tools=FULL_TOOLS` à `tools=READ_TOOLS` (lecture seule).
  - Backstory renforcée : "Tu ne corriges JAMAIS toi-même : tu relis et tu bloques."
  - `review_task` : la mention "Lance les tests si tu en trouves (run_shell)" est retirée, remplacée par une consigne explicite de lecture seule et d'escalade dans le feedback.
- **Fichiers touchés** : `crew/crew.py`, `DOCUMENT_MAITRE_PROJET.md` (cette entrée).
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation réelle** : non. À tester au prochain run réel sur un petit projet — vérifier que le Critic ne tente plus d'écrire ni d'appeler `run_shell`, et qu'il rend bien un verdict `APPROVED` / `CHANGES_NEEDED` sans toucher aux fichiers.
- **Commit** : `ea6e5a0` (poussé sur `origin/main`).
- **Dette acceptée** : tant que le **Validation Agent** (§7.2 #6) n'existe pas, aucun agent ne lance les tests automatiquement. Cette dette est explicitement tolérée jusqu'à l'introduction du Validation Agent dans une phase ultérieure. Ne pas réintroduire de shell chez le Critic pour compenser.

