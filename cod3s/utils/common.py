import sys
import importlib
import operator


def get_class_by_name(class_name):
    """
    Parse class_name to get the class handler.

    Args:
        class_name (str): class name (for example 'pycatshoo.PyCComponent')

    Returns:
        type: The class handler

    Raises:
        ImportError: If the module cannot be imported
        AttributeError: If the class doesn't exist in the module
    """
    # Check if the class name includes a module
    if "." in class_name:
        module_name, class_name = class_name.rsplit(".", 1)
        try:
            module = importlib.import_module(module_name)
            if not hasattr(module, class_name):
                raise AttributeError(
                    f"The class '{class_name}' doesn't exist in the module '{module_name}'."
                )
            return getattr(module, class_name)
        except ImportError:
            raise ImportError(f"The module '{module_name}' cannot be imported.")
    else:
        # If no module is specified, assume the class is available directly in globals()
        try:
            if class_name in globals():
                return globals()[class_name]
            else:
                # Search through imported modules to find the class
                for module_name, module in sys.modules.items():
                    if hasattr(module, class_name):
                        return getattr(module, class_name)
                    f"The class '{class_name}' was not found in the global namespace or in imported modules."
                raise AttributeError()
        except Exception as e:
            raise ValueError(f"Error while searching for class '{class_name}': {e}")


def get_operator_function(operator_str):
    """
    Get the operator function corresponding to an operator string.

    Args:
        operator_str (str): Operator string like "==", "!=", "<=", "<", ">=", ">"

    Returns:
        function: The corresponding operator function

    Raises:
        ValueError: If the operator string is not supported
    """
    operator_map = {
        "==": operator.eq,
        "!=": operator.ne,
        "<": operator.lt,
        "<=": operator.le,
        ">": operator.gt,
        ">=": operator.ge,
    }

    if operator_str not in operator_map:
        raise ValueError(
            f"Unsupported operator: {operator_str}. Supported operators: {list(operator_map.keys())}"
        )

    return operator_map[operator_str]
