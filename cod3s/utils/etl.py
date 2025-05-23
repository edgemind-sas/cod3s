def update_dict_deep(target, updates, key_attr=None):
    """
    Recursively update a dictionary with another dictionary's values.

    Args:
        target (dict): The target dictionary to be updated.
        updates (dict): The dictionary with updates to apply to target.
        key_attr (str, optional): The attribute name used as a key for matching items
                                  in lists of dictionaries. Default is None, which means
                                  that lists will be replaced rather than merged.

    Returns:
        dict: The updated target dictionary.

    Examples:
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
        >>> update_dict_deep(target_dict, updates_dict, 'name') == {
        ...     'name': 'updated',
        ...     'components': [
        ...         {'name': 'a', 'value': 10},
        ...         {'name': 'b', 'value': 2},
        ...         {'name': 'c', 'value': 3}
        ...     ]
        ... }
        True
        >>> target_dict = {
        ...     'name': 'original',
        ...     'components': [
        ...         {'id': 1, 'value': 'one'},
        ...         {'id': 2, 'value': 'two'}
        ...     ]
        ... }
        >>> updates_dict = {
        ...     'name': 'updated',
        ...     'components': [
        ...         {'id': 1, 'value': 'uno'},
        ...         {'id': 3, 'value': 'tres'}
        ...     ]
        ... }
        >>> update_dict_deep(target_dict, updates_dict) == {
        ...     'name': 'updated',
        ...     'components': [
        ...         {'id': 1, 'value': 'uno'},
        ...         {'id': 3, 'value': 'tres'}
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
            if key_attr:
                # Merge lists of dictionaries by key_attr
                target_list = {d.get(key_attr): d for d in target[key] if key_attr in d}
                updates_list = {
                    d.get(key_attr): d for d in updates_value if key_attr in d
                }
                # Update existing items and append new items
                for item in updates_value:
                    item_key = item.get(key_attr)
                    if item_key in target_list:
                        update_dict_deep(
                            target_list[item_key], updates_list[item_key], key_attr
                        )
                    else:
                        target[key].append(item)
            else:
                # Replace the list in target with the list from updates
                target[key] = updates_value
        elif isinstance(target[key], dict) and isinstance(updates_value, dict):
            update_dict_deep(target[key], updates_value, key_attr)
        else:
            target[key] = updates_value

    return target


def dict_diff(dict_ref, dict_new):
    """
    Calculate the difference between two dictionaries, returning only the
    items from dict_new that are not present in dict_ref. This function
    recursively finds differences in nested dictionaries and lists.

    Args:
        dict_ref (dict): The reference dictionary.
        dict_new (dict): The new dictionary with potential updates.

    Returns:
        dict: A dictionary containing items from dict_new that are not in dict_ref.

    Examples:
    >>> dict_ref = {'a': 1, 'b': {'x': 10, 'y': 20}, 'c': [1, 2, 3]}
    >>> dict_new = {'a': 1, 'b': {'x': 100, 'y': 20}, 'c': [1, 2, 3, 4]}
    >>> dict_diff(dict_ref, dict_new)
    {'b': {'x': 100}, 'c': [4]}

    >>> dict_ref = {'a': 1, 'b': 2}
    >>> dict_new = {'a': 1, 'b': 3}
    >>> dict_diff(dict_ref, dict_new)
    {'b': 3}
    """
    diff = {}
    for key in dict_new:
        # Key is not present in the reference dict, add to diff
        if key not in dict_ref:
            diff[key] = dict_new[key]
        else:
            # If both values are dictionaries, recurse
            if isinstance(dict_new[key], dict) and isinstance(dict_ref[key], dict):
                nested_diff = dict_diff(dict_ref[key], dict_new[key])
                # Only add to diff if there's something different
                if nested_diff:
                    diff[key] = nested_diff
            # If both values are lists, find the difference
            elif isinstance(dict_new[key], list) and isinstance(dict_ref[key], list):
                list_diff = [i for i in dict_new[key] if i not in dict_ref[key]]
                # Only add to diff if there are new items
                if list_diff:
                    diff[key] = list_diff
            # For non-dict, non-list values, check for inequality
            elif dict_new[key] != dict_ref[key]:
                diff[key] = dict_new[key]
    return diff


def remove_key_from_dict(obj, key_to_remove, recursive=False):
    """
    Remove occurrences of a specific key from a dictionary or nested structure.
    Creates and returns a new structure without modifying the input.

    Args:
        obj: The object to process (dict, list, or other value)
        key_to_remove: The key to remove from all dictionaries
        recursive: If True, recursively remove the key from nested structures.
                  If False, only remove from the top level. Default is False.

    Returns:
        A new object with occurrences of key_to_remove removed

    Examples:
        >>> data = {"a": 1, "b": {"a": 2, "c": 3}, "d": [{"a": 4, "e": 5}]}
        >>> remove_key_from_dict(data, "a", recursive=True)
        {'b': {'c': 3}, 'd': [{'e': 5}]}
        >>> remove_key_from_dict(data, "a", recursive=False)
        {'b': {'a': 2, 'c': 3}, 'd': [{'a': 4, 'e': 5}]}
        >>> data  # Original data is unchanged
        {'a': 1, 'b': {'a': 2, 'c': 3}, 'd': [{'a': 4, 'e': 5}]}

        >>> remove_key_from_dict({"x": 1, "y": 2}, "z")  # Key not present
        {'x': 1, 'y': 2}

        >>> remove_key_from_dict([1, 2, {"a": 3}], "a", recursive=True)  # Mixed types
        [1, 2, {}]

        >>> remove_key_from_dict(42, "a")  # Non-container input
        42
    """
    if isinstance(obj, dict):
        # Create a new dictionary excluding the key_to_remove
        if recursive:
            return {
                k: remove_key_from_dict(v, key_to_remove, recursive)
                for k, v in obj.items()
                if k != key_to_remove
            }
        else:
            return {k: v for k, v in obj.items() if k != key_to_remove}
    elif isinstance(obj, list) and recursive:
        # Create a new list with processed items (only if recursive is True)
        return [remove_key_from_dict(item, key_to_remove, recursive) for item in obj]
    else:
        # Return non-container values or lists (when not recursive) as is
        return obj


if __name__ == "__main__":
    import doctest

    doctest.testmod()
