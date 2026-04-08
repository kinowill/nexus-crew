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

- introduire des contrats de sortie par agent ;
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
- **Commit** : à venir.
- **Dette acceptée** : tant que le **Validation Agent** (§7.2 #6) n'existe pas, aucun agent ne lance les tests automatiquement. Cette dette est explicitement tolérée jusqu'à l'introduction du Validation Agent dans une phase ultérieure. Ne pas réintroduire de shell chez le Critic pour compenser.

