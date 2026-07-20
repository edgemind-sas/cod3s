"""Multi-state degradation mode primitive (``ObjDegMode``).

Generalises the two-state ``ObjFM`` failure modes into a linear
degradation chain ``healthy -> D1 -> ... -> Dn``:

* progression goes through every state in order; the last state is
  absorbing except for repair;
* repair jumps straight back to the healthy state, with one law and one
  optional condition per departure state (``rep_law=None`` = no repair
  edge from that state; a fully repair-less mode is a valid
  run-to-failure model);
* common cause (CC) only drives the FIRST transition
  (healthy -> D1): an order-k CC event moves k targets simultaneously
  (``lambda_k`` vector, 2^N-1 combination automata on the carrier
  component); progression beyond D1 and repairs are strictly individual;
* behaviour is the ``external_rep_indep`` trigger model, always: the
  carrier only latches a per-target boolean ``ctrl``; each target hosts
  its own K+1-state automaton whose healthy->D1 edge is a ``delay(0)``
  guarded by ``ctrl`` ONLY (the whole entry gating — global occurrence
  condition and all-targets-healthy — happens once, in the carrier
  combination guard; re-testing it on the target edge would strand
  latches when a co-target's D1 effects flip the condition within the
  same fixpoint pass);
* the first-state entry law is exponential ONLY. Two distinct
  combinations eligible at the exact same date both fire in the same
  PyCATSHOO batch without guard re-evaluation between them (spike
  2026-07-20), so correctness relies on same-date ties having measure
  zero — true for exp, false for delay. Deeper transitions accept exp
  or delay.

Event grammar (the downstream sequence-parsing contract):

* carrier CC fire: ``<carrier>.occ_<state1>__cc_<i>_<j>...`` (1-based
  indices, underscore-separated; order = number of indices). For a
  single-target mode the suffix is empty (``<carrier>.occ_<state1>``).
* target progression: ``<target>.<fm_name>__occ_<state>``;
* target repair: ``<target>.<fm_name>__rep_<departure state>``;
* the carrier re-arm edge is an ``inst p=1`` transition silenced with a
  never-match monitor mask (out-state masks only apply to inst
  transitions — a ``delay(0)`` re-arm would show up in sequences).

Each target also carries an integer level variable ``<fm_name>_level``
(0 = healthy ... K), maintained by state clamps — the support for
indicators and inter-component conditions.
"""

import copy
import itertools
import re
import typing

import pydantic

import Pycatshoo as pyc

from ..utils import get_operator_function
from .common import prepare_attr_tree, sanitize_cond_format
from .component import ObjFM, PycComponent
from .fm_wiring import FmWiringMixin, cc_comb_suffix, order_param_name

DEFAULT_HEALTHY_STATE = "sain"

_NEVER_MATCH_MASK = "#$^"

# ASCII, no dot, no double underscore (the ``__cc_`` suffix and the
# ``<fm_name>__`` prefix structure event names; a ``__`` inside a state
# name would break their parsing), no leading/trailing underscore.
_STATE_NAME_RE = re.compile(r"^[A-Za-z0-9]+(_[A-Za-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Law specs (discriminated union on ``cls``)
# ---------------------------------------------------------------------------


class DegLawExp(pydantic.BaseModel):
    """Exponential occurrence law (rate per unit of time)."""

    model_config = pydantic.ConfigDict(extra="forbid")

    cls: typing.Literal["exp"] = "exp"
    rate: float | list[float] = pydantic.Field(
        ...,
        description=(
            "Rate (lambda / mu). A list is only meaningful on the FIRST "
            "state's occ_law: lambda_k vector indexed by CC order "
            "(len == number of targets, strict)."
        ),
    )


class DegLawDelay(pydantic.BaseModel):
    """Deterministic delay occurrence law."""

    model_config = pydantic.ConfigDict(extra="forbid")

    cls: typing.Literal["delay"] = "delay"
    time: float = pydantic.Field(..., ge=0, description="Deterministic delay.")


DegLaw = typing.Annotated[
    typing.Union[DegLawExp, DegLawDelay], pydantic.Field(discriminator="cls")
]


class DegState(pydantic.BaseModel):
    """One degraded state of the chain, with everything that concerns it.

    State-centric declaration: entry (occ_*), stay (effects), repair
    back to healthy (rep_*). Accepts bare dicts everywhere (wire-format
    friendly: the constructor kwargs survive a YAML -> model_dump ->
    constructor round trip).
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    name: str = pydantic.Field(..., description="State name (event-grammar safe).")

    occ_law: DegLaw = pydantic.Field(
        ..., description="Entry law (from the previous state in the chain)."
    )
    occ_cond: typing.Any = pydantic.Field(
        True,
        description=(
            "Local entry condition, ANDed with the mode's global occ_cond. "
            "bool | callable (Python API only) | structured condition tree."
        ),
    )
    occ_effects_trans: dict[str, typing.Any] = pydantic.Field(
        default_factory=dict,
        description="One-shot pulse effects fired when the entry edge fires.",
    )

    effects: dict[str, typing.Any] = pydantic.Field(
        default_factory=dict,
        description=(
            "State-based effects (level clamp re-applied while the state "
            "is active). Full set per state: no cumulative inheritance."
        ),
    )

    rep_law: typing.Optional[DegLaw] = pydantic.Field(
        None,
        description=(
            "Repair law (this state -> healthy). None = no repair edge "
            "from this state."
        ),
    )
    rep_cond: typing.Any = pydantic.Field(
        True, description="Repair condition. Same shapes as occ_cond."
    )
    rep_effects_trans: dict[str, typing.Any] = pydantic.Field(
        default_factory=dict,
        description="One-shot pulse effects fired when the repair edge fires.",
    )

    def __init__(self, name=None, /, **data):
        if name is not None:
            data["name"] = name
        super().__init__(**data)


# ---------------------------------------------------------------------------
# Condition compilation (per transition, per target)
# ---------------------------------------------------------------------------


def compile_condition(cond, target_comp, system, inner_logic=all, outer_logic=any):
    """Compile a condition into a zero-arg callable evaluated on one target.

    Accepted shapes (same as ObjFM's failure_cond/repair_cond):

    * ``bool`` — constant;
    * callable — used as-is (Python API only, not wire-serialisable);
    * structured tree (list of lists of ``{"attr", "value", "ope",
      "obj"?}`` dicts) — outer level ORed (``outer_logic``), inner level
      ANDed (``inner_logic``), attributes resolved on ``target_comp`` by
      default.
    """
    if isinstance(cond, list):
        tree = prepare_attr_tree(
            sanitize_cond_format(cond), obj_default=target_comp, system=system
        )

        def cond_fun():
            return outer_logic(
                inner_logic(
                    get_operator_function(c_inner.get("ope", "=="))(
                        getattr(c_inner["attr"], c_inner["attr_val_name"])(),
                        c_inner["value"],
                    )
                    for c_inner in c_outer
                )
                for c_outer in tree
            )

        return cond_fun

    if callable(cond):
        return cond

    return (lambda: True) if cond else (lambda: False)


def _and_conds(*conds):
    """AND a list of zero-arg callables (short-circuiting)."""
    active = [c for c in conds if c is not None]

    def combined():
        return all(c() for c in active)

    return combined


# ---------------------------------------------------------------------------
# ObjDegMode
# ---------------------------------------------------------------------------

# FailureModeBaseSpec fields that have no ObjDegMode meaning: accepted
# when they carry their BaseSpec default (they always travel through the
# ObjFMGenericSpec wire path — ``model_dump`` emits defaults), rejected
# with a clear error on any explicit non-default value (never silently
# ignored).
_BASESPEC_PASSTHROUGH_DEFAULTS: dict[str, tuple] = {
    "failure_state": ("occ",),
    "repair_state": ("rep",),
    "failure_effects": (None, {}),
    "failure_effects_trans": (None, {}),
    "repair_cond": (None, True),
    "repair_effects": (None, {}),
    "repair_effects_trans": (None, {}),
    "failure_param_name": (None, [], ""),
    "repair_param_name": (None, [], ""),
    "failure_param": (None, []),
    "repair_param": (None, []),
}


class ObjDegMode(FmWiringMixin, PycComponent):
    """Multi-state degradation mode (see module docstring).

    Python API::

        ObjDegMode(
            fm_name="Fissure",
            targets=["Rail_1", "Rail_2"],
            occ_cond=[...],                      # global gate
            states=[
                DegState("O",
                    occ_law={"cls": "exp", "rate": [l1, l2]},  # lambda_k
                    effects={"Etat_O": True},
                    rep_law={"cls": "exp", "rate": mu_O}),
                DegState("X1", occ_law={"cls": "exp", "rate": l_x1}),
                DegState("X2", occ_law={"cls": "delay", "time": ttf}),
            ],
        )

    Wire path: ``register_fm_class("ObjDegMode", ObjDegMode)`` +
    ``ObjFMGenericSpec`` (``cls: ObjDegMode`` + ``states`` / ``occ_cond``
    as extra fields).
    """

    def __init__(
        self,
        fm_name,
        targets=None,
        states=None,
        occ_cond=True,
        target_name=None,
        healthy_state=DEFAULT_HEALTHY_STATE,
        drop_inactive_automata=True,
        cond_inner_logic=all,
        cond_outer_logic=any,
        step=None,
        # --- FailureModeBaseSpec compatibility (ObjFMGenericSpec path) ---
        failure_cond=None,
        behaviour=None,
        **kwargs,
    ):
        # ---- BaseSpec compatibility table (never silently ignore) ----
        for key, accepted in _BASESPEC_PASSTHROUGH_DEFAULTS.items():
            if key in kwargs:
                value = kwargs.pop(key)
                if not any(value == acc for acc in accepted):
                    raise ValueError(
                        f"ObjDegMode {fm_name!r}: field {key!r}={value!r} has no "
                        f"meaning for a degradation mode (it belongs to the "
                        f"two-state ObjFM API). Use the ObjDegMode fields "
                        f"(states / occ_cond) instead."
                    )
        if kwargs:
            raise TypeError(
                f"ObjDegMode {fm_name!r}: unexpected keyword arguments "
                f"{sorted(kwargs)}. Known fields: fm_name, targets, states, "
                f"occ_cond, target_name, healthy_state, "
                f"drop_inactive_automata, cond_inner_logic, cond_outer_logic, "
                f"step (+ tolerated FailureModeBaseSpec defaults)."
            )
        if behaviour not in (None, "internal", "external_rep_indep"):
            # "internal" is the BaseSpec Pydantic default: after model_dump
            # it is indistinguishable from an unset field, so it is treated
            # as unset (documented limitation). Anything else explicit is a
            # modelling error: ObjDegMode is structurally external_rep_indep.
            raise ValueError(
                f"ObjDegMode {fm_name!r}: behaviour={behaviour!r} is not "
                f"supported. ObjDegMode always behaves as "
                f"'external_rep_indep' (trigger carrier + independent "
                f"per-target repair)."
            )
        if failure_cond is not None and failure_cond is not True:
            # Wire alias of the global occ_cond.
            if occ_cond is not True:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: both occ_cond and failure_cond "
                    f"are set; failure_cond is only the wire alias of "
                    f"occ_cond — set exactly one."
                )
            occ_cond = failure_cond

        # ---- normalisation + fail-fast validation (before any build) ----
        if not fm_name or not isinstance(fm_name, str):
            raise ValueError("ObjDegMode: fm_name must be a non-empty string.")
        targets = [targets] if isinstance(targets, str) else list(targets or [])
        if not targets:
            raise ValueError(f"ObjDegMode {fm_name!r}: targets must be non-empty.")
        if len(set(targets)) != len(targets):
            raise ValueError(f"ObjDegMode {fm_name!r}: duplicated targets {targets}.")

        if not states:
            raise ValueError(
                f"ObjDegMode {fm_name!r}: states must be a non-empty ordered "
                f"list of degraded states (the healthy state is implicit)."
            )
        states = [st if isinstance(st, DegState) else DegState(**st) for st in states]

        if not _STATE_NAME_RE.match(healthy_state):
            raise ValueError(
                f"ObjDegMode {fm_name!r}: invalid healthy_state name "
                f"{healthy_state!r} (ASCII, no '.', no '__')."
            )
        seen = set()
        for st in states:
            if not _STATE_NAME_RE.match(st.name):
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: invalid state name {st.name!r} "
                    f"(ASCII [A-Za-z0-9_], no '.', no '__', no edge '_')."
                )
            if st.name == healthy_state:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: state name {st.name!r} collides "
                    f"with the healthy state."
                )
            if st.name in seen:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: duplicated state name {st.name!r}."
                )
            seen.add(st.name)

        order_max = len(targets)

        # First state: exp only, lambda_k vector strict.
        first = states[0]
        if not isinstance(first.occ_law, DegLawExp):
            raise ValueError(
                f"ObjDegMode {fm_name!r}: the first state's occ_law must be "
                f"exponential (got {first.occ_law.cls!r}). Two combinations "
                f"eligible at the exact same date both fire (no guard "
                f"re-evaluation inside a PyCATSHOO batch): correctness of the "
                f"CC entry relies on same-date ties having measure zero, "
                f"which only holds for exp."
            )
        rate = first.occ_law.rate
        if isinstance(rate, list):
            if len(rate) != order_max:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: lambda_k vector of the first "
                    f"state has length {len(rate)}, expected exactly "
                    f"{order_max} (one rate per CC order, no silent padding). "
                    f"Use 0 to deactivate an order explicitly."
                )
            lambda_by_order = [float(v) for v in rate]
        else:
            # Scalar = order 1 only, higher orders explicitly inactive.
            lambda_by_order = [float(rate)] + [0.0] * (order_max - 1)

        # Deeper states: scalar laws only (progression and repair are
        # strictly individual).
        for st in states[1:]:
            if isinstance(st.occ_law, DegLawExp) and isinstance(st.occ_law.rate, list):
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: state {st.name!r} occ_law rate "
                    f"must be a scalar (lambda_k vectors only apply to the "
                    f"first state's CC entry)."
                )
        for st in states:
            if (
                st.rep_law is not None
                and isinstance(st.rep_law, DegLawExp)
                and isinstance(st.rep_law.rate, list)
            ):
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: state {st.name!r} rep_law rate "
                    f"must be a scalar (repair is individual, order 1 only)."
                )

        for st in states:
            if st.rep_law is None and st.rep_effects_trans:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: state {st.name!r} declares "
                    f"rep_effects_trans but has no rep_law (no repair edge "
                    f"to carry the pulse)."
                )

        # state_based vs trans_based overlap: a clamp from ANY state would
        # silently overwrite a pulse on the same variable.
        clamp_vars = set().union(*(st.effects.keys() for st in states))
        pulse_vars = set().union(
            *(st.occ_effects_trans.keys() for st in states),
            *(st.rep_effects_trans.keys() for st in states),
        )
        overlap = clamp_vars & pulse_vars
        if overlap:
            raise ValueError(
                f"ObjDegMode {fm_name!r}: variables {sorted(overlap)} are "
                f"driven by BOTH state-based (effects) and trans-based "
                f"(occ/rep_effects_trans) effects. A level clamp re-applied "
                f"while its state is active silently overwrites a one-shot "
                f"pulse. Use distinct variables."
            )

        self.fm_name = fm_name
        self.targets = targets
        if target_name is None and len(targets) == 1:
            target_name = targets[0]
        self.target_name = target_name or ObjFM._factorize_target_names(targets)
        self.healthy_state = healthy_state
        self.states = copy.deepcopy(states)
        self.occ_cond = copy.deepcopy(occ_cond)
        self.drop_inactive_automata = drop_inactive_automata
        self.cond_inner_logic = cond_inner_logic
        self.cond_outer_logic = cond_outer_logic
        self.lambda_by_order = lambda_by_order

        comp_name = f"{self.target_name}__{self.fm_name}"
        super().__init__(comp_name)

        if isinstance(step, str):
            step_name = step
            step = self.system().step(step_name)
            if step is None:
                raise ValueError(f"Step {step_name} does not exist in this system")
        self.step = step

        # Monitor masks registered before any automaton build; the study
        # runner re-applies them after ``monitorTransition`` via the
        # duck-typed ``reapply_monitor_masks`` hook (ObjFMInst precedent).
        self._monitor_masks = []

        # ---- resolve targets (fail fast, clear message) ----
        target_comps = {}
        for tn in self.targets:
            try:
                comp = self.system().component(tn)
            except Exception:
                comp = None
            if comp is None:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: target component {tn!r} not "
                    f"found in the system (declare targets before the mode)."
                )
            existing_auts = [aut.basename() for aut in comp.automata()]
            if self.fm_name in existing_auts:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: target {tn!r} already hosts an "
                    f"automaton named {self.fm_name!r} (another mode with the "
                    f"same name?)."
                )
            target_comps[tn] = comp

        # ---- ctrl latches + per-target level variables ----
        self.ctrl_vars = {}
        for tn in self.targets:
            ctrl = self.addVariable(
                f"ctrl_{self.fm_name}_{tn}", pyc.TVarType.t_bool, False
            )
            ctrl.setReinitialized(True)
            self.ctrl_vars[tn] = ctrl

        level_var_name = f"{self.fm_name}_level"
        self.level_vars = {}
        for tn, comp in target_comps.items():
            if level_var_name in [v.basename() for v in comp.variables()]:
                raise ValueError(
                    f"ObjDegMode {fm_name!r}: target {tn!r} already has a "
                    f"variable named {level_var_name!r}."
                )
            level = comp.addVariable(level_var_name, pyc.TVarType.t_int, 0)
            level.setReinitialized(True)
            self.level_vars[tn] = level

        # ---- parameter variables (all hosted on the carrier) ----
        # First state (CC entry): lambda_<state1>[__<k>_o_<N>] per order.
        self.var_params = {}
        first_name = first.name
        self.lambda_vars_by_order = []
        for order in range(1, order_max + 1):
            pname = order_param_name(f"lambda_{first_name}", order, order_max)
            var = self.addVariable(
                pname, pyc.TVarType.t_double, lambda_by_order[order - 1]
            )
            self.var_params[pname] = var
            self.lambda_vars_by_order.append(var)

        # Deeper states: lambda_<state>/ttf_<state>; repairs mu_<state>/ttr_<state>.
        self._occ_param_vars = {}
        self._rep_param_vars = {}
        for st in states[1:]:
            if isinstance(st.occ_law, DegLawExp):
                pname, value = f"lambda_{st.name}", float(st.occ_law.rate)
            else:
                pname, value = f"ttf_{st.name}", float(st.occ_law.time)
            var = self.addVariable(pname, pyc.TVarType.t_double, value)
            self.var_params[pname] = var
            self._occ_param_vars[st.name] = var
        for st in states:
            if st.rep_law is None:
                continue
            if isinstance(st.rep_law, DegLawExp):
                pname, value = f"mu_{st.name}", float(st.rep_law.rate)
            else:
                pname, value = f"ttr_{st.name}", float(st.rep_law.time)
            var = self.addVariable(pname, pyc.TVarType.t_double, value)
            self.var_params[pname] = var
            self._rep_param_vars[st.name] = var

        # ---- carrier: one 2-state trigger automaton per active combination ----
        self._build_carrier(target_comps)

        # ---- targets: one K+1-state degradation automaton each ----
        for tn, comp in target_comps.items():
            self._build_target_automaton(tn, comp)

        self.reapply_monitor_masks()

    # ------------------------------------------------------------------
    # carrier
    # ------------------------------------------------------------------

    def _build_carrier(self, target_comps):
        first = self.states[0]
        order_max = len(self.targets)
        self.carrier_automata = []

        for order in range(1, order_max + 1):
            lambda_var = self.lambda_vars_by_order[order - 1]
            if self.drop_inactive_automata and lambda_var.value() == 0:
                continue

            for target_set_idx in itertools.combinations(range(order_max), order):
                suffix = cc_comb_suffix(target_set_idx, order_max)
                fire_name = f"occ_{first.name}{suffix}"
                aut_name = f"{self.fm_name}{suffix}"
                ready, fired = f"ready{suffix}", f"fired{suffix}"

                aut = self.add_automaton(
                    name=aut_name,
                    states=[ready, fired],
                    init_state=ready,
                    transitions=[
                        {
                            "name": fire_name,
                            "source": ready,
                            "target": fired,
                            # Float baked here; re-bound to the lambda
                            # variable right after (runtime overrides).
                            "occ_law": {"cls": "exp", "rate": lambda_var.value()},
                        },
                        {
                            "name": f"rearm{suffix}",
                            "source": fired,
                            "target": ready,
                            # inst p=1: drains with priority at the same
                            # instant AND is maskable (out-state masks only
                            # apply to inst transitions). ObjFMInst re-arm
                            # precedent.
                            "occ_law": {"cls": "inst", "probs": [1]},
                        },
                    ],
                )

                combo_targets = [self.targets[i] for i in target_set_idx]
                combo_comps = [target_comps[tn] for tn in combo_targets]

                # Guard: all combo targets healthy AND global occ_cond AND
                # first-state local occ_cond — everything evaluated HERE,
                # once, at fire time (the target edge only tests ctrl).
                healthy_conds = []
                for comp in combo_comps:
                    healthy_conds.append(self._make_healthy_cond(comp))
                global_conds = [
                    compile_condition(
                        self.occ_cond,
                        comp,
                        self.system(),
                        inner_logic=self.cond_inner_logic,
                        outer_logic=self.cond_outer_logic,
                    )
                    for comp in combo_comps
                ] + [
                    compile_condition(
                        first.occ_cond,
                        comp,
                        self.system(),
                        inner_logic=self.cond_inner_logic,
                        outer_logic=self.cond_outer_logic,
                    )
                    for comp in combo_comps
                ]
                fire_bkd = aut.get_transition_by_name(fire_name)._bkd
                fire_bkd.setCondition(_and_conds(*healthy_conds, *global_conds))

                # Re-bind the exp law to the per-order lambda variable.
                fire_bkd.distLaw().setParameter(lambda_var, 0)

                # Latch the ctrl of each combo target while 'fired' is
                # active (transient state, consumed by the targets).
                latch_records = [
                    {"var": self.ctrl_vars[tn], "value": True} for tn in combo_targets
                ]
                self._wire_state_effects(
                    aut, fired, latch_records, trans_name=fire_name
                )

                # Silence the re-arm edge in sequences.
                rearm_bkd = aut.get_transition_by_name(f"rearm{suffix}")._bkd
                self._monitor_masks.append((rearm_bkd, _NEVER_MATCH_MASK))

                self.carrier_automata.append(aut)

    def _make_healthy_cond(self, comp):
        """Return a callable: True when ``comp``'s degradation automaton
        (this mode's) is in the healthy state."""
        aut_name = self.fm_name
        healthy_full = f"{self.fm_name}__{self.healthy_state}"

        def cond():
            aut = comp.automata_d.get(aut_name)
            if aut is None:
                # Target automata are built after the carrier: during
                # construction this guard is never evaluated (no
                # simulation yet), so a defensive False keeps semantics.
                return False
            return aut.get_state_by_name(healthy_full)._bkd.isActive()

        return cond

    # ------------------------------------------------------------------
    # target automaton
    # ------------------------------------------------------------------

    def _build_target_automaton(self, tn, comp):
        prefixed = lambda st: f"{self.fm_name}__{st}"  # noqa: E731
        healthy = prefixed(self.healthy_state)
        state_names = [healthy] + [prefixed(st.name) for st in self.states]

        ctrl = self.ctrl_vars[tn]
        level = self.level_vars[tn]

        transitions = []
        # Entry edge: delay(0), guarded by ctrl ONLY (see module docstring).
        first = self.states[0]
        entry_name = f"{self.fm_name}__occ_{first.name}"
        transitions.append(
            {
                "name": entry_name,
                "source": healthy,
                "target": prefixed(first.name),
                "occ_law": {"cls": "delay", "time": 0},
            }
        )
        # Progressions.
        for prev, st in zip(self.states, self.states[1:]):
            law = (
                {"cls": "exp", "rate": float(st.occ_law.rate)}
                if isinstance(st.occ_law, DegLawExp)
                else {"cls": "delay", "time": float(st.occ_law.time)}
            )
            transitions.append(
                {
                    "name": f"{self.fm_name}__occ_{st.name}",
                    "source": prefixed(prev.name),
                    "target": prefixed(st.name),
                    "occ_law": law,
                }
            )
        # Repairs (jump back to healthy).
        for st in self.states:
            if st.rep_law is None:
                continue
            law = (
                {"cls": "exp", "rate": float(st.rep_law.rate)}
                if isinstance(st.rep_law, DegLawExp)
                else {"cls": "delay", "time": float(st.rep_law.time)}
            )
            transitions.append(
                {
                    "name": f"{self.fm_name}__rep_{st.name}",
                    "source": prefixed(st.name),
                    "target": healthy,
                    "occ_law": law,
                }
            )

        aut = comp.add_automaton(
            name=self.fm_name,
            states=state_names,
            init_state=healthy,
            transitions=transitions,
        )

        # -- conditions --
        aut.get_transition_by_name(entry_name)._bkd.setCondition(
            lambda: ctrl.value() is True
        )
        global_cond = compile_condition(
            self.occ_cond,
            comp,
            self.system(),
            inner_logic=self.cond_inner_logic,
            outer_logic=self.cond_outer_logic,
        )
        for st in self.states[1:]:
            local = compile_condition(
                st.occ_cond,
                comp,
                self.system(),
                inner_logic=self.cond_inner_logic,
                outer_logic=self.cond_outer_logic,
            )
            aut.get_transition_by_name(
                f"{self.fm_name}__occ_{st.name}"
            )._bkd.setCondition(_and_conds(global_cond, local))
        for st in self.states:
            if st.rep_law is None:
                continue
            rep_cond = compile_condition(
                st.rep_cond,
                comp,
                self.system(),
                inner_logic=self.cond_inner_logic,
                outer_logic=self.cond_outer_logic,
            )
            aut.get_transition_by_name(
                f"{self.fm_name}__rep_{st.name}"
            )._bkd.setCondition(rep_cond)

        # -- re-bind laws to carrier parameter variables --
        for st in self.states[1:]:
            trans_bkd = aut.get_transition_by_name(
                f"{self.fm_name}__occ_{st.name}"
            )._bkd
            trans_bkd.distLaw().setParameter(self._occ_param_vars[st.name], 0)
        for st in self.states:
            if st.rep_law is None:
                continue
            trans_bkd = aut.get_transition_by_name(
                f"{self.fm_name}__rep_{st.name}"
            )._bkd
            trans_bkd.distLaw().setParameter(self._rep_param_vars[st.name], 0)

        # -- ctrl consumption / orphan-latch purge (defence in depth) --
        # Sensitive method on the AUTOMATON (never an effects_st on the
        # variable — ObjFM l.1983 precedent): the latch is cleared as soon
        # as the target is not healthy, so an orphan latch cannot survive
        # structurally.
        healthy_bkd = aut.get_state_by_name(healthy)._bkd

        def purge_ctrl():
            if not healthy_bkd.isActive() and ctrl.value() is True:
                ctrl.setValue(False)

        purge_name = f"purge_ctrl__{self.fm_name}__{tn}"
        aut._bkd.addSensitiveMethod(purge_name, purge_ctrl)
        ctrl.addSensitiveMethod(purge_name, purge_ctrl)

        # -- level variable clamps (self-healing: registered on the
        # automaton AND the variable AND as start method) --
        self._wire_state_effects(
            aut, healthy, [{"var": level, "value": 0}], trans_name=f"level0_{tn}"
        )
        for k, st in enumerate(self.states, start=1):
            self._wire_state_effects(
                aut,
                prefixed(st.name),
                [{"var": level, "value": k}],
                trans_name=f"level{k}_{tn}",
            )

        # -- user effects --
        for st in self.states:
            if st.effects:
                records = self._resolve_target_effects(
                    comp, tn, st.effects, kind=f"effects[{st.name}]"
                )
                self._wire_state_effects(
                    aut,
                    prefixed(st.name),
                    records,
                    trans_name=f"{self.fm_name}__occ_{st.name}",
                )
            if st.occ_effects_trans:
                records = self._resolve_target_effects(
                    comp, tn, st.occ_effects_trans, kind=f"occ_effects_trans[{st.name}]"
                )
                self._wire_transition_effects(
                    aut, f"{self.fm_name}__occ_{st.name}", records
                )
            if st.rep_law is not None and st.rep_effects_trans:
                records = self._resolve_target_effects(
                    comp, tn, st.rep_effects_trans, kind=f"rep_effects_trans[{st.name}]"
                )
                self._wire_transition_effects(
                    aut, f"{self.fm_name}__rep_{st.name}", records
                )

    # ------------------------------------------------------------------
    # monitoring
    # ------------------------------------------------------------------

    def reapply_monitor_masks(self):
        """(Re-)apply the out-state monitoring masks of this mode.

        Called at construction, and again by the study runner *after*
        ``monitorTransition`` patterns are applied (duck-typed hook shared
        with ObjFMInst) — monitoring a transition may reset its out-state
        mask, and the masks are what keeps the carrier re-arm edges out
        of the recorded sequences.
        """
        for trans_bkd, mask in self._monitor_masks:
            trans_bkd.setMonitoredOutStateMask(mask)
