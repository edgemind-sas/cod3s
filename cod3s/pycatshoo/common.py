import Pycatshoo as pyc
import operator


def get_pyc_type(var_type):
    if var_type == "bool":
        return (bool, pyc.TVarType.t_bool)
    elif var_type == "int":
        return (int, pyc.TVarType.t_integer)
    elif var_type == "float":
        return (float, pyc.TVarType.t_double)
    else:
        raise ValueError(f"Type {var_type} not supported by PyCATSHOO")


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
