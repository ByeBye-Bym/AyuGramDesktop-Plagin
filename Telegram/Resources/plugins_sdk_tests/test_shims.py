import datetime, json, os, shutil, sys, tempfile, threading, types

sdk, plugin_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, sdk)
calls = []
fake = types.ModuleType("_ayugram")
fake.request = lambda m, a: (calls.append((m, json.loads(a))), json.dumps({"result": None}))[1]
sys.modules["_ayugram"] = fake
import ayu_plugins, traceback
sys.excepthook = lambda *e: sys.__stderr__.write("".join(traceback.format_exception(*e)))

tmp = tempfile.mkdtemp()
p = os.path.join(tmp, "p")
os.makedirs(p)
shutil.copy(plugin_path, p)

def raw(m, **a):
    return json.loads(ayu_plugins.handle(m, json.dumps(a)))

def call(m, **a):
    r = raw(m, **a)
    assert r["ok"], r
    return r["result"]

call("init", plugins_dir=p, data_dir=os.path.join(tmp, "d"), app_version="t")
info = call("list")[0]
assert info["enabled"] and not info["error"], info["error"]
assert raw("list")["message_hooks"] is True

menu = call("menu_items", menu_type="MESSAGE_CONTEXT_MENU")
assert [m["text"] for m in menu] == ["Edit", "Restore"], menu

date = int(datetime.datetime(2026, 10, 25, 14, 30).timestamp())
msg = {"id": 7, "text": "привет", "date": date, "out": True, "dialog_id": 42, "from_id": 1}
ctx = {"account": 0, "dialog_id": 42, "message": msg}

calls.clear()
call("menu_click", plugin="shim_example", item=menu[0]["item"], context=ctx)
show = [c for c in calls if c[0] == "dialog_show"]
assert show, calls
d = show[0][1]
assert d["title"] == "Edit" and len(d["fields"]) == 2, d
assert d["fields"][0]["text"] == "привет" and d["fields"][0]["multiline"], d
assert d["fields"][1]["text"] == "14:30", d
assert [b["which"] for b in d["buttons"]] == [-2, -1], d

# bad time keeps dialog open
calls.clear()
assert call("dialog_button", token=d["token"], which=-1, values=["пока", "25:99"]) == {"dismiss": False}
assert ("toast", {"text": "Bad time"}) in calls, calls

calls.clear()
assert call("dialog_button", token=d["token"], which=-1, values=["пока", "09:05"]) == {"dismiss": True}
new_date = int(datetime.datetime(2026, 10, 25, 9, 5).timestamp())
edits = [c[1] for c in calls if c[0] == "edit_local"]
assert edits == [{"account": 0, "peer": 42, "id": 7, "text": "пока", "date": new_date}], calls
assert ("dialog_dismiss", {"token": d["token"]}) in calls

# reload of the same message re-applies the saved edit
assert call("message_bind", account=0, message=msg) == {"text": "пока", "date": new_date}
other = dict(msg, id=8)
assert call("message_bind", account=0, message=other) == {}

# restore
calls.clear()
call("menu_click", plugin="shim_example", item=menu[1]["item"], context={"account": 0, "message": dict(msg, text="пока", date=new_date)})
edits = [c[1] for c in calls if c[0] == "edit_local"]
assert edits == [{"account": 0, "peer": 42, "id": 7, "text": "привет", "date": date}], calls
assert call("message_bind", account=0, message=msg) == {}

# cancel button
calls.clear()
call("menu_click", plugin="shim_example", item=menu[0]["item"], context=ctx)
t = [c for c in calls if c[0] == "dialog_show"][0][1]["token"]
assert call("dialog_button", token=t, which=-2, values=["x", "10:00"]) == {"dismiss": True}
assert not [c for c in calls if c[0] == "edit_local"]

call("set_enabled", id="shim_example", enabled=False)
assert raw("list")["message_hooks"] is False
sys.__stdout__.write("SHIMS OK\n")
