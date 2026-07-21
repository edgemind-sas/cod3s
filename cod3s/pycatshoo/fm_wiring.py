"""Shared failure-mode wiring bricks.

This module hosts the pieces of the ObjFM machinery that are not tied to
the two-state (occ/rep) automaton topology, so that other failure-mode
primitives (e.g. a multi-state degradation mode) can reuse them without
inheriting from ``ObjFM``:

* pure helpers for the common-cause (CCF) combinatorics naming — the
  ``__cc_<i>_<j>`` transition suffixes and the per-order parameter names
  ``<base>__<order>_o_<order_max>``;
* ``FmWiringMixin`` — effect resolution and wiring (state-entry level
  clamps and transition-edge one-shot pulses) usable by any
  ``PycComponent`` subclass.

Extracted from ``ObjFM`` / ``ObjFMInst`` (pure movement, signatures and
behaviour preserved — the obj_fm test suite is the oracle).
"""

DEFAULT_ORDER_PARAM_PREFIX = "__{order}_o_{order_max}"
DEFAULT_CC_TRANS_PREFIX = "__cc_{target_comb_u}"


def order_param_name(base, order, order_max, fmt=DEFAULT_ORDER_PARAM_PREFIX):
    """Return the per-order parameter variable name.

    Single-target FMs (``order_max == 1``) keep the bare ``base`` name
    (no suffix), matching the historical ObjFM behaviour.
    """
    if order_max <= 1:
        return base
    return base + fmt.format(order=order, order_max=order_max)


def cc_comb_suffix(
    target_set_idx,
    order_max,
    trans_name_prefix=DEFAULT_CC_TRANS_PREFIX,
    trans_name_prefix_fun=None,
):
    """Return the combination suffix appended to automaton/state names.

    ``target_set_idx`` holds 0-based target indices; the rendered
    ``target_comb*`` fields are 1-based (sequence-trace convention:
    ``occ__cc_1_2`` = targets 1 and 2 together). Returns ``""`` for
    single-target FMs (no combination namespace needed).

    ``trans_name_prefix_fun`` (callable) takes precedence over the
    format-string ``trans_name_prefix``; both receive the same fields.
    """
    if order_max <= 1:
        return ""
    order = len(target_set_idx)
    target_comb = "".join([str(i + 1) for i in target_set_idx])
    target_comb_u = "_".join([str(i + 1) for i in target_set_idx])
    target_binary = "".join(
        ["1" if i in target_set_idx else "0" for i in range(order_max)]
    )
    if callable(trans_name_prefix_fun):
        return trans_name_prefix_fun(
            target_set_idx=target_set_idx,
            target_comb=target_comb,
            target_binary=target_binary,
            target_comb_u=target_comb_u,
            order=order,
            order_max=order_max,
        )
    return trans_name_prefix.format(
        target_comb=target_comb,
        target_binary=target_binary,
        target_comb_u=target_comb_u,
        order=order,
        order_max=order_max,
    )


