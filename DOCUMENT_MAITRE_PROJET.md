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

- **PRIORITÉ 0 (ajoutée 2026-04-09 après run réel, MISE À JOUR le même jour)** :
  - **0.a — Matrice tool use par modèle NIM** : ✅ FAIT (`scripts/test_tool_use.py`, résultats dans `scripts/tool_use_matrix.md`). 11 modèles testés, 9 NATIVE / 2 ERROR. Conclusion **inverse de l'hypothèse initiale** : Qwen 3 Coder 480B (Coder), Kimi K2 Thinking (Critic) et tous leurs fallbacks répondent NATIVEMENT au format `tool_calls` OpenAI au niveau brut litellm. Le bug "intentions vides" du run Phase 0 n'est donc PAS un problème de capacité modèle. Seuls DeepSeek V3.2 (timeout 60s) et Gemma 3 27B (incapable structurellement côté NIM) sont à exclure.
  - **0.b — Swap chaîne `architect`** : ✅ FAIT. DeepSeek V3.2 → fallback, Qwen 3.5 397B → primaire (DeepSeek timeout 100% du temps sur l'appel test).
  - **0.c — Fix schemas tool use CrewAI → NIM** : ✅ FAIT. Cause racine : CrewAI met TOUS les params dans `required` (même ceux avec defaults Python). Qwen Coder et Kimi K2 basculent en XML Hermes cassé dès qu'ils voient `required: ["path", "offset", "limit"]`. Fix : `_strip_strict_tools()` dans `FallbackLLM.call()` retire `strict`, `additionalProperties`, et sort du `required` les params avec `default`. Validation directe : Qwen 3 Coder → `NATIVE: read_file({"path":"README.md"})` post-fix. Script de preuve : `scripts/test_crewai_schema.py`.
  - **0.d — Re-run NEXUS réel** : ✅ FAIT. Run complet exit code 0, 12 appels d'outils, 6/6 agents avec vrai livrable (vs 1/6 avant fix). Rapport final structuré en 5 sections. Zéro intention vide. **PRIORITÉ 0 CLÔTURÉE.**
- **§1 — Contrats de sortie + validation des appels d'outils** : ✅ FAIT (2026-04-10).
  - Nouveau module `crew/contracts.py` : contrats par task (pas par rôle — un même agent peut jouer des rôles différents selon la task).
  - 7 contrats définis : `research`, `plan`, `code`, `review`, `rework`, `final`, `scan`.
  - Chaque contrat vérifie : appels d'outils requis, longueur minimale de l'output, patterns obligatoires (ex: Critic doit contenir APPROVED ou CHANGES_NEEDED).
  - `ContractTracker` branché dans le Crew via `step_callback` (collecte les appels d'outils) + `task_callback` (valide le contrat après chaque task).
  - Violations loguées en temps réel (`[CONTRAT VIOLE]`) + rapport de synthèse en fin de run.
  - Pas de retry automatique sur violation (prévu Phase 2).
- **§3 — Résilience NIM : backoff 429 + retry XML Hermes + logs debug** : ✅ FAIT au niveau logique (2026-04-19).
  - `RATE_LIMIT_BACKOFFS = [1.0, 2.0, 4.0]` : 3 retries sur le même modèle avant fallback chain sur 429.
  - `_is_rate_limit_error()` + `_output_looks_malformed()` ajoutés.
  - Retry-1 sur sortie XML Hermes quand des tools ont été fournis (traite variance Kimi K2 ~10 %).
  - Logs opt-in via `NEXUS_DEBUG_LLM=1` (model / rl_try / msgs / bytes / tools / roles).
  - Validation : 6 mock tests + 13 unit tests OK. **Runtime NIM réel non encore observé**, prévu dans une session instrumentée dédiée.
  - **§3bis — retry budget épuisable + timeout LLM** : ✅ FAIT (2026-07-09). `_malformed_output_kind()` distingue `xml_hermes` et `intention_0_tools`; `FallbackLLM.call()` autorise désormais un retry par type de sortie cassée sur le même modèle, avec log désambiguïsé. `LLM_TIMEOUT_SECONDS = 90` borne aussi chaque appel modèle avant fallback chain; `NEXUS_LLM_TIMEOUT_SECONDS` permet de descendre temporairement à 30-45s pour les validations Codex courtes.
- introduire une couche de gouvernance ;
- **§2 — Séparer les modes `read`, `edit`, `review`, `debug`** : ✅ SLICE A FAITE (2026-04-20).
  - CLI `--mode {read,edit,review,debug}` dans `crew.py`, défaut `edit` (non-régression).
  - `build_crew` route les tasks par mode : `read` = 1 task (Researcher direct), `review` = 3 tasks (Researcher + review standalone + synthèse), `edit`/`debug` = pipeline complet 6 tasks (inchangé). `debug` garde la même composition que `edit`, mais dispose désormais de consignes prompt-level dédiées au diagnostic en Phase 2 §X.
  - Garde-fou : `--write` silencieusement ignoré en mode `read` et `review`.
  - Validation : 31/31 `test_modes.py` + 22/22 `test_phase0.py` + 31/31 `test_resilience.py`.
  - **Slice B — Classifier automatique local de mode** : ✅ FAIT en Phase 2 §W (2026-07-17). `--mode auto` classe localement `task_text` vers `read`, `review`, `debug` ou `edit` sans appel LLM dédié. Le défaut reste `edit` pour non-régression.

### Phase 2 - Coopération multi-agent réelle

- **§A — État de gouvernance après contrats** : ✅ FAIT (2026-07-09). `ContractTracker` produit désormais un `GovernanceReport` final : `OK` sans violation, `BLOCKED_CONTRACT_VIOLATIONS` si un contrat est violé. Le CLI affiche toujours cet état après le résumé des contrats. `--strict-contracts` permet aux automatisations de retourner exit code 2 en cas de blocage, sans changer le comportement par défaut. Pas de retry automatique dans cette slice : l'objectif est de rendre l'état final non ambigu avant les boucles correctives Phase 2 suivantes.
- **§B — Rapport de gouvernance JSON** : ✅ FAIT (2026-07-09). `ContractTracker` expose `governance_payload()`, `governance_json()` et `write_governance_json()`. Le CLI ajoute `--governance-json <chemin>` pour écrire un rapport machine-readable sous `--project`, avec garde-fou qui refuse les chemins hors projet. Cette slice trace l'état et les violations sans modifier la composition des agents, sans retry automatique et sans élargir les permissions.
- **§C — Violations typées pour boucles correctives** : ✅ FAIT (2026-07-09). Les violations exposent maintenant `severity` (`blocker`) et `action_hint` (`rerun_task_with_required_tool`, `rerun_task_with_more_complete_output`, `rerun_task_with_required_verdict_or_pattern`). Le payload JSON conserve ces champs pour préparer les futures boucles de correction sans activer de retry automatique dans cette slice.
- **§D — Plan correctif borne apres violation de contrat** : ✅ FAIT (2026-07-16). `ContractTracker` produit maintenant une action corrective par task violee, avec priorite deterministe (`required_tools` avant verdict/pattern, puis longueur), budget de relance par task et etat `should_rerun`. Le CLI imprime ce plan quand la gouvernance bloque, et le JSON expose `corrective_actions`. Pas de relance LLM automatique dans cette slice : elle prepare la boucle corrective sans changer la composition CrewAI ni les permissions.
- **§E — Budget correctif configurable CLI/JSON** : ✅ FAIT (2026-07-16). Le CLI expose `--correction-attempt-budget` pour piloter le budget annonce dans le plan correctif et le rapport JSON. La valeur doit etre >= 0. Ce flag ne declenche toujours aucune relance LLM automatique; il rend seulement la decision corrective parametree et traçable pour une future automatisation.
- **§F — Interactions correctives typees dans la gouvernance** : ✅ FAIT (2026-07-16). Chaque `CorrectiveAction` expose maintenant un `interaction_type` stable (`request_task_rerun`, `request_verdict_revision`, `request_output_expansion`) derive de l'action corrective. Le CLI et le JSON rendent donc lisible le type d'interaction a effectuer, sans encore executer de boucle inter-agent automatique.
- **§G — Identifiants stables d'interactions correctives** : ✅ FAIT (2026-07-16). Chaque action corrective expose maintenant `interaction_id` sous la forme `task:agent:interaction_type`. Ce champ rend les futures relances ou validations traçables entre CLI, JSON et journal sans activer de retry automatique.
- **§H — Résumé machine-readable du plan correctif** : ✅ FAIT (2026-07-16). Le rapport JSON expose maintenant `correction_plan` avec `status`, compte d'actions, nombre relançable, nombre épuisé et budget. Ce résumé évite aux intégrations de recalculer l'état depuis `corrective_actions`, sans déclencher de retry automatique.
- **§I — Enveloppes d'interactions correctives JSON** : ✅ FAIT (2026-07-16). Les actions correctives peuvent maintenant être exposées sous `corrective_interactions`, avec `interaction_id`, `interaction_type`, `status`, source, agent cible, task, raison et état de dispatch. C'est une préparation traçable des futures interactions inter-agents, sans exécution automatique.
- **§J — Version de schéma du rapport de gouvernance** : ✅ FAIT (2026-07-16). Le payload de gouvernance expose maintenant `schema_version` afin que les outils et futures boucles d'orchestration puissent reconnaître explicitement le format JSON consommé.
- **§K — Suivi des tentatives par interaction corrective** : ✅ FAIT (2026-07-16). Les helpers correctifs acceptent maintenant `attempts_used_by_interaction_id`, prioritaire sur `attempts_used_by_task`, afin de suivre les budgets sur l'identifiant stable `interaction_id` plutôt que sur un nom de task trop grossier.
- **§L — Propagation du ledger de tentatives dans le JSON** : ✅ FAIT (2026-07-16). `governance_payload()`, `governance_json()` et `write_governance_json()` acceptent maintenant les ledgers optionnels de tentatives par task ou par `interaction_id`, afin que `correction_plan`, `corrective_actions` et `corrective_interactions` reflètent directement l'état consommé.
- **§M — Chargement CLI du ledger correctif JSON** : ✅ FAIT (2026-07-16). Le CLI expose `--correction-ledger-json` pour lire, sous `--project`, un ledger de tentatives correctives (`attempts_used_by_task`, `attempts_used_by_interaction_id`) et l'appliquer au résumé correctif comme au rapport `--governance-json`, sans relance automatique.
- **§N — Snapshot CLI du ledger correctif JSON** : ✅ FAIT (2026-07-16). Le CLI expose `--correction-ledger-out-json` pour écrire, sous `--project`, un snapshot du ledger correctif consommé, du plan correctif et des interactions pending/bloquées. Ce snapshot n'incrémente aucune tentative et ne déclenche toujours aucune relance automatique.
- **§O — Version de schéma du ledger correctif JSON** : ✅ FAIT (2026-07-16). Le ledger correctif expose maintenant `schema_version = 1` via `CORRECTION_LEDGER_SCHEMA_VERSION`; le CLI accepte les ledgers entrants sans version pour compatibilité, mais refuse une version présente et inconnue.
- **§P — Manifeste dry-run de dispatch correctif** : ✅ FAIT (2026-07-16). Le CLI expose `--correction-dispatch-json` pour écrire, sous `--project`, les interactions correctives dispatchables, les interactions bloquées par budget et le `next_ledger` qui résulterait de leur consommation. Cette slice ne relance aucun agent et ne modifie pas le ledger d'entrée.
- **§Q — Écriture directe du next ledger correctif** : ✅ FAIT (2026-07-16). Le CLI expose `--correction-next-ledger-json` pour écrire directement, sous `--project`, le `next_ledger` projeté par le manifeste dry-run. Le fichier produit est relisible par `--correction-ledger-json`; aucune relance automatique n'est exécutée.
- **§R — Constantes de statuts dispatch correctif** : ✅ FAIT (2026-07-16). Les statuts du manifeste dry-run sont centralisés (`DISPATCH_AVAILABLE`, `DISPATCH_BLOCKED_BUDGET_EXHAUSTED`, `NO_DISPATCH_NEEDED`) pour éviter les chaînes brutes dans le code appelant. Le JSON produit reste compatible.
- **§S — Exit code strict pour dispatch correctif disponible** : ✅ FAIT (2026-07-17). Le CLI expose `--strict-correction-dispatch` pour retourner exit code 3 quand un dispatch correctif dry-run est disponible, sans relance automatique. `--strict-contracts` garde la priorité avec exit code 2.
- **§T — Résumé CLI du dispatch correctif strict** : ✅ FAIT (2026-07-17). Quand `--strict-correction-dispatch` est actif, le CLI imprime un résumé compact du statut dry-run, du nombre d'interactions dispatchables/bloquées et de l'exit code 3 éventuel avant de sortir. Aucun ledger n'est consommé et aucune relance automatique n'est exécutée.
- **§U — Résumé CLI du manifeste dispatch JSON** : ✅ FAIT (2026-07-17). `--correction-dispatch-json` imprime maintenant le même résumé compact que le mode strict après écriture du manifeste. Le payload est calculé une seule fois puis réutilisé pour l'écriture et l'affichage, sans consommer de ledger et sans relance automatique.
- **§V — IDs d'interactions dans le résumé dispatch** : ✅ FAIT (2026-07-17). Le résumé CLI du dispatch affiche maintenant les `interaction_id` dispatchables et bloqués, bornés à 5 IDs par ligne avec compteur résiduel. Cela rend la reprise plus directe sans ouvrir le JSON et sans changer le payload.
- **§W — Mode auto local sans appel LLM dédié** : ✅ FAIT (2026-07-17). `--mode auto` résout la demande vers `read`, `review`, `debug` ou `edit` via heuristique locale déterministe. Le défaut CLI reste `edit`, et les modes explicites gardent priorité sur la classification.
- **§X — Différenciation prompt-level du mode debug** : ✅ FAIT (2026-07-17). `debug` conserve la même composition que `edit`, mais ajoute des consignes par task sur reproduction, cause racine, patch minimal, review ciblée et synthèse de validation. Aucun agent, outil ou retry automatique supplémentaire n'est ajouté.
- **§Y — IDs dispatchables au premier niveau du manifeste** : ✅ FAIT (2026-07-17). Le manifeste dry-run expose maintenant `dispatchable_interaction_ids` en plus des enveloppes complètes, aligné avec `blocked_interaction_ids`. Les automatisations peuvent consommer directement les IDs sans reparcourir `dispatchable_interactions`.
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

**Runtime et orchestration**
- `README.md`
- `crew/crew.py` — orchestration CrewAI, `FallbackLLM`, `_output_looks_malformed`, `ContractTracker` branché
- `crew/contracts.py` — contrats de sortie par task (§1)
- `nexus.bat` — entrée utilisateur principale
- `requirements.txt`

**Scripts de validation / diagnostic (offline, sans réseau)**
- `scripts/test_phase0.py` — validation statique Phase 0 (22/22)
- `scripts/test_resilience.py` — tests unitaires résilience NIM §3 + §3bis (31/31)
- `scripts/test_modes.py` — tests unitaires modes d'usage Phase 1 §2 + gardes chemin JSON/ledger/dispatch, snapshot correctif, next ledger, statuts dispatch, résumés CLI avec IDs, mode auto/debug, exit strict et schémas (89/89)
- `scripts/test_contracts.py` — tests contrats + rapports de gouvernance Phase 2 §A/§B/§C/§D/§E/§F/§G/§H/§I/§J/§K/§L (76/76)
- `test_phase0.bat` — lanceur Windows pour `test_phase0.py`

**Scripts de diagnostic NIM (avec réseau, coûteux en tokens)**
- `scripts/test_tool_use.py` — matrice tool use par modèle NIM
- `scripts/tool_use_matrix.md` — résultats de la matrice
- `scripts/test_crewai_schema.py` — preuve du fix schemas CrewAI→NIM (§0.c)
- `scripts/test_connection.py` — santé connexion NIM

**Contexte produit**
- `Audit Technique Complet du Projet NEXUS Crew - généré par LLM.txt` (gitignored)
- `Utilisation 08.04.2026 - 15h30.txt` (gitignored)

Ce document maître doit être lu avant toute refonte importante du protocole ou des rôles agents.

---

## 19. Journal de validation

> Trace des modifications apportées au projet, conformément au protocole
> (distinction repo modifié / prod alignée / validation réelle).
> Les entrées les plus récentes sont en haut.

### 2026-07-17 — Phase 2 §Y / IDs dispatchables au premier niveau du manifeste

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : le manifeste dry-run exposait déjà les enveloppes dispatchables et les IDs bloqués, mais les automatisations devaient reparcourir `dispatchable_interactions` pour obtenir la liste simple des IDs à reprendre.
- **Changement appliqué** : ajout de `dispatchable_interaction_ids` dans `_correction_dispatch_payload()`, trié et placé au premier niveau du JSON, en miroir de `blocked_interaction_ids`. Aucun dispatch réel, aucun ledger consommé, aucun retry automatique.
- **Tests ajoutés** : `scripts/test_modes.py` vérifie le champ dans le payload direct et dans le fichier écrit par `_write_correction_dispatch_json()`.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 89/89 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §X / Différenciation prompt-level du mode debug

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après `--mode auto`, le mode `debug` pouvait être choisi automatiquement mais restait encore identique à `edit` dans les consignes données aux tasks.
- **Changement appliqué** : ajout de consignes `Mode DEBUG` par task (`research`, `plan`, `code`, `review`, `rework`, `final`) pour orienter le pipeline vers reproduction, cause racine, patch minimal, review ciblée et synthèse des validations. La composition reste volontairement identique à `edit` : 6 tasks, mêmes agents, aucun retry automatique.
- **Tests ajoutés** : `scripts/test_modes.py` vérifie que `debug` garde le pipeline/les agents de `edit`, contient les consignes diagnostic, et que `edit` ne les reçoit pas.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 87/87 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non effectuée; le changement est prompt-level et couvert structurellement offline, mais l'effet qualitatif devra être observé sur un vrai bug.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §W / Mode auto local sans appel LLM dédié

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : la Phase 1 §2 avait volontairement différé le classifier automatique de mode. Le routage explicite était stable; il manquait une option locale pour éviter le pipeline complet sur les demandes évidentes de lecture ou review.
- **Changement appliqué** : ajout de `--mode auto`. Le classifieur local détermine `read`, `review`, `debug` ou `edit` depuis `task_text`, sans appel LLM dédié. Le défaut historique reste `edit`; les modes explicites gardent priorité. La bannière affiche `AUTO -> MODE` et `--write` est ignoré si `auto` résout vers `read` ou `review`.
- **Tests ajoutés** : `scripts/test_modes.py` couvre les classifications `read`, `review`, `debug`, `edit`, le fallback ambigu vers `edit`, la priorité des modes explicites, `build_crew(..., mode="auto")` et `--deep + auto`.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 85/85 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice de routage déterministe/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §V / IDs d'interactions dans le résumé dispatch

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : les résumés CLI donnaient le statut et les comptes, mais pas les `interaction_id` exacts à reprendre ou à inspecter.
- **Changement appliqué** : le résumé dispatch affiche maintenant les IDs dispatchables et bloqués, bornés à 5 par ligne avec compteur résiduel. Le JSON et les décisions de dispatch restent inchangés.
- **Tests ajoutés** : `scripts/test_modes.py` couvre l'affichage d'un ID dispatchable et d'un ID bloqué dans les résumés.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 73/73 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §U / Résumé CLI du manifeste dispatch JSON

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : `--correction-dispatch-json` écrivait un manifeste exploitable, mais le terminal n'affichait encore que le chemin du fichier. L'utilisateur devait ouvrir le JSON pour connaître le statut réel du dispatch.
- **Changement appliqué** : le CLI calcule le payload de dispatch une seule fois, l'utilise pour écrire le manifeste, puis imprime le résumé compact du statut dry-run. Si `--strict-correction-dispatch` est combiné au manifeste, le résumé inclut aussi l'exit code 3 éventuel. Aucun retry automatique et aucune consommation de ledger.
- **Tests ajoutés** : `scripts/test_modes.py` couvre l'écriture d'un payload fourni sans recalcul.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 71/71 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §T / Résumé CLI du dispatch correctif strict

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : `--strict-correction-dispatch` donnait un signal d'automatisation via exit code 3, mais le terminal ne rendait pas encore ce signal explicitement lisible au moment de sortir.
- **Changement appliqué** : ajout d'un résumé CLI compact du dispatch dry-run quand `--strict-correction-dispatch` est actif. Il affiche le statut, le nombre d'interactions dispatchables/bloquées et l'exit code 3 quand il s'applique. Aucun retry automatique et aucune consommation de ledger.
- **Tests ajoutés** : `scripts/test_modes.py` couvre le résumé disponible, l'annonce de l'exit code 3 en strict et l'absence d'annonce en non strict.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 70/70 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-17 — Phase 2 §S / Exit code strict pour dispatch correctif disponible

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : le manifeste dry-run permettait déjà de savoir qu'un dispatch correctif était disponible, mais les automatisations ne disposaient pas encore d'un signal CLI strict dédié.
- **Changement appliqué** : ajout de `--strict-correction-dispatch`. Quand le dispatch dry-run expose `DISPATCH_AVAILABLE`, le CLI retourne exit code 3. Si `--strict-contracts` bloque déjà le run, l'exit code 2 reste prioritaire. Aucun retry automatique n'est déclenché.
- **Tests ajoutés** : `scripts/test_modes.py` couvre le mode non strict, le dispatch disponible, le budget épuisé et l'absence de dispatch.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 67/67 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §R / Constantes de statuts dispatch correctif

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §P/§Q exposaient des statuts de dispatch utiles aux automatisations, mais `_correction_dispatch_payload()` utilisait encore des chaînes brutes internes.
- **Changement applique** : ajout de constantes publiques `CORRECTION_DISPATCH_AVAILABLE`, `CORRECTION_DISPATCH_BLOCKED_BUDGET_EXHAUSTED` et `CORRECTION_DISPATCH_NO_DISPATCH_NEEDED`; le payload conserve les mêmes valeurs JSON.
- **Tests ajoutés** : `scripts/test_modes.py` couvre la stabilité des trois statuts publics et utilise ces constantes dans les assertions de dispatch.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 63/63 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice constantes/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §Q / Écriture directe du next ledger correctif

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §P exposait le `next_ledger` dans le manifeste de dispatch, mais une session suivante devait encore l'extraire manuellement pour le fournir à `--correction-ledger-json`.
- **Changement applique** : ajout de `--correction-next-ledger-json`, borné à `--project`, qui écrit directement le `next_ledger` projeté par `_correction_dispatch_payload()`. Le fichier produit conserve `schema_version`, `attempts_used_by_task` et `attempts_used_by_interaction_id`, et reste relisible par le loader de ledger.
- **Tests ajoutés** : `scripts/test_modes.py` couvre écriture du next ledger, relecture par `_load_correction_attempt_ledger()`, conservation du budget épuisé et refus d'écriture hors projet.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 62/62 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §P / Manifeste dry-run de dispatch correctif

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après §N/§O, le système savait exposer et versionner l'état correctif, mais pas encore produire un plan de consommation exploitable par une couche d'orchestration externe.
- **Changement applique** : ajout de `--correction-dispatch-json`, borné à `--project`. Le manifeste expose `schema_version`, `ledger_schema_version`, `status`, `dispatchable_interactions`, `blocked_interaction_ids`, `correction_plan` et `next_ledger` avec les tentatives par `interaction_id` incrémentées virtuellement pour les interactions dispatchables.
- **Tests ajoutés** : `scripts/test_modes.py` couvre chemin dispatch borné, dispatch disponible, budget épuisé, aucun dispatch nécessaire, écriture fichier et refus d'écriture hors projet.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 58/58 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §O / Version de schéma du ledger correctif JSON

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §N écrivait un snapshot de ledger avec `schema_version`, mais cette version n'était pas centralisée et l'entrée CLI ne refusait pas encore une version explicitement inconnue.
- **Changement applique** : ajout de `CORRECTION_LEDGER_SCHEMA_VERSION = 1`; le snapshot écrit cette constante et `_load_correction_attempt_ledger()` refuse un `schema_version` présent mais différent. Les ledgers entrants sans `schema_version` restent acceptés pour compatibilité.
- **Tests ajoutés** : `scripts/test_modes.py` couvre version courante acceptée, version inconnue refusée et présence de la version dans le snapshot sortant.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 47/47 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §N / Snapshot CLI du ledger correctif JSON

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §M savait charger un ledger correctif entrant, mais la session ne pouvait pas encore écrire un état de reprise lisible pour un orchestrateur ou une prochaine session.
- **Changement applique** : ajout de `--correction-ledger-out-json`, borné à `--project`. Le fichier écrit conserve `attempts_used_by_task` et `attempts_used_by_interaction_id`, expose `correction_plan`, `pending_interaction_ids`, `blocked_interaction_ids` et `interactions_count`. Il n'incrémente aucune tentative puisqu'aucune relance automatique n'est exécutée.
- **Tests ajoutés** : `scripts/test_modes.py` couvre snapshot pending sans consommation, budget épuisé, écriture fichier et refus de chemin hors projet.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 44/44 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §M / Chargement CLI du ledger correctif JSON

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §L rendait le ledger exploitable par les helpers Python, mais pas encore par l'interface CLI. Une automatisation devait pouvoir fournir un fichier de tentatives sans modifier le code appelant.
- **Changement applique** : ajout de `--correction-ledger-json`, borné à `--project`, avec validation stricte du JSON (`attempts_used_by_task` et `attempts_used_by_interaction_id` objets string -> entier >= 0). Le ledger alimente `correction_summary()` et `write_governance_json()`; aucun retry automatique n'est activé.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 38/38 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `crew.py --help` OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice CLI/JSON/tests offline uniquement.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §L / Propagation du ledger de tentatives dans le JSON

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §K permettait de calculer l'état de tentative par `interaction_id`, mais `governance_payload()` et `governance_json()` ne recevaient pas encore ce ledger. Les consommateurs JSON devaient donc appeler les helpers bas niveau séparément.
- **Changement applique** : `governance_payload()`, `governance_json()` et `write_governance_json()` acceptent `attempts_used_by_task` et `attempts_used_by_interaction_id`, puis propagent ces valeurs vers `correction_plan`, `corrective_actions` et `corrective_interactions`. Aucune relance automatique n'est activée.
- **Validation offline** : `test_contracts.py` 76/76 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice (contrats/JSON/tests offline uniquement).
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §K / Suivi des tentatives par interaction corrective

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après l'ajout de `interaction_id`, continuer à compter les tentatives uniquement par `task_name` restait trop grossier. Deux actions correctives peuvent viser la même task avec des agents ou types d'interaction différents.
- **Changement applique** : `corrective_actions()`, `correction_summary()`, `corrective_interactions()` et `correction_plan_payload()` acceptent `attempts_used_by_interaction_id`. Cette source est prioritaire sur `attempts_used_by_task`, qui reste compatible. Aucune relance automatique n'est activée.
- **Validation offline** : `test_contracts.py` 71/71 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice (contrats/JSON/tests offline uniquement).
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §J / Version de schéma du rapport de gouvernance

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après l'ajout de champs JSON correctifs, les consommateurs du rapport avaient besoin d'un repère stable pour savoir quel format ils lisent. Un champ de version évite de deviner le schéma depuis la présence ou l'absence de clés.
- **Changement applique** : ajout de `GOVERNANCE_PAYLOAD_SCHEMA_VERSION = 1` et du champ `schema_version` dans `governance_payload()` / `governance_json()`. Tests ajoutés sur payload dict et JSON.
- **Validation offline** : `test_contracts.py` 66/66 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice (contrats/JSON/tests offline uniquement).
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §I / Enveloppes d'interactions correctives JSON

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après `interaction_type`, `interaction_id` et `correction_plan`, le JSON savait quoi corriger mais ne fournissait pas encore d'enveloppe d'interaction directement traçable. La future boucle inter-agents a besoin d'un objet stable à dispatcher ou à bloquer.
- **Changement applique** : ajout de `CorrectiveAction.as_interaction_dict()` et `ContractTracker.corrective_interactions()`. Le rapport JSON expose `corrective_interactions` avec `status` (`PENDING` ou `BLOCKED_BUDGET_EXHAUSTED`), `source`, `target_agent`, task, raison, budget et `should_dispatch`.
- **Validation offline** : `test_contracts.py` 64/64 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `py_compile` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice (contrats/JSON/tests offline uniquement).
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §H / Résumé machine-readable du plan correctif

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après `corrective_actions`, les intégrations devaient encore recalculer elles-mêmes si une correction était disponible, inutile ou bloquée par budget. Le JSON avait besoin d'un résumé stable et lisible sans activer de retry automatique.
- **Changement applique** : ajout de `ContractTracker.correction_plan_payload()` et du bloc JSON `correction_plan` (`status`, `actions_count`, `rerunnable_count`, `exhausted_count`, `has_rerunnable_actions`, `attempts_budget`). Les détails restent dans `corrective_actions`.
- **Validation offline** : `test_contracts.py` 53/53 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `py_compile` OK, `crew.py --help` OK, `git diff --check` OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A (outil local).
- **Validation runtime NIM** : non nécessaire pour cette slice (contrats/JSON/tests offline uniquement).
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §G / Identifiants stables d'interactions correctives

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §F rendait le type d'interaction lisible, mais pas encore adressable. Pour tracer une future relance ou validation corrective, chaque interaction doit avoir une cle stable dans le CLI et le JSON.
- **Changement applique** : `CorrectiveAction` expose `interaction_id` au format `task:agent:interaction_type`; le resume CLI et le JSON le conservent. Tests ajoutes pour les trois types d'interaction corrective.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 45/45 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM reelle** : non effectuee; changement gouvernance/reporting uniquement, sans nouvel appel LLM.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : oui pour validation offline automatisee; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-16 — Alignement post-audit §D/§E/§F

- **Scope** : `crew/crew.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : l'audit lecture seule apres §F a repere trois incoherences de suivi : aide CLI `read` encore annoncee `Researcher + Architect`, tableau README Phase 2 limite a §A, et formulation README redondante sur le budget correctif.
- **Changement applique** : aide CLI alignee sur le code (`read` = Researcher seul), tableau README Phase 2 aligne sur §A-§F, formulation du budget correctif simplifiee. Aucun comportement runtime modifie.
- **Validation offline** : `crew.py --help` OK, `git diff --check` OK. Couvert ensuite par validation complete §G : `test_phase0.py` 22/22, `test_modes.py` 33/33, `test_resilience.py` 31/31, `test_contracts.py` 45/45, `ruff check crew scripts` OK.
- **Validation runtime NIM reelle** : non effectuee; correction documentation/aide CLI uniquement.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : oui pour validation offline automatisee; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §F / Interactions correctives typees

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §D/§E rendent les corrections visibles et bornees, mais il manquait encore un type d'interaction explicite pour preparer les futures boucles inter-agents sans reintroduire de delegation libre.
- **Changement applique** : `CorrectiveAction` expose `interaction_type`. Les mappings sont deterministes : outil requis -> `request_task_rerun`, verdict/pattern manquant -> `request_verdict_revision`, sortie trop courte -> `request_output_expansion`. Le resume CLI et le JSON incluent ce champ.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 41/41 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM reelle** : non effectuee dans cette session; changement gouvernance/reporting uniquement, sans nouvel appel LLM.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : oui pour validation offline automatisee; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §E / Budget correctif configurable CLI et JSON

- **Scope** : `crew/contracts.py`, `crew/crew.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : §D produisait un plan correctif borne, mais le budget etait fixe a 1. Pour qu'une automatisation ou une session longue puisse reprendre clairement l'etat, le budget doit etre explicite et parametrable sans activer de retry automatique.
- **Changement applique** : `governance_json()` et `write_governance_json()` acceptent `correction_attempt_budget`; le CLI ajoute `--correction-attempt-budget` avec garde-fou `>= 0`; le resume correctif et le JSON utilisent ce budget.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 36/36 OK, `ruff check crew scripts` OK, `git diff --check` OK, `crew.py --help` OK.
- **Validation runtime NIM reelle** : non effectuee dans cette session; changement CLI/reporting uniquement, sans nouvel appel LLM.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : oui pour validation offline automatisee; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-16 — Phase 2 §D / Plan correctif borne apres violation de contrat

- **Scope** : `crew/contracts.py`, `crew/crew.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : les violations typees de §C donnaient l'action attendue, mais pas encore une decision de correction exploitable par le CLI ou par une automatisation. Il fallait franchir une etape sans activer trop tot de relance LLM automatique.
- **Changement applique** : ajout de `CorrectiveAction` et de `ContractTracker.corrective_actions()` / `correction_summary()`. Les violations sont regroupees par task, priorisees de facon deterministe (`required_tools` puis verdict/pattern puis longueur), bornees par un budget de relance par task et exposees dans `governance_payload()` sous `corrective_actions`. Le CLI imprime le plan correctif uniquement quand la gouvernance bloque.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 33/33 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM reelle** : non effectuee dans cette session; changement gouvernance/reporting uniquement, sans nouvel appel LLM.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : oui pour validation offline automatisee; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-09 — Phase 2 §C / Violations typées

- **Scope** : `crew/contracts.py`, `scripts/test_contracts.py`, `DOCUMENT_MAITRE_PROJET.md`, `README.md`.
- **Motivation** : les rapports JSON de §B étaient structurés, mais les violations ne donnaient pas encore d'indication machine-readable sur leur criticité ni sur l'action corrective attendue. Pour préparer les boucles correctives Phase 2 sans les activer trop tôt, il faut typer ces signaux.
- **Changement appliqué** : `Violation` expose `severity` (actuellement `blocker`) et `action_hint`. Les règles `required_tools`, `min_output_length` et `required_patterns` produisent respectivement `rerun_task_with_required_tool`, `rerun_task_with_more_complete_output` et `rerun_task_with_required_verdict_or_pattern`. `Violation.as_dict()` et donc le JSON de gouvernance conservent ces champs.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 21/21 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM réelle** : non effectuée dans cette session; changement contrat/reporting uniquement.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle effectuée** : oui pour validation offline automatisée; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-09 — Phase 2 §B / Rapport de gouvernance JSON

- **Scope** : `crew/contracts.py`, `crew/crew.py`, `scripts/test_contracts.py`, `scripts/test_modes.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : après l'état `OK` / `BLOCKED_CONTRACT_VIOLATIONS`, la gouvernance devait devenir traçable par une automatisation ou une session longue, sans dépendre d'un résumé texte.
- **Changement appliqué** : `Violation.as_dict()`, `ContractTracker.governance_payload()`, `governance_json()` et `write_governance_json()` fournissent un payload stable (`status`, `should_block`, `violations_count`, `exit_code`, `strict_contracts`, `violations`). Le CLI ajoute `--governance-json <chemin>` pour écrire ce rapport sous le projet. Les chemins absolus hors `--project` sont refusés.
- **Tests ajoutés** : `test_contracts.py` couvre payload dict, JSON parsable et écriture fichier temporaire; `test_modes.py` couvre le garde-fou de chemin relatif accepté / chemin hors projet refusé.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 33/33 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 17/17 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM réelle** : non effectuée dans cette session; changement CLI/contrats offline uniquement, sans nouvel appel LLM.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle effectuée** : oui pour validation offline automatisée; non pour runtime NIM.
- **Commit** : *(ce commit).*

### 2026-07-09 — Phase 2 §A / État de gouvernance après contrats

- **Scope** : `crew/contracts.py`, `crew/crew.py`, `scripts/test_contracts.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Motivation** : Phase 1 détectait les violations de contrat mais les laissait seulement comme logs. Pour ouvrir Phase 2 sans refonte lourde, il fallait rendre l'état final exploitable par un humain et par l'automatisation.
- **Changement appliqué** : `ContractTracker` expose désormais `governance_report()`, `governance_summary()` et `should_block()`. Deux états existent : `OK` et `BLOCKED_CONTRACT_VIOLATIONS`. Le CLI imprime toujours l'état de gouvernance après le résumé des contrats. Nouveau flag `--strict-contracts` : si un contrat est violé, le run retourne exit code 2; par défaut, l'exit code historique reste inchangé pour éviter une régression.
- **Tests ajoutés** : `scripts/test_contracts.py` couvre le cas OK, le cas bloqué, le comptage de violations, le résumé de gouvernance, un verdict `CHANGES_NEEDED` valide et l'ignorance des tasks non enregistrées.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 31/31 OK, `test_resilience.py` 31/31 OK, `test_contracts.py` 12/12 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM réelle** : non effectuée dans cette session. Le changement est couvert offline et ne modifie pas la composition des agents ni les appels LLM.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle effectuée** : oui pour validation offline automatisée; non pour runtime NIM.
- **Commit** : `6ff08cd` (poussé sur `origin/main`).

### 2026-07-09 — Phase 0 dette shell Windows : parsing chemins absolus corrige

- **Scope** : `crew/crew.py`, `scripts/test_phase0.py`, `DOCUMENT_MAITRE_PROJET.md`.
- **Changement** : remplacement du parsing shell `shlex.split(..., posix=True)` par `_split_shell_command()`, qui utilise `CommandLineToArgvW` sur Windows afin de preserver les chemins absolus `C:\...` et les chemins quotes avec espaces, tout en gardant `shlex` POSIX hors Windows.
- **Validation reelle effectuee** : `test_phase0.py` 22/22 OK, `ruff check crew scripts` OK, `git diff --check` OK. Tests ajoutes pour chemin Windows absolu et chemin quote avec espace.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Commit** : *(ce commit)*.
### 2026-07-09 — Docs README post-read simplifie

- **Scope** : `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Changement** : correction de deux restes de documentation apres le passage du mode `read` a 1 task Researcher direct : l'exemple CLI ne parle plus de "2 agents", et l'exemple de validation runtime bornee utilise maintenant le mode `read` valide plutot que `review`.
- **Repo modifie** : oui.
- **Prod alignee** : N/A.
- **Validation reelle effectuee** : `git diff --check` OK; pas de test Python requis (docs uniquement).
- **Commit** : *(ce commit)*.

### 2026-07-09 — Phase 1 §2/§3 runtime borné : délégation désactivée, read simplifié, fallbacks Researcher/Architect corrigés

- **Scope** : `crew/crew.py`, `scripts/test_modes.py`, `scripts/test_resilience.py`, `README.md`, `DOCUMENT_MAITRE_PROJET.md`.
- **Contexte** : après le commit `76ed724`, plusieurs runs `--mode read` bornés avec `NEXUS_LLM_TIMEOUT_SECONDS=30` ont encore dépassé la limite Codex (~244 s). Les logs sont dans `run_bounded_read.log` (gitignored).
- **Diagnostic runtime successif** :
  - Run 1 : la délégation CrewAI était encore active (`delegate_work_to_coworker`) malgré le mode read. Cause : `allow_delegation=True` sur tous les agents.
  - Run 2 : délégation désactivée, mais Qwen timeout + DeepSeek 404 étaient repayés à chaque tour ReAct. Cause : les modèles en erreur n'étaient pas mémorisés comme indisponibles dans `FallbackLLM`.
  - Run 3 : cache des modèles indisponibles OK (`ignore (desactive pour ce run)`), mais Llama 3.3 70B casse en runtime multi-outils avec erreur NIM `single tool-calls only`.
  - Mini-test direct multi-outils : `devstral` et `kimi-k2-instruct` retournent 404 côté NIM actuel; `nvidia/llama-3.3-nemotron-super-49b-v1.5` et `openai/gpt-oss-120b` renvoient un `tool_call` avec plusieurs outils disponibles.
  - Run 4 : chaînes Researcher/Architect corrigées vers `Qwen -> GPT-OSS -> Nemotron`; Researcher produit une carte complète, mais le mode read à 2 tasks timeout au démarrage de l'Architect.
  - Run 5 : mode read réduit à 1 task Researcher et fallbacks ordonnés `Qwen -> GPT-OSS -> Nemotron`; le run produit un rapport final complet dans `run_bounded_read.log`. Qwen timeout au premier appel, puis GPT-OSS prend le relais sans délégation ni boucle Architect.
- **Changements appliqués** :
  - `allow_delegation=False` pour Researcher, Architect, Coder, Critic, Scanner tant que la gouvernance Phase 2 n'existe pas.
  - `FallbackLLM` mémorise les modèles en erreur non-429 dans `_disabled_model_indices` et les ignore aux appels suivants du même agent.
  - Chaînes `researcher` et `architect` : DeepSeek/Llama 70B retirés; fallbacks actuels `GPT-OSS 120B`, puis `Nemotron Super 49B`.
  - Mode `read` : simplifié à 1 task Researcher direct (plus de synthèse Architect) pour réduire le coût runtime.
- **Validation offline** : `test_phase0.py` 22/22 OK, `test_modes.py` 31/31 OK, `test_resilience.py` 31/31 OK, `ruff check crew scripts` OK, `git diff --check` OK.
- **Validation runtime NIM réelle** : oui sur le périmètre `read` borné. Le log final contient un rapport complet et aucun processus Python NEXUS n'est resté actif. Limite résiduelle : Qwen timeout au premier appel dans ce run; le fallback GPT-OSS permet toutefois d'obtenir une sortie exploitable.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle effectuée** : offline oui; runtime NIM oui sur `--mode read`; autres modes non retestés dans ce bloc.
- **Commit** : *(ce commit)*.

### 2026-07-09 — Phase 1 §3bis / Retry budgets séparés + timeout LLM

- **Scope** : `crew/crew.py`, `scripts/test_resilience.py`, corrections lint mécaniques dans les scripts de diagnostic/tests, README et document maître.
- **Cause racine reprise du journal 2026-04-20** : `malformed_retry_used` était un booléen unique partagé entre XML Hermes et intention courte 0-tools. Une cascade `XML Hermes -> intention courte` consommait donc tout le budget au premier symptôme et laissait passer le second.
- **Changement appliqué** : ajout de `_malformed_output_kind()` pour classifier `xml_hermes` vs `intention_0_tools`; `FallbackLLM.call()` garde maintenant un set `malformed_retries_used` et autorise un retry par type sur le même modèle. Le log devient `[sortie malformed <kind> ...]` au lieu de toujours annoncer XML Hermes. Ajout aussi de `LLM_TIMEOUT_SECONDS = 90`, transmis aux `crewai.LLM`, pour borner un appel modèle avant fallback chain. Le timeout est surchargeable par `NEXUS_LLM_TIMEOUT_SECONDS`, ce qui permet des runs de validation courts compatibles avec la limite d'exécution Codex.
- **Tests ajoutés** : scénario fake LLM offline `XML Hermes -> intention courte -> réponse valide`, qui vérifie 3 appels et deux retries distincts; contrôle que les LLM internes reçoivent bien `timeout=LLM_TIMEOUT_SECONDS`; contrôle aussi l'override env valide (`30`) et le fallback sur valeur invalide.
- **Validation offline** :
  - `uv run --with-requirements requirements.txt python scripts\test_phase0.py` : 20/20 OK.
  - `uv run --with-requirements requirements.txt python scripts\test_modes.py` : 31/31 OK.
  - `uv run --with-requirements requirements.txt python scripts\test_resilience.py` : 31/31 OK.
  - `python -c "ast.parse(...)"` sur `crew/crew.py` et `scripts/test_resilience.py` : OK.
  - `git diff --check` : OK.
  - `uv run --with ruff ruff check crew scripts` : OK.
- **Validation runtime NIM réelle** : tentée dans cette session avec `NEXUS_DEBUG_LLM=1 uv run --with-requirements requirements.txt python crew\crew.py "Relis crew/crew.py et identifie les risques ou points faibles" --project . --mode review`. Résultat : timeout après ~244 s sans sortie exploitable; deux processus Python NEXUS restés actifs ont été identifiés puis arrêtés (`Stop-Process -Id 2156,16268 -Force`). La cascade réelle reste donc non confirmée.
- **Repo modifié** : oui (`crew/crew.py`, `scripts/test_resilience.py`, `scripts/test_connection.py`, `scripts/test_crewai_schema.py`, `scripts/test_modes.py`, `scripts/test_phase0.py`, `scripts/test_rate_headers.py`, `scripts/test_tool_use.py`, `DOCUMENT_MAITRE_PROJET.md`, `README.md`).
- **Prod alignée** : N/A.
- **Validation réelle effectuée** : oui pour validation offline automatisée; non pour runtime NIM réel.
- **Commit** : *(ce commit)*

### 2026-04-20 — Observation runtime mode REVIEW + **dette §3bis : retry budget épuisable**

- **Scope** : run NEXUS réel `--mode review`, prompt `"Relis crew/crew.py et identifie les risques ou points faibles"`, `NEXUS_DEBUG_LLM=1`. Log : `run_mode_review.log` (gitignored).
- **Résultat** : exit 0, rapport final structuré par l'Architect (sécurité / robustesse / architecture / tests / documentation + résumé exécutif + priorités). Pipeline mode=review validé bout-en-bout.
- **Métriques** : 7 LLM calls (3 Qwen 3.5 397B + 4 Kimi K2 Thinking), 1 retry XML Hermes déclenché, 0 × 429, 0 fallback actif, **1 violation contrat runtime** (`research` / `required_tools` : aucun outil appelé).
- **DÉCOUVERTE IMPORTANTE — §3bis n'a pas déclenché alors qu'il aurait dû**. Séquence observée :
  1. 1er appel Researcher → sortie XML Hermes cassée → `_output_looks_malformed` retourne True.
  2. Retry-1 déclenché, `malformed_retry_used = True`.
  3. 2e appel Researcher → sortie d'intention narrative plate : *« Je vais analyser le projet situé dans... Commençons par explorer... »* (~270 chars, contient les marqueurs `"je vais"` ET `"commençons"`, aurait été détectée par §3bis).
  4. MAIS `malformed_retry_used` est déjà True → la sortie est retournée telle quelle → violation contrat aval.
- **Cause racine** : le retry budget actuel (`crew/crew.py:300`) est de **1 retry par appel agent**, partagé entre les deux modes de défaillance (XML Hermes et intention 0-tools). Quand les deux se succèdent sur la même requête, le second est brûlé.
- **Pourquoi le run a tout de même abouti** : le Critic Kimi K2 a compensé en lisant `crew/crew.py` directement via ses propres outils (4 calls), et l'Architect a synthétisé à partir du Critic plutôt que du Researcher. Le pipeline mode=review s'est auto-rattrapé, mais la carte Researcher était vide.
- **Dettes runtime mises à jour** :
  - **§3b (retry XML Hermes) : re-confirmée** (1 déclenchement, mais cette fois sans bénéfice net car la suite a re-cassé).
  - **§3bis (variance 0-tools) : dette reformulée** — le filtre logique est correct, MAIS le retry budget est épuisable. Logique non défectueuse, stratégie de retry insuffisante.
  - **Mode=review : clôturée runtime côté composition** (routing correct, Critic/Architect corrects, rapport final exploitable). Mais le scénario où la carte Researcher est vide révèle une dépendance insuffisante explicite entre tasks — à creuser Phase 2.
- **Pistes pour session future (NON traitées ici)** :
  1. Étendre le retry à **deux budgets distincts** : `xml_hermes_retry_used` et `intention_retry_used`, indépendants. Permet de rattraper une cascade `XML Hermes → intention`.
  2. OU passer au **fallback chain** dès qu'un 2e mode de défaillance est détecté (pragmatique : change de modèle plutôt que de ré-insister).
  3. Durcir le contrat `research` pour forcer au moins un outil avant acceptance (échec fort au lieu de violation logguée).
  4. Désambiguïser le `print()` de retry-1 : actuellement `[sortie XML Hermes ... : retry-1]` alors que le filtre couvre aussi la variance 0-tools. Libellé trompeur quand ce deuxième chemin se déclenche.
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée). Aucun changement de code.
- **Repo modifié** : oui (journal uniquement).
- **Prod alignée** : N/A.
- **Validation réelle** : oui, runtime NEXUS exit 0. Mode=review fonctionnel malgré Researcher défaillant. Nouvelle dette identifiée (retry budget).
- **Commit** : *(ce commit)*.

### 2026-04-20 — Observation runtime mode READ + validation §3b retry XML Hermes

- **Scope** : run NEXUS réel avec `--mode read`, `NEXUS_DEBUG_LLM=1`, prompt témoin identique à `ea8fa3a` pour permettre comparaison directe.
- **Commande** : `python crew/crew.py "Explique en 3 lignes ce que fait ce projet (lis README.md)" --project . --mode read`
- **Log** : `run_mode_read.log` (gitignored).
- **Résultat** : exit 0, rapport final structuré produit par l'Architect (explication + modes + roadmap + vision), marqueur explicite `Aucune modification apportée au projet (mode READ).`
- **Métriques comparées** :

| Métrique | Run témoin `ea8fa3a` (mode edit) | Run mode=read |
|---|---|---|
| Tasks exécutées | 6 | **2** |
| Appels LLM tracés | 15 | **9** |
| Violations contrat runtime | 1 (Critic) | **0** |
| Déclenchements 429 | 0 | 0 |
| Retries XML Hermes | 0 | **2** |
| Fallbacks actifs | 0 | 0 |

- **Dette runtime §3b (retry XML Hermes) : ✅ CLÔTURÉE**. Première observation runtime du retry-1 en conditions réelles, deux fois sur `qwen3.5-397b-a17b` (Researcher primaire). Les deux retries ont abouti (`[LLM] qwen3.5-397b-a17b OK apres rl_retries=0 malformed_retry=True`), confirmant que le mécanisme fonctionne bout-en-bout. La variance XML Hermes n'est pas systématique mais le retry-1 la rattrape.
- **Dette runtime mode=read : ✅ CLÔTURÉE**. Composition correcte (Researcher + Architect uniquement, pas de Coder/Critic), rapport final structuré adapté à un humain non-développeur, aucune violation de contrat, `--write` proprement ignoré (bannière affichait `write_file : OFF`).
- **Dettes runtime encore ouvertes** :
  - §3a (backoff 429) : 0 déclenchement, conditions non reproductibles à la demande.
  - §3bis (variance 0-tools intention courte) : 0 déclenchement, idem — le Researcher n'a pas produit d'intention courte ce run, le filtre étendu n'a pas eu à agir.
  - Mode=`review`, mode=`debug`, mode=`read + --deep` : jamais exercés en runtime.
- **Gain produit mesuré** : **-40% d'appels LLM** (9 vs 15) pour un prompt de type « comprendre le projet ». Le rapport final est aussi plus court et ciblé (pas de sections parasites « Ce qui a été reviewé / Corrections appliquées » qui n'ont pas de sens en lecture seule). Économie concrète NIM tokens + pertinence du livrable.
- **Observation bonus** : le Researcher a lu spontanément `DOCUMENT_MAITRE_PROJET.md` et `crew/contracts.py` en plus du `README.md` demandé, et le rapport final reflète la vraie structure du projet (y compris la section modes qu'on vient de créer). Le workflow multi-fichiers fonctionne bien sur ce type de prompt.
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée). Aucun changement de code.
- **Repo modifié** : oui (journal uniquement).
- **Prod alignée** : N/A.
- **Validation réelle** : oui, runtime NEXUS exit 0 + métriques capturées + log archivé localement (gitignored).
- **Commit** : *(ce commit)*.

