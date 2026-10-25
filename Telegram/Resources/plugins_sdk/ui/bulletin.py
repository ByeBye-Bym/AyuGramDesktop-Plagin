# Bulletins are shown as AyuGram toasts.

from ayu_plugins import native


class BulletinHelper:
    @staticmethod
    def show_info(message, *args, **kwargs):
        native("toast", text=str(message))

    show_error = show_info
    show_success = show_info
    show_simple = show_info

    @staticmethod
    def show_copied_to_clipboard(*args, **kwargs):
        native("toast", text="Copied to clipboard")
