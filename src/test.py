def core_func(x):
    return x**2


class Core:
    a = 1
    b = 3.2

    def __init__(self):
        self.c = core_func(self.b)
        print("Core inited")

    def core_method(self):
        a2 = self.a * 2
        print(f"Core method executed, 2*a = {a2}")


class Interface(Core):
    plugins = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.plugins.append(cls)

    def __init__(self):
        super().__init__()

        for plugin in self.plugins:
            self.__dict__.update(plugin.__dict__)
            plugin()

    def attributes(self):
        print("Interface attributes:")
        print(*self.__dict__.keys(), sep='\n')


class Plugin1(Interface):
    plugin1_prop = 22

    def __init__(self):
        print("Inited plugin1")

    def new_feature(self):
        print(self.plugin1_prop)


class Plugin2(Interface):
    plugin2_prop = 37

    def __init__(self):
        print("Inited plugin2")

    def also_new_feature(self):
        print(self.plugin2_prop)


total = Interface()
print()
total.attributes()