### 2026-04-20 — Phase 1 §2 slice A : modes d'usage v1 (CLI `--mode`)

- **Scope** : `crew/crew.py` — refonte de `build_crew()` pour router les tasks selon un nouveau paramètre `mode ∈ {read, edit, review, debug}` (cible produit §9 du maître). Ajout des constantes exposées `VALID_MODES`, `DEFAULT_MODE="edit"`. Nouveau flag CLI `--mode` / `-m`. Bannière et help mis à jour. Nouveau `scripts/test_modes.py` : 26 tests unitaires offline.
- **Motivation** : dette §14 du maître (« crew séquentiel qui lance presque toujours toute la chaîne »). Concrètement, une tâche type « explique ce projet » déclenchait Coder + Critic + rework inutilement — coûts NIM, risque d'erreur, bruit dans le rapport final. §9 définit 4 modes distincts, §15 les liste comme Phase 1 §2.
- **Design retenu (choix d'implémentation)** :
  - **CLI flag explicite** plutôt que classifier automatique. Raison : un classifier nécessite soit une heuristique textuelle fragile, soit un appel LLM supplémentaire dédié — ajouter de la complexité avant d'avoir observé les modes en usage réel n'est pas productif. Slice B différée.
  - **Default `edit`** → comportement actuel préservé, zéro régression pour les utilisateurs existants.
  - **`debug` alias de `edit`** côté composition : §9 les décrit avec les mêmes agents. La différenciation produit (orientation diagnostic vs. implementation) sera prompt-level, reportée Phase 2.
  - **Tasks distinctes par mode** (pas de réutilisation avec description conditionnelle) : `review_standalone_task` et `final_task` dédiés pour `read` / `review`. Raison : les descriptions actuelles font des références implicites au Coder/Architect qui n'existent pas dans ces modes. Plus propre de dupliquer les ~10 lignes de description que de tout conditionner.
  - **Garde-fou `--write` en mode read/review** : ignoré silencieusement avec message d'avertissement. Évite qu'un utilisateur pense qu'il active quelque chose qui n'a pas de sens.
- **Compositions** :
  - `read` : 2 tasks (Researcher → Architect synthèse), 2 agents.
  - `review` : 3 tasks (Researcher → Critic standalone → Architect synthèse), 3 agents.
  - `edit` : 6 tasks (Researcher → Architect plan → Coder → Critic → Coder rework → Architect synthèse), 4 agents. **Pipeline actuel inchangé.**
  - `debug` : identique à `edit`.
  - `--deep` prepend `scan_task` quel que soit le mode.
- **Contrats (§1)** : `ContractTracker.register()` n'enregistre que les tasks effectivement présentes dans le pipeline, pour chaque mode. Un contrat `review` pointe sur `review_task` en mode `edit` et sur `review_standalone_task` en mode `review` — les deux sont validés par le même contrat kind=`review` dans `contracts.py` (même contrainte : pattern APPROVED|CHANGES_NEEDED).
- **Validation offline** :
  - `scripts/test_modes.py` : 26/26 OK. Couvre composition par mode, agents présents/absents, contrats enregistrés, `--deep` × tous les modes, mode invalide lève `ValueError`, défaut sans `mode=` = `edit`.
  - `scripts/test_phase0.py` : 20/20 OK (aucune régression sur les agents unitaires).
  - `scripts/test_resilience.py` : 24/24 OK (aucune régression sur `_output_looks_malformed` / backoff).
  - CLI `--help` inspecté visuellement : modes rendus correctement.
- **Validation runtime NIM réelle** : **non effectuée dans cette session**. Raison : le gain produit attendu (économie d'appels LLM en mode `read`/`review`, rapports plus courts et ciblés) n'a pas d'impact sur la stabilité du code — tout le chemin des tasks individuelles (Researcher + Architect + Critic) est déjà exercé dans le mode `edit` actuel. Un run réel mode=`read` reste à faire sur une session instrumentée, idéalement comparé au même prompt en mode `edit` pour quantifier le gain.
- **Risque résiduel** :
  - Default reste `edit` donc un utilisateur qui passait « explique ce projet » sans `--mode` ne verra aucune différence — il faut qu'il découvre et utilise `--mode read`. La slice B (classifier auto) règlerait ça.
  - `debug` = `edit` en pratique — pas de différenciation visible pour l'utilisateur si ce n'est le libellé dans la bannière. Acceptable tant que la Phase 2 n'a pas affiné les prompts.
- **Fichiers touchés** : `crew/crew.py`, `scripts/test_modes.py` (nouveau), `DOCUMENT_MAITRE_PROJET.md` (§15 + §18 + cette entrée §19).
- **Repo modifié** : oui.
- **Prod alignée** : N/A (local).
- **Validation réelle** : 70/70 tests unitaires offline cumulés (26+20+24) + CLI help vérifié. Runtime NEXUS non exercé.
- **Commit** : *(ce commit)*.

### 2026-04-20 — Phase 1 §3bis : couverture variance NIM « 0 tools au tour 1 »

- **Scope** : `crew/crew.py` — extension de `_output_looks_malformed()`. Ajout de deux constantes exposées au niveau module (`MALFORMED_SHORT_TEXT_MAX = 300`, `_INTENTION_PATTERNS`). `scripts/test_resilience.py` nouveau : 24 tests unitaires offline.
- **Motivation** : dette identifiée le 2026-04-19 (entrée « Tentative Critic v2 … rollback »). Le Researcher répondait parfois en texte nu court (~132 chars) sans émettre de `tool_call` alors que des outils étaient fournis. Ce mode de défaillance échappait à `_output_looks_malformed` qui ne détectait que le XML Hermes (`<tool_call>` / `<function=`).
- **Choix parmi les 3 pistes du journal précédent** : **Piste 1** (heuristique dans le filtre). Raisons :
  - réutilise l'infra retry-1 déjà câblée (`crew.py:297`), pas de nouveau chemin ;
  - ne modifie pas les prompts CrewAI (évite le biais over-tooling de la piste 2) ;
  - ne brûle pas de fallbacks inutilement (contrairement à la piste 3) ;
  - easy rollback si faux positifs (révertir la fonction seule).
- **Heuristique retenue** : sortie flaggée si `had_tools=True` ET `len(out) < 300` ET présence d'un marqueur d'intention dans `_INTENTION_PATTERNS` (`je vais`, `let me`, `i need to`, `i'll`, `d'abord`, `thought:`, etc.). La **condition cumulative** est importante — une réponse finale courte sans marqueur d'intention (ex. `VERDICT: APPROVED`, code snippet, valeur brute) n'est pas flaggée.
- **Validation tests unitaires (`scripts/test_resilience.py`)** : 24/24 OK. Couvre :
  - détection XML Hermes (non-régression §3) ;
  - détection intention courte FR/EN + marqueur ReAct `Thought:` ;
  - non-régression : `VERDICT: APPROVED`/`CHANGES_NEEDED` courts NON flaggés, code snippet NON flaggé, intention longue NON flaggée, `had_tools=False` filtre inerte, `out` non-str filtre inerte.
- **Validation Phase 0 (`scripts/test_phase0.py`)** : 20/20 OK, aucune régression.
- **Validation runtime NIM réelle** : **non effectuée** dans cette session. La condition qui déclenche la variance 0-tools n'est pas reproductible à la demande (la session précédente a observé le mode 2 fois sur 3 runs, puis 0 fois sur le re-run suivant). Le retry-1 additionnel sera observé opportunément lors d'une session où le mode se présente, comme pour §3a/§3b. Dette runtime toujours ouverte mais couverture logique élargie.
- **Risque résiduel** : faux positif possible si un agent produit une réponse finale courte (< 300 chars) qui contient par hasard un marqueur (« Let me summarize »). Surveillance : si `[sortie XML Hermes X : retry-1]` apparaît sur des réponses finales légitimes, resserrer `MALFORMED_SHORT_TEXT_MAX` (ex. 200) ou durcir la liste de marqueurs. Message de log inchangé — le libellé « XML Hermes » est imprécis mais le chemin code est le même ; renommage déféré pour éviter de casser les grep runtime existants.
- **Fichiers touchés** : `crew/crew.py`, `scripts/test_resilience.py`, `DOCUMENT_MAITRE_PROJET.md` (cette entrée).
- **Repo modifié** : oui.
- **Prod alignée** : N/A (local).
- **Validation réelle** : partielle — 24/24 unit tests + 20/20 Phase 0, **pas de run NEXUS instrumenté** dans cette session (cf. dette runtime ouverte).
- **Commit** : *(ce commit)*.

### 2026-04-19 — Tentative Critic v2 (contrat 3 sections + VERDICT:) rollback / variance NIM 0-tools non couverte

- **Scope** : `crew/crew.py` — modifications de `make_critic()` backstory + `review_task` description/expected_output pour imposer un format de sortie strict à 3 sections (`Fichiers relus:` / `Findings:` / `VERDICT: APPROVED|CHANGES_NEEDED`) et forcer l'appel de `read_file`.
- **Motivation** : l'entrée « Observation runtime Phase 1 §3 » ci-dessous signalait 1 violation de contrat Critic (pattern `APPROVED|CHANGES_NEEDED` manquant). La v2 du prompt visait à corriger ça proprement côté instructions.
- **Protocole de test** : après dépop du stash portant la v2, re-run NEXUS avec la même tâche qu'avant (`Explique en 3 lignes ce que fait ce projet (lis README.md)`, `NEXUS_DEBUG_LLM=1`), comparaison directe avec le run du commit `ea8fa3a`.
- **Résultat observé (`run_critic_v2_debug.log`, gitignored)** :
  | Métrique | Run HEAD (ea8fa3a) | Run v2 |
  |---|---|---|
  | Appels LLM tracés | 15 | **7** |
  | Contrats violés | 1 (Critic) | **6** |
  | Tool calls Researcher | 1 (`read_file` OK) | **0** |
  | Taille output Researcher | ~1.5 KB structurée | **132 caractères** |
  | Déclenchements 429 | 0 | 0 |
  | Retries XML Hermes | 0 | **0** (aucun XML détecté) |
- **Diagnostic** : l'échec n'est **pas causé par le changement Critic** (qui vient en aval). Le Researcher a produit une intention courte en **texte nu sans aucun appel d'outil, au tour 1**. Ce mode de défaillance est distinct des deux couverts par §3 :
  - §3a (backoff 429) : rate limit n'a pas été atteint.
  - §3b (retry XML Hermes) : `_output_looks_malformed` ne détecte que `<tool_call>` et `<function=` — une sortie texte plate sans balise échappe au filtre.
  - **Nouveau mode de défaillance identifié** : variance NIM « 0 tools au tour 1 alors que des outils sont disponibles » (l'agent répond en texte narratif au lieu d'émettre un `tool_call`). Ce mode avait déjà été observé 2 fois en runs précédents (journal session 2026-04-19 runs 2 & 3) mais n'avait pas été isolé formellement.
- **Décision** : **rollback de la v2 Critic** (revert de `crew/crew.py` à HEAD). Raisons :
  1. La cause racine (variance 0-tools upstream) n'est pas dans le scope de la v2 et il n'est pas productif d'insister sur un prompt aval tant que l'amont casse ponctuellement.
  2. Le run de test ne prouve ni n'infirme la qualité de la v2 — il a été bloqué en amont. Aucune donnée exploitable sur la v2 elle-même.
  3. Mieux vaut consolider la session avec 3 commits solides (§1, §3, fix contracts) et documenter honnêtement la dette plutôt que commiter une v2 non validée.
- **Dette assumée** : le pattern `APPROVED|CHANGES_NEEDED` du contrat Critic reste violé occasionnellement en runs (1 violation sur le run HEAD de référence). Acceptée jusqu'à traitement de la variance 0-tools upstream.
- **Dette nouvelle identifiée** : variance NIM « 0 tools au tour 1 » non couverte par §3. Pistes pour session future :
  - Extension de `_output_looks_malformed` avec heuristique « `had_tools` AND réponse < N chars AND contenu ressemble à une intention plutôt qu'à une réponse finale → retry-1 ».
  - OU message système additionnel forçant explicitement l'appel d'outil au premier tour (risque : biais vers over-tooling).
  - OU accepter et re-router via fallback chain dès qu'on détecte « output court sans tool_call alors que des tools sont disponibles ».
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée). `crew/crew.py` reverté à HEAD, le diff v2 est perdu (pas re-stashé — il est reconstructible depuis ce journal au besoin).
- **Repo modifié** : oui (journal uniquement).
- **Prod alignée** : N/A.
- **Validation réelle** : N/A (pas de changement de code).
- **Commit** : *(ce commit)*.

### 2026-04-19 — Observation runtime Phase 1 §3 / Logs NEXUS_DEBUG_LLM sur run réel

- **Scope** : run NEXUS complet avec `NEXUS_DEBUG_LLM=1` pour valider en conditions réelles la résilience NIM du commit `ea8fa3a`.
- **Commande** : `NEXUS_DEBUG_LLM=1 python crew/crew.py "Explique en 3 lignes ce que fait ce projet (lis README.md)" --project .`
- **Résultat** : exit 0, run complet, synthèse finale structurée en 5 sections.
- **Mesures collectées dans `run_phase1_3_debug.log`** (gitignored) :
  | Métrique | Valeur |
  |---|---|
  | Appels LLM tracés | 15 |
  | Déclenchements 429 (`[429 ... : backoff]`) | 0 |
  | Retries XML Hermes (`[sortie XML Hermes ... : retry-1]`) | 0 |
  | Fallbacks actifs | 0 |
  | Contrats violés | 1 (Critic, sans APPROVED/CHANGES_NEEDED — prompt v1 de HEAD, v2 toujours stashé) |
- **Validation runtime partielle** :
  - ✅ **3c (logs debug)** : confirmé en conditions réelles. Format `model / rl_try / msgs / bytes / tools / roles` lisible et exploitable.
  - ⏳ **3a (backoff 429)** et **3b (retry XML Hermes)** : câblés mais **non déclenchés** — le run était suffisamment court et le rate limit n'a pas été atteint, Kimi K2 n'a pas variance-dérapé cette fois. Les conditions de reproduction ne sont pas fiables à la demande. Validation runtime complète reportée à une session où une de ces conditions se produit naturellement.
- **Donnée quantitative importante pour l'hypothèse "tours successifs CrewAI"** (journal 2026-04-19 précédent) :
  - **Researcher (Qwen 3.5 397B)** : 6 tours ReAct, `msgs` passe de 2 → 5 → 8 → 11 → 14, **`bytes` 1134 → 50655 (×44)** en 5 tours.
  - **Coder (Qwen 3 Coder 480B)** : 3 tours, msgs 2 → 10, bytes 4092 → 19621 (×4.8).
  - **Critic (Kimi K2 Thinking)** : 4 tours, msgs 2 → 13, bytes 4734 → 13458 (×2.8). La variable `tools` passe de 5 à 3 au dernier tour (probable délégation CrewAI qui retire certains outils).
  - **Interprétation** : l'hypothèse est **confirmée quantitativement**. Le payload CrewAI explose tour après tour. Un modèle qui tient bien au tour 1 peut dégrader au tour 5 simplement parce que la message history est devenue énorme. Les « intentions vides » des runs NEXUS 2 & 3 de la session précédente correspondaient probablement à ce gonflement + éventuel rate limit. Piste pour Phase 2 : agressivement résumer / tronquer la message history entre tours ReAct.
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée). Le log `run_phase1_3_debug.log` reste sur disque, gitignored.
- **Repo modifié** : oui (journal uniquement).
- **Prod alignée** : N/A.
- **Validation réelle** : partielle (3c oui, 3a+3b câblés mais non déclenchés).
- **Commit** : *(ce commit)*.

