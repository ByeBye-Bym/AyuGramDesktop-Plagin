# exteraGram-compatible client helpers for AyuGram Desktop.

import threading

from ayu_plugins import is_main_thread, native, post_to_main

STAGE_QUEUE = "stageQueue"
GLOBAL_QUEUE = "globalQueue"
CACHE_CLEAR_QUEUE = "cacheClearQueue"
SEARCH_QUEUE = "searchQueue"
PHONE_BOOK_QUEUE = "phoneBookQueue"
THEME_QUEUE = "themeQueue"
EXTERNAL_NETWORK_QUEUE = "externalNetworkQueue"
PLUGINS_QUEUE = "pluginsQueue"


def run_on_queue(fn, queue_name=PLUGINS_QUEUE, delay_ms=0):
    timer = threading.Timer(delay_ms / 1000, fn)
    timer.daemon = True
    timer.start()


def _on_main(fn):
    if is_main_thread():
        fn()
    else:
        post_to_main(fn)


def _peer_of(message_obj_or_peer):
    if hasattr(message_obj_or_peer, "getDialogId"):
        return message_obj_or_peer.getDialogId()
    return int(message_obj_or_peer)


def send_text(peer_id, text, replyToMsg=None, parse_mode=None, account=None):
    reply = replyToMsg.getId() if hasattr(replyToMsg, "getId") else (replyToMsg or 0)
    _on_main(lambda: native(
        "send_text", peer=int(peer_id), text=str(text),
        reply_to=int(reply), account=account))


def send_message(params, parse_mode=None):
    text = params.get("message") or params.get("caption")
    if text is None:
        raise NotImplementedError("Only text messages are supported on desktop")
    send_text(params["peer"], text, params.get("replyToMsg"), parse_mode)


def edit_message_local(message_obj, text):
    """Desktop extension: changes message text only on this device."""
    from base_plugin import flush_messages
    message_obj.messageOwner.message = message_obj.messageText = str(text)
    _on_main(flush_messages)


def get_message(peer_id, msg_id, account=0):
    """Desktop extension: returns a MessageObject or None."""
    from base_plugin import MessageObject
    if not is_main_thread():
        raise RuntimeError("get_message must be called on the main thread")
    data = native("get_message", peer=int(peer_id), id=int(msg_id), account=account)
    result = data and data.get("result")
    return MessageObject(result, account) if result else None


class _Adapter:
    def notifyDataSetChanged(self):
        pass  # local edits refresh their messages themselves


class _Activity:
    pass


class _Fragment:
    chatAdapter = _Adapter()

    def getParentActivity(self):
        return _Activity()

    def getContext(self):
        return _Activity()


def get_last_fragment():
    return _Fragment()


def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    raise NotImplementedError(f"client_utils.{name} is not available on desktop")
