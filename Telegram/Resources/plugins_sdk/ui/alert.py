# AlertDialogBuilder rendered as an AyuGram box. EditText views become input fields.

from ayu_plugins import is_main_thread, native, post_to_main

_dialogs = {}
_next = [0]


def _collect(view, fields, labels):
    from android.widget import EditText, LinearLayout, TextView
    if view is None or getattr(view, "visibility", 0) != 0:
        return
    if isinstance(view, EditText):
        fields.append(view)
    elif isinstance(view, TextView):
        if view.text:
            labels.append(view.text)
    elif isinstance(view, LinearLayout):
        for child in view.children:
            _collect(child, fields, labels)


class AlertDialogBuilder:
    BUTTON_POSITIVE = -1
    BUTTON_NEGATIVE = -2
    BUTTON_NEUTRAL = -3

    ALERT_TYPE_MESSAGE = 0
    ALERT_TYPE_SPINNER = 1
    ALERT_TYPE_LOADING = 2

    def __init__(self, context=None, progress_style=0, *args):
        self._title = ""
        self._message = ""
        self._view = None
        self._buttons = {}
        self._fields = []
        self._token = 0
        self._dismissed = False

    def set_title(self, title):
        self._title = str(title)
        return self

    def set_message(self, message):
        self._message = str(message)
        return self

    def set_view(self, view):
        self._view = view
        return self

    def set_positive_button(self, text, listener=None):
        self._buttons[self.BUTTON_POSITIVE] = (str(text), listener)
        return self

    def set_negative_button(self, text, listener=None):
        self._buttons[self.BUTTON_NEGATIVE] = (str(text), listener)
        return self

    def set_neutral_button(self, text, listener=None):
        self._buttons[self.BUTTON_NEUTRAL] = (str(text), listener)
        return self

    def __getattr__(self, name):
        if name.startswith("set_"):
            return lambda *args, **kwargs: self
        raise AttributeError(name)

    def create(self):
        return self

    def show(self):
        if not is_main_thread():
            post_to_main(self.show)
            return self
        labels = [self._message] if self._message else []
        self._fields = []
        _collect(self._view, self._fields, labels)
        _next[0] += 1
        self._token = _next[0]
        self._dismissed = False
        _dialogs[self._token] = self
        order = [self.BUTTON_NEUTRAL, self.BUTTON_NEGATIVE, self.BUTTON_POSITIVE]
        native(
            "dialog_show",
            token=self._token,
            title=self._title,
            message="\n\n".join(labels),
            fields=[
                {"hint": f.hint, "text": f.text, "multiline": f.multiline}
                for f in self._fields
            ],
            buttons=[
                {"which": which, "text": self._buttons[which][0]}
                for which in order if which in self._buttons
            ])
        return self

    def dismiss(self):
        self._dismissed = True
        if self._token in _dialogs:
            _dialogs.pop(self._token)
            native("dialog_dismiss", token=self._token)

    def get_dialog(self):
        return self


def _button(token, which, values):
    builder = _dialogs.get(token)
    if not builder:
        return True
    for field, value in zip(builder._fields, values):
        field.text = value
    listener = builder._buttons.get(which, (None, None))[1]
    if listener is None:
        builder.dismiss()
    else:
        listener(builder, which)
    return builder._dismissed


def _closed(token):
    _dialogs.pop(token, None)
