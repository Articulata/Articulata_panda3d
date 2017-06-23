class Test:
    a = 10
    b = 2.2

    def __init__(self, c_):
        self.c = c_
        self.d = self.a * c_

    def multiply(self, num):
        return self.b * num


def find_class(lst, attr, eq):
    assert lst, "List can not be empty"
    assert hasattr(lst[0], attr), "Instance has no attribute " + attr
    return tuple(filter(lambda cls: cls.__dict__[attr] == eq, lst))


def iter_class_attr(lst: list, attr: str):
    assert hasattr(lst[0], attr), "Instance has no attribute " + attr
    for cls in lst:
        yield cls.__dict__[attr]

# Tests
class_list = [Test(1), Test(3), Test(4.4)]
print(*class_list)

for c in iter_class_attr(class_list, "c"):
    print(c)

print(find_class(class_list, "d", 44))

try:
    find_class(class_list, "d", 44)
except AssertionError as e:
    print(e)
