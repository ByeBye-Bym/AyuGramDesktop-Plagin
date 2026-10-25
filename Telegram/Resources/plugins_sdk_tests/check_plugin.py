import json, os, shutil, sys, tempfile, types
sys.path.insert(0, sys.argv[1])
fake = types.ModuleType("_ayugram"); fake.request = lambda m, a: json.dumps({"result": None}); sys.modules["_ayugram"] = fake
import ayu_plugins
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, "p"); os.makedirs(p); shutil.copy(sys.argv[2], p)
call = lambda m, **a: json.loads(ayu_plugins.handle(m, json.dumps(a)))["result"]
call("init", plugins_dir=p, data_dir=tmp, app_version="t")
info = call("list")[0]; assert info["enabled"] and not info["error"], info
assert call("send_message", account=0, params={"peer": 1, "message": ".hello Ann"})["message"] == "Hello, Ann!"
call("settings_set", id="ayu_test", key="case", value=1)
assert call("send_message", account=0, params={"peer": 1, "message": ".hello Ann"})["message"] == "HELLO, ANN!"
assert len(call("settings", id="ayu_test")) == 5
sys.__stdout__.write("PLUGIN OK\n")
