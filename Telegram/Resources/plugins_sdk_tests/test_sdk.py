import json, os, sys, tempfile, types

sdk = sys.argv[1]
sys.path.insert(0, sdk)
calls = []
fake = types.ModuleType("_ayugram")
fake.request = lambda method, args: (calls.append((method, json.loads(args))), json.dumps({"result": None}))[1]
sys.modules["_ayugram"] = fake

import ayu_plugins, atexit, traceback
sys.excepthook = lambda *e: sys.__stderr__.write("".join(traceback.format_exception(*e)))

tmp = tempfile.mkdtemp()
plugins, data = os.path.join(tmp, "plugins"), os.path.join(tmp, "data")
os.makedirs(plugins)
# data dir must be created by init

HELLO = '''
from typing import Any, List
from base_plugin import BasePlugin, HookResult, HookStrategy, MenuItemData, MenuItemType
from ui.settings import Header, Input, Text, Switch
from client_utils import edit_message_local

__id__ = "hello_world"
__name__ = "Hello World"
__description__ = "Turns .hello commands into greetings"
__version__ = "1.0.0"

class HelloWorldPlugin(BasePlugin):
    def on_plugin_load(self):
        self.add_on_send_message_hook()
        self.add_menu_item(MenuItemData(menu_type=MenuItemType.MESSAGE_CONTEXT_MENU, text="Edit locally", on_click=self.click, item_id="edit"))
    def click(self, ctx):
        edit_message_local(ctx["message"], ctx["message"].messageOwner.message.upper())
    def create_settings(self):
        return [Header(text="Hello"), Input(key="template", text="Template", default="Hello, {name}!"), Switch(key="on", text="On", default=True, on_change=lambda v: self.log(f"on={v}"))]
    def on_send_message_hook(self, account, params):
        if not params.message.startswith(".hello"):
            return HookResult()
        if params.message == ".cancel":
            return HookResult(strategy=HookStrategy.CANCEL)
        params.message = self.get_setting("template", "Hello, {name}!").format(name=params.message[7:])
        return HookResult(strategy=HookStrategy.MODIFY, params=params)
'''
BROKEN = '__id__ = "broken"\n__name__ = "Broken"\nimport nonexistent_mod\n'
open(os.path.join(plugins, "hello.plugin"), "w").write(HELLO)
open(os.path.join(plugins, "broken.plugin"), "w").write(BROKEN)

def call(method, **args):
    r = json.loads(ayu_plugins.handle(method, json.dumps(args)))
    assert r["ok"], r
    return r["result"]

call("init", plugins_dir=plugins, data_dir=data, app_version="test")
lst = {p["id"]: p for p in call("list")}
assert lst["hello_world"]["enabled"] and lst["hello_world"]["has_settings"], lst
assert not lst["broken"]["enabled"] and "nonexistent_mod" in lst["broken"]["error"], lst["broken"]

assert call("send_message", account=0, params={"peer": 1, "message": "hi"}) == {"strategy": "default"}
assert call("send_message", account=0, params={"peer": 1, "message": ".hello Bob"}) == {"strategy": "modify", "message": "Hello, Bob!"}

items = call("settings", id="hello_world")
assert [i["type"] for i in items] == ["header", "input", "switch"], items
call("settings_set", id="hello_world", key="template", value="Hi {name}")
call("settings_set", id="hello_world", key="on", value=False)
assert call("send_message", account=0, params={"peer": 1, "message": ".hello Ann"})["message"] == "Hi Ann"
assert json.load(open(os.path.join(data, "settings", "hello_world.json")))["template"] == "Hi {name}"

menu = call("menu_items", menu_type="MESSAGE_CONTEXT_MENU")
assert menu == [{"plugin": "hello_world", "item": "edit", "text": "Edit locally", "subtext": ""}], menu
msg = {"id": 5, "text": "abc", "date": 0, "out": True, "dialog_id": 1, "from_id": 1}
call("menu_click", plugin="hello_world", item="edit", context={"account": 0, "dialog_id": 1, "message": msg})
assert calls[-1] == ("edit_local", {"peer": 1, "id": 5, "text": "ABC", "account": 0}), calls

call("set_enabled", id="hello_world", enabled=False)
assert call("send_message", account=0, params={"peer": 1, "message": ".hello X"}) == {"strategy": "default"}
assert call("menu_items", menu_type="MESSAGE_CONTEXT_MENU") == []
call("set_enabled", id="hello_world", enabled=True)
assert call("send_message", account=0, params={"peer": 1, "message": ".hello X"})["strategy"] == "modify"

src = os.path.join(tmp, "new.plugin")
open(src, "w").write(HELLO.replace("hello_world", "hello2"))
assert call("install", path=src) == {"id": "hello2", "error": ""}
assert os.path.exists(os.path.join(plugins, "hello2.plugin"))
call("uninstall", id="hello2")
assert "hello2" not in {p["id"] for p in call("list")}

bad = json.loads(ayu_plugins.handle("install", json.dumps({"path": os.path.join(plugins, "missing")})))
assert not bad["ok"]
call("shutdown")
sys.__stdout__.write("SDK OK\n")

