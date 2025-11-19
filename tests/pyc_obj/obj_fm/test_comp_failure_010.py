import pytest
import cod3s
from cod3s.pycatshoo.system import PycSystem
from pyc_obj.kb_test import ObjFlow 


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

    def trans_name_prefix_fun(target_set_idx, order_max, **kwargs):
        order = len(target_set_idx)
        if order < order_max:
            return "__" + "_".join([f"{i + 1:02}" for i in target_set_idx])
        else:
            return "__all"

    obj_frun = the_system.add_component(
        cls="ObjFMExp",
        fm_name="frun",
        targets=comp_name_list,
        failure_effects={"flow_out_max": 2, "flow_in_max": 4},
        failure_param=[1, 0, 1, 0, 1],
        trans_name_prefix_fun=trans_name_prefix_fun,
        drop_inactive_automata=True,
    )

    assert len(obj_frun.automata_d) == 16

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
    assert len(transitions) == 16
    assert transitions[0].name.endswith("occ__01")
    assert transitions[1].name.endswith("occ__01_02_03")
    assert transitions[2].name.endswith("occ__01_02_04")
    assert transitions[-1].name.endswith("occ__all")


def test_delete(the_system):
    the_system.deleteSys()
    cod3s.terminate_session()