### 2026-04-19 — Fix dette : résolution import `contracts` dans `scripts/test_phase0.py`

- **Scope** : `scripts/test_phase0.py` — import preload de `contracts` via `importlib`.
- **Contexte** : dette préexistante depuis Phase 1 §1 (commit `afe9eb36`, ajout de `crew/contracts.py`), signalée dans l'entrée Phase 1 §3. Le test Phase 0 ne tournait plus depuis, mais personne ne l'avait rejoué.
- **Cause** : `crew/crew.py` fait `from contracts import ContractTracker` en import implicitement relatif (pas de `__init__.py` dans `crew/`). Quand `test_phase0.py` fait `from crew import crew` depuis la racine, Python ne trouve pas `contracts` car `sys.path` ne contient que `ROOT`.
- **Fix** : preload de `contracts` dans `sys.modules` via `importlib.util` avant d'importer `crew.crew`, **sans** toucher `sys.path` (sinon `crew/crew.py` serait résolu comme module top-level `crew` et masquerait le namespace package `crew/`). Tentative intermédiaire (ajout `crew/` à `sys.path`) rejetée pour cette raison.
- **Fichiers touchés** : `scripts/test_phase0.py`, `DOCUMENT_MAITRE_PROJET.md`.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : OUI — `python scripts/test_phase0.py` → **20/20**.
- **Commit** : *(ce commit)*.

