import os
import glob
import pandas as pd
from pathlib import Path
import subprocess
import shutil

def run_test(study_specs_file, 
             model_file, 
             subdir, #results_dir, 
             compare_csv_subset=None,
             is_reference_mode=False,
             delete_xml_html=True):
    """Executes the test with the specified files and processes the results."""

    for file in [study_specs_file, model_file]:
        assert os.path.exists(file), f"{file} does not exist."

    results_dir = Path(subdir)
    if not is_reference_mode:
        results_dir = results_dir / f"{os.path.basename(subdir)}_results"
    else:
        results_dir = results_dir / f"{os.path.basename(subdir)}_references"
        # Check if the ref_path folder already exists, delete the folder if it exists
        if results_dir.exists():
            shutil.rmtree(results_dir)  # to delete a non-empty folder

    # Process
    run = subprocess.run(
        ['run-cod3s-study', 
         '--study-specs', study_specs_file,
         '--results-dir', str(results_dir),
         '--model', model_file
        ],
        capture_output=True,
        text=True,
        encoding='latin-1'
    )
    assert run.returncode == 0, f"Error during execution. : {run.stderr}"
    
    # CSV results
    process_csv_results(results_dir, delete_xml_html)

    if is_reference_mode:
        return

    # if no reference mode : compare CSV file 
    if compare_csv_subset:
        compare_csv_files(Path(results_dir).parent, compare_csv_subset)
    else:
        compare_csv_files(Path(results_dir).parent)


def process_csv_results(results_dir, delete_xml_html):
    """
    Process CSV files in the specified results directory. 
    If the directory does not exist, it will be created.

    Parameters:
    - results_dir: The directory where the results (CSV files) are expected to be found.

    Returns:
    - A tuple containing a success message and any error messages encountered during processing.
    """
    error_messages = []

    # Check that the results directory has been created
    assert os.path.exists(results_dir), f"{results_dir} has not been created."

    # Find all CSV files in the folder
    csv_files = glob.glob(os.path.join(results_dir, '*.csv'))
    assert csv_files, f"No CSV files found in {results_dir}."

    if delete_xml_html:
        delete_xml_html_files(results_dir)

    # Return a success message
    return "All CSV files have been concatenated and saved'."

def compare_csv_files(current_dir, tolerance = 1e-3, subset = None):
    """
    Compare two CSV files for equality with a specified tolerance for numerical values.

    Parameters:
    - current_dir: Path to the current directory
    - tolerance: Tolerance for numerical comparisons.

    Returns:
    - A tuple containing a boolean indicating if the files match and a list of discrepancies.
    """

    # Check that the results directory has been created
    results_dir_name = str(os.path.basename(os.path.normpath(current_dir))) + "_results"
    results_dir = os.path.join(current_dir, results_dir_name)
    assert os.path.exists(results_dir), f"{results_dir} has not been created."

    # Find result CSV file in the folder
    csv_res_files = glob.glob(os.path.join(results_dir, '*.csv'))
    assert csv_res_files, "Error: No .csv file found in the 'result' folder."

    # Check that the references directory has been created
    ref_dir_name = str(os.path.basename(os.path.normpath(current_dir))) + "_references"
    ref_dir = os.path.join(current_dir, ref_dir_name)
    assert os.path.exists(ref_dir), f"{ref_dir} has not been created."

    # Find result reference CSV file in the folder
    csv_ref_files = glob.glob(os.path.join(ref_dir, '*.csv'))
    assert csv_ref_files, "Error: No .csv file found in the 'reference' folder."

    # Extract file names without the path
    result_file_names = {os.path.basename(f) for f in csv_res_files}
    reference_file_names = {os.path.basename(f) for f in csv_ref_files}

    # Check for missing files
    identical_files = result_file_names.intersection(reference_file_names)
    missing_in_result = reference_file_names - result_file_names
    missing_in_reference = result_file_names - reference_file_names
    assert not missing_in_result, f"Error: The following files are missing in 'result': {missing_in_result}"
    assert not missing_in_reference, f"Error: The following files are missing in 'reference': {missing_in_reference}"

    # List to collect all differences
    all_differences = []

    # Compare files with identical names
    for file_name in identical_files:
        result_file_path = os.path.join(results_dir, file_name)
        reference_file_path = os.path.join(ref_dir, file_name)

        # Read the CSV files with pandas
        results_df = pd.read_csv(result_file_path)
        references_df = pd.read_csv(reference_file_path)
        diff = []
        try:
            # Compare the DataFrames
            if subset is None:
                pd.testing.assert_frame_equal(results_df, 
                                            references_df, 
                                            check_exact=False, 
                                            check_dtype=True, 
                                            rtol=tolerance)  # Tolerance relative 
            else:
                pd.testing.assert_frame_equal(results_df[subset], 
                                            references_df[subset], 
                                            check_exact=False, 
                                            check_dtype=True, 
                                            rtol=tolerance)
        except AssertionError as e:
            # If there is an assertion error, we need to find the differences
            diff.append({'Error': str(e)})  # Store the error message in the diff list
            columns_to_include = ['name', 'instant', 'values']
            
            # Find the differences
            for index in range(max(len(results_df), len(references_df))):
                result_row = results_df.iloc[index] if index < len(results_df) else None
                ref_row = references_df.iloc[index] if index < len(references_df) else None
                
                if result_row is not None and ref_row is not None:
                    if not result_row.equals(ref_row):
                        diff.append({
                            'Index': index,
                            'Reference': ref_row[columns_to_include].to_dict() if columns_to_include else ref_row.to_dict(),
                            'Result': result_row[columns_to_include].to_dict() if columns_to_include else result_row.to_dict()
                        })
                elif ref_row is None:
                    diff.append({
                        'Index': index,
                        'Reference': 'Row missing in reference',
                        'Result': result_row[columns_to_include].to_dict() if columns_to_include else 'Row missing in results'
                    })
                elif result_row is None:
                    diff.append({
                        'Index': index,
                        'Reference': ref_row[columns_to_include].to_dict() if columns_to_include else 'Row missing in references',
                        'Result': 'Row missing in results'
                    })

            # Create a DataFrame for the differences
            diff_df = pd.DataFrame(diff)

            # Save the differences to a CSV file
            diff_file_name = file_name.replace('.csv', '_diff.csv')
            diff_file_path = os.path.join(current_dir, diff_file_name)
            diff_df.to_csv(diff_file_path, index=False)

            # Collect the differences for later assertion
            all_differences.append(diff_file_path)

    # After processing all files, check if there were any differences
    if all_differences:
        raise AssertionError(f"Differences found. See the following files for details: {', '.join(all_differences)}")
    

def delete_xml_html_files(directory):
    """
    Deletes all files with the .xml and .html extensions in the specified directory.
    param directory: The path of the directory to search.
    """
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                if filename.endswith('.xml') or filename == 'sequences.html':
                    os.remove(file_path)
                    print(f'Deleted: {file_path}')
                    
    except Exception as e:
        print(f'An error occurred: {e}')