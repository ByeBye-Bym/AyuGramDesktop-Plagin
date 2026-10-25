import base64, json, os, sys, tempfile, types

sdk, api_tl = sys.argv[1], sys.argv[2]
sys.path.insert(0, sdk)
fake = types.ModuleType("_ayugram")
fake.request = lambda method, args: json.dumps({"result": None})
sys.modules["_ayugram"] = fake

import ayu_plugins, tl_schema, traceback
sys.excepthook = lambda *e: sys.__stderr__.write("".join(traceback.format_exception(*e)))

schema = tl_schema.Schema(api_tl)
tl_schema._schema.append(schema)

# Codec round trip, flags and bare vectors.
msg = schema.new("TL_messages_sendMessage",
                 peer=schema.new("TL_inputPeerSelf"), message="привет", random_id=-5,
                 silent=True, entities=[schema.new("TL_messageEntityBold", offset=0, length=3)])
raw = schema.encode(msg)
back = schema.decode(raw)
assert type(back).__name__ == "TL_messages_sendMessage"
assert back.message == "привет" and back.random_id == -5 and back.silent and not back.background
assert back.entities[0].length == 3 and back.reply_to is None
assert schema.encode(back) == raw
back.silent = False
assert schema.decode(schema.encode(back)).silent is False
assert schema.decode(schema.encode([1, 2], "Vector<long>"), "Vector<long>") == [1, 2]
err_raw = bytes.fromhex("19ca4421") + (400).to_bytes(4, "little") + b"\x03ABC"
err = schema.decode(err_raw)
assert isinstance(err, tl_schema.TL_error) and err.code == 400 and err.text == "ABC"

PLUGIN = '''
from base_plugin import BasePlugin, HookResult, HookStrategy

__id__ = "hooks"
__name__ = "Hooks"

class Hooks(BasePlugin):
    def on_plugin_load(self):
        self.add_hook("TL_messages_sendMessage")
        self.add_hook("TL_account_updateStatus")
        self.add_hook("TL_updateUserTyping")
        self.seen = []
    def pre_request_hook(self, name, account, request):
        if name == "TL_account_updateStatus":
            return HookResult(strategy=HookStrategy.CANCEL)
        request.message = request.message.upper()
        return HookResult(strategy=HookStrategy.MODIFY, request=request)
    def post_request_hook(self, name, account, response, error):
        self.seen.append((name, response, error))
        return HookResult()
    def on_update_hook(self, name, account, update):
        return HookResult(strategy=HookStrategy.CANCEL)
'''

tmp = tempfile.mkdtemp()
plugins = os.path.join(tmp, "plugins")
os.makedirs(plugins)
with open(os.path.join(plugins, "hooks.plugin"), "w", encoding="utf-8") as f:
    f.write(PLUGIN)


def call(method, **args):
    result = json.loads(ayu_plugins.handle(method, json.dumps(args)))
    assert result["ok"], result
    return result


r = call("init", plugins_dir=plugins, data_dir=os.path.join(tmp, "data"), app_version="1")
send_id = schema.by_name["TL_messages_sendMessage"].cid
assert send_id in r["request_hooks"] and r["update_hooks"], r

b64 = lambda data: base64.b64encode(data).decode()
out = call("request", account=0, request_id=7, data=b64(raw))["result"]
assert schema.decode(base64.b64decode(out["data"])).message == "ПРИВЕТ"

status = schema.encode(schema.new("TL_account_updateStatus", offline=True))
assert call("request", account=0, request_id=8, data=b64(status))["result"] == {"cancel": True}

assert call("response", account=0, request_id=7, data=b64(err_raw))["result"] == {}
seen = ayu_plugins._plugins["hooks"].instance.seen
assert seen[0][0] == "TL_messages_sendMessage" and seen[0][1] is None and seen[0][2].text == "ABC"

typing = schema.new("TL_updateUserTyping", user_id=1, action=schema.new("TL_sendMessageTypingAction"))
other = schema.new("TL_updateDeleteMessages", messages=[1], pts=2, pts_count=1)
updates = schema.new("TL_updates", updates=[typing, other], users=[], chats=[], date=0, seq=0)
out = call("updates", account=0, data=b64(schema.encode(updates)))["result"]
kept = schema.decode(base64.b64decode(out["data"])).updates
assert [type(u).__name__ for u in kept] == ["TL_updateDeleteMessages"]

short = schema.new("TL_updateShort", update=typing, date=0)
assert call("updates", account=0, data=b64(schema.encode(short)))["result"] == {"drop": True}