### 2026-04-19 — Phase 1 §3 / Résilience NIM : backoff 429 + retry XML Hermes + logs debug

- **Scope** : `crew/crew.py` — `FallbackLLM.call()` + 2 helpers + 1 constante.
- **Demande** : étape 3 prévue au plan de fin de session §C (entrée précédente) pour traiter les 3 causes documentées d'« intentions vides » en run NEXUS.
- **Diagnostic rappelé (journal 2026-04-19 bloc précédent)** :
  - Coder 480B subit des 429 en rafales serrées (free tier ~40 req/min, pas de header `retry-after` côté NIM).
  - Kimi K2 Thinking a ~10 % de réponses texte sans `tool_calls` quand des tools sont fournis (variance intrinsèque, pas du rate limit).
  - Qwen 3.5 397B est déterministe.
- **Changements** :
  - Nouvelle constante `RATE_LIMIT_BACKOFFS = [1.0, 2.0, 4.0]` : 3 tentatives supplémentaires avec attentes 1s/2s/4s avant de basculer au modèle suivant de la chaîne.
  - Nouveau helper `_is_rate_limit_error(err)` : détecte les 429 par nom de classe (`*RateLimit*`) ou par message (`429`, `rate limit`, `too many requests`).
  - Nouveau helper `_output_looks_malformed(out, had_tools)` : détecte XML Hermes (`<tool_call>` ou `<function=`) uniquement si des tools ont été fournis.
  - Réécriture de la boucle `FallbackLLM.call()` :
    - **3a** — sur exception détectée comme 429, attendre et retry sur le *même* modèle (3 retries max). Les erreurs non-429 (timeout, autre) basculent direct sur le fallback comme avant.
    - **3b** — si la sortie contient du XML Hermes et que des tools étaient fournis, retry-1 sur le même modèle. Si le 2e output est encore malformed, il est retourné tel quel (retry-1 consommé, pas de fallback automatique) — **choix documenté** : la littéralité "retry-1" du plan. Le fallback vers un autre modèle en cas de malformed persistant est une amélioration possible, non retenue ici pour ne pas gonfler le scope.
    - **3c** — logs opt-in via `NEXUS_DEBUG_LLM=1` : à chaque appel réel (y compris retries) dump `model / rl_try / msgs / bytes / tools / roles`. But déclaré : instrumenter l'hypothèse "tours successifs CrewAI" pour une session ultérieure.
