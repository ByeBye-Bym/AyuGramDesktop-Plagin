# Reflection helpers. Desktop has no Java classes, only a few known names are mapped.

KNOWN_CLASSES = {
    "org.telegram.ui.Cells.ChatMessageCell",
}


class JavaClass:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<JavaClass {self.name}>"


def find_class(name):
    return JavaClass(name) if name in KNOWN_CLASSES else None


def get_private_field(obj, name):
    return getattr(obj, name, None)


def set_private_field(obj, name, value):
    setattr(obj, name, value)
    return True


def get_static_field(cls, name):
    return None


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise NotImplementedError(f"hook_utils.{name} is not available on desktop")
