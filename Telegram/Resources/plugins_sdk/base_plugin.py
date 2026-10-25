# exteraGram-compatible plugin base for AyuGram Desktop.

import json
import logging
import os
import uuid
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import ayu_plugins


class AppEvent(Enum):
    START = "START"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"


class HookStrategy(Enum):
    DEFAULT = "DEFAULT"
    CANCEL = "CANCEL"
    MODIFY = "MODIFY"
    MODIFY_FINAL = "MODIFY_FINAL"


@dataclass
class HookResult:
    strategy: HookStrategy = HookStrategy.DEFAULT
    request: Any = None
    response: Any = None
    update: Any = None
    updates: Any = None
    params: Any = None


class MenuItemType(Enum):
    MESSAGE_CONTEXT_MENU = "MESSAGE_CONTEXT_MENU"
    DRAWER_MENU = "DRAWER_MENU"
    MAIN_MENU = "MAIN_MENU"
    CHAT_ACTION_MENU = "CHAT_ACTION_MENU"
    PROFILE_ACTION_MENU = "PROFILE_ACTION_MENU"


@dataclass
class MenuItemData:
    menu_type: MenuItemType
    text: str
    on_click: Callable[[Dict[str, Any]], None]
    item_id: Optional[str] = None
    icon: Optional[str] = None
    subtext: Optional[str] = None
    condition: Optional[str] = None
    priority: int = 0


class SendMessageParams:
    """Mimics the Android SendMessageParams fields plugins usually touch."""

    def __init__(self, params):
        self.message = params.get("message")
        self.peer = params.get("peer")
        self.replyToMsgId = params.get("reply_to_msg_id") or 0
        self.caption = None
        self.entities = None


class _MessageOwner:
    def __init__(self, data):
        self.id = data["id"]
        self.message = data["text"]
        self.date = data["date"]
        self.out = data["out"]
        self.dialog_id = data["dialog_id"]
        self.from_id = data["from_id"]
        self.entities = []


_live_messages = weakref.WeakSet()
_pending_messages = []  # strong refs until the next flush, plugins drop them early


class MessageObject:
    """Desktop stand-in for org.telegram.messenger.MessageObject.

    Plugins edit messageOwner.message / .date in place, take_changes() reports
    what differs from the app so it can be applied locally.
    """

    def __init__(self, data, account):
        self.account = account
        self.messageOwner = _MessageOwner(data)
        self.messageText = data["text"]
        self.currentAccount = account
        self._synced = (data["text"], data["date"])
        _live_messages.add(self)
        _pending_messages.append(self)

    def applyNewText(self, *args):
        self.messageText = self.messageOwner.message

    def take_changes(self):
        text = "" if self.messageOwner.message is None else str(self.messageOwner.message)
        date = int(self.messageOwner.date)
        changes = {}
        if text != self._synced[0]:
            changes["text"] = text
        if date != self._synced[1]:
            changes["date"] = date
        self._synced = (text, date)
        return changes

    def getId(self):
        return self.messageOwner.id

    def getDialogId(self):
        return self.messageOwner.dialog_id

    def isOut(self):
        return self.messageOwner.out

    def getSenderId(self):
        return self.messageOwner.from_id

    @property
    def id(self):
        return self.messageOwner.id

    @property
    def text(self):
        return self.messageOwner.message


def flush_messages():
    for message in list(_live_messages):
        changes = message.take_changes()
        if changes:
            ayu_plugins.native(
                "edit_local",
                account=message.account,
                peer=message.getDialogId(),
                id=message.getId(),
                **changes)
    _pending_messages.clear()


class MethodHook:
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        pass


class MethodReplacement(MethodHook):
    def replace_hooked_method(self, param):
        return None


class HookParam:
    def __init__(self, this_object, args):
        self.thisObject = this_object
        self.args = list(args)
        self.result = None
        self.returnEarly = False

    def setResult(self, result):
        self.result = result
        self.returnEarly = True

    def getResult(self):
        return self.result


# Java methods with a desktop equivalent: (class, method) -> event name.
HOOKABLE = {
    ("org.telegram.ui.Cells.ChatMessageCell", "setMessageObject"): "message_bind",
}


def make_menu_context(context):
    result = dict(context)
    message = context.get("message")
    if message:
        result["message"] = MessageObject(message, context.get("account", 0))
    return result


class _PluginLogger:
    def __init__(self, plugin_id):
        self._log = logging.getLogger("plugin." + plugin_id)

    def debug(self, msg, *args):
        self._log.debug(msg, *args)

    def info(self, msg, *args):
        self._log.info(msg, *args)

    def warning(self, msg, *args):
        self._log.warning(msg, *args)

    warn = warning

    def error(self, msg, *args):
        self._log.error(msg, *args)

    def exception(self, msg, *args):
        self._log.exception(msg, *args)

    def dump(self, obj):
        self._log.info("%r: %r", obj, getattr(obj, "__dict__", obj))


