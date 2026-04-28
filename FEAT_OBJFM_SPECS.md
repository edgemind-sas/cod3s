# Spécification : Paramètre `behaviour` pour ObjFM

**Version**: 1.1
**Date initiale**: 2026-01-15
**Date révision**: 2026-04-28
**Auteur**: Développement COD3S

> **Révision 1.1 (2026-04-28)** — Aligne la spec sur les décisions du brainstorm `docs/brainstorms/2026-04-28-objfm-external-modes-brainstorm.md` et l'implémentation effective :
> - Les `failure_effects` / `repair_effects` sont **appliqués** (et non plus ignorés) en mode `external` et `external_rep_indep`. Ils s'exécutent via l'automate du target. Aucun warning n'est émis.
> - Le mode `external_rep_indep` adopte un **modèle pulse** : ObjFM transite occ→rep en `delay(0)` sans condition après avoir déclenché les targets. Loi de réparation target = ordre 1 ; condition = `repair_cond` originale évaluée sur le target.
> - Le mécanisme de `ctrl_var` est **différencié** : méthode sensible centralisée pour `external`, effets directs sur transitions pour `external_rep_indep` (avec une méthode sensible dédiée sur l'automate du target pour le reset de `ctrl`, afin d'éviter une cascade d'effets contradictoires).
> - Garde explicite (`ValueError`) sur la loi de réparation d'ordre 1 inactive en `external_rep_indep`.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Motivations](#motivations)
3. [Spécifications des behaviours](#spécifications-des-behaviours)
4. [Architecture et implémentation](#architecture-et-implémentation)
5. [Exemples d'utilisation](#exemples-dutilisation)
6. [Détails techniques](#détails-techniques)
7. [Tests](#tests)
8. [Cas d'usage](#cas-dusage)
9. [Migration et compatibilité](#migration-et-compatibilité)

---

## Vue d'ensemble

Cette spécification décrit l'ajout d'un nouveau paramètre `behaviour` à la classe `ObjFM` (Object Failure Mode) du framework COD3S. Ce paramètre permet de contrôler comment les modes de défaillance gèrent l'état de leurs composants cibles (targets).

## Motivations

### Problématique

Dans la version actuelle, les `ObjFM` gèrent les défaillances de manière centralisée :
- L'état de défaillance n'est visible que dans l'ObjFM
- Les composants targets n'ont pas de représentation explicite de leur état de défaillance
- Les `failure_effects` appliquent des modifications sur les variables des targets

Cette approche présente des limitations :
1. **Manque de visibilité** : L'état de défaillance d'un composant n'est pas directement
   observable en termes d'états. Notamment dans le calcul des séquences où cela est utile.
2. **Couplage fort** : Les targets dépendent entièrement de l'ObjFM pour leur état
3. **Flexibilité limitée** : Impossible de modéliser des réparations indépendantes

### Objectifs

1. **Décentralisation** : Permettre aux targets de gérer leur propre état de défaillance
2. **Visibilité** : Rendre l'état de défaillance observable directement dans le composant
3. **Flexibilité** : Autoriser des stratégies de réparation variées (synchronisée ou indépendante)
4. **Rétrocompatibilité** : Conserver le comportement actuel par défaut

---

## Spécifications des behaviours

### 1. `behaviour="internal"` (défaut)

**Description** : Comportement actuel, inchangé.

| Aspect | Comportement |
|--------|-------------|
| **Automates ObjFM** | Créés dans l'ObjFM (ex: `frun__cc_1`, `frun__cc_12`) |
| **Automates targets** | Aucun automate créé dans les targets |
| **Gestion état** | L'ObjFM contrôle tout en interne |
| **failure_effects** | Appliqués aux variables des targets via `setValue()` |
| **repair_effects** | Appliqués aux variables des targets via `setValue()` |
| **Visibilité** | État de défaillance visible uniquement dans l'ObjFM |

**Flux d'exécution** :
```
1. ObjFM.frun__cc_1 transite vers "occ"
   └─> Exécute failure_effects sur C1 (ex: C1.flow_in_max = 3)

2. ObjFM.frun__cc_1 transite vers "rep"
   └─> Exécute repair_effects sur C1 (ex: C1.flow_in_max = -1)
```

**Cas d'usage** :
- Modélisation simple de défaillances
- Effets directs sur les variables des targets
- Analyse centralisée des modes de défaillance

---

### 2. `behaviour="external"`

**Description** : L'ObjFM crée des automates synchronisés dans chaque target. ObjFM et target sont **mutuellement verrouillés** : l'ObjFM ne peut transiter que si tous les targets de la combo sont dans l'état adéquat, et le target suit l'ObjFM via une variable de contrôle.

| Aspect | Comportement |
|--------|-------------|
| **Automates ObjFM** | Créés dans l'ObjFM (un par combinaison de targets) |
| **Automates targets** | Un automate `{fm_name}` (états `{failure_state}` / `{repair_state}`) créé dans chaque target |
| **Gestion état** | État distribué : ObjFM + targets, verrouillés mutuellement |
| **Synchronisation** | Via variables de contrôle `ctrl_{fm_name}_{target_name}` (booléen, sur l'ObjFM) |
| **failure_effects** | **Appliqués sur l'automate du target** lors de la transition vers `failure_state` |
| **repair_effects** | **Appliqués sur l'automate du target** lors de la transition vers `repair_state` |
| **Visibilité** | État de défaillance visible dans le target ET l'ObjFM |

**Flux d'exécution** :
```
DÉFAILLANCE:
1. ObjFM.frun__cc_1 transite vers occ (loi exp(λ_1) ou delay)
   └─> Méthode sensible centralisée recalcule ctrl_frun_C1 = True
       (= OR des automates impactant en occ)

2. C1.frun voit cond (ctrl_frun_C1 == True) satisfaite, loi delay(0)
   └─> C1.frun transite vers failure_state, applique failure_effects

RÉPARATION:
3. ObjFM.frun__cc_1 transite vers rep (loi exp(μ_1) ou delay), conditionné
   par "tous les targets de la combo en failure_state" (verrou)
   └─> Méthode sensible recalcule ctrl_frun_C1 = False

4. C1.frun voit cond (ctrl_frun_C1 == False), loi delay(0)
   └─> C1.frun transite vers repair_state, applique repair_effects
```

**Détails techniques** :
- **Variables de contrôle** : Booléennes créées dans l'ObjFM, init `False`.
- **Maintenance de ctrl_var** : méthode sensible centralisée enregistrée sur les automates ObjFM impactant chaque target. Elle recalcule `ctrl = OR(combos_impactants en failure_state)`.
- **Augmentation des conditions ObjFM** :
  - failure_cond : `failure_cond_user AND tous_targets_de_la_combo_en_repair_state`.
  - repair_cond : `repair_cond_user AND tous_targets_de_la_combo_en_failure_state`.
- **Loi des transitions target** : `delay(0)` dans les deux sens.
- **Conditions transitions target** :
  - vers failure : `ctrl_var.value() == True`
  - vers repair : `ctrl_var.value() == False`

**Cas d'usage** :
- Besoin de visibilité locale de l'état de défaillance.
- Modélisation de systèmes distribués.
- Indicateurs basés sur l'état du composant.
- Analyse de séquences enrichie : chaque transition apparaît dans la trace.

---

### 3. `behaviour="external_rep_indep"`

**Description** : Modèle **pulse** — l'ObjFM agit comme un **déclencheur transitoire**. Il pulse en occ juste le temps de propager la défaillance aux targets, puis se réinitialise instantanément. Chaque target gère ensuite son cycle de réparation indépendamment, selon la loi d'ordre 1 de l'ObjFM.

| Aspect | Comportement |
|--------|-------------|
| **Automates ObjFM** | Créés dans l'ObjFM (un par combinaison) |
| **Automates targets** | Un automate `{fm_name}` (états `{failure_state}` / `{repair_state}`) créé dans chaque target |
| **Synchronisation défaillance** | Via effet direct sur la transition `ObjFM.occ` : `ctrl_{fm_name}_{target_name} := True` pour les targets de la combo |
| **Synchronisation réparation** | **INDÉPENDANTE** — chaque target gère sa propre réparation |
| **Loi de réparation target** | Loi de l'**ordre 1** de l'ObjFM (`exp(μ_1)` pour ObjFMExp, `delay(ttr_1)` pour ObjFMDelay), quelle que soit la combo qui a déclenché la défaillance |
| **Condition de réparation target** | `repair_cond` originale de l'ObjFM, **évaluée sur le target courant** |
| **failure_effects** | **Appliqués sur l'automate du target** lors de sa transition vers `failure_state` |
| **repair_effects** | **Appliqués sur l'automate du target** lors de sa transition vers `repair_state` |
| **ObjFM repair** | Loi `delay(0)` sans condition — pulse instantané, **n'affecte pas les ctrl_vars** |

**Flux d'exécution** :
```
DÉFAILLANCE (pulse) — toutes ces transitions se chaînent en un seul step à la
même date, en ordre garanti par les conditions et les delay(0):

1. ObjFM.frun__cc_12 transite rep → occ (loi exp(λ_12) ou delay), conditionné
   par "failure_cond_user AND tous_targets_en_repair_state"
   └─> Effet direct : ctrl_frun_C1 := True, ctrl_frun_C2 := True

2. C1.frun, C2.frun voient cond (ctrl == True) satisfaite, loi delay(0)
   └─> Chacun transite vers failure_state, applique failure_effects sur ses
       variables locales

3. ObjFM.frun__cc_12 transite occ → rep (loi delay(0), condition True)
   └─> Aucun effet sur ctrl_vars : ils restent True
   └─> ObjFM est libre pour un nouveau cycle dès que les targets repassent
       en repair

RÉPARATION (indépendante par target):

4. C1.frun (en occ) tire sa transition occ → rep avec sa propre loi exp(μ_1)
   et condition = repair_cond utilisateur évaluée sur C1
   └─> Applique repair_effects sur les variables de C1
   └─> Méthode sensible enregistrée sur l'automate de C1 détecte le passage
       en repair_state et remet ctrl_frun_C1 := False
       (PAS via effets_st1, qui créeraient un conflit avec l'effet ObjFM.occ)

5. C2 vit son propre cycle de réparation indépendamment, avec sa loi μ_1.

Note : tant qu'un target reste en occ, aucune combo qui le contient ne peut
re-déclencher (failure_cond augmentée). Une combo cc_1 sur C1 redevient
fireable dès que C1 a réparé, même si C2 est encore en occ.
```

**Détails techniques** :
- **Loi de réparation target** : `set_occ_law_repair(repair_var_params_order1)` :
  - ObjFMExp : `{"cls": "exp", "rate": μ_1}` (μ_1 = `repair_param[0]`).
  - ObjFMDelay : `{"cls": "delay", "time": ttr_1}` (ttr_1 = `repair_param[0]`).
- **Condition de réparation target** : `self.get_repair_cond(target_comps=[target_comp], param=self.repair_var_params_order1)`. Pour ObjFMExp cela donne `μ_1 > 0 AND repair_cond_user(C1)`.
- **Reset ctrl_var** : effectué par une méthode sensible enregistrée sur l'automate du target (et NON sur la variable). Lorsque le target entre en `repair_state`, la méthode positionne `ctrl = False`. Cette indirection évite la cascade d'effets contradictoires entre la transition `ObjFM.occ` (qui veut `ctrl = True`) et le `effects_st1` du target (qui voudrait `ctrl = False`) lors de l'initialisation et au fil de la simulation.
- **Augmentation de failure_cond** : identique à `external` (`failure_cond_user AND tous_targets_en_repair_state`).
- **Repair_cond ObjFM** : remplacée par `lambda: True` (pas de condition, pulse).
- **Garde** : `ValueError` à la construction si la loi de réparation d'ordre 1 est inactive (μ_1 = 0 ou ttr_1 = 0). Sans cette garde, les targets ne pourraient jamais se réparer.

**Cas d'usage** :
- Modélisation de réparations locales (équipe de maintenance sur site).
- Temps de réparation indépendants entre composants.
- Analyse de disponibilité avec réparations stochastiques.
- Causes communes asymétriques : un évènement déclencheur impacte plusieurs composants, mais leurs dynamiques de réparation sont indépendantes.

---

## Architecture et implémentation

### Modifications dans `cod3s/pycatshoo/component.py`

#### 1. Constante et paramètre

```python
class ObjFM(PycComponent):
    VALID_BEHAVIOURS = ("internal", "external", "external_rep_indep")

    def __init__(
        self,
        fm_name,
        targets=[],
        target_name=None,
        behaviour="internal",  # NOUVEAU PARAMÈTRE
        failure_state="occ",
        failure_cond=True,
        failure_effects={},
        # ... autres paramètres
    ):
```

#### 2. Validation du paramètre

```python
if behaviour not in self.VALID_BEHAVIOURS:
    raise ValueError(
        f"behaviour must be one of {self.VALID_BEHAVIOURS}, got '{behaviour}'"
    )
self.behaviour = behaviour
```

#### 3. Effets en mode external/external_rep_indep

> **Note (révisée 2026-04-28)** : la version initiale de cette spec prévoyait d'**ignorer** `failure_effects` / `repair_effects` en mode `external*` avec un warning. Cette décision a été inversée lors du brainstorm 2026-04-28 : les effets sont **appliqués** sur l'automate du target, ce qui simplifie la déclaration (un seul endroit pour décrire l'impact d'une défaillance sur le composant). Aucun warning n'est émis. Les tests `test_comp_failure_external_002.py` et `test_comp_failure_external_rep_indep_004.py` valident cette propagation.

#### 4. Création des variables de contrôle

```python
# Create control variables for external behaviours
self.ctrl_vars = {}
if self.behaviour in ("external", "external_rep_indep"):
    for target_name_cur in self.targets:
        ctrl_var_name = f"ctrl_{self.fm_name}_{target_name_cur}"
        ctrl_var = self.addVariable(ctrl_var_name, pyc.TVarType.t_bool, False)
        self.ctrl_vars[target_name_cur] = ctrl_var
```

#### 5. Stockage des paramètres repair de l'ordre 1

```python
# Store order 1 repair params for external_rep_indep behaviour
self.repair_var_params_order1 = None

for order in range(1, order_max + 1):
    # ... création des variables de paramètres ...

    # Store order 1 params
    if order == 1:
        self.repair_var_params_order1 = repair_var_params_cur
```

#### 6. Effets sur les transitions ObjFM selon le behaviour

> **Note d'implémentation (2026-04-28)** : la stratégie de gestion des `ctrl_vars` diffère entre `external` et `external_rep_indep` parce qu'un effet enregistré sur une variable est ré-évalué à chaque changement de cette variable, ce qui crée des conflits en mode synchrone (cc_X.rep est en état initial actif → veut `ctrl=False`, en conflit avec cc_Y.occ qui veut `ctrl=True`). Le mode pulse de `external_rep_indep` n'a pas ce conflit car les effets `effects_st1` sont vides côté ObjFM.

```python
for target_set_idx in itertools.combinations(range(order_max), order):

    if self.behaviour == "external":
        # Centralized management via a sensitive method (see #7).
        # ObjFM transitions carry no direct effects on ctrl_vars.
        failure_effects_cur = []
        repair_effects_cur = []

    elif self.behaviour == "external_rep_indep":
        # Pulse model: ObjFM.occ sets ctrl=True directly on the transition.
        # ObjFM.rep does NOT touch ctrl (target owns reset, see #8).
        failure_effects_cur = [
            {"var": self.ctrl_vars[self.targets[idx]], "value": True}
            for idx in target_set_idx
        ]
        repair_effects_cur = []

    else:  # internal behaviour: classic effects on target variables.
        failure_effects_cur = [...]  # resolve self.failure_effects on targets
        repair_effects_cur = [...]   # resolve self.repair_effects on targets
```

#### 6bis. Conditions et lois ObjFM

```python
if self.behaviour in ("external", "external_rep_indep"):
    # Failure: targets must all be in repair_state.
    failure_cond_cur = make_external_cond(
        failure_cond_cur, target_comps_cur, self.fm_name, self.repair_state,
    )
    if self.behaviour == "external":
        # Repair: targets must all be in failure_state (mutual lock).
        repair_cond_cur = make_external_cond(
            repair_cond_cur, target_comps_cur, self.fm_name, self.failure_state,
        )
    else:  # external_rep_indep
        # Pulse: ObjFM.rep is unconditional (delay 0, see law below).
        repair_cond_cur = lambda: True

if self.behaviour == "external_rep_indep":
    objfm_repair_law = {"cls": "delay", "time": 0}  # pulse
else:
    objfm_repair_law = self.set_occ_law_repair(repair_var_params_cur)
```

#### 6ter. Méthode sensible centralisée (external uniquement)

Pour le mode `external`, une méthode sensible enregistrée sur les automates ObjFM impactant chaque target maintient `ctrl_var = OR(combos_impactant en failure_state)`. Cela évite que des combos concurrents s'écrasent mutuellement. **Cette méthode n'est pas enregistrée pour `external_rep_indep`** (incompatible avec le pulse — l'ObjFM repassant en rep réinitialiserait ctrl=False trop tôt).

```python
if self.behaviour == "external":
    # Build and register make_ctrl_method per target — see component.py
    ...
```

#### 7. Création des automates dans les targets

```python
# Create automata in target components for external behaviours
if self.behaviour in ("external", "external_rep_indep"):
    for target_name_cur in self.targets:
        # Create fresh dict each time to avoid mutation issues
        if self.behaviour == "external":
            repair_occ_law = {"cls": "delay", "time": 0}
        else:  # external_rep_indep
            repair_occ_law = self.set_occ_law_repair(self.repair_var_params_order1)

        self._create_target_automaton(target_name_cur, repair_occ_law)
```

#### 8. Méthode `_create_target_automaton`

```python
def _create_target_automaton(
    self, target_name, repair_occ_law, failure_effects={}, repair_effects={}
):
    """Create a synchronized automaton in the target component.

    Args:
        target_name: name of the target component
        repair_occ_law: occurrence law for the target's repair transition
            - {"cls": "delay", "time": 0} for `external` (synchronized)
            - order-1 repair law (e.g., {"cls": "exp", "rate": mu_var}) for
              `external_rep_indep`
        failure_effects: ObjFM-level failure_effects (applied on the target's
            transition into failure_state)
        repair_effects: ObjFM-level repair_effects (applied on the target's
            transition into repair_state)
    """
    target_comp = self.system().component(target_name)

    # Name conflict check.
    existing_aut_names = [aut.basename() for aut in target_comp.automata()]
    if self.fm_name in existing_aut_names:
        raise ValueError(
            f"Target '{target_name}' already has an automaton named "
            f"'{self.fm_name}'. Cannot create external FM automaton."
        )

    ctrl_var = self.ctrl_vars[target_name]

    def occ_condition():
        return ctrl_var.value() is True

    if self.behaviour == "external":
        # Synchronized: target follows ctrl_var driven by ObjFM.
        def rep_condition():
            return ctrl_var.value() is False
    else:  # external_rep_indep
        # Reuse the user's original repair_cond, evaluated on this target,
        # using the order-1 repair params (matches the order-1 law used as
        # repair_occ_law).
        rep_condition = self.get_repair_cond(
            target_comps=[target_comp],
            param=self.repair_var_params_order1,
        )

    # Resolve failure_effects / repair_effects on target_comp variables.
    final_failure_effects = [...]  # records of {var: target_var, value: ...}
    final_repair_effects = [...]   # idem for repair_effects

    target_aut = target_comp.add_aut2st(
        name=self.fm_name,
        st1=self.repair_state,
        st2=self.failure_state,
        init_st2=False,
        trans_name_12_fmt="{st2}",
        cond_occ_12=occ_condition,
        occ_law_12={"cls": "delay", "time": 0},   # always instantaneous
        occ_interruptible_12=True,
        effects_st2=final_failure_effects,
        effects_st2_format="records",
        trans_name_21_fmt="{st1}",
        cond_occ_21=rep_condition,
        occ_law_21=repair_occ_law,
        occ_interruptible_21=True,
        effects_st1=final_repair_effects,
        effects_st1_format="records",
        step=self.step,
    )

    # In external_rep_indep, the ObjFM doesn't reset ctrl_var on its own
    # repair (pulse model). The target clears ctrl_var when its automaton
    # returns to the repair state. We use a sensitive method on the target
    # automaton (NOT on the ctrl variable) to avoid the cascading
    # re-evaluation that would happen if `ctrl=False` were placed in
    # effects_st1 (such an effect is registered on the variable itself,
    # creating a conflict with the ObjFM.occ effect at simulation start).
    if self.behaviour == "external_rep_indep":
        rep_state_bkd = target_aut.get_state_by_name(self.repair_state)._bkd

        def reset_ctrl_on_target_repair():
            if rep_state_bkd.isActive() and ctrl_var.value() is True:
                ctrl_var.setValue(False)

        target_aut._bkd.addSensitiveMethod(
            f"reset_ctrl__{self.fm_name}__{target_name}",
            reset_ctrl_on_target_repair,
        )
```

#### 9. Garde `external_rep_indep` : loi d'ordre 1 active

Le mode pulse repose sur la loi de réparation d'ordre 1 pour la dynamique d'auto-réparation du target. Si cette loi est inactive (`μ_1 = 0` ou `ttr_1 = 0`), les targets ne pourraient jamais réparer — c'est presque toujours une erreur de configuration. Une `ValueError` est levée à la construction :

```python
if self.behaviour == "external_rep_indep":
    if self.repair_var_params_order1 is None or not self.is_occ_law_repair_active(
        self.repair_var_params_order1
    ):
        raise ValueError(
            f"behaviour='external_rep_indep' requires the order-1 "
            f"repair law to be active for FM '{self.fm_name}'. "
            f"Provide a non-zero repair_param for order 1."
        )
```

### Impact sur les sous-classes

#### ObjFMExp

**Aucune modification requise**. La classe continue de surcharger :
- `set_occ_law_failure()` : Retourne `{"cls": "exp", "rate": lambda_var}`
- `set_occ_law_repair()` : Retourne `{"cls": "exp", "rate": mu_var}`
- `get_failure_cond()` : Ajoute la condition `lambda > 0`

La loi `exp(mu)` est automatiquement utilisée pour `external_rep_indep`.

#### ObjFMDelay

**Aucune modification requise**. La classe continue de surcharger :
- `set_occ_law_failure()` : Retourne `{"cls": "delay", "time": ttf_var}`
- `set_occ_law_repair()` : Retourne `{"cls": "delay", "time": ttr_var}`

La loi `delay(ttr)` est automatiquement utilisée pour `external_rep_indep`.

---

## Exemples d'utilisation

### Exemple 1 : `behaviour="internal"` (défaut)

```python
from cod3s.pycatshoo.system import PycSystem

system = PycSystem(name="InternalExample")
system.pdmp_manager = system.addPDMPManager("pdmp_manager")

# Composants
system.add_component(name="Pump1", cls="ObjFlow")
system.add_component(name="Pump2", cls="ObjFlow")

# Mode de défaillance interne (comportement classique)
system.add_component(
    cls="ObjFMExp",
    fm_name="frun",
    targets=["Pump1", "Pump2"],
    behaviour="internal",  # Optionnel, c'est la valeur par défaut
    failure_effects={"flow_in_max": 0, "flow_available_out": False},
    failure_param=[0.001, 0.0005],  # lambda pour ordre 1 et 2
    repair_param=[0.1, 0.05],       # mu pour ordre 1 et 2
)

# Simulation
system.isimu_start()
system.isimu_set_transition(0, date=100)
system.isimu_step_forward()

# État : Pump1.flow_in_max a été modifié à 0
print(system.comp["Pump1"].flow_in_max.value())  # 0

system.isimu_stop()
```

### Exemple 2 : `behaviour="external"`

```python
from cod3s.pycatshoo.system import PycSystem

system = PycSystem(name="ExternalExample")
system.pdmp_manager = system.addPDMPManager("pdmp_manager")

# Composants
system.add_component(name="Turbine1", cls="ObjFlow")

# Mode de défaillance externe (automate dans le target)
system.add_component(
    cls="ObjFMExp",
    fm_name="blade_failure",
    targets=["Turbine1"],
    behaviour="external",
    failure_param=0.002,  # lambda = 0.002 défaillances/heure
    repair_param=0.5,     # mu = 0.5 réparations/heure (MTTR = 2h)
)

# Vérifier la création de l'automate dans le target
print("Automates dans Turbine1:", [a.basename() for a in system.comp["Turbine1"].automata()])
# Output: ['blade_failure']

# Simulation
system.isimu_start()

# Déclencher défaillance
system.isimu_set_transition(0, date=100)
system.isimu_step_forward()

# Variable de contrôle mise à True
fm = system.comp["Turbine1__blade_failure"]
print(fm.ctrl_vars["Turbine1"].value())  # True

# Propagation au target (nécessite un second step)
system.isimu_set_transition(0)
system.isimu_step_forward()

# État du target
turbine_aut = system.comp["Turbine1"].automata_d["blade_failure"]
print(turbine_aut.get_state_by_name("occ")._bkd.isActive())  # True

# Utilisation dans des conditions
if turbine_aut.get_state_by_name("occ")._bkd.isActive():
    print("Turbine1 est en panne!")

system.isimu_stop()
```

### Exemple 3 : `behaviour="external_rep_indep"`

```python
from cod3s.pycatshoo.system import PycSystem

system = PycSystem(name="IndependentRepairExample")
system.pdmp_manager = system.addPDMPManager("pdmp_manager")

# Composants distribués géographiquement
system.add_component(name="SiteA_Pump", cls="ObjFlow")
system.add_component(name="SiteB_Pump", cls="ObjFlow")

# Défaillance commune, mais réparations indépendantes
system.add_component(
    cls="ObjFMExp",
    fm_name="electrical_fault",
    targets=["SiteA_Pump", "SiteB_Pump"],
    behaviour="external_rep_indep",
    failure_param=[0.001, 0.0001],  # Ordre 1 et 2
    repair_param=[0.2, 0.1],        # Ordre 1: MTTR=5h par site
)

# Chaque site a son propre automate avec réparation indépendante
print("SiteA automates:", [a.basename() for a in system.comp["SiteA_Pump"].automata()])
print("SiteB automates:", [a.basename() for a in system.comp["SiteB_Pump"].automata()])
# Output: ['electrical_fault'], ['electrical_fault']

# Simulation
system.isimu_start()

# Défaillance commune des deux pompes
system.isimu_set_transition(0, date=100)
system.isimu_step_forward()

# Propagation aux targets
system.isimu_set_transition(0)
system.isimu_step_forward()
system.isimu_set_transition(0)
system.isimu_step_forward()

# Les deux sites sont en panne
siteA_aut = system.comp["SiteA_Pump"].automata_d["electrical_fault"]
siteB_aut = system.comp["SiteB_Pump"].automata_d["electrical_fault"]
print("SiteA en panne:", siteA_aut.get_state_by_name("occ")._bkd.isActive())  # True
print("SiteB en panne:", siteB_aut.get_state_by_name("occ")._bkd.isActive())  # True

# Chaque site se répare INDÉPENDAMMENT selon exp(0.2)
# SiteA peut se réparer avant SiteB (ou inversement)
# Pas de réparation synchronisée par l'ObjFM

system.isimu_stop()
```

### Exemple 4 : Analyse de disponibilité avec `external_rep_indep`

```python
from cod3s.pycatshoo.system import PycSystem, PycMCSimulationParam
import numpy as np

# Système avec composants réparables
system = PycSystem(name="AvailabilityStudy")
system.pdmp_manager = system.addPDMPManager("pdmp_manager")

system.add_component(name="Server", cls="ObjFlow")

system.add_component(
    cls="ObjFMExp",
    fm_name="hardware_failure",
    targets=["Server"],
    behaviour="external_rep_indep",
    failure_param=0.01,   # MTTF = 100 heures
    repair_param=1.0,     # MTTR = 1 heure
)

# Indicateur de disponibilité
from cod3s.pycatshoo.indicator import PycVarIndicator

# Surveiller l'état de l'automate du serveur
server_aut = system.comp["Server"].automata_d["hardware_failure"]
rep_state = server_aut.get_state_by_name("rep")

availability_indicator = PycVarIndicator(
    name="server_availability",
    system=system,
    var=rep_state._bkd,  # Variable d'état "rep" = serveur disponible
    cond="==",
    value=True,
)

# Simulation Monte Carlo
sim_params = PycMCSimulationParam(
    nb_runs=10000,
    t_max=8760.0,  # 1 an
)

results = system.simulate(sim_params)

# Disponibilité moyenne
availability = availability_indicator.mean()
print(f"Disponibilité du serveur: {availability:.4f}")
# Théorique: MTTF/(MTTF+MTTR) = 100/(100+1) = 0.9901

# Quantiles
q = availability_indicator.quantiles([0.05, 0.5, 0.95])
print(f"Quantile 5%: {q[0]:.4f}")
print(f"Médiane: {q[1]:.4f}")
print(f"Quantile 95%: {q[2]:.4f}")
```

---

## Détails techniques

### Synchronisation PyCATSHOO

La synchronisation entre l'ObjFM et les targets nécessite **deux pas de simulation** :

1. **Premier pas** : La transition de l'ObjFM se déclenche
   - Les effets sont appliqués (modification de `ctrl_var`)
   - L'état de la variable de contrôle change

2. **Second pas** : PyCATSHOO évalue les conditions
   - L'automate du target voit que sa condition est satisfaite
   - La transition instantanée (`delay(0)`) se déclenche
   - Le target change d'état

**Exemple chronologique** :
```
t=0    : État initial - Tout en "rep"
t=10   : isimu_set_transition(0, date=10)
       : isimu_step_forward()
       : → ObjFM.frun__cc_1 : rep → occ
       : → ctrl_frun_C1 = True
       : C1.frun reste en "rep" (pas encore propagé)

t=10   : isimu_set_transition(0)
       : isimu_step_forward()
       : → C1.frun : rep → occ (transition instantanée)
       : C1.frun est maintenant en "occ"
```

### Nommage des entités

| Entité | Format | Exemple |
|--------|--------|---------|
| **ObjFM composant** | `{target_name}__{fm_name}` | `C1__frun` ou `CX__frun` |
| **Variables de contrôle** | `ctrl_{fm_name}_{target_name}` | `ctrl_frun_C1` |
| **Automate dans target** | `{fm_name}` | `frun` |
| **États dans target** | `{fm_name}_{failure_state}`, `{fm_name}_{repair_state}` | `frun_occ`, `frun_rep` |
| **Transitions dans target** | `{st2}`, `{st1}` | `occ`, `rep` |

### Gestion des combinaisons multi-targets

Pour un ObjFM avec `targets=["C1", "C2"]` en mode `external` :

- **Automates ObjFM** : Créés pour toutes les combinaisons (ordre 1 et 2)
  - `frun__cc_1` : Défaillance de C1 seul
  - `frun__cc_2` : Défaillance de C2 seul
  - `frun__cc_12` : Défaillance commune C1+C2

- **Automates targets** : **UN seul** par target
  - `C1.frun` : Activé par `frun__cc_1` OU `frun__cc_12`
  - `C2.frun` : Activé par `frun__cc_2` OU `frun__cc_12`

**Logique** : Un target est défaillant dès qu'UNE combinaison l'incluant est active.

### Gestion des erreurs

| Erreur | Condition | Message |
|--------|-----------|---------|
| **behaviour invalide** | `behaviour not in VALID_BEHAVIOURS` | `"behaviour must be one of ('internal', 'external', 'external_rep_indep'), got '{behaviour}'"` |
| **Conflit de nom** | Target a déjà un automate `{fm_name}` | `"Target '{target_name}' already has an automaton named '{fm_name}'. Cannot create external FM automaton."` |
| **Loi d'ordre 1 inactive** | `external_rep_indep` avec `μ_1 = 0` ou `ttr_1 = 0` | `"behaviour='external_rep_indep' requires the order-1 repair law to be active for FM '{fm_name}'. Provide a non-zero repair_param for order 1."` |

---

## Tests

### Fichiers de tests

Tests dédiés à la feature `behaviour` dans `tests/pyc_obj/obj_fm/` :

```
test_comp_failure_external_001.py        # external — création + sync 1/multi-target
test_comp_failure_external_002.py        # external — propagation des effects
test_comp_failure_external_003.py        # external — 7 combos paramétrés (3 targets)
test_comp_failure_external_004.py        # external — système réel multi-FM avec dépendances
test_comp_failure_external_rep_indep_001.py  # rep_indep — création + structure
test_comp_failure_external_rep_indep_002.py  # rep_indep — pulse 1 target
test_comp_failure_external_rep_indep_003.py  # rep_indep — multi-target combos
test_comp_failure_external_rep_indep_004.py  # rep_indep — propagation des effects
test_comp_failure_external_rep_indep_005.py  # rep_indep — repair_cond gating
test_comp_failure_external_rep_indep_006.py  # rep_indep — ObjFMDelay
test_comp_failure_external_modes_errors.py   # erreurs (behaviour invalide, conflits, ordre 1)
```

Les tests `internal` (mode par défaut) sont dans `test_comp_failure_001..013.py` et constituent la baseline de non-régression.

### Liste des tests (28 tests sur le périmètre `behaviour`)

| Test | Description | Behaviour |
|------|-------------|-----------|
| `test_external_single_automaton_created` | Création automate dans target unique | external |
| `test_external_single_synchronization` | Cycle complet 1 target (verrou mutuel) | external |
| `test_external_multi_synchronization` | Multi-target combos cc_1, cc_2, cc_12 | external |
| `test_external_effects_propagation` | failure/repair_effects appliqués via target | external |
| `test_external_3_targets_all_combos[cc_X]` | 7 combos paramétrés (cc_1..cc_123) | external |
| `test_external_dependency_system` | Système réel multi-FM avec dépendances ObjFlow2I1O | external |
| `test_rep_indep_creates_target_automaton` | Automate `frun` créé dans le target | external_rep_indep |
| `test_rep_indep_creates_ctrl_vars` | `ctrl_{fm}_{tgt}` créés, init `False` | external_rep_indep |
| `test_rep_indep_no_warning_on_effects` | Aucun warning sur effects | external_rep_indep |
| `test_rep_indep_pulse_single_target` | Cycle pulse complet (1 target) | external_rep_indep |
| `test_rep_indep_target_repair_resets_ctrl` | Reset ctrl par target.rep | external_rep_indep |
| `test_rep_indep_combo_order2_independent_repair` | cc_12 puis réparations désynchronisées | external_rep_indep |
| `test_rep_indep_partial_state_blocks_higher_order_combo` | cc_X bloqué tant qu'un target reste failed | external_rep_indep |
| `test_rep_indep_failure_effects_applied` | failure_effects appliqués (pulse + target.occ) | external_rep_indep |
| `test_rep_indep_repair_effects_applied` | repair_effects appliqués (target.rep) | external_rep_indep |
| `test_rep_indep_repair_cond_default_true` | Cond par défaut `True` | external_rep_indep |
| `test_rep_indep_repair_cond_callable_evaluated_on_target` | Cond callable réutilisée et évaluée localement | external_rep_indep |
| `test_rep_indep_objfmdelay_uses_delay_law` | ObjFMDelay → loi `delay(ttr_1)` côté target | external_rep_indep |
| `test_behaviour_invalid_raises` | Erreur `ValueError` pour behaviour invalide | - |
| `test_external_name_conflict_raises` | Conflit de nom d'automate (external) | external |
| `test_external_rep_indep_name_conflict_raises` | Conflit de nom (external_rep_indep) | external_rep_indep |
| `test_external_rep_indep_drop_inactive_order1_raises` | Loi repair ordre 1 inactive → erreur claire | external_rep_indep |

### Exécution des tests

```bash
# Périmètre complet de la feature
pytest tests/pyc_obj/obj_fm/test_comp_failure_external_*.py \
       tests/pyc_obj/obj_fm/test_comp_failure_external_modes_errors.py -v

# Mode rep_indep uniquement
pytest tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_*.py -v

# Test spécifique
pytest tests/pyc_obj/obj_fm/test_comp_failure_external_rep_indep_002.py::test_rep_indep_pulse_single_target -v

# Suite complète (régression incluse)
pytest -v
```

**Statut au 2026-04-28** : 213 tests passés / 213 (16 nouveaux tests `external_rep_indep` + erreurs, 0 régression sur `internal` et `external`).

---

## Cas d'usage

### 1. Système distribué avec visibilité locale

**Contexte** : Réseau électrique avec transformateurs répartis géographiquement.

**Besoin** : Chaque transformateur doit connaître son propre état de défaillance pour déclencher des alarmes locales.

**Solution** :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="transformer_failure",
    targets=["T1", "T2", "T3"],
    behaviour="external",
    failure_param=[0.01, 0.005, 0.001],
    repair_param=[0.1, 0.1, 0.1],
)

# Chaque transformateur a un automate "transformer_failure"
# Permet des indicateurs locaux
if system.comp["T1"].automata_d["transformer_failure"].get_state_by_name("occ")._bkd.isActive():
    trigger_local_alarm("T1")
```

### 2. Maintenance décentralisée

**Contexte** : Flotte de véhicules avec équipes de maintenance sur plusieurs sites.

**Besoin** : Chaque véhicule est réparé localement selon la disponibilité de l'équipe locale.

**Solution** :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="engine_failure",
    targets=["Vehicle1", "Vehicle2", "Vehicle3"],
    behaviour="external_rep_indep",
    failure_param=0.005,   # Défaillances communes (même modèle)
    repair_param=0.2,      # MTTR moyen = 5 heures par site
)

# Chaque véhicule se répare indépendamment
# Permet de modéliser des délais de réparation variables
```

### 3. Analyse de fiabilité avec indicateurs d'état

**Contexte** : Système de refroidissement avec plusieurs unités.

**Besoin** : Calculer la disponibilité instantanée du système (au moins N unités opérationnelles).

**Solution** :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="cooling_failure",
    targets=["Unit1", "Unit2", "Unit3", "Unit4"],
    behaviour="external",
    failure_param=[0.01] * 4,
    repair_param=[0.5] * 4,
)

# Créer un indicateur personnalisé
def check_system_operational():
    operational_count = sum(
        1 for unit in ["Unit1", "Unit2", "Unit3", "Unit4"]
        if system.comp[unit].automata_d["cooling_failure"].get_state_by_name("rep")._bkd.isActive()
    )
    return operational_count >= 2  # Au moins 2 unités opérationnelles

# Utiliser dans un PycFunIndicator
```

### 4. Modélisation de causes communes progressives

**Contexte** : Composants soumis à une dégradation environnementale commune.

**Besoin** : La défaillance se propage progressivement, mais les réparations sont indépendantes.

**Solution** :
```python
system.add_component(
    cls="ObjFMDelay",
    fm_name="corrosion",
    targets=["Pipe1", "Pipe2", "Pipe3"],
    behaviour="external_rep_indep",
    failure_param=1000,    # Délai de 1000h pour défaillance
    repair_param=10,       # Délai de réparation : 10h
)

# La corrosion affecte tous les tuyaux au même moment (1000h)
# Mais chaque tuyau est réparé indépendamment (10h chacun)
```

---

## Migration et compatibilité

### Rétrocompatibilité

**Garantie** : Le comportement par défaut (`behaviour="internal"`) est **strictement identique** au comportement avant l'ajout de cette fonctionnalité.

**Code existant** : Aucune modification requise. Le code existant continue de fonctionner sans changement.

```python
# Code existant (avant)
system.add_component(
    cls="ObjFMExp",
    fm_name="frun",
    targets=["C1"],
    failure_effects={"flow_in_max": 3},
    failure_param=0.1,
    repair_param=0.1,
)

# Code existant (après) - FONCTIONNE À L'IDENTIQUE
system.add_component(
    cls="ObjFMExp",
    fm_name="frun",
    targets=["C1"],
    failure_effects={"flow_in_max": 3},
    failure_param=0.1,
    repair_param=0.1,
    # behaviour="internal" est implicite
)
```

### Migration vers external / external_rep_indep

Pour migrer un ObjFM existant vers `behaviour="external"` ou `"external_rep_indep"` :

1. **Ajouter `behaviour="external"` ou `"external_rep_indep"`**
2. **Conserver `failure_effects` / `repair_effects` tels quels** — ils continuent de fonctionner et sont simplement appliqués via l'automate du target (révision 2026-04-28).
3. **Pour `external_rep_indep` uniquement** : vérifier que la loi de réparation d'ordre 1 est active (μ_1 > 0 ou ttr_1 > 0). Sinon une `ValueError` est levée à la construction.

**Avant** :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="pump_failure",
    targets=["Pump1"],
    failure_effects={"flow_out": 0},
    failure_param=0.01,
    repair_param=0.1,
)
```

**Après (mode external)** — verrou mutuel ObjFM/target, effects préservés :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="pump_failure",
    targets=["Pump1"],
    behaviour="external",
    failure_effects={"flow_out": 0},   # toujours pris en compte
    repair_effects={"flow_out": 1.0},  # idem
    failure_param=0.01,
    repair_param=0.1,
)

# L'état de la défaillance est désormais accessible directement sur le target :
# system.comp["Pump1"].automata_d["pump_failure"].get_state_by_name("occ")._bkd.isActive()
```

**Après (mode external_rep_indep)** — pulse + réparations indépendantes :
```python
system.add_component(
    cls="ObjFMExp",
    fm_name="pump_failure",
    targets=["Pump1"],
    behaviour="external_rep_indep",
    failure_effects={"flow_out": 0},
    repair_effects={"flow_out": 1.0},
    failure_param=0.01,
    repair_param=0.1,   # μ_1 obligatoirement > 0
)
```

### Versioning

| Version COD3S | Statut |
|---------------|--------|
| ≤ 1.0.32 | Pas de paramètre `behaviour`, comportement « internal » implicite |
| 1.0.33 | Paramètre `behaviour` introduit (mode `external` opérationnel ; `external_rep_indep` partiellement implémenté avec un TODO sur la `repair_cond` et aucun test) |
| 1.1.0 (à publier) | `external_rep_indep` finalisé en modèle pulse, refactor du mécanisme `ctrl_var` (méthode sensible toujours utilisée pour `external` ; effets directs sur transitions pour `external_rep_indep`), spec et tests alignés (28 tests sur le périmètre `behaviour`, 213 tests verts au total) |

---

## Références

### Fichiers modifiés

- **`cod3s/pycatshoo/component.py`** : Classe `ObjFM` étendue

### Fichiers non modifiés (compatibles)

- `cod3s/pycatshoo/automaton.py` : Utilisé tel quel
- `cod3s/pycatshoo/system.py` : Utilisé tel quel
- Toutes les sous-classes de `ObjFM` : `ObjFMExp`, `ObjFMDelay`

### Documentation associée

- `README.md` : Documentation du projet (à mettre à jour)

---

## Annexes

### A. Diagramme des behaviours

```
                    ┌─────────────────────────────────────────────┐
                    │              ObjFM                          │
                    │   behaviour = "internal" | "external" |     │
                    │              "external_rep_indep"           │
                    └─────────────────────────────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
┌─────────────────┐      ┌─────────────────────┐      ┌──────────────────────┐
│    internal     │      │      external       │      │  external_rep_indep  │
├─────────────────┤      ├─────────────────────┤      ├──────────────────────┤
│ Automate: ObjFM │      │ Automate: ObjFM     │      │ Automate: ObjFM      │
│ Effects: targets│      │ Effects: ctrl_vars  │      │ Effects: ctrl_vars   │
│                 │      │                     │      │ (failure only)       │
│ Target: pas     │      │ Automate: Target    │      │                      │
│ d'automate      │      │ Sync: failure+repair│      │ Automate: Target     │
│                 │      │ via ctrl_var        │      │ Sync failure: ctrl   │
│                 │      │ (instantané)        │      │ Repair: loi propre   │
│                 │      │                     │      │ (exp/delay ObjFM)    │
└─────────────────┘      └─────────────────────┘      └──────────────────────┘
```

### B. Tableau comparatif complet

| Caractéristique | internal | external | external_rep_indep |
|-----------------|----------|----------|-------------------|
| **Automate ObjFM** | ✓ | ✓ | ✓ |
| **Automate Target** | ✗ | ✓ | ✓ |
| **Variable contrôle** | ✗ | ✓ | ✓ |
| **failure_effects** | ✓ Appliqués | ✗ Ignorés | ✗ Ignorés |
| **repair_effects** | ✓ Appliqués | ✗ Ignorés | ✗ Ignorés |
| **Défaillance controlée par** | ObjFM | ObjFM via ctrl_var | ObjFM via ctrl_var |
| **Réparation contrôlée par** | ObjFM | ObjFM via ctrl_var | **Target (indépendant)** |
| **Loi repair target** | N/A | delay(0) | exp(mu) ou delay(ttr) |
| **Visibilité état local** | ✗ | ✓ | ✓ |
| **Réparations simultanées** | ✓ | ✓ | ✗ |
| **Use case typique** | Modélisation simple | Visibilité distribuée | Maintenance décentralisée |

---

**Fin de la spécification**
