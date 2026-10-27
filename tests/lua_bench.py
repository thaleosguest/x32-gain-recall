"""Banc d'essai Lua du template TouchOSC (27/10/2026) : fait tourner les scripts du template HORS de TouchOSC, avec une
imitation minimale de son API (arbre des contrôles, findByName, values, Color, AlignH / Shape / OutlineStyle /
PointerState, getMillis, sendOSC). Sert à trouver les erreurs Lua avant un essai sur la tablette (un script racine en
erreur n'envoie plus de hello : « la tablette ne se connecte pas », a14).

Il faut le module lupa (Lua dans Python) : `py -3.14 -m pip install --target <dossier> lupa`, puis
    py -3.14 tests/lua_bench.py [<dossier de lupa>]
Le moteur est Lua 5.4 (lupa.lua54) ; TouchOSC suit le Lua 5.4 lui aussi (entiers / réels).
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
import lupa.lua54 as lupa  # noqa: E402
from touchosc import build_tosc, protocol as P, views  # noqa: E402
from touchosc.tosc import Color, Rect  # noqa: E402


def lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, Color):
        return "Color(%s)" % ", ".join(repr(c / 255.0) for c in v)
    if isinstance(v, Rect):
        return "{x=%s, y=%s, w=%s, h=%s}" % tuple(v)
    return repr(str(v)).replace("\\'", "'") if "'" not in str(v) else '"%s"' % str(v).replace('"', '\\"')


API = r'''
local api = {}
local clock = 0
function api.getMillis() clock = clock + 16 ; return clock end
api.Color = setmetatable({}, { __call = function(_, r, g, b, a) return { r = r, g = g, b = b, a = a or 1 } end })
api.Color.fromHexString = function(s) return { hex = s } end
api.AlignH = { LEFT = 1, CENTER = 2, RIGHT = 3 }
api.AlignV = { TOP = 1, MIDDLE = 2, BOTTOM = 3 }
api.Shape = { RECTANGLE = 0, CIRCLE = 1 }
api.OutlineStyle = { FULL = 0, CORNERS = 1, EDGES = 2 }
api.PointerState = { BEGIN = 0, MOVE = 1, END = 2 }
api.Response = { ABSOLUTE = 0, RELATIVE = 1 }
api.sent = {}
function api.sendOSC(path, ...) table.insert(api.sent, { path, select('#', ...) }) end
api.math, api.string, api.table, api.pairs, api.ipairs, api.tostring, api.tonumber = math, string, table, pairs, ipairs, tostring, tonumber
api.type, api.print, api.select, api.next, api.error, api.pcall = type, print, select, next, error, pcall

local Control = {}
Control.__index = Control
function Control:findByName(name, recursive)
  for _, ch in ipairs(self.children) do
    if ch.name == name then return ch end
  end
  if recursive then
    for _, ch in ipairs(self.children) do
      local hit = ch:findByName(name, true)
      if hit then return hit end
    end
  end
  return nil
end
api.Control = Control
function api.node(name, props, values)
  local n = setmetatable({ name = name, children = {}, values = values, properties = props }, Control)
  for k, v in pairs(props) do n[k] = v end
  return n
end
return api
'''


def build_lua_tree(root):
    """Code Lua qui construit l'arbre des contrôles du template et range chaque script à charger."""
    lines, scripts = ["local api = ...", "local Color = api.Color", "local node = api.node", "local nodes = {}"], []

    def walk(n, parent_var, idx):
        idx[0] += 1
        var = "nodes[%d]" % idx[0]                 # (une table : Lua limite les variables locales à 200)
        props = ", ".join("[%r] = %s" % (k, lua_value(v)) for k, v in n.props.items() if k != "script")
        vals = {"touch": False, "x": 0.0, "text": ""}
        vals.update(n.values)
        values = ", ".join("[%r] = %s" % (k, lua_value(v)) for k, v in vals.items())
        lines.append("%s = node(%r, {%s}, {%s})" % (var, n.name, props, values))
        if parent_var:
            lines.append("%s.parent = %s ; table.insert(%s.children, %s)" % (var, parent_var, parent_var, var))
        if n.props.get("script"):
            scripts.append((var, n.name, n.props["script"]))
            lines.append("%s.__script_index = %d" % (var, len(scripts)))
        for ch in n.children:
            walk(ch, var, idx)
        return var

    rv = walk(root, None, [0])
    lines.append("return %s, nodes" % rv)
    return "\n".join(lines), scripts