class BasePlugin:
    def _ayu_setup(self, meta):
        self.id = meta["id"]
        self.name = meta["name"]
        self.metadata = meta
        self.logger = _PluginLogger(self.id)
        self._ayu_send_hooks = []
        self._ayu_request_hooks = {}
        self._ayu_menu_items = {}
        self._ayu_method_hooks = {}
        self._ayu_settings_cache = None
        self._ayu_settings_path = os.path.join(
            ayu_plugins.data_dir("settings"), self.id + ".json")
        try:
            with open(self._ayu_settings_path, encoding="utf-8") as f:
                self._ayu_values = json.load(f)
        except (OSError, ValueError):
            self._ayu_values = {}

    def _ayu_teardown(self):
        self._ayu_send_hooks.clear()
        self._ayu_request_hooks.clear()
        self._ayu_menu_items.clear()
        self._ayu_method_hooks.clear()

    # ---- lifecycle ----

    def on_plugin_load(self) -> None:
        pass

    def on_plugin_unload(self) -> None:
        pass

    def on_app_event(self, event_type: AppEvent) -> None:
        pass

    def create_settings(self) -> List[Any]:
        return []

    # ---- logging ----

    def log(self, message):
        self.logger.info("%s", message)

    # ---- settings ----

    def get_setting(self, key, default=None):
        return self._ayu_values.get(key, default)

    def set_setting(self, key, value, reload_settings=False):
        self._ayu_values[key] = value
        self._ayu_save()

    def export_settings(self) -> dict:
        return dict(self._ayu_values)

    def import_settings(self, settings, reload_settings=True):
        self._ayu_values = dict(settings)
        self._ayu_save()

    def _ayu_save(self):
        with open(self._ayu_settings_path, "w", encoding="utf-8") as f:
            json.dump(self._ayu_values, f, ensure_ascii=False, indent=2)

    def _ayu_has_settings(self):
        try:
            return bool(self.create_settings())
        except Exception:
            return False

    def _ayu_settings_dump(self):
        from ui import settings as ui
        self._ayu_settings_cache = items = self.create_settings() or []
        result = []
        for item in items:
            if isinstance(item, ui.Header):
                result.append({"type": "header", "text": item.text})
            elif isinstance(item, ui.Divider):
                result.append({"type": "divider", "text": item.text or ""})
            elif isinstance(item, ui.Switch):
                result.append({
                    "type": "switch", "key": item.key, "text": item.text,
                    "subtext": item.subtext or "",
                    "value": bool(self.get_setting(item.key, item.default)),
                })
            elif isinstance(item, ui.Selector):
                result.append({
                    "type": "selector", "key": item.key, "text": item.text,
                    "items": [str(i) for i in item.items],
                    "value": int(self.get_setting(item.key, item.default) or 0),
                })
            elif isinstance(item, (ui.Input, ui.EditText)):
                default = item.default if item.default is not None else ""
                result.append({
                    "type": "input", "key": item.key,
                    "text": getattr(item, "text", None) or getattr(item, "hint", ""),
                    "subtext": getattr(item, "subtext", None) or "",
                    "multiline": bool(getattr(item, "multiline", False)),
                    "value": str(self.get_setting(item.key, default)),
                })
            elif isinstance(item, ui.Text):
                result.append({
                    "type": "text", "text": item.text,
                    "subtext": item.subtext or "",
                    "clickable": item.on_click is not None,
                    "red": bool(item.red), "accent": bool(item.accent),
                })
            else:
                result.append({"type": "unsupported"})
        return result

    def _ayu_settings_set(self, key, value):
        self.set_setting(key, value)
        for item in self._ayu_settings_cache or []:
            if getattr(item, "key", None) == key and getattr(item, "on_change", None):
                try:
                    item.on_change(value)
                except Exception:
                    self.logger.exception("on_change failed")

    def _ayu_settings_click(self, index):
        items = self._ayu_settings_cache or []
        if 0 <= index < len(items) and getattr(items[index], "on_click", None):
            try:
                items[index].on_click(None)
            except Exception:
                self.logger.exception("on_click failed")

    # ---- hooks ----

    def add_on_send_message_hook(self, priority: int = 0):
        self._ayu_send_hooks.append(priority)

    def remove_on_send_message_hook(self):
        self._ayu_send_hooks.clear()

    def add_hook(self, name: str, match_substring: bool = False, priority: int = 0):
        self._ayu_request_hooks[name] = (priority, match_substring)

    def remove_hook(self, name: str):
        self._ayu_request_hooks.pop(name, None)

    def on_send_message_hook(self, account: int, params: Any) -> HookResult:
        return HookResult()

    def pre_request_hook(self, request_name, account, request) -> HookResult:
        return HookResult()

    def post_request_hook(self, request_name, account, response, error) -> HookResult:
        return HookResult()

    def on_update_hook(self, update_name, account, update) -> HookResult:
        return HookResult()

    def on_updates_hook(self, container_name, account, updates) -> HookResult:
        return HookResult()

    # ---- Java method hooks, only the HOOKABLE ones fire ----

    def hook_all_methods(self, cls, method_name, hook, priority=0):
        event = HOOKABLE.get((getattr(cls, "name", None), method_name))
        if not event:
            self.logger.warning("Hooking %s.%s is not supported on desktop", cls, method_name)
            return []
        self._ayu_method_hooks.setdefault(event, []).append(hook)
        return [hook]

    def hook_all_constructors(self, cls, hook, priority=0):
        self.logger.warning("Hooking constructors of %s is not supported on desktop", cls)
        return []

    def hook_method(self, method, hook, priority=0):
        self.logger.warning("hook_method is not supported on desktop, use hook_all_methods")
        return None

    def unhook_method(self, unhook):
        for hooks in self._ayu_method_hooks.values():
            if unhook in hooks:
                hooks.remove(unhook)

    def _ayu_run_method_hooks(self, event, this_object, args):
        for hook in list(self._ayu_method_hooks.get(event, [])):
            param = HookParam(this_object, args)
            try:
                hook.before_hooked_method(param)
                hook.after_hooked_method(param)
            except Exception:
                self.logger.exception("Method hook failed")

    # ---- menu ----

    def add_menu_item(self, data: MenuItemData):
        item_id = data.item_id or uuid.uuid4().hex
        self._ayu_menu_items[item_id] = data
        return item_id

    def remove_menu_item(self, item_id):
        return self._ayu_menu_items.pop(item_id, None) is not None
