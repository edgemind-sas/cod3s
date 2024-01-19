import pkg_resources
installed_pkg = {pkg.key for pkg in pkg_resources.working_set}
if 'ipdb' in installed_pkg:
    import ipdb  # noqa: F401


def update_dict_deep(target, updates, key_attr):
    """
    Recursively update a dictionary with another dictionary's values.

    Args:
        target (dict): The target dictionary to be updated.
        updates (dict): The dictionary with updates to apply to target.
        key_attr (str): The attribute name used as a key for matching items
                        in lists of dictionaries.

    Returns:
        dict: The updated target dictionary.

    >>> target_dict = {
    ...     'name': 'original',
    ...     'components': [
    ...         {'name': 'a', 'value': 1},
    ...         {'name': 'b', 'value': 2}
    ...     ]
    ... }
    >>> updates_dict = {
    ...     'name': 'updated',
    ...     'components': [
    ...         {'name': 'a', 'value': 10},
    ...         {'name': 'c', 'value': 3}
    ...     ]
    ... }
    >>> updated_dict = update_dict_deep(target_dict, updates_dict, 'name')
    >>> updated_dict == {
    ...     'name': 'updated',
    ...     'components': [
    ...         {'name': 'a', 'value': 10},
    ...         {'name': 'b', 'value': 2},
    ...         {'name': 'c', 'value': 3}
    ...     ]
    ... }
    True

    Note:
        If the corresponding item in the target does not exist, it will be added.
        This function does not remove items that exist in the target but not in the updates.
    """
    if not isinstance(target, dict) or not isinstance(updates, dict):
        return updates
    
    for key, updates_value in updates.items():
        if key not in target:
            target[key] = updates_value
        elif isinstance(target[key], list) and isinstance(updates_value, list):
            # Merge lists of dictionaries by key_attr
            target_list = {d[key_attr]: d for d in target[key] if key_attr in d}
            updates_list = {d[key_attr]: d for d in updates_value if key_attr in d}

            # Update existing items
            for item_key in updates_list:
                if item_key in target_list:
                    update_dict_deep(target_list[item_key], updates_list[item_key], key_attr)
                else:
                    target[key].append(updates_list[item_key])
        elif isinstance(target[key], dict) and isinstance(updates_value, dict):
            update_dict_deep(target[key], updates_value, key_attr)
        else:
            target[key] = updates_value
            
    return target


if __name__ == "__main__":
    import doctest
    doctest.testmod()
