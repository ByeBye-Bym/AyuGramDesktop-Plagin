# Minimal android_utils replacement for AyuGram Desktop.

import logging

from ayu_plugins import is_main_thread, native, post_to_main

_log = logging.getLogger("android_utils")


def log(message):
    _log.info("%s", message)


def run_on_ui_thread(fn, delay=0):
    if delay:
        import threading
        timer = threading.Timer(delay / 1000, lambda: post_to_main(fn))
        timer.daemon = True
        timer.start()
    elif is_main_thread():
        fn()
    else:
        post_to_main(fn)


def copy_to_clipboard(text):
    native("clipboard", text=str(text))


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise NotImplementedError(f"android_utils.{name} is not available on desktop")
