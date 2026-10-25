# Desktop stand-ins for android.widget. Views only hold data, ui.alert renders them.

from android.text import InputType


class _Editable(str):
    def toString(self):
        return str(self)


class View:
    VISIBLE = 0
    INVISIBLE = 4
    GONE = 8

    def __init__(self, context=None, *args):
        self.context = context
        self.visibility = View.VISIBLE

    def setVisibility(self, visibility):
        self.visibility = visibility

    def __getattr__(self, name):
        # Layout and styling setters have no desktop meaning.
        if name.startswith(("set", "add", "request", "post", "invalidate")):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class TextView(View):
    def __init__(self, context=None, *args):
        super().__init__(context)
        self.text = ""
        self.hint = ""

    def setText(self, text, *args):
        self.text = str(text) if text is not None else ""

    def getText(self):
        return _Editable(self.text)

    def setHint(self, hint):
        self.hint = str(hint) if hint is not None else ""


class EditText(TextView):
    def __init__(self, context=None, *args):
        super().__init__(context)
        self.multiline = False
        self.max_length = 0

    def setInputType(self, input_type):
        self.multiline = bool(input_type & InputType.TYPE_TEXT_FLAG_MULTI_LINE)

    def setSingleLine(self, single=True):
        self.multiline = not single

    def setMinLines(self, lines):
        if lines > 1:
            self.multiline = True

    def setLines(self, lines):
        self.setMinLines(lines)


class LinearLayout(View):
    HORIZONTAL = 0
    VERTICAL = 1

    def __init__(self, context=None, *args):
        super().__init__(context)
        self.children = []

    def addView(self, view, *args):
        self.children.append(view)

    def removeAllViews(self):
        self.children.clear()


FrameLayout = LinearLayout


class Toast:
    LENGTH_SHORT = 0
    LENGTH_LONG = 1

    def __init__(self, text):
        self.text = text

    @staticmethod
    def makeText(context, text, duration=0):
        return Toast(str(text))

    def show(self):
        from ayu_plugins import native
        native("toast", text=self.text)