def run(messages, drop=None):
    """Charge tous les scripts du template ; script racine : init, update, puis les messages de Gain Recall. Rend la
    liste des erreurs (texte). drop : nom d'un contrôle retiré du template (essai de robustesse)."""
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    api = lua.execute(API)
    root_def = build_tosc.build()
    if drop:
        def cut(n):
            n.children = [c for c in n.children if c.name != drop]
            for c in n.children:
                cut(c)
        cut(root_def)
    code, scripts = build_lua_tree(root_def)
    root, nodes = lua.execute(code, api)
    errors, envs = [], {}
    make_env = lua.eval('''function(api, self)
        local env = setmetatable({ self = self }, { __index = api })
        env.root = self
        while env.root.parent do env.root = env.root.parent end
        return env
    end''')
    load = lua.eval("function(src, name, env) return load(src, name, 't', env) end")
    call = lua.eval('''function(env, fname, ...)
        local f = rawget(env, fname)
        if f == nil then return true end
        local ok, err = pcall(f, ...)
        if not ok then return tostring(err) end
        return true
    end''')
    for i in range(1, len(nodes) + 1):
        n = nodes[i]
        idx = n["__script_index"]
        if idx is None:
            continue
        _var, name, src = scripts[idx - 1]
        env = make_env(api, n)
        chunk = load(src, "=" + name, env)
        if isinstance(chunk, tuple) or chunk is None:
            errors.append("%s : syntaxe : %s" % (name, chunk[1] if isinstance(chunk, tuple) else "?"))
            continue
        err = lua.eval("function(f) local ok, e = pcall(f) ; if ok then return '' end ; return tostring(e) end")(chunk)
        if err:
            errors.append("%s : chargement : %s" % (name, err))
            continue
        envs[name] = env
        r = call(env, "init")
        if r is not True:
            errors.append("%s : init : %s" % (name, r))
    env = envs.get("root")
    if env is None:
        return errors + ["root : script absent ou en erreur"]
    for _ in range(3):
        r = call(env, "update")
        if r is not True:
            errors.append("root : update : %s" % r)
            break
    sent = [api.sent[i][1] for i in range(1, len(api.sent) + 1)]
    if "/xgr/hello" not in sent:
        errors.append("root : aucun /xgr/hello envoyé")
    if "/xgr/error" in sent:
        errors.append("root : /xgr/error envoyé (erreur Lua remontée)")
    mk = lua.eval('''function(path, args)
        return { path, args }
    end''')
    for address, args in messages:
        targs = lua.table(*[lua.table_from({"tag": t, "value": v}) for t, v in args])
        r = call(env, "onReceiveOSC", mk(address, targs), lua.table())
        if r is not True:
            errors.append("root : onReceiveOSC %s : %s" % (address, r))
    for _ in range(3):
        r = call(env, "update")
        if r is not True:
            errors.append("root : update (après les messages) : %s" % r)
            break
    return errors


def sample_messages():
    """Messages réalistes : welcome, puis tout l'état d'une page (couche Masters avec LR / C / M, entrées, scènes)."""
    sets80 = {"sets": {"input": [("Ch 1-16", [(0, i) for i in range(16)])],
                       "mix": [("Groups", [(1, i) for i in range(16)]), ("Masters", [(3, 0), (4, 0), (5, 0), None, (7, 0)])],
                       "custom0": [("Page-1", [(0, 61), None, (6, 0)])]},
              "shown": {0: {"kind": "mix", "layers": [("Groups", [(1, i) for i in range(16)]),
                                                      ("Masters", [(3, 0), (4, 0), (5, 0), None, (7, 0)])], "index": 1}}}
    mixer = {(3, 0): {"name": "LR", "fader": -0.2, "mute": False, "meter": -40.0},
             (7, 0): {"name": "Cue", "fader": -144.0, "pal": 19, "mute": True},
             (0, 0): {"name": "Channel 1", "fader": -4.5, "mute": False, "solo": True, "trim": {0: 1.5}, "phase": {0: True}}}
    state = {"connected": True, "info": {"name": "X32"}, "lv1_live": True, "lv1_sets": sets80, "lv1_mixer": mixer,
             "exp_map": {32: 1, 33: 2}, "lv1_sources": {"1": [1, 2]}, "gains": [10.0] * 128, "phantom": [0] * 128,
             "lv1_channels": {"1": {"name": "P170", "label": "P170", "color": "#FF4F4F", "input": "A"}},
             "presets": [{"id": "a1", "name": "Show 1", "created": "2026-10-27T14:32:10"}], "can_undo": True,
             "last_recall": {"name": "Show 1", "sent_gain": 2, "verified": True, "bad": []},
             "consoles": [{"n": 0, "card": 1, "connected": True}]}
    msgs = [P.welcome(P.PROTO, "3.2.0", state)]
    for view in (None, ("input", 0), ("custom", 0)):
        page = views.gain_page(state, view=view)
        msgs += [(a, list(args)) for a, args in sorted(P.state_messages(state, 1, page).items())]
    msgs.append((P.NOTIFY, [("s", "Recalled 'Show 1'")]))
    return msgs


if __name__ == "__main__":
    errs = run(sample_messages())
    print("\n".join(errs) if errs else "OK : tous les scripts chargent, init / update / messages sans erreur")
    # robustesse (a15) : un contrôle manquant -> erreur remontée, mais le hello part quand même
    rob = run(sample_messages(), drop="sc_off")
    good = "root : /xgr/error envoyé (erreur Lua remontée)" in rob and "root : aucun /xgr/hello envoyé" not in rob
    print("robustesse (sc_off retiré) : %s" % ("OK, erreur remontée et hello envoyé" if good else "ÉCHEC %s" % rob))
    sys.exit(1 if errs or not good else 0)
