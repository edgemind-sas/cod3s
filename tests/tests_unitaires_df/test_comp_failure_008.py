import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from bk_ObjFlow import ObjFlow 
import itertools

@pytest.fixture(scope="module")
def the_system():
    system = PycSystem(name="Sys")

    system.pdmp_manager = system.addPDMPManager("pdmp_manager")

    return system


def test_system(the_system):

    nb_comp = 5
    comp_name_list = []
    for i in range(nb_comp):
        comp_name = f"C{i:03}"
        comp_name_list.append(comp_name)
        the_system.add_component(name=comp_name, cls="ObjFlow")

    obj_frun = the_system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=comp_name_list,
        failure_effects={"flow_out_max": 2, "flow_in_max": 4},
        failure_param=[1, 0, 0, 0, 1],
        repair_param=[1, 0, 0, 0, 1],
        trans_name_prefix="__{target_binary}",
        drop_inactive_automata=False, # pas de suppression des automates inactifs
    )

    # expected value : len(obj_frun.automata_d) = 31
    assert len(obj_frun.automata_d) == sum(
        [
            len(list(itertools.combinations(range(nb_comp), i + 1)))
            for i in range(nb_comp)
        ]
    )

    # Run simulation
    the_system.isimu_start()

    assert the_system.comp["C000"].flow_in_max.value() == -1
    assert the_system.comp["C000"].flow_out_max.value() == -1
    assert the_system.comp["C001"].flow_in_max.value() == -1
    assert the_system.comp["C001"].flow_out_max.value() == -1
    assert the_system.comp["C002"].flow_in_max.value() == -1
    assert the_system.comp["C002"].flow_out_max.value() == -1
    assert the_system.comp["C003"].flow_in_max.value() == -1
    assert the_system.comp["C003"].flow_out_max.value() == -1
    assert the_system.comp["C004"].flow_in_max.value() == -1
    assert the_system.comp["C004"].flow_out_max.value() == -1

    # Ensure transitions are valid before proceeding
    transitions = the_system.isimu_fireable_transitions()
    assert len(transitions) == 6
    assert transitions[0].name.endswith("00001")
    assert transitions[1].name.endswith("00010")
    assert transitions[-1].name.endswith("11111")

    the_system.isimu_set_transition(1, date=10)
    trans_fired = the_system.isimu_step_forward()
    assert len(trans_fired) == 1
    assert the_system.currentTime() == 10

    assert the_system.comp["C000"].flow_in_max.value() == -1
    assert the_system.comp["C000"].flow_out_max.value() == -1
    assert the_system.comp["C001"].flow_in_max.value() == -1
    assert the_system.comp["C001"].flow_out_max.value() == -1
    assert the_system.comp["C002"].flow_in_max.value() == -1
    assert the_system.comp["C002"].flow_out_max.value() == -1
    assert the_system.comp["C003"].flow_in_max.value() == 4
    assert the_system.comp["C003"].flow_out_max.value() == 2
    assert the_system.comp["C004"].flow_in_max.value() == -1
    assert the_system.comp["C004"].flow_out_max.value() == -1


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

