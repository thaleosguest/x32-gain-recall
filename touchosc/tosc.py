"""touchosc/tosc.py — écriture / lecture des fichiers .tosc de TouchOSC (Hexler), sans dépendance.

Format (relevé le 27/10/2026 dans les chaînes de TouchOSC.exe, LXDocumentLoader) : XML compressé zlib,
    <?xml version='1.0' encoding='UTF-8'?>
    <lexml version='3'>
      <node ID='…' type='GROUP'>                       (types : GROUP, BOX, BUTTON, LABEL, TEXT, FADER, RADIAL,
        <properties>                                     ENCODER, RADAR, RADIO, PAGER, …)
          <property type='s|b|i|f|c|r'><key><![CDATA[nom]]></key><value>…</value></property>
        </properties>
        <values><value><key>…</key><locked>0</locked><lockedDefaultCurrent>0</lockedDefaultCurrent>
                <default>…</default><defaultPull>0</defaultPull></value></values>
        <children> … </children>
      </node>
    </lexml>
Propriétés : s = texte (CDATA), b = 0|1, i = entier, f = réel, c = couleur <r><g><b><a> (0..1), r = cadre <x><y><w><h>.
Les propriétés absentes prennent la valeur par défaut de TouchOSC. Toute la logique (envoi / réception OSC) est dans
des scripts Lua (propriété « script ») : pas de <messages> à décrire, moins de risque de se tromper de format.
ID des nœuds : uuid5 du chemin des noms -> fichier identique à chaque génération (diff lisible, builds reproductibles).
"""
import uuid
import zlib
import xml.etree.ElementTree as ET

NS = uuid.UUID("6f1c7e52-3b0e-4f43-9a63-2d1f1f0c3201")


class Color(tuple):
    """Couleur 0..255 (comme les relevés de la LV1), écrite en 0..1."""
    def __new__(cls, r, g, b, a=255):
        return super().__new__(cls, (r, g, b, a))


class Rect(tuple):
    def __new__(cls, x, y, w, h):
        return super().__new__(cls, (x, y, w, h))


class Node:
    def __init__(self, type_, name, frame=None, props=None, values=None, script=None, children=None):
        self.type, self.name = type_, name
        self.props = dict(props or {})
        if frame is not None:
            self.props["frame"] = Rect(*frame)
        if script:
            self.props["script"] = script
        self.props["name"] = name
        self.values = dict(values or {})      # nom -> valeur par défaut (texte d'un LABEL, x d'un fader…)
        self.children = list(children or [])

    def add(self, *nodes):
        self.children.extend(nodes)
        return self

    def find(self, name):
        if self.name == name:
            return self
        for c in self.children:
            hit = c.find(name)
            if hit:
                return hit
        return None


def _cdata(s):
    s = str(s)
    if "]]>" in s:
        raise ValueError("« ]]> » interdit dans un texte du template")
    return "<![CDATA[%s]]>" % s


def _num(v):
    return ("%.4f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def _prop(key, v):
    if isinstance(v, Color):
        body = "".join("<%s>%s</%s>" % (k, _num(round(c / 255.0, 4)), k) for k, c in zip("rgba", v))
        t = "c"
    elif isinstance(v, Rect):
        body = "".join("<%s>%s</%s>" % (k, _num(c), k) for k, c in zip("xywh", v))
        t = "r"
    elif isinstance(v, bool):
        body, t = "1" if v else "0", "b"
    elif isinstance(v, int):
        body, t = str(v), "i"
    elif isinstance(v, float):
        body, t = _num(v), "f"
    else:
        body, t = _cdata(v), "s"
    return "<property type='%s'><key>%s</key><value>%s</value></property>" % (t, _cdata(key), body)


def _value(key, v):
    if isinstance(v, bool):
        v = "true" if v else "false"
    elif isinstance(v, (int, float)):
        v = _num(v)
    return ("<value><key>%s</key><locked>0</locked><lockedDefaultCurrent>0</lockedDefaultCurrent>"
            "<default>%s</default><defaultPull>0</defaultPull></value>" % (_cdata(key), _cdata(v)))


def _node(n, path):
    path = path + "/" + n.name
    out = ["<node ID='%s' type='%s'>" % (uuid.uuid5(NS, path), n.type), "<properties>"]
    out += [_prop(k, v) for k, v in sorted(n.props.items())]
    out.append("</properties>")
    if n.values:
        out += ["<values>"] + [_value(k, v) for k, v in n.values.items()] + ["</values>"]
    if n.children:
        out += ["<children>"] + [_node(c, path) for c in n.children] + ["</children>"]
    out.append("</node>")
    return "".join(out)


def to_xml(root):
    return "<?xml version='1.0' encoding='UTF-8'?><lexml version='3'>%s</lexml>" % _node(root, "")


def write(root, path):
    data = zlib.compress(to_xml(root).encode("utf-8"), 9)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def read_xml(path):
    """XML d'un .tosc (compressé ou non) -> ElementTree (tests, inspection d'un fichier enregistré par TouchOSC)."""
    raw = open(path, "rb").read()
    try:
        raw = zlib.decompress(raw)
    except zlib.error:
        pass
    return ET.fromstring(raw)


def props_of(elem):
    """Propriétés d'un <node> lu : {nom: texte brut de <value>} (couleur / cadre : dict des sous-balises)."""
    out = {}
    for p in elem.find("properties") or []:
        v = p.find("value")
        out[p.find("key").text] = {c.tag: c.text for c in v} if len(v) else v.text
    return out
