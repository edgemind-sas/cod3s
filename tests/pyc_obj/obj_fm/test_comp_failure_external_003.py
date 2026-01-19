import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from kb_test import ObjFlow


@pytest.fixture(autouse=True)
def run_around_tests():
    yield
    cod3s.terminate_session()


# --- Helpers ---


def is_state_active(automaton, state_name):
    return automaton.get_state_by_name(state_name)._bkd.isActive()


def fire_transition(system, name, date=None):
    if date is not None:
        system.isimu_set_transition(name, date=date)
    else:
        system.isimu_set_transition(name)
    system.isimu_step_forward()


# --- Tests ---


@pytest.mark.parametrize(
    "combo, affected_targets",
    [
        ("cc_1", ["C1"]),
        ("cc_2", ["C2"]),
        ("cc_3", ["C3"]),
        ("cc_12", ["C1", "C2"]),
        ("cc_13", ["C1", "C3"]),
        ("cc_23", ["C2", "C3"]),
        ("cc_123", ["C1", "C2", "C3"]),
    ],
)
def test_external_3_targets_all_combos(combo, affected_targets):
    """Vérifie toutes les combinaisons (1, 2, 3) avec effets de défaillance uniquement"""
    system = PycSystem(name=f"Sys3T_{combo}")
    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    for name in ["C1", "C2", "C3"]:
        system.add_component(name=name, cls="ObjFlow", flow_in_max=10.0)

    # Nom factorisé pour C1, C2, C3 -> CX
    fm_comp_name = "CX__frun"

    system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=["C1", "C2", "C3"],
        behaviour="external",
        failure_effects={"flow_in_max": 0.0},
        # Pas de repair_effects
        failure_param=[0.1, 0.01, 0.001],  # lambda pour ordres 1, 2, 3
        repair_param=[0.1, 0.1, 0.1],
    )

    system.isimu_start()

    # Vérification état initial
    for t in ["C1", "C2", "C3"]:
        assert system.comp[t].flow_in_max.value() == 10.0

    # Déclenchement de la combinaison de défaillance
    fire_transition(system, f"{fm_comp_name}.occ__{combo}", date=10)

    # Propagation aux cibles (le point fixe traite toutes les cibles simultanées)
    fire_transition(system, f"{affected_targets[0]}.occ")

    # Vérification des états et des effets
    for t in ["C1", "C2", "C3"]:
        target_aut = system.comp[t].automata_d["frun"]
        if t in affected_targets:
            assert is_state_active(target_aut, "occ")
            assert system.comp[t].flow_in_max.value() == 0.0
        else:
            assert is_state_active(target_aut, "rep")
            assert system.comp[t].flow_in_max.value() == 10.0

    # Réparation de l'ObjFM
    fire_transition(system, f"{fm_comp_name}.rep__{combo}", date=20)

    # Propagation de la réparation aux cibles
    fire_transition(system, f"{affected_targets[0]}.rep")

    # Vérification finale : les états sont 'rep' mais les valeurs restent à 0 car pas de repair_effects
    for t in ["C1", "C2", "C3"]:
        target_aut = system.comp[t].automata_d["frun"]
        assert is_state_active(target_aut, "rep")
        if t in affected_targets:
            assert system.comp[t].flow_in_max.value() == 0.0
        else:
            assert system.comp[t].flow_in_max.value() == 10.0

    system.isimu_stop()
