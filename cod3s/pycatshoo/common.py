import Pycatshoo as pyc
import operator
import re


def get_pyc_type(var_type):
    if var_type == "bool":
        return (bool, pyc.TVarType.t_bool)
    elif var_type == "int":
        return (int, pyc.TVarType.t_integer)
    elif var_type == "float":
        return (float, pyc.TVarType.t_double)
    else:
        raise ValueError(f"Type {var_type} not supported by PyCATSHOO")


def get_pyc_simu_mode(simu_mode):

    if simu_mode == pyc.TSimuMode.sm_stopped:
        return "stop"
    elif simu_mode == pyc.TSimuMode.sm_standard:
        return "standard"
    elif simu_mode == pyc.TSimuMode.sm_interactive:
        return "interactive"
    else:
        raise ValueError(f"Simu type {simu_mode} not supported for now")


def get_pyc_attr_list_name(attr_type):
    if attr_type == "VAR":
        return "variables"
    elif attr_type == "ST":
        return "states"
    elif attr_type == "AUT":
        return "automata"
    else:
        raise ValueError(f"{attr_type} not supported by PyCATSHOO")


def parse_inequality(input_string, default_ope=">="):

    if input_string is None:
        return None, None

    if isinstance(input_string, float):
        return input_string, default_ope

    # Mapping from string operators to the respective functions in the operator module
    # WARNING NOTE: Here key ordering matters for the following comparisons
    operator_map = {
        "<=": operator.le,
        ">=": operator.ge,
        "<": operator.lt,
        ">": operator.gt,
    }

    # Iterate over the operators to find which one is in the input string
    for op_str in operator_map:
        if input_string.startswith(op_str):
            # Extract the number part after the operator
            try:
                number = float(input_string[len(op_str) :].strip())
                return number, operator_map[op_str]
            except ValueError:
                raise ValueError("Invalid number format in input string")

    raise ValueError("Invalid input format or unsupported operator")


def compute_reference_mean(var_ref, default_value=0):
    # Get the sum of all values in the reference
    total_value = var_ref.sumValue(default_value)
    # Get the number of connected values
    count = var_ref.cnctCount()
    # Compute the mean
    mean_value = total_value / count if count > 0 else total_value
    return mean_value


def parse_quantile(quantile_string, return_pct=False):
    """
    Parse a string in the form 'qle(q1, q2, ..., qn)' or 'qgt(q1, q2, ..., qn)' and return a list of float values [q1, q2, ..., qn].

    Args:
        quantile_string (str): A string in the format 'qle(q1, q2, ..., qn)' or 'qgt(q1, q2, ..., qn)' where q1, q2, ..., qn are float values.
        return_pct (bool, optional): If True, return percentiles instead of quantiles. Defaults to False.

    Returns:
        list: A list of float values extracted from the input string. If return_pct is True, values are multiplied by 100.

    Raises:
        ValueError: If the input string format is invalid or if any value can't be converted to float.

    Examples:
        >>> parse_quantile("qle(0.1, 0.5, 0.9)")
        [0.1, 0.5, 0.9]

        >>> parse_quantile("qgt(0.25, 0.75)")
        [0.25, 0.75]

        >>> parse_quantile("qle(0.1)")
        [0.1]

        >>> parse_quantile("qgt()")
        []

        >>> parse_quantile("qle(0.1, 0.2, 0.3, 0.4, 0.5)")
        [0.1, 0.2, 0.3, 0.4, 0.5]

        >>> parse_quantile("qle(0.1, 0.5, 0.9)", return_pct=True)
        [10.0, 50.0, 90.0]

        >>> parse_quantile("qgt(invalid)")
        Traceback (most recent call last):
            ...
        ValueError: could not convert string to float: 'invalid'

        >>> parse_quantile("invalid_format")
        Traceback (most recent call last):
            ...
        ValueError: Invalid quantile string format. Expected 'qle(q1, q2, ..., qn)' or 'qgt(q1, q2, ..., qn)'
    """
    match = re.search(r"q(?:le|gt)\((.*?)\)", quantile_string)

    if not match:
        raise ValueError(
            "Invalid quantile string format. Expected 'qle(q1, q2, ..., qn)' or 'qgt(q1, q2, ..., qn)'"
        )

    content = match.group(1).strip()
    if content:
        quantiles = [float(q.strip()) for q in content.split(",")]
        if return_pct:
            quantiles = [q * 100 for q in quantiles]
    else:
        quantiles = []

    return quantiles


if __name__ == "__main__":
    import doctest

    doctest.testmod()