class FmWiringMixin:
    """Effect resolution and wiring shared by failure-mode components.

    Host class requirements (all provided by ``PycComponent``):
    ``self.name()``, ``self.addStartMethod``; plus an optional
    ``self.step`` (``None`` when absent).
    """

    def _resolve_target_effects(self, target_comp, target_name, effects_dict, kind):
        """Resolve ``{var_name: value}`` effects against a target component.

        Returns records ``[{"var": handle, "value": value}, ...]``; raises
        a clear error when a variable does not exist on the target (the
        check runs at construction time, not at first firing).
        """
        resolved = []
        for var, value in (effects_dict or {}).items():
            if hasattr(target_comp, var):
                comp_var = getattr(target_comp, var)
            elif var in [v.basename() for v in target_comp.variables()]:
                comp_var = target_comp.variable(var)
            else:
                raise ValueError(
                    f"{kind}: variable {var!r} not found on target "
                    f"{target_name!r} (FM {self._fm_wiring_label()!r}). Check the "
                    f"spelling against the target's declared variables."
                )
            resolved.append({"var": comp_var, "value": value})
        return resolved

    def _fm_wiring_label(self):
        """Label used in wiring error messages (FM name when available)."""
        return getattr(self, "fm_name", None) or self.name()

    def _wire_transition_effects(
        self, aut, trans_name, effects_records, target_state=None
    ):
        """Register a transition-edge sensitive method applying ``effects_records``
        once, at the instant ``trans_name`` fires (mode="trans_based").

        Unlike state-effect wiring (a level clamp re-applied while the
        target state is active), this fires exactly once per firing —
        ``ITransition.addSensitiveMethod`` is a true edge callback
        (verified: once per firing, post-transition, re-armable).
        Registered ONLY on the transition: no re-apply on every fixpoint
        pass, no firing at t=0, no standing value (no write-war). A pulse
        only "sticks" on a persistent gate (muscadet ``fed_available_reset=
        False``), written by pulses only on both set and clear sides
        (both-pulse).

        ``target_state`` guards multi-branch transitions (e.g. an
        ObjFMInst Bernoulli draw: failure vs not_occ) so the pulse fires
        only on the branch that landed there. For single-target occ/rep —
        including every CCF combination transition — the occ side passes
        its own failure state (harmless: it is always active post-firing)
        and the rep side passes ``None``.
        """
        if not effects_records:
            return
        trans_bkd = aut.get_transition_by_name(trans_name)._bkd
        st_bkd = aut.get_state_by_name(target_state)._bkd if target_state else None

        def sensitive_method():
            if st_bkd is not None and not st_bkd.isActive():
                return
            for elt in effects_records:
                if elt["var"].value() != elt["value"]:
                    elt["var"].setValue(elt["value"])

        trans_bkd.addSensitiveMethod(
            f"effect_trans__{self.name()}_{aut.name}_{trans_name}", sensitive_method
        )

    def _wire_state_effects_multi(self, aut, state_names, effects_records, trans_name):
        """Level clamp spanning SEVERAL states through one sensitive method.

        Same registration pattern as :meth:`_wire_state_effects` (one
        method on the automaton + each written variable + start + step)
        with a composite any-active predicate — used for a logical
        state and its parked micro-state(s) in the inst machinery.
        Never register one clamp per micro-state: that would double the
        per-fixpoint-pass cost on every written variable.
        """
        if not effects_records:
            return
        st_bkds = [aut.get_state_by_name(name)._bkd for name in state_names]

        def sensitive_method():
            if any(st.isActive() for st in st_bkds):
                for elt in effects_records:
                    if elt["var"].value() != elt["value"]:
                        elt["var"].setValue(elt["value"])

        method_name = f"effect__{self.name()}_{aut.name}_{trans_name}"
        aut._bkd.addSensitiveMethod(method_name, sensitive_method)
        for elt in effects_records:
            elt["var"].addSensitiveMethod(method_name, sensitive_method)
        self.addStartMethod(method_name, sensitive_method)
        try:
            step = self.step
        except AttributeError:
            raise TypeError(
                f"{type(self).__name__} must define self.step (None allowed) "
                f"before wiring state effects (FmWiringMixin host contract)."
            ) from None
        if step:
            step.addMethod(self, method_name)

    def _wire_state_effects(self, aut, state_name, effects_records, trans_name):
        """Register a state-entry sensitive method applying ``effects_records``.

        Level-clamp semantics: the method re-applies the values on every
        fixpoint pass while ``state_name`` is active. It is registered on
        the automaton AND on each written variable AND as a start method
        (self-healing clamp: a value overwritten elsewhere, or reset by an
        isimu replay, is re-clamped as long as the state is active).

        ``trans_name`` must be unique across every ``_wire_state_effects``
        call of the host component: PyCATSHOO keys start/step
        registrations by name per element, so a duplicated name silently
        replaces the previous clamp.

        The host must define ``self.step`` (``None`` allowed) before
        wiring — a missing attribute raises instead of silently skipping
        the top-step registration.
        """
        if not effects_records:
            return
        st_bkd = aut.get_state_by_name(state_name)._bkd

        def sensitive_method():
            if st_bkd.isActive():
                for elt in effects_records:
                    if elt["var"].value() != elt["value"]:
                        elt["var"].setValue(elt["value"])

        method_name = f"effect__{self.name()}_{aut.name}_{trans_name}"
        aut._bkd.addSensitiveMethod(method_name, sensitive_method)
        for elt in effects_records:
            elt["var"].addSensitiveMethod(method_name, sensitive_method)
        self.addStartMethod(method_name, sensitive_method)
        try:
            step = self.step
        except AttributeError:
            raise TypeError(
                f"{type(self).__name__} must define self.step (None allowed) "
                f"before wiring state effects (FmWiringMixin host contract)."
            ) from None
        if step:
            step.addMethod(self, method_name)
