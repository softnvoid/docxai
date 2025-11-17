def copy_style(run):
    """Copy all font styling attributes from a run.

    Args:
        run: A docx run object

    Returns:
        dict: Dictionary containing all font attributes
    """
    if not run or not hasattr(run, 'font'):
        return {}

    attr_dict = dict()
    for attr in dir(run.font):
        if not attr.startswith("_") and attr != "part":
            try:
                attr_dict[attr] = getattr(run.font, attr)
            except Exception:
                # Skip attributes that can't be read
                continue

    return attr_dict


def apply_style(run, style):
    """Apply font styling attributes to a run.

    Args:
        run: A docx run object to apply style to
        style: Dictionary containing font attributes
    """
    if not run or not hasattr(run, 'font') or not style:
        return

    for attr in style.keys():
        # Skip attributes that shouldn't be set directly
        if attr not in ["color", "element", "part"]:
            try:
                setattr(run.font, attr, style[attr])
            except Exception:
                # Skip attributes that can't be set
                continue
