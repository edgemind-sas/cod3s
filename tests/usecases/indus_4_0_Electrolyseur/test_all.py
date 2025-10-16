import pytest
import os
import yaml
from pathlib import Path
import shutil
from utils import run_test

CURRENT_FILE = Path(__file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent


def cleanup(results_dir):
    if os.path.exists(results_dir):
        shutil.rmtree(results_dir)


@pytest.mark.slow
@pytest.mark.parametrize(
    "test_case, is_reference_mode",
    [
        ("test_activate_3automatons", False),
        ("test_automaton", False),
        ("test_batteries_DistribNode_noPercentValues", False),
        ("test_batteries_DistribNode_percentValues", False),
        ("test_battery_stop", False),
        ("test_capacityMulti_consumerSin", False),
        ("test_consumer_flow_in_max", False),
        ("test_consumer_flow_out_max", False),
        ("test_consumerInf", False),
        ("test_consumerInf_Battery", False),
        ("test_dcc_sensor", False),
        ("test_demandInfFlow", False),
        ("test_df_activate_3automatons", False),
        ("test_df_content_sensor", False),
        ("test_emptyBattery_stack_capacity", False),
        ("test_pump_df_pct", False),
        ("test_run_cod3s_negativeH2", False),
        ("test_sensor_df_forced_measure", False),
        ("test_source", False),
        ("test_sourceSinusoidale", False),
        ("test_stack_df_H2leak", False),
        ("test_stack_df_H2_membrane_leak", False),
        ("test_stack_flow_out_max", False),
        ("test_StartStopComponent_AndMethod", False),
        ("test_StartStopComponent_MedianMethod_3Sensors", False),
        ("test_StartStopComponent_MedianMethod_4Sensors", False),
    ],
)
def tests_indus_4_0_Electrolyseur(test_case, is_reference_mode):

    model_yaml_path = os.path.join(CURRENT_DIR, test_case, "system.yaml")
    study_yaml_path = os.path.join(CURRENT_DIR, test_case, "study.yaml")

    result_dir = CURRENT_DIR / test_case / f"{test_case}_results"
    cleanup(result_dir)

    run_test(
        study_yaml_path, model_yaml_path, CURRENT_DIR / test_case, is_reference_mode
    )

    cleanup(result_dir)
