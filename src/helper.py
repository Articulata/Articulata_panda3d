def find_class(lst, attr, eq):
    assert lst, "List can not be empty"
    assert hasattr(lst[0], attr), "Instance has no attribute " + attr
    return [cls for cls in lst if cls.__dict__[attr] == eq][0]


def iter_class_attr(lst: list, attr: str):
    assert hasattr(lst[0], attr), "Instance has no attribute " + attr
    for cls in lst:
        yield cls.__dict__[attr]
