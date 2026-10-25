# Reads and writes raw MTProto objects using api.tl, for request/update hooks.

import os
import re
import struct

VECTOR = 0x1cb5c415
BOOL_TRUE = 0x997275b5
BOOL_FALSE = 0xbc799737
RPC_ERROR = 0x2144ca19

_LINE = re.compile(r"^([\w.]+)#([0-9a-f]+)\s*(.*?)\s*=\s*([\w.<>]+)\s*;$")
_PRIMITIVES = {"int", "long", "double", "string", "bytes", "int128", "int256", "true", "#"}


class Combinator:
    def __init__(self, name, cid, params, result, is_function):
        self.name = name
        self.cid = cid
        self.params = params  # [(field, type, (flags_field, bit) | None)]
        self.result = result
        self.is_function = is_function
        self.java_name = "TL_" + name.replace(".", "_")
        self.cls = None


class TLObject:
    """A decoded TL object, fields are plain attributes named as in api.tl."""

    def _fields(self):
        return {k: v for k, v in vars(self).items() if not k.startswith("_")}

    def __repr__(self):
        args = ", ".join(f"{k}={v!r}" for k, v in self._fields().items())
        return f"{type(self).__name__}({args})"


class TL_error(TLObject):
    def __init__(self, code, text):
        self.code = code
        self.text = text


class Schema:
    def __init__(self, path):
        self.by_id = {}
        self.by_name = {}
        is_function = False
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line == "---functions---":
                    is_function = True
                elif line == "---types---":
                    is_function = False
                match = _LINE.match(line)
                if not match:
                    continue
                name, cid, args, result = match.groups()
                params = []
                for arg in args.split():
                    if arg.startswith("{") or ":" not in arg:
                        continue
                    field, kind = arg.split(":", 1)
                    cond = None
                    if "?" in kind:
                        flag, kind = kind.split("?", 1)
                        flags_field, bit = flag.split(".")
                        cond = (flags_field, int(bit))
                    params.append((field, kind, cond))
                c = Combinator(name, int(cid, 16), params, result, is_function)
                self.by_id[c.cid] = c
                self.by_name[c.java_name] = c

    def new(self, java_name, **fields):
        c = self.by_name[java_name]
        obj = self._class(c)()
        for field, kind, cond in c.params:
            if kind != "#":
                setattr(obj, field, fields.get(field, False if kind == "true" else None))
        return obj

    def _class(self, c):
        if c.cls is None:
            c.cls = type(c.java_name, (TLObject,), {"_combinator": c})
        return c.cls

    # ---- reading ----

    def decode(self, data, kind=None):
        reader = _Reader(data)
        if reader.peek() == RPC_ERROR:
            reader.u32()
            return TL_error(reader.i32(), reader.string())
        return self._read(reader, kind or "Object")

    def _read(self, r, kind):
        if kind == "int":
            return r.i32()
        if kind == "long":
            return r.unpack("<q", 8)
        if kind == "double":
            return r.unpack("<d", 8)
        if kind == "int128":
            return r.take(16)
        if kind == "int256":
            return r.take(32)
        if kind == "bytes":
            return r.raw_string()
        if kind == "string":
            return r.string()
        if kind == "Bool":
            return r.u32() == BOOL_TRUE
        if kind.startswith(("Vector<", "vector<")):
            if kind[0] == "V" and r.u32() != VECTOR:
                raise ValueError("Vector expected")
            inner = kind[7:-1]
            return [self._read(r, inner) for _ in range(r.i32())]
        cid = r.u32()
        c = self.by_id.get(cid)
        if c is None:
            raise ValueError(f"Unknown constructor {cid:#010x}")
        obj = self._class(c)()
        flags = {}
        for field, ptype, cond in c.params:
            if ptype == "#":
                flags[field] = r.u32()
                setattr(obj, "_" + field, flags[field])
                continue
            if cond and not (flags[cond[0]] >> cond[1]) & 1:
                setattr(obj, field, False if ptype == "true" else None)
                continue
            if ptype == "true":
                setattr(obj, field, True)
            elif ptype == "!X":
                setattr(obj, field, self._read(r, "Object"))
            else:
                setattr(obj, field, self._read(r, ptype))
        return obj

    # ---- writing ----

    def encode(self, obj, kind=None):
        out = bytearray()
        self._write(out, obj, kind or "Object")
        return bytes(out)

    def _write(self, out, value, kind):
        if kind == "int":
            out += struct.pack("<i", value)
        elif kind == "long":
            out += struct.pack("<q", value)
        elif kind == "double":
            out += struct.pack("<d", value)
        elif kind in ("int128", "int256"):
            out += value
        elif kind in ("bytes", "string"):
            _put_string(out, value.encode("utf-8") if isinstance(value, str) else bytes(value))
        elif kind == "Bool":
            out += struct.pack("<I", BOOL_TRUE if value else BOOL_FALSE)
        elif kind.startswith(("Vector<", "vector<")):
            if kind[0] == "V":
                out += struct.pack("<I", VECTOR)
            out += struct.pack("<i", len(value))
            for item in value:
                self._write(out, item, kind[7:-1])
        else:
            c = getattr(type(value), "_combinator", None)
            if c is None:
                raise TypeError(f"Can't serialize {type(value).__name__} as {kind}")
            out += struct.pack("<I", c.cid)
            flags = {}
            for field, ptype, cond in c.params:
                if ptype == "#":
                    flags[field] = getattr(value, "_" + field, 0)
                elif cond:
                    field_value = getattr(value, field, None)
                    present = bool(field_value) if ptype == "true" else field_value is not None
                    mask = 1 << cond[1]
                    flags[cond[0]] = (flags[cond[0]] | mask) if present else (flags[cond[0]] & ~mask)
            for field, ptype, cond in c.params:
                if ptype == "#":
                    out += struct.pack("<I", flags[field])
                elif cond and not (flags[cond[0]] >> cond[1]) & 1:
                    continue
                elif ptype != "true":
                    self._write(out, getattr(value, field), "Object" if ptype == "!X" else ptype)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def take(self, size):
        if self.pos + size > len(self.data):
            raise ValueError("Unexpected end of data")
        chunk = self.data[self.pos:self.pos + size]
        self.pos += size
        return chunk

    def unpack(self, fmt, size):
        return struct.unpack(fmt, self.take(size))[0]

    def peek(self):
        return struct.unpack_from("<I", self.data, 0)[0] if len(self.data) >= 4 else 0

    def u32(self):
        return self.unpack("<I", 4)

    def i32(self):
        return self.unpack("<i", 4)

    def raw_string(self):
        size = self.take(1)[0]
        header = 1
        if size == 254:
            size = int.from_bytes(self.take(3), "little")
            header = 4
        value = self.take(size)
        self.take((-(header + size)) % 4)
        return value

    def string(self):
        return self.raw_string().decode("utf-8", errors="replace")


def _put_string(out, data):
    size = len(data)
    if size < 254:
        out.append(size)
        header = 1
    else:
        out += bytes([254]) + size.to_bytes(3, "little")
        header = 4
    out += data
    out += bytes((-(header + size)) % 4)


_schema = []


def schema():
    if not _schema:
        _schema.append(Schema(os.path.join(os.path.dirname(__file__), "api.tl")))
    return _schema[0]