- **Fichiers modifiés** : `crew/crew.py`, `DOCUMENT_MAITRE_PROJET.md` (cette entrée).
- **Stash géré en amont** : `git stash push crew/crew.py -m "WIP v2 Critic prompt (non valide runtime)"` avant implémentation, pour isoler le diff v2 Critic (prompt review non validé runtime, entrée précédente). Le stash est resté en place après le commit pour la prochaine itération Critic. **À retravailler dans une session dédiée**, pas pendant l'étape 3.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** :
  - **OUI pour la logique** — 6 mock tests sur `FallbackLLM.call()` avec un `FakeLLM` (séquences programmées) + patch `RATE_LIMIT_BACKOFFS` à 0.01s pour tests rapides. Cas couverts :
    1. 429 transient → backoff + retry même modèle → 2 appels, succès au 2e.
    2. 429 persistant (4 échecs) → épuise les 3 retries puis fallback → A=4 tries, B=1.
    3. XML Hermes avec tools → retry-1 même modèle → succès au 2e.
    4. Malformed 2x → retry-1 consommé, 2e output retourné tel quel (pas de fallback).
    5. XML dans output **sans** tools fournis → pas de retry (correct : les tools n'étaient pas attendus).
    6. Timeout (non-429) → fallback direct, pas de backoff (correct : non-429 = sortie immédiate de la boucle).
  - **OUI pour les helpers** — 13 unit tests sur `_is_rate_limit_error` (6 cas) et `_output_looks_malformed` (6 cas) + vérification de la constante.
  - **OUI pour la syntaxe** — `python -m py_compile crew/crew.py` passe.
  - **NON encore pour le runtime NIM réel** — il faut un run NEXUS pour observer le backoff se déclencher sur de vrais 429 Coder 480B et le retry-1 sur de vrais malformed Kimi K2. Ça consomme du quota NIM et dépend de la variance. À lancer avec `NEXUS_DEBUG_LLM=1` dans une session dédiée (objet : vérifier que les logs tracent correctement la cause d'une éventuelle intention vide résiduelle).
- **Dette découverte hors scope** : `scripts/test_phase0.py` échoue à l'import de `crew.crew` depuis la racine (`from contracts import ContractTracker` à la ligne 68 de `crew/crew.py` n'est pas résolvable depuis `sys.path = ROOT`). Ce bug est silencieusement présent depuis le commit `afe9eb36` (Phase 1 §1, ajout de `contracts.py`) et n'avait pas été rejoué depuis. Non corrigé dans ce commit — à traiter dans un commit dédié (`test(phase0): fix resolution import contracts`).
- **Prochaine étape prévue** :
  1. Run NEXUS instrumenté (`NEXUS_DEBUG_LLM=1`) sur une tâche de taille modérée pour collecter des logs réels et valider que la résilience se déclenche.
  2. Fix import `test_phase0.py` (commit séparé).
  3. Itération Critic : pop du stash, retravailler le prompt v2 Critic (qui n'avait pas été validable en session précédente à cause des intentions vides upstream — maintenant qu'on a backoff+retry, une nouvelle tentative est possible).
- **Commit** : *(ce commit)*.

### 2026-04-19 — Phase 1 §2 / Tentative de fix Critic + découverte intermittence tool use NIM (NON COMMITÉ, EN COURS)

> ⚠️ Entrée documentant du travail **en cours, non commité**. À consolider ou éclater au moment du commit.

- **Contexte** : le journal du 2026-04-10 (§1) notait que le Critic avait violé son contrat (pas de `read_file`, pas de `APPROVED`/`CHANGES_NEEDED`). Session d'aujourd'hui ouverte sur option A (protocole §8 après arbitrage utilisateur) pour corriger ça avant d'attaquer les modes d'usage (§9 MASTER).
- **Modifications code (crew/crew.py)** :
  - `review_task` description : resserrée avec obligations explicites (appeler `read_file`, finir par `VERDICT: APPROVED`/`CHANGES_NEEDED`) + format 3 sections imposé (`Fichiers relus:` / `Findings:` / `VERDICT:`).
  - `make_critic()` backstory : renforcée (appelle TOUJOURS `read_file`, termine TOUJOURS par `VERDICT:`).
- **Validation réelle — 3 runs consécutifs avec la même commande** :
  `python crew/crew.py "Explique en 3 lignes ce que fait ce projet (lis README.md)" --project .` (sans `--write`, sans `--allow-shell`).

  | Run | Prompt Critic | Researcher / Architect / Coder | Critic | Total violations |
  |---|---|---|---|---|
  | 1 | v1 (verdict simple) | 3/3 OK, 12 tool calls | `VERDICT: APPROVED` (18 chars) | **1** (length) |
  | 2 | v2 (3 sections) | 0/3 → "intentions vides" | jamais joué utilement | 6 |
  | 3 | v2 (inchangé) | 0/3 → "intentions vides" | jamais joué utilement | 5 |

- **Découverte importante — la dette tool use NIM n'est pas réellement résolue** :
  - Le journal §0.d (2026-04-10) annonçait "6/6 agents fonctionnels, PRIORITÉ 0 CLÔTURÉE".
  - Run 1 de cette session a reproduit ce succès (tool calls propres, Critic lit README.md).
  - Runs 2 & 3 (strictement le même code, cache vidé à chaque démarrage) ont tous les agents qui produisent des "Je vais explorer...", **zéro tool call**, outputs courts.
  - **Conclusion** : le fix `_strip_strict_tools()` ne résout pas le problème de façon déterministe. Il est **intermittent**. La clôture de §0.d sur un seul run n'était pas suffisante pour valider le fix.
- **Cause probable (hypothèses à valider)** :
  - Rate limiting / throttling NVIDIA NIM free tier sur rafales d'appels consécutifs.
  - Variance intrinsèque des modèles Qwen/Kimi (non-déterminisme, pas forcément lié au schema tool use).
  - Effet combiné : à chaud, les modèles répondent correctement ; après N appels rapprochés, ils dégradent.
- **Sur le fix Critic lui-même** :
  - Prompt v1 : validé en run 1 (2 violations → 1 : `required_tools` ✅ et `required_patterns` ✅ passent, seule `min_output_length` échoue — le Critic compresse à "VERDICT: APPROVED" = 18 chars).
  - Prompt v2 (3 sections) : non validable dans cette session car upstream cassé.
- **Question utilisateur ouverte** : le dossier racine du projet a été déplacé (`Desktop/AGENTIQUE` → `C:/PROJETS/AGENTIQUE`). À investiguer si ça influence le comportement NIM. Points vérifiés :
  - `.env` présent au nouveau chemin, `NVIDIA_API_KEY` chargée.
  - `.crew_cache/cache.db` présent.
  - Aucun path absolu en dur dans `crew/crew.py` ni dans `scripts/*.py` (chemins relatifs via `Path(__file__).parent.parent`).
  - Conclusion provisoire : déplacement peu probable d'être la cause directe, mais à confirmer par un `test_connection.py` et éventuellement un redémarrage session fraîche.
- **Fichiers modifiés** (non commité) : `crew/crew.py` (review_task description + Critic backstory).
- **Fichiers créés** : `run_phase1_critic_fix.log` (écrasé à chaque run, contient le dernier).
- **Repo modifié** : OUI.
- **Prod alignée** : N/A.
- **Validation réelle** : PARTIELLE. Run 1 prouve que le Critic respecte `required_tools` + `required_patterns` avec le prompt v1. Prompt v2 non validé.
- **Prochaine étape à arbitrer** (options présentées à l'utilisateur) :
  - **A.** Revenir au prompt v1 (validé), commit incrémental (2 violations → 1), accepter la violation `min_output_length` comme dette.
  - **B.** Garder le prompt v2 (non validé), commit avec mention explicite "non validé runtime".
  - **C.** Suspendre le chantier Critic, basculer sur l'investigation de l'intermittence tool use NIM (plus grave : remet en cause la clôture §0.d).
- **Arbitrage utilisateur** : **C** retenu.
- **Investigation §C — étape 1 (batch test NIM isolé)** :
  - Nouveau script : `scripts/test_tool_use_batch.py`. Fire N appels séquentiels identiques à un modèle NIM avec le schéma CrewAI réel déjà normalisé par `_strip_strict_tools`. Classifie chaque réponse NATIVE/TEXT/MALFORMED/ERROR.
  - Run 1 : `--role researcher --n 10 --sleep 0.5` → Qwen 3.5 397B → **10/10 NATIVE** en 195s. Aucune variance, aucun échec, aucune réponse texte, aucun XML cassé.
  - **Conclusion étape 1** : Le fix `_strip_strict_tools` est **déterministe côté NIM** pour Qwen 3.5 397B. La cause des "intentions vides" observées en runs NEXUS 2 & 3 **n'est pas** la variance modèle NIM sur appels directs.
  - **Hypothèse reformulée** : le bug intermittent est dans la **couche CrewAI / orchestration** — probablement l'un de :
    - tours successifs (message history qui s'allonge et casse le format natif),
    - délégation inter-agents (system messages additionnels injectés),
    - context cross-task CrewAI (les `context=[...]` injectent-ils du contenu qui casse les appels ?),
    - cache LiteLLM (réponses servies depuis cache dégradent ? peu probable, cache vidé au démarrage).
- **Étape 2 prévue** : instrumenter `FallbackLLM.call()` pour logger, à chaque appel réel, la taille du payload, le nombre de messages, leur rôle, et si `tool_calls` natif ou non dans la réponse. Puis re-run NEXUS et analyser où ça casse.
- **Environnement vérifié** : `scripts/test_connection.py` → 18/18 OK (API + 5 modèles + embedder + fichiers + deps). Déplacement du dossier racine `Desktop → C:/PROJETS` éliminé comme cause.
- **Fichiers créés pendant l'investigation** : `scripts/test_tool_use_batch.py`, `run_batch_researcher.log`.
- **Batch complémentaires** (mêmes hypothèses, autres rôles) :
  - `--role coder --n 10` : Qwen 3 Coder 480B — 8/10 NATIVE, **2 ERROR 429** autour du 8e appel → rate limit NIM free tier atteint.
  - `--role critic --n 10` : Kimi K2 Thinking — 9/10 NATIVE, **1 TEXT** (réponse nue sans `tool_calls`) → variance intrinsèque du modèle, pas du rate limit.
- **Investigation §C — étape 2 (rate limit NIM)** :
  - `scripts/test_rate_headers.py` : 1 appel direct `httpx.post` sur `/chat/completions`, dump de tous les headers de réponse.
  - Résultat : NIM **n'expose AUCUN header de rate limit** (pas de `x-ratelimit-*`, pas de `retry-after`). Seuls `nvcf-reqid`, `nvcf-status` sont renvoyés.
  - Conséquence : le code ne peut pas lire une limite restante en réponse. Il faut se rabattre sur : (a) doc officielle, (b) backoff défensif sur 429.
  - WebSearch/WebFetch docs externes (free-llm.com, developer.nvidia.com) : **40 req/min** free tier, pas de cap journalier documenté publiquement, pas de différentiation par modèle documentée (mais expérimentalement Coder 480B semble plafonner plus tôt en bursts).
- **Conclusions consolidées de la session 2026-04-19** :
  - Qwen 3.5 397B (Researcher/Architect) : **déterministe** sur tool use avec le fix `_strip_strict_tools`.
  - Qwen 3 Coder 480B (Coder) : déterministe tool use, **sensible au rate limit** (429 en rafale serrée).
  - Kimi K2 Thinking (Critic) : **variance ~10 %** (1 réponse texte sur 10 à `sleep=0.5s`, sans 429) — c'est la source probable des "Critic sans read_file" observés en §1.
  - Le bug "intentions vides" sur runs 2 & 3 est **multi-causal** : rate limit (Coder) + variance modèle (Kimi) + potentiel effet d'orchestration CrewAI à investiguer.
- **Étape 3 prévue** : implémenter dans `FallbackLLM.call()` (a) un **backoff défensif 429** (ex: 1s / 2s / 4s puis fallback chain), (b) un **retry-1 sur 200 avec `tool_calls` vides** quand des tools ont été fournis (traite la variance Kimi), (c) logs payload/messages pour instrumenter l'hypothèse "tours successifs CrewAI".
- **Fichiers créés** (consolidé) : `scripts/test_tool_use_batch.py` (déjà commité `f05fda4`), `scripts/test_rate_headers.py` (commit session), `run_batch_*.log` (gitignored).
- **Fichiers modifiés non commités à la clôture de session** : `crew/crew.py` (prompt v2 Critic, non validé en runtime — à retravailler après le backoff/retry).
- **Commit** : `f05fda4` (test_tool_use_batch) + `ffa4a7a` (journal intermédiaire) + *(commit de clôture : journal consolidé + test_rate_headers)*.

### 2026-04-10 — Phase 1 §1 / Contrats de sortie + validation des appels d'outils

- **Scope** : nouveau module `crew/contracts.py` + branchement dans `crew/crew.py`.
- **Demande** : Phase 1 suite — le système doit détecter quand un agent n'a pas rempli son contrat (pas d'outils appelés, output vide, verdict manquant).
- **Design** :
  - Contrats par **task** (pas par rôle). Un même agent (ex: Architect) peut exécuter la task `plan` (contrat strict : plan numéroté) et la task `final` (contrat souple : synthèse ≥ 100 chars). Le contrat est adapté à chaque task.
  - 7 contrats : `research` (outils + ≥ 200 chars), `plan` (≥ 100 chars + pattern numéroté), `code` (read_file + ≥ 50 chars), `review` (read_file + APPROVED|CHANGES_NEEDED), `rework` (≥ 20 chars, pas d'exigence d'outil car conditionnel), `final` (≥ 100 chars), `scan` (list_files + ≥ 50 chars).
  - `ContractTracker` : `on_step()` collecte les noms d'outils via `step_callback`, `on_task_done()` valide via `task_callback`.
  - Violations loguées en temps réel + rapport de synthèse en fin de run.
- **Fichiers créés** : `crew/contracts.py`.
- **Fichiers modifiés** : `crew/crew.py` (import + tracker + callbacks + rapport final), `DOCUMENT_MAITRE_PROJET.md` (§15 + cette entrée).
- **Tests** : validation unitaire en simulation (3 scénarios : agent valide → 0 violation, agent sans outils → 2 violations, Critic sans verdict → 1 violation). Tous OK.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : OUI.
  - Run #1 : a révélé que `step_callback` CrewAI ne capture PAS les tool calls natifs. Fix : extraction depuis `TaskOutput.messages`. Tests unitaires 4/4 OK post-fix.
  - Run #2 (post-fix) : exit code 0, **2 violations détectées** (Critic : pas de read_file, pas de verdict APPROVED/CHANGES_NEEDED). Researcher, Coder, Architect = contrats respectés. Les violations sont de vraies violations (le Critic n'a pas agi), pas des faux positifs.
- **Commit** : *(ce commit)*.

### 2026-04-10 — Phase 1 §0.d / Re-run NEXUS réel — validation runtime du fix §0.c — PRIORITÉ 0 CLÔTURÉE

- **Scope** : run NEXUS complet sur AGENTIQUE pour valider le fix `_strip_strict_tools()` en conditions réelles.
- **Demande** : §0.d — confirmer que les agents produisent de vrais outputs (pas des intentions vides) avec le fix §0.c.
- **Commande** : `python crew/crew.py "Explique en 3 lignes ce que fait ce projet (lis README.md)" --project .`
- **Mode** : NORMAL (4 agents), pas de `--write`, pas de `--allow-shell`.
- **Résultat** : exit code 0, **succès complet**.
  - **12 appels d'outils** (read_file, list_files) répartis sur plusieurs agents.
  - **6/6 Final Answers avec vrai livrable** (vs 1/6 avant fix Phase 0).
  - **0 intention vide**, **0 XML Hermes cassé**.
  - **0 appel write_file**, **0 appel run_shell** (mode lecture respecté).
  - Rapport final structuré : synthèse en 5 sections (ce qui a été fait, reviewé, état final, fichiers consultés, points d'attention).
  - Le Coder a lu des fichiers et produit une synthèse réelle. Le Critic a fait une review. L'Architect a produit un rapport final consolidé.
- **Comparaison avec le run Phase 0 (avant fix)** :
  | Métrique | Phase 0 | §0.d |
  |---|---|---|
  | Appels d'outils | 10 (Researcher seul) | 12 (multi-agents) |
  | Agents avec vrai livrable | 1/6 | **6/6** |
  | Résultat final | intention vide | rapport structuré |
- **Fichiers touchés** : `DOCUMENT_MAITRE_PROJET.md` (cette entrée + §15 mis à jour).
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : OUI — run NIM complet, exit code 0, 6/6 agents fonctionnels.
- **PRIORITÉ 0 — STATUT** : **CLÔTURÉE**. §0.a ✅ §0.b ✅ §0.c ✅ §0.d ✅. La dette tool use NIM est résolue. Phase 1 peut maintenant avancer sur les contrats de sortie, la gouvernance et les modes d'usage.
- **Commit** : *(ce commit)*.

### 2026-04-10 — Phase 1 §0.b + §0.c / Swap architect + Fix schemas tool use CrewAI → NIM

- **Scope** : `crew/crew.py` — swap chaîne architect (§0.b) + fix de la cause racine des "intentions vides" (§0.c).
- **Demande** : avancer la priorité 0 de Phase 1 — rendre les agents capables de produire de vrais outputs au lieu d'intentions XML cassées.

- **§0.b — Swap chaîne `architect`** : ✅ FAIT.
  - `crew/crew.py` : DeepSeek V3.2 rétrogradé en fallback, Qwen 3.5 397B promu primaire. Llama 3.3 70B reste fallback final.
  - Justification : DeepSeek timeout 60s sur l'appel test simple de la matrice.

- **§0.c — Fix schemas tool use** : ✅ FAIT. Investigation complète + cause racine confirmée + fix appliqué.
  - **Test de confirmation** (`scripts/test_crewai_schema.py`) : compare la réponse de Qwen 3 Coder 480B entre un schema simple (`get_weather`, 1 param required) et le schema réel CrewAI (`read_file`, 3 params ALL required). Résultat : SIMPLE=NATIVE, CREWAI REEL=MALFORMED (XML Hermes cassé). Le schema CrewAI casse le modèle.
  - **Isolation de la variable** : 4 variantes testées en appel direct litellm. Le discriminant unique est `required` : dès que des params avec `default` Python sont dans `required`, Qwen Coder bascule en XML Hermes. Ni `strict:true`, ni `additionalProperties:false`, ni `title`, ni `default` dans le schema ne sont la cause isolément.
  - **Cause racine** : `crewai/utilities/agent_utils.py:convert_tools_to_openai_schema()` met TOUS les params dans `required` (contrainte du mode `strict:true` OpenAI). Cela crée une contradiction que Qwen Coder et Kimi K2 résolvent en abandonnant le format tool_calls natif pour leur format XML Hermes préféré — qui n'est pas parsé par CrewAI, d'où les "intentions vides".
  - **Fix** : `_strip_strict_tools()` (crew/crew.py, avant `FallbackLLM`) normalise les schemas avant envoi à NIM :
    1. Retire `strict: true` de `function`
    2. Retire `additionalProperties: false` de `parameters`
    3. Sort du `required` les params qui ont un `default` dans le schema
  - **Validation directe** : Qwen 3 Coder 480B avec le schema post-fix → `NATIVE: read_file({"path":"README.md"})`. Même modèle, même tool, le format change de MALFORMED à NATIVE.
  - **Hypothèse 1 (`strict:true` seul) invalidée** : déjà invalidée session précédente par `scripts/test_tool_use_strict.py`. Confirmé ici : retirer strict sans toucher `required` ne suffit pas.

- **Fichiers modifiés** :
  - `crew/crew.py` : swap architect (§0.b) + ajout `_strip_strict_tools()` (§0.c).
  - `.gitignore` : `scripts/*_payload.json` (session précédente, déjà modifié).
  - `DOCUMENT_MAITRE_PROJET.md` : cette entrée + mise à jour §15.
- **Fichiers créés** :
  - `scripts/test_crewai_schema.py` : script de preuve §0.c (6 appels NIM, reproductible).
  - `scripts/test_tool_use_strict.py` : script hypothèse 1 (session précédente, non encore commité).
  - `scripts/inspect_crewai_payload.py` : interception payload (session précédente, non encore commité).
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : OUI pour le fix isolé (appel litellm direct post-fix → NATIVE). NON encore validé en run NEXUS complet (→ §0.d).
- **Commit** : *(ce commit)*.

### 2026-04-09 — README / Bandeau WIP + statut par phase + dette tool use connue

- **Scope** : `README.md` — rendre explicite que le projet est un prototype expérimental, en développement actif, NON utilisable en production.
- **Demande** : "modifie le readme pour bien montrer que le projet est en cours" — éviter qu'un visiteur croie que c'est un outil prêt à l'emploi.
- **Changements** :
  - Bandeau d'avertissement en tête de README (block quote `> ⚠️ PROJET EN COURS DE DEVELOPPEMENT`).
  - Section "Statut" refondue : tableau d'avancement par phase (Phase 0 ✅ clôturée, Phase 1 🔄 en cours sur §0, Phases 2-5 ⏳).
  - Mention explicite de la dette tool use NIM (cause racine identifiée, fix en cours).
  - Mise à jour de la table fallback : Architect = Qwen 3.5 397B en primaire (suite au swap §0.b non encore commité, mais déjà décidé).
  - Référence à `scripts/tool_use_matrix.md` pour la calibration des chaînes.
  - "Limites connues" : ajout de la dette tool use NIM en tête de liste.
- **Fichiers touchés** : `README.md` uniquement.
- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** : N/A (changement doc pur).
- **Commit** : `a805cfd` (poussé sur `origin/main`).

### 2026-04-09 — Phase 1 §0.b fait + §0.c en cours / Investigation FallbackLLM (NON COMMITÉ)

> ⚠️ Cette entrée documente du travail **en cours, non commité**, pour qu'une éventuelle interruption de session ne perde pas le contexte. À mettre à jour ou éclater en plusieurs entrées au moment du commit.

- **§0.b — Swap chaîne `architect`** : ✅ FAIT (non commité).
  - `crew/crew.py` : DeepSeek V3.2 retrogradé en fallback, Qwen 3.5 397B promu primaire. Llama 3.3 70B reste fallback final.
  - Justification : DeepSeek timeout 60s sur l'appel test simple de la matrice ; Qwen 3.5 397B est NATIVE et déjà éprouvé sur le rôle Researcher dans le run de validation Phase 0.
  - Commentaire inline ajouté avec date et référence à `scripts/tool_use_matrix.md`.

- **§0.c — Investigation `FallbackLLM` / intégration CrewAI** : 🔄 EN COURS.

  **Données déjà recueillies (relecture de `run_phase0.log`)** :
  - Le **Researcher (Qwen 3.5 397B)** appelle ses tools normalement : 12 appels `read_file`/`list_files` entre les lignes 61-527 du log, Final Answer riche (~1000 mots).
  - **Tous les autres agents** (Architect, Coder, Critic, Coder rework, Architect synthèse) : **0 appel d'outil**, Final Answer = soit intention vide ("Je vais d'abord lire..."), soit `<tool_call>` XML cassé tronqué en plein milieu (ex: ligne 1162-1167 du log, format Hermes/Qwen XML : `<tool_call><function=read_file><parameter=path>README.md</parameter><parameter` — coupé).
  - Pattern : ces modèles connaissent le format XML Hermes (formé dessus) et tentent de l'émettre, alors que CrewAI attend du `tool_calls` natif au format OpenAI.

  **Mécanisme CrewAI compris (lecture source)** :
  - `crew_agent_executor.py:462 _invoke_loop_native_tools()` appelle `convert_tools_to_openai_schema(self.original_tools)` puis passe `tools=openai_tools` à `get_llm_response`, qui forwarde vers `LLM.call()`.
  - `crewai/utilities/agent_utils.py:144 convert_tools_to_openai_schema()` génère un schema avec **`"strict": True`** (ligne 207).
  - `crewai/llm.py:609 _prepare_completion_params()` passe `"tools": tools` directement dans `litellm.completion(...)` sans transformation supplémentaire (ligne 655).

  **Hypothèse 1 — `strict: true` casse certains modèles** : ⚠️ INVALIDÉE.
  - Test isolé : `scripts/test_tool_use_strict.py` (créé, non commité). Re-teste 3 modèles avec un schema strict (additionalProperties:false + required complet + strict:true) sur le tool simple `get_weather(city)`.
  - Résultats : Qwen 3 Coder 480B = NATIVE, Kimi K2 thinking = NATIVE, Qwen 3.5 397B = ERROR (timeout, non significatif — il marche en CrewAI).
  - **Conclusion** : `strict: true` SEUL n'est PAS la cause. Les deux modèles "qui cassent en CrewAI" répondent NATIVEMENT en appel direct, même avec strict, sur un schema simple à 1 param.

  **Hypothèse 2 — Inspection payload réel CrewAI** : 🔴 CAUSE RACINE TRÈS PROBABLE IDENTIFIÉE.
  - Méthode : `scripts/inspect_crewai_payload.py` (créé, non commité). Monkey-patche `litellm.completion` AVANT tout import de crew, crée un Agent Coder réel via `make_coder()`, lance un mini-Crew avec une task qui force `read_file`, intercepte le 1er appel et dump les params dans `scripts/coder_payload.json`. **Coût NIM : zéro appel.**
  - **🚨 Incident sécurité (résolu) lors du 1er run** : le dump initial contenait la clé `api_key` NIM en clair (champ standard kwargs litellm). Détecté immédiatement, fichier supprimé, JAMAIS commité (jamais tracké par git). Patch immédiat : `inspect_crewai_payload.py` REDACT maintenant `api_key` / `openai_api_key` / `nvidia_api_key` / etc. avant écriture. `.gitignore` mis à jour avec `scripts/coder_payload.json` et `scripts/*_payload.json` par sécurité. **La clé n'a jamais quitté le disque local.** À noter : l'utilisateur peut souhaiter rotater la clé NIM par précaution puisqu'elle a transité par un fichier sur disque même brièvement.
  - **Findings du payload (dump propre, post-redact)** :
    - **Tools** : 4 (read_file, list_files, grep, write_file), tous au format OpenAI standard avec `strict: true` et `additionalProperties: false` (cohérent avec source CrewAI lue).
    - **🔴 Anomalie clé** : `read_file.parameters.required = ["path", "offset", "limit"]` alors que `offset` (default=0) et `limit` (default=40000) ont des valeurs par défaut Python. Idem pour `list_files.required = ["directory"]` (default="."), `grep.required = ["pattern", "glob"]` (default="*"). **Cause** : OpenAI strict mode exige que TOUS les champs soient dans `required` (c'est une contrainte du flag `strict: true`), donc CrewAI/Pydantic met tout, y compris les params à default. Pour les modèles, ça crée une contradiction visible : "tu DOIS fournir `offset`/`limit`" vs "ces params ont des defaults". Hypothèse forte : Qwen 3 Coder et Kimi K2 abandonnent le format `tool_calls` natif et tentent leur format XML Hermes qu'ils maîtrisent mieux. C'est exactement le `<tool_call><function=read_file><parameter=path>...` qu'on voit dans `run_phase0.log` ligne 1162.
    - **Pourquoi le Researcher (Qwen 3.5 397B) n'est PAS affecté** : il est probablement plus "obéissant" au format OpenAI strict et accepte de fournir des valeurs même quand les params required ont l'air optionnels. Les modèles formés agressivement sur XML Hermes (Qwen Coder, Kimi K2) préfèrent leur format préféré et abandonnent le natif.
    - **Anomalies secondaires non bloquantes** :
      - System message dupliqué 3x dans le dump : artefact de `FallbackLLM.call()` qui fusionne les system messages à chaque retry CrewAI. À nettoyer mais pas critique.
      - 3 user messages identiques : artefact des retries CrewAI quand l'agent ne produit pas de tool call valide.
      - Pas de `tool_choice` envoyé (default `"auto"`). Pourrait être forcé à `"required"` pour la 1ère iter.

  **Pistes de fix (à valider en §0.c suite)** :
  1. **Override `convert_tools_to_openai_schema` pour passer `strict: false`** : retire la contrainte stricte, laisse les modèles utiliser le mode tool_calls "souple" (qui marche déjà chez beaucoup de serveurs vLLM). Coût : monkey-patch dans `crew/crew.py` au démarrage. Risque : casse possible sur d'autres providers.
  2. **Retirer les `default` des args_schema des tools NEXUS** : force le modèle à toujours fournir une valeur, plus de contradiction. Plus propre mais demande de modifier les signatures pydantic des tools.
  3. **Combinaison** : retirer les defaults ET garder strict:true. C'est ce qu'OpenAI recommande officiellement pour strict mode.

  **Prochain pas (à valider)** : test isolé qui rejoue Qwen 3 Coder 480B + Kimi K2 thinking avec le **vrai schema CrewAI** (read_file complet, required=[path,offset,limit], strict:true). Si ça casse (NATIVE → MALFORMED) là où `get_weather` simple marchait, hypothèse 2 confirmée à 100% et on peut écrire le fix avec confiance.

- **Fichiers créés/modifiés (non commités)** :
  - `crew/crew.py` (modifié, §0.b) : swap chaîne architect.
  - `scripts/test_tool_use_strict.py` (nouveau, §0.c hyp 1) : test isolé strict:true (hypothèse invalidée).
  - `scripts/inspect_crewai_payload.py` (nouveau, §0.c hyp 2) : monkey-patch d'interception payload CrewAI, coût NIM zéro.
  - `.gitignore` (modifié) : ajout `scripts/coder_payload.json` et `scripts/*_payload.json` (prévention fuite secrets).
  - `DOCUMENT_MAITRE_PROJET.md` (modifié, cette entrée).
- **Fichiers volontairement ignorés** : `scripts/coder_payload.json` (dump runtime, contient des champs sensibles même après redact, gitignored).

- **Repo modifié** : oui.
- **Prod alignée** : N/A.
- **Validation réelle** :
  - §0.b : non encore validé runtime (pas de re-run NEXUS depuis le swap).
  - §0.c hypothèse 1 : OUI invalidée par appel litellm direct sur 3 modèles.
- **État** : §0.b fait, §0.c en investigation active, §0.d (re-run NEXUS) en attente du fix de §0.c.
- **Commit** : *(à venir, après plus d'avancée sur §0.c — ne pas committer §0.b seul, ça serait incomplet sans le fix d'intégration)*.

### 2026-04-09 — Phase 1 §0.a / Matrice tool use NIM — hypothèse précédente invalidée

- **Scope** : test systématique de chaque modèle NIM des `MODEL_CHAINS` pour mesurer leur capacité réelle à appeler un outil au format OpenAI `tool_calls`. Doit valider ou invalider l'hypothèse de l'entrée précédente (qui attribuait les "intentions vides" à une incapacité tool use des modèles Coder/Critic/Architect).
- **Demande** : "matrice tool use par modèle NIM" — priorité 0 ajoutée à Phase 1 dans l'entrée précédente.
- **Méthode** :
  - Nouveau script `scripts/test_tool_use.py` : pour chaque modèle unique de `MODEL_CHAINS`, envoie un appel `litellm.completion` direct avec un outil simple `get_weather(city)` et un prompt qui demande explicitement de l'utiliser. Classe la réponse en NATIVE / TEXT / MALFORMED / ERROR.
  - Le script parse `MODEL_CHAINS` par regex sur le source de `crew/crew.py` (pour ne pas avoir à importer `crew.crew` qui exige `CREW_PROJECT`).
  - Run en séquentiel (pour rester poli sur le rate limit NIM), 11 modèles, ~3 min total.
  - Sauvegarde markdown durable dans `scripts/tool_use_matrix.md`.
- **Résultats** : `Total : 11 | NATIVE=9 | ERROR=2`.
  - **NATIVE (9)** : Qwen 3.5 397B, Llama 3.3 70B, Qwen 3 Coder 480B, Devstral 2 123B, Kimi K2 instruct, Kimi K2 thinking, Qwen 3 next 80B thinking, Nemotron 49B, GPT-OSS 120B.
  - **ERROR (2)** : DeepSeek V3.2 (`litellm.Timeout` 60s — lent côté NIM, pas une incapacité), Gemma 3 27B (`"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set` — incapacité structurelle côté NIM).
- **🔴 Découverte critique — INVALIDATION de l'hypothèse de l'entrée précédente** :
  - L'entrée précédente (`8457f88`) affirmait : *"Cause racine probable : tool use natif non supporté de manière fiable par DeepSeek V3.2 (Architect), Qwen 3 Coder 480B (Coder) et Kimi K2 Thinking (Critic) côté NIM."*
  - **C'est faux** pour Qwen 3 Coder 480B et Kimi K2 Thinking. Tous les deux répondent NATIVEMENT au format `tool_calls` OpenAI au niveau brut litellm.
  - Toute la chaîne Coder est NATIVE x3. Toute la chaîne Critic est NATIVE x3.
  - **Conclusion révisée** : le bug "intentions vides" du run de validation Phase 0 n'est PAS dû aux modèles. Il est dans la couche d'intégration entre CrewAI et notre `FallbackLLM` custom (`crew/crew.py:132-204`). Pistes à investiguer :
    - Prompt ReAct injecté par CrewAI qui contredit le format `tool_calls` natif.
    - `LLM().call()` de CrewAI qui ne propage pas correctement le paramètre `tools` quand l'instance est wrappée dans un `BaseLLM` custom.
    - Normalisation des messages système dans `FallbackLLM.call()` qui casserait quelque chose (peu probable car affecte tous les agents et le Researcher marche).
    - L'agent CrewAI passe peut-être ses tools custom (read_file, etc.) dans un format différent du format OpenAI standard testé ici.
- **Seul changement chaîne nécessaire** : `architect` — DeepSeek V3.2 timeout 100% du temps sur l'appel test (60s), à basculer en fallback ; Qwen 3.5 397B en primaire. Aucun autre rôle ne nécessite de swap selon la matrice.
- **Mise à jour §15 Phase 1** : la priorité 0 est éclatée en 4 sous-étapes (0.a matrice ✅, 0.b swap architect, 0.c investigation FallbackLLM, 0.d re-run réel).
- **Fichiers créés (non encore commités)** :
  - `scripts/test_tool_use.py` — script de test (~300 lignes, durable, à committer).
  - `scripts/tool_use_matrix.md` — résultats (~65 lignes, à committer comme référence).
  - `tool_use_run.log` — log du run (ignoré par `*.log`).
- **Fichiers modifiés (non encore commités)** :
  - `DOCUMENT_MAITRE_PROJET.md` (cette entrée + mise à jour §15 Phase 1 priorité 0).
- **Repo modifié** : oui, mais aucun commit encore.
- **Prod alignée** : N/A.
- **Validation réelle** : OUI — la matrice est elle-même une validation (chaque modèle testé en conditions réelles avec un appel litellm complet, exit code 0, classification cohérente).
- **État Phase 1** : §0.a fait, §0.b/0.c/0.d à faire.
- **Commits** : `a68f234` (feat scripts — matrice + script, poussé sur `origin/main`) et `01dc99c` (docs journal — invalidation hypothèse, poussé sur `origin/main`).

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

