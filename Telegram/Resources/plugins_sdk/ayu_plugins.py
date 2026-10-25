# Plugin loader for AyuGram Desktop.
# C++ calls handle(method, args_json) and gets a JSON string back.

import ast
import importlib.machinery
import importlib.util
import json
import logging
import os
import shutil
import sys
import threading
import traceback

import _ayugram

log = logging.getLogger("plugins")

_state = {
    "plugins_dir": "",
    "data_dir": "",
    "main_thread": None,
}
_plugins = {}  # id -> Entry
_callbacks = {}  # token -> callable, for run_on_ui_thread
_next_token = [0]
_lock = threading.Lock()

ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


class Entry:
    def __init__(self, path, meta):
        self.path = path
        self.meta = meta
        self.module = None
        self.instance = None
        self.error = ""


class _LogWriter:
    def __init__(self, level):
        self.level = level

    def write(self, text):
        text = text.rstrip()
        if text:
            log.log(self.level, text)

    def flush(self):
        pass


def native(method, **args):
    result = _ayugram.request(method, json.dumps(args))
    return json.loads(result) if result else None


def is_main_thread():
    return threading.get_ident() == _state["main_thread"]


def post_to_main(fn):
    with _lock:
        _next_token[0] += 1
        token = _next_token[0]
        _callbacks[token] = fn
    native("call_later", token=token)


def data_dir(*parts):
    path = os.path.join(_state["data_dir"], *parts)
    os.makedirs(path, exist_ok=True)
    return path


def parse_metadata(source):
    meta = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        name = target.id
        if not (name.startswith("__") and name.endswith("__")):
            continue
        try:
            meta[name[2:-2]] = ast.literal_eval(node.value)
        except ValueError:
            pass
    plugin_id = meta.get("id")
    if not isinstance(plugin_id, str) or not (2 <= len(plugin_id) <= 32) \
            or not plugin_id[0].isalpha() or not set(plugin_id) <= ID_CHARS:
        raise ValueError("Invalid or missing __id__")
    if not isinstance(meta.get("name"), str) or not meta["name"]:
        raise ValueError("Missing __name__")
    meta.setdefault("version", "1.0")
    return meta


def _enabled_path():
    return os.path.join(data_dir(), "enabled.json")


