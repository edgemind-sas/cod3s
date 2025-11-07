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


# TODO: Why not uniformizing it using cod3s.utils.get_operator_function ?
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


def cod3s_deepcopy(obj):
    """Custom deep copy that handles Pycatshoo objects that can't be pickled."""
    if isinstance(obj, list):
        return [cod3s_deepcopy(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: cod3s_deepcopy(value) for key, value in obj.items()}
    elif hasattr(obj, "__dict__") and hasattr(obj, "__class__"):
        # For Pycatshoo objects, just return the original reference
        # since we'll replace them with actual objects anyway
        return obj
    else:
        # For primitive types, return as-is
        return obj


def sanitize_cond_format(cond):

    if isinstance(cond, dict):
        cond = [[cond]]
    else:
        if isinstance(cond, list):
            if all([isinstance(c, list) for c in cond]):
                if any([any([not isinstance(ci, dict) for ci in co]) for co in cond]):
                    raise ValueError(
                        "Condition specification must be a list of list of dict"
                    )
            elif all([isinstance(c, dict) for c in cond]):
                # Just add the second level of list
                cond = [cond]
            else:
                raise ValueError(
                    "Condition specification must be a list of list of dict"
                )

    return cond


def prepare_attr_tree(attr_tree, obj_default=None, system=None):
    """
    Prepare an attribute tree by replacing string attribute names with actual objects.

    Takes a hierarcbhical structure of nested lists where terminal elements are dictionaries
    containing at least an "attr" key. Returns a deep copy of this structure where string
    attribute names are replaced with the corresponding variable or state objects.

    Args:
        attr_tree: Hierarchical structure of lists and dictionaries containing attribute specifications
        obj_default (pyc.CComponent, optional): Default component object to use when "obj" key is not
            specified in dictionary elements. If None, each dictionary must contain an "obj" key.
        system (pyc.CSystem, optional): System object used to resolve component names when "obj"

            contains a string reference. Required when obj references are strings.

    Returns:
        Deep copy of attr_tree with string attributes replaced by objects

    Raises:
        ValueError: If an attribute name is not found in variables or states, or if required
            parameters are missing

    Examples:
        Basic usage with obj_default:
        >>> component = pyc_system.comp["pump_01"]
        >>> attr_tree = [{"attr": "flow_rate", "operator": ">=", "value": 10}]
        >>> processed_tree = prepare_attr_tree(attr_tree, obj_default=component)

        Usage with explicit obj references:
        >>> attr_tree = [
        ...     {"attr": "pressure", "obj": pump_component, "operator": ">", "value": 5},
        ...     {"attr": "temperature", "obj": "heater_01", "operator": "<=", "value": 100}
        ... ]
        >>> processed_tree = prepare_attr_tree(attr_tree, system=pyc_system)

        Complex nested structure:
        >>> attr_tree = [
        ...     [
        ...         {"attr": "state_active", "obj": component1},
        ...         {"attr": "flow_rate", "obj": component2, "operator": ">=", "value": 0}
        ...     ],
        ...     [{"attr": "temperature", "operator": "<", "value": 80}]
        ... ]
        >>> processed_tree = prepare_attr_tree(attr_tree, obj_default=default_comp, system=sys)
    """

    # Make a deep copy of attr_tree
    attr_tree_copy = cod3s_deepcopy(attr_tree)

    def process_element(element):
        """Recursively process elements in the tree structure."""
        if isinstance(element, list):
            # Process each element in the list
            for item in element:
                process_element(item)
        elif isinstance(element, dict):
            # Process dictionary elements
            if "attr" in element:
                if isinstance(element["attr"], str):
                    attr_name = element["attr"]

                    obj = element.get("obj", obj_default)

                    if obj:
                        # obj = element["obj"]
                        if isinstance(obj, str):
                            if system and isinstance(system, pyc.CSystem):
                                obj = system.comp[obj]
                            else:
                                raise ValueError(
                                    "system argument is required in this case and must be of type pyc.CSystem"
                                )

                        if not isinstance(obj, pyc.CComponent):
                            raise ValueError(
                                "Key 'obj' must contain an object of type pyc.CComponent"
                            )
                    else:
                        raise ValueError(
                            "'attr' key provided as a string, you must reference the related object as the value of key 'obj'"
                        )
                    # Get variable and state names for lookup
                    variable_names = [v.basename() for v in obj.variables()]
                    state_names = [s.basename() for s in obj.states()]

                    # Check if it's a variable
                    if attr_name in variable_names:
                        element["attr"] = obj.variable(attr_name)
                    # Check if it's a state
                    elif attr_name in state_names:
                        element["attr"] = obj.state(attr_name)
                    elif hasattr(obj, attr_name):
                        element["attr"] = getattr(obj, attr_name)
                    else:
                        raise ValueError(
                            f"{attr_name} must be a variable or a state or an attribute of {repr(obj)}"
                        )
                if isinstance(element["attr"], pyc.IVariable):
                    element["attr_val_name"] = "value"
                elif isinstance(element["attr"], pyc.IState):
                    element["attr_val_name"] = "isActive"
                else:
                    raise ValueError(
                        f"Attribute type {type(element['attr'])} not supported"
                    )
            else:
                raise ValueError(f"Element {element} must have a key 'attr'")

            # Recursively process other dictionary values
            for value in element.values():
                if isinstance(value, (list, dict)):
                    process_element(value)

    # Scan depth first attr_tree_copy and process as requested
    process_element(attr_tree_copy)

    return attr_tree_copy


if __name__ == "__main__":
    import doctest

    doctest.testmod()
