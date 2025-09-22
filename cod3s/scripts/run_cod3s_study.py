#!/usr/bin/env python3
"""
Script CLI pour exécuter des études COD3S.

Ce script utilise l'environnement virtuel Python courant pour exécuter
des simulations COD3S basées sur des fichiers de configuration YAML.
"""

import Pycatshoo as Pyc
import cod3s
import sys
from pathlib import Path
import os
import datetime
import yaml
import argparse
import logging
import importlib.util


def main():
    """Point d'entrée principal du CLI COD3S Study."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Run COD3S study",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default study specifications file
  run-cod3s-study --model system.yaml
  
  # Use custom study specifications file
  run-cod3s-study --model system.yaml --study-specs custom_config.yaml
  
  # Run with debug logging to see detailed output
  run-cod3s-study --model system.yaml --log-level DEBUG
  
  # Specify custom results directory
  run-cod3s-study --model system.yaml --results-dir my_results
        """,
    )

    parser.add_argument(
        "--study-specs",
        type=str,
        default="study.yaml",
        help="Study specifications YAML file name (default: study.yaml)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="DISABLED",
        choices=[
            "DISABLED",
            "DEBUG",
            "INFO",
            "INFO1",
            "INFO2",
            "INFO3",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ],
        help="Logging level (default: DISABLED)",
    )

    parser.add_argument(
        "--results-dir",
        type=str,
        default=None,
        help="Directory to store study results (default: derived from study-specs filename)",
    )

    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="YAML specification file of the model to be used in the study",
    )

    args_cli = parser.parse_args()

    # Initialize logger first
    if args_cli.log_level.upper() == "DISABLED":
        logger = None
    else:
        logger = cod3s.utils.COD3SLogger(
            "COD3SRunStudy", level_name=args_cli.log_level.upper()
        )

    # Load model specs YAML file
    MODEL_SPECS_FILENAME = Path(args_cli.model)
    if not MODEL_SPECS_FILENAME.exists():
        raise FileNotFoundError(
            f"Model specification file '{MODEL_SPECS_FILENAME}' not found!"
        )

    with open(MODEL_SPECS_FILENAME, "r") as file:
        model_specs = yaml.safe_load(file)

    if logger:
        logger.info2(f"Loaded model specifications from '{MODEL_SPECS_FILENAME}'")

    # Dynamically import files specified in model specs
    import_files = model_specs.get("imports", [])
    if import_files:
        for import_file in import_files:
            import_path = Path(import_file).resolve()
            if import_path.exists():
                # Add the directory to Python path if not already there
                import_dir = import_path.parent
                if str(import_dir) not in sys.path:
                    sys.path.insert(0, str(import_dir))

                # Import the module
                module_name = import_path.stem
                spec = importlib.util.spec_from_file_location(module_name, import_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Import all public names from the module into global namespace
                for name in dir(module):
                    if not name.startswith("_"):
                        globals()[name] = getattr(module, name)

                if logger:
                    logger.info(f"Dynamically imported: {import_file}")
            else:
                if logger:
                    logger.warning(f"Import file not found: {import_file}")
                else:
                    print(f"Warning: Import file not found: {import_file}")

    system_specs = model_specs.get("system", {})
    # Get system class from model specs or use default
    system_cls_name = system_specs.pop("python_class", "PycSystem")

    # Try to get the system class from globals (loaded via dynamic imports)
    if system_cls_name in globals():
        system_cls_bkd = globals()[system_cls_name]
    else:
        raise NameError(
            f"System class '{system_cls_name}' not found. Make sure to import the file containing this class using imports key in the YAML model file."
        )

    # Use user-specified filename
    STUDY_SPECS_FILENAME = Path(args_cli.study_specs)
    # Check if file exists and read failure modes from YAML file
    study_specs_data = {}
    if not STUDY_SPECS_FILENAME.exists():
        if logger:
            logger.warning(
                f"Study specifications file '{STUDY_SPECS_FILENAME}' not found!"
            )
    else:
        with open(STUDY_SPECS_FILENAME, "r") as file:
            study_specs_data = yaml.safe_load(file)
        if logger:
            logger.info2(f"Loaded study specifications from '{STUDY_SPECS_FILENAME}'")

    # Determine study result directory
    if args_cli.results_dir:
        RESULTS_DIR = Path(args_cli.results_dir)
    elif STUDY_SPECS_FILENAME.exists():
        RESULTS_DIR = STUDY_SPECS_FILENAME.parent / STUDY_SPECS_FILENAME.stem
    else:
        # Use timestamp-based directory name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        RESULTS_DIR = Path(f"study_{timestamp}")

    RESULTS_DIR.mkdir(exist_ok=True)

    if logger:
        logger.info2(f"Using {RESULTS_DIR} to store results")

    if logger:
        logger.info1(f"PyCATSHOO Version: {Pyc.ILogManager.glLogManager().version()}")

    system = system_cls_bkd(**system_specs)
    if logger:
        logger.info1(f"{system.__class__.__name__} {system.name()} created")

    if logger:
        logger.info1("Add components")
    system.add_components(model_specs.get("components", []), logger=logger)
    if logger:
        logger.info1("Add connections")
    system.add_connections(model_specs.get("connections", []), logger=logger)
    if logger:
        logger.info1("Add failure modes")
    system.add_failure_mode(study_specs_data.get("failure_modes", []), logger=logger)
    if logger:
        logger.info1("Add events")
    system.add_events(study_specs_data.get("events", []), logger=logger)

    # __import__("ipdb").set_trace()

    # system_parameters_filename = os.path.join(current_dir, f"system_param.xml")
    # system.loadParameters(system_parameters_filename)

    # system.setTrace(args_cli.trace_level)

    # system.isimu_start()
    # system.isimu_show_fireable_transitions()
    # system.isimu_set_transition("CX__frun.occ__cc_12")
    # system.isimu_step_forward()

    # Add indicators from configuration
    if logger:
        logger.info1("Add indicators")
    system.add_indicators(study_specs_data.get("indicators", []), logger=logger)

    # Configure sequences
    # -------------------
    if logger:
        logger.info1("Add targets")
    system.add_targets(study_specs_data.get("targets", []), logger=logger)

    # TODO COD3S : Add monitoring specification in simulation parameters object
    system.monitorTransition("#.*")

    # System simulation
    # =================
    # Get simulation parameters from study specs or use defaults
    simulation_config = study_specs_data.get("simulation", {})
    nb_runs = simulation_config.get("nb_runs")
    start_date = datetime.datetime.now()
    if logger:
        logger.info1(f"Starting simulation [{nb_runs} runs]")

    system.simulate(simulation_config)
    end_date = datetime.datetime.now()
    simulation_duration = end_date - start_date

    if logger:
        logger.info2(f"Simulation completed in: {simulation_duration}")

    pyc_parameters_filename = os.path.join(RESULTS_DIR, f"pyc_param.xml")
    system.dumpParameters(pyc_parameters_filename, False)

    # We create an anlyzer which holds the values of all the monitored elements
    sequences_xml_filename = os.path.join(RESULTS_DIR, "sequences.xml")
    analyser = Pyc.CAnalyser(system)
    analyser.keepFilteredSeq(True)
    analyser.printFilteredSeq(100, sequences_xml_filename, "PySeq.xsl")

    # Generate plots from configuration
    if logger:
        logger.info2("Storing results")

    # Handle new results structure with plot_indics
    results_config = study_specs_data.get("results", {})

    # Process indicators for CSV export
    indicators_list = results_config.get("indicators", [])
    for indicator_specs in indicators_list:

        indicator_id = indicator_specs.get("id")
        if not indicator_id:
            error_msg = "Indicator 'id' is mandatory but not specified"
            if logger:
                logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            continue

        output_formats = indicator_specs.get("output", [])

        if not output_formats:
            if logger:
                logger.warning(
                    f"No output format provided for indicator: {indicator_id}"
                )
            continue

        # Validate output formats
        for output_format in output_formats:
            if output_format.lower() != "csv":
                error_msg = f"Unsupported output format '{output_format}' for indicators. Only 'csv' is supported."
                if logger:
                    logger.error(error_msg)
                else:
                    print(f"Error: {error_msg}")
                continue

        if "csv" in [fmt.lower() for fmt in output_formats]:
            comp_pattern = indicator_specs.get("comp_pattern", ".*")
            attr_pattern = indicator_specs.get("attr_pattern", ".*")

            if logger:
                logger.info3(f"Generating indicators CSV for: {indicator_id}")

            try:
                df_indicators = system.indic_to_frame(
                    comp_pattern=comp_pattern, attr_pattern=attr_pattern
                )

                if indicator_id:
                    csv_filename = os.path.join(RESULTS_DIR, f"{indicator_id}.csv")
                else:
                    csv_filename = os.path.join(RESULTS_DIR, "indicators.csv")

                df_indicators.to_csv(csv_filename, index=False)

                if logger:
                    logger.info3(f"Indicators CSV saved to: {csv_filename}")

            except Exception as e:
                if logger:
                    logger.error(f"Failed to write indicators CSV: {e}")
                else:
                    print(f"Error: Failed to write indicators CSV: {e}")

    plot_indics_list = results_config.get("plot_indicators", [])

    # Process new plot_indics structure
    for plot_specs in plot_indics_list:
        plot_id = plot_specs.get("id")
        if not plot_id:
            error_msg = "Plot indicator 'id' is mandatory but not specified"
            if logger:
                logger.error(error_msg)
            else:
                print(f"Error: {error_msg}")
            continue

        output_formats = plot_specs.get("output", [])

        if not output_formats:
            if logger:
                logger.warning(f"No output format provided for plot: {plot_id}")
            continue

        plot_write_options = plot_specs.pop("write_options", {})
        plot_config = {k: v for k, v in plot_specs.items() if k not in ["id", "output"]}
        if logger:
            logger.info3(f"Generating plot for: {plot_id}")

        fig_indics = system.indic_px_line(**plot_config)

        # Save graphic to disk based on specified output formats
        for output_format in output_formats:
            if output_format.lower() == "html":
                fig_indics_filename_html = os.path.join(RESULTS_DIR, f"{plot_id}.html")
                try:
                    fig_indics.write_html(fig_indics_filename_html)
                    if logger:
                        logger.info3(f"Plot saved to: {fig_indics_filename_html}")
                except Exception as e:
                    if logger:
                        logger.error(
                            f"Failed to write HTML plot {fig_indics_filename_html}: {e}"
                        )
                    else:
                        print(
                            f"Error: Failed to write HTML plot {fig_indics_filename_html}: {e}"
                        )

            elif output_format.lower() == "png":
                fig_indics_filename_png = os.path.join(RESULTS_DIR, f"{plot_id}.png")
                try:
                    fig_indics.write_image(
                        fig_indics_filename_png, **plot_write_options
                    )
                    if logger:
                        logger.info3(f"Plot saved to: {fig_indics_filename_png}")
                except Exception as e:
                    if logger:
                        logger.error(
                            f"Failed to write PNG plot {fig_indics_filename_png}: {e}"
                        )
                    else:
                        print(
                            f"Error: Failed to write PNG plot {fig_indics_filename_png}: {e}"
                        )

    # Process legacy plot_results for backward compatibility
    # Also handle legacy plot_results for backward compatibility
    legacy_plot_results = study_specs_data.get("plot_results", [])

    if legacy_plot_results:
        if logger:
            logger.warning(
                "The 'plot_results' configuration is deprecated. Please use the new 'results.plot_indics' format instead."
            )
            logger.warning(
                "New format example: results: { plot_indics: [{ id: 'plot_name', output: ['html', 'png'], ... }] }"
            )
        else:
            print(
                "Warning: The 'plot_results' configuration is deprecated. Please use the new 'results.plot_indics' format instead."
            )
            print(
                "New format example: results: { plot_indics: [{ id: 'plot_name', output: ['html', 'png'], ... }] }"
            )

    for plot_specs in legacy_plot_results:
        plot_id = plot_specs.pop("plot_id")
        plot_write_options = plot_specs.pop("write_options", {})
        if logger:
            logger.warning(f"Generating legacy plot for: {plot_id}")

        fig_indics = system.indic_px_line(**plot_specs)
        fig_indics_filename_html = os.path.join(RESULTS_DIR, f"{plot_id}_indics.html")
        fig_indics_filename_png = os.path.join(RESULTS_DIR, f"{plot_id}_indics.png")
        try:
            fig_indics.write_html(fig_indics_filename_html)
            if logger:
                logger.info(f"Plot saved to: {fig_indics_filename_html}")
        except Exception as e:
            if logger:
                logger.error(
                    f"Failed to write HTML plot {fig_indics_filename_html}: {e}"
                )
            else:
                print(
                    f"Error: Failed to write HTML plot {fig_indics_filename_html}: {e}"
                )

        try:
            fig_indics.write_image(fig_indics_filename_png, **plot_write_options)
            if logger:
                logger.info(f"Plot saved to: {fig_indics_filename_png}")
        except Exception as e:
            if logger:
                logger.error(f"Failed to write PNG plot {fig_indics_filename_png}: {e}")
            else:
                print(f"Error: Failed to write PNG plot {fig_indics_filename_png}: {e}")


if __name__ == "__main__":
    main()