def _load_enabled():
    try:
        with open(_enabled_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_enabled(enabled):
    with open(_enabled_path(), "w", encoding="utf-8") as f:
        json.dump(enabled, f, ensure_ascii=False, indent=2)


def _activate(entry):
    import base_plugin
    plugin_id = entry.meta["id"]
    module_name = "ayu_plugin_" + plugin_id.replace("-", "_")
    loader = importlib.machinery.SourceFileLoader(module_name, entry.path)
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
        classes = [
            value for value in vars(module).values()
            if isinstance(value, type)
            and issubclass(value, base_plugin.BasePlugin)
            and value is not base_plugin.BasePlugin
            and value.__module__ == module.__name__  # plugins overwrite __name__
        ]
        if not classes:
            raise RuntimeError("No BasePlugin subclass found")
        instance = classes[0].__new__(classes[0])
        instance._ayu_setup(entry.meta)
        instance.__init__()
        entry.module = module
        entry.instance = instance
        instance.on_plugin_load()
        instance.on_app_event(base_plugin.AppEvent.START)
        entry.error = ""
    except Exception:
        entry.error = traceback.format_exc(limit=5)
        log.error("Failed to load %s:\n%s", plugin_id, entry.error)
        entry.module = None
        entry.instance = None
        sys.modules.pop(module_name, None)


def _deactivate(entry):
    instance = entry.instance
    if not instance:
        return
    try:
        instance.on_plugin_unload()
    except Exception:
        log.exception("on_plugin_unload failed for %s", entry.meta["id"])
    instance._ayu_teardown()
    entry.instance = None
    entry.module = None


def _scan():
    enabled = _load_enabled()
    for name in sorted(os.listdir(_state["plugins_dir"])):
        if not name.endswith((".plugin", ".py")):
            continue
        path = os.path.join(_state["plugins_dir"], name)
        try:
            with open(path, encoding="utf-8") as f:
                meta = parse_metadata(f.read())
        except Exception as e:
            log.error("Skipping %s: %s", name, e)
            continue
        entry = Entry(path, meta)
        _plugins[meta["id"]] = entry
        if enabled.get(meta["id"], True):
            _activate(entry)


def _active():
    return [e.instance for e in _plugins.values() if e.instance]


def _sorted_by_priority(items):
    return sorted(items, key=lambda pair: -pair[0])


# ---- handlers called from C++ ----

def h_init(plugins_dir, data_dir, app_version):
    _state["plugins_dir"] = plugins_dir
    _state["data_dir"] = data_dir
    _state["app_version"] = app_version
    _state["main_thread"] = threading.get_ident()
    os.makedirs(plugins_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(data_dir, "plugins.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8")
    sys.stdout = _LogWriter(logging.INFO)
    sys.stderr = _LogWriter(logging.ERROR)
    _scan()
    log.info("Loaded %d plugin(s)", len(_active()))


def h_shutdown():
    import base_plugin
    for entry in _plugins.values():
        if entry.instance:
            try:
                entry.instance.on_app_event(base_plugin.AppEvent.STOP)
            except Exception:
                log.exception("on_app_event failed")
            _deactivate(entry)


def h_list():
    result = []
    for entry in _plugins.values():
        meta = entry.meta
        result.append({
            "id": meta["id"],
            "name": meta["name"],
            "description": str(meta.get("description", "")),
            "author": str(meta.get("author", "")),
            "version": str(meta.get("version", "")),
            "enabled": entry.instance is not None,
            "error": entry.error,
            "has_settings": bool(entry.instance and entry.instance._ayu_has_settings()),
        })
    return sorted(result, key=lambda p: p["name"].lower())


def h_set_enabled(id, enabled):
    entry = _plugins[id]
    states = _load_enabled()
    states[id] = enabled
    _save_enabled(states)
    if enabled and not entry.instance:
        _activate(entry)
    elif not enabled:
        _deactivate(entry)
        entry.error = ""


def h_install(path):
    with open(path, encoding="utf-8") as f:
        meta = parse_metadata(f.read())
    plugin_id = meta["id"]
    old = _plugins.get(plugin_id)
    if old:
        _deactivate(old)
        if os.path.abspath(old.path) != os.path.abspath(
                os.path.join(_state["plugins_dir"], plugin_id + ".plugin")):
            os.remove(old.path)
    target = os.path.join(_state["plugins_dir"], plugin_id + ".plugin")
    if os.path.abspath(path) != os.path.abspath(target):
        shutil.copyfile(path, target)
    entry = Entry(target, meta)
    _plugins[plugin_id] = entry
    states = _load_enabled()
    states[plugin_id] = True
    _save_enabled(states)
    _activate(entry)
    return {"id": plugin_id, "error": entry.error}


def h_uninstall(id):
    entry = _plugins.pop(id)
    _deactivate(entry)
    os.remove(entry.path)
    states = _load_enabled()
    states.pop(id, None)
    _save_enabled(states)


def h_send_message(account, params):
    from base_plugin import HookStrategy, SendMessageParams
    obj = SendMessageParams(params)
    hooks = []
    for instance in _active():
        for priority in instance._ayu_send_hooks:
            hooks.append((priority, instance))
    modified = False
    for _, instance in _sorted_by_priority(hooks):
        try:
            result = instance.on_send_message_hook(account, obj)
        except Exception:
            instance.logger.exception("on_send_message_hook failed")
            continue
        if result is None:
            continue
        if result.strategy == HookStrategy.CANCEL:
            return {"strategy": "cancel"}
        if result.strategy in (HookStrategy.MODIFY, HookStrategy.MODIFY_FINAL):
            if result.params is not None:
                obj = result.params
            modified = True
            if result.strategy == HookStrategy.MODIFY_FINAL:
                break
    if not modified:
        return {"strategy": "default"}
    return {"strategy": "modify", "message": str(getattr(obj, "message", "") or "")}


def h_menu_items(menu_type):
    result = []
    for instance in _active():
        for item_id, data in instance._ayu_menu_items.items():
            if data.menu_type.name != menu_type:
                continue
            result.append((data.priority, {
                "plugin": instance.id,
                "item": item_id,
                "text": data.text,
                "subtext": data.subtext or "",
            }))
    return [item for _, item in _sorted_by_priority(result)]


def h_menu_click(plugin, item, context):
    from base_plugin import flush_messages, make_menu_context
    entry = _plugins.get(plugin)
    if not entry or not entry.instance:
        return
    data = entry.instance._ayu_menu_items.get(item)
    if not data:
        return
    try:
        data.on_click(make_menu_context(context))
    except Exception:
        entry.instance.logger.exception("Menu item handler failed")
    flush_messages()


def h_message_bind(account, message):
    from base_plugin import MessageObject, _pending_messages
    obj = MessageObject(message, account)
    _pending_messages.remove(obj)  # changes are returned directly, not flushed
    for instance in _active():
        instance._ayu_run_method_hooks("message_bind", None, [obj])
    return obj.take_changes()


def h_dialog_button(token, which, values):
    from base_plugin import flush_messages
    from ui import alert
    keep_alive = alert._dialogs.get(token)  # its listeners own the edited messages until flush
    try:
        dismiss = alert._button(token, which, values)
    except Exception:
        log.exception("Dialog button handler failed")
        dismiss = False
    flush_messages()
    return {"dismiss": dismiss}


def h_dialog_closed(token):
    from ui import alert
    alert._closed(token)


def h_settings(id):
    entry = _plugins.get(id)
    if not entry or not entry.instance:
        return []
    return entry.instance._ayu_settings_dump()


def h_settings_set(id, key, value):
    _plugins[id].instance._ayu_settings_set(key, value)


def h_settings_click(id, index):
    from base_plugin import flush_messages
    _plugins[id].instance._ayu_settings_click(index)
    flush_messages()


def h_callback(token):
    from base_plugin import flush_messages
    with _lock:
        fn = _callbacks.pop(token, None)
    if fn:
        try:
            fn()
        except Exception:
            log.exception("Callback failed")
    flush_messages()


def _has_message_hooks():
    return any(i._ayu_method_hooks.get("message_bind") for i in _active())


def handle(method, args_json):
    try:
        args = json.loads(args_json) if args_json else {}
        result = globals()["h_" + method](**args)
        return json.dumps({
            "ok": True,
            "result": result,
            "message_hooks": _has_message_hooks(),
        })
    except Exception as e:
        log.exception("handle(%s) failed", method)
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})
