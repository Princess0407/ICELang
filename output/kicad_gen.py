import sys
import os
import uuid
sys.path.insert(0, '/home/princess/icelang')

from icelang_parser import CktBlock
from component_registry import lookup as _reg_lookup
MODELS = {}

SHEET_CENTRE_X = 150.0
SHEET_CENTRE_Y = 100.0
SCALE          = 5.0
SHEET_UUID     = str(uuid.uuid4())
PIN_HALF       = 3.81   # distance from component centre to wire connection point

KICAD_SYM_PATHS = [
    "/usr/share/kicad/symbols",
    "/usr/local/share/kicad/symbols",
    os.path.expanduser("~/.local/share/kicad/9.0/symbols"),
    os.path.expanduser("~/.local/share/kicad/symbols"),
]


def _uid():
    return str(uuid.uuid4())


def _scale(x, y):
    sx = round(SHEET_CENTRE_X + x * SCALE, 4)
    sy = round(SHEET_CENTRE_Y - y * SCALE, 4)
    return sx, sy


def find_kicad_lib(lib_name):
    for base in KICAD_SYM_PATHS:
        path = os.path.join(base, f"{lib_name}.kicad_sym")
        if os.path.exists(path):
            return path
    return None


def extract_symbol(lib_name, sym_name):
    path = find_kicad_lib(lib_name)
    if not path:
        print(f"  WARNING: library {lib_name} not found")
        return None

    with open(path) as f:
        content = f.read()

    target = f'(symbol "{sym_name}"'
    start  = content.find(target)
    if start == -1:
        print(f"  WARNING: {sym_name} not found in {lib_name}")
        return None

    depth = 0
    i     = start
    while i < len(content):
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
            if depth == 0:
                sym       = content[start:i+1]
                full_name = f"{lib_name}:{sym_name}"
                sym = sym.replace(
                    f'(symbol "{sym_name}"',
                    f'(symbol "{full_name}"',
                    1
                )
                return "\n".join("    " + l for l in sym.splitlines())
        i += 1
    return None


def build_lib_symbols(comp_types, needs_gnd):
    parts = []
    seen  = set()
    for ct in comp_types:
        if ct in seen:
            continue
        entry = _reg_lookup(ct)
        if not entry:
            continue
        lib_id = entry.get("kicad_symbol", "")
        if ":" not in lib_id:
            continue
        lib, sym = lib_id.split(":", 1)
        s = extract_symbol(lib, sym)
        if s:
            parts.append(s)
            seen.add(ct)
            print(f"  embedded {lib}:{sym}")
    if needs_gnd:
        s = extract_symbol("power", "GND")
        if s:
            parts.append(s)
            print(f"  embedded power:GND")
    if not parts:
        return "  (lib_symbols)"
    return "  (lib_symbols\n" + "\n".join(parts) + "\n  )"


def pin_positions(kx, ky, rotation):
    if rotation == 0:
        return (kx, ky - PIN_HALF), (kx, ky + PIN_HALF)
    else:
        return (kx - PIN_HALF, ky), (kx + PIN_HALF, ky)


def closer_pin(n_kx, n_ky, pin_a, pin_b):
    da = (pin_a[0]-n_kx)**2 + (pin_a[1]-n_ky)**2
    db = (pin_b[0]-n_kx)**2 + (pin_b[1]-n_ky)**2
    return (pin_a, pin_b) if da <= db else (pin_b, pin_a)


def manhattan_wires(x1, y1, x2, y2):
    segs = []
    if abs(x1-x2) < 0.01 and abs(y1-y2) < 0.01:
        return segs
    if abs(x1-x2) < 0.01:
        segs.append((x1, y1, x2, y2))
    elif abs(y1-y2) < 0.01:
        segs.append((x1, y1, x2, y2))
    else:
        segs.append((x1, y1, x2, y1))
        segs.append((x2, y1, x2, y2))
    return segs


def _wire(x1, y1, x2, y2):
    return f"""  (wire
    (pts (xy {x1} {y1}) (xy {x2} {y2}))
    (stroke (width 0) (type default))
    (uuid "{_uid()}")
  )"""


def _junction(x, y):
    return (f'  (junction (at {x} {y}) '
            f'(diameter 0) (color 0 0 0 0) (uuid "{_uid()}"))')


def _placed_symbol(lib_id, ref, x, y, value, rotation=0):
    return f"""  (symbol
    (lib_id "{lib_id}")
    (at {x} {y} {rotation})
    (unit 1)
    (in_bom yes)
    (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "{ref}"
      (at {round(x+2.032,4)} {round(y-1.0,4)} 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "{value}"
      (at {round(x-2.032,4)} {round(y-1.0,4)} 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Datasheet" "~" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (instances
      (project "schematic"
        (path "/{SHEET_UUID}"
          (reference "{ref}")
          (unit 1)
        )
      )
    )
  )"""


def _gnd_symbol(ref, x, y):
    return f"""  (symbol
    (lib_id "power:GND")
    (at {x} {y} 0)
    (unit 1)
    (in_bom yes)
    (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "{ref}"
      (at {x} {round(y+6.35,4)} 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Value" "GND"
      (at {x} {round(y+3.81,4)} 0)
      (effects (font (size 1.27 1.27)))
    )
    (property "Footprint" "" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Datasheet" "" (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (instances
      (project "schematic"
        (path "/{SHEET_UUID}"
          (reference "{ref}")
          (unit 1)
        )
      )
    )
  )"""


def _global_label(name, x, y, shape="input"):
    return f"""  (global_label "{name}"
    (shape {shape})
    (at {x} {y} 0)
    (fields_autoplaced yes)
    (effects (font (size 1.27 1.27)))
    (uuid "{_uid()}")
    (property "Intersheet References" "${{INTERSHEET_REFS}}"
      (at 0 0 0)
      (effects (font (size 1.27 1.27)) hide)
    )
  )"""


def get_lib_id(comp_type: str) -> str:
    entry = _reg_lookup(comp_type)
    if entry:
        return entry["kicad_symbol"]
    return None


def generate(ckt, placed, routing):
    blocks    = []
    wire_segs = []

    comp_types = [c.type for c in ckt.components]
    needs_gnd  = "gnd" in placed

    blocks.append('(kicad_sch')
    blocks.append('  (version 20240101)')
    blocks.append('  (generator "icelang")')
    blocks.append('  (generator_version "1.0")')
    blocks.append('  (paper "A4")')
    blocks.append(f'  (title_block (title "{ckt.name}"))')
    blocks.append(build_lib_symbols(comp_types, needs_gnd))

    counter     = {}
    power_nodes = {"gnd", "vcc", "vdd"}
    gnd_counter = 0

    for comp in ckt.components:
        lib_id = get_lib_id(comp.type)
        if not lib_id:
            continue

        model  = _reg_lookup(comp.type)
        prefix = model["spice_prefix"] if model else comp.type[0].upper()
        counter[prefix] = counter.get(prefix, 0) + 1
        ref    = f"{prefix}{counter[prefix]}"

        raw_x1, raw_y1 = placed.get(comp.nodes[0], (0.0, 0.0))
        raw_x2, raw_y2 = placed.get(comp.nodes[1], (0.0, 0.0))

        mid_x = (raw_x1 + raw_x2) / 2
        mid_y = (raw_y1 + raw_y2) / 2
        kx, ky = _scale(mid_x, mid_y)

        dx = abs(raw_x2 - raw_x1)
        dy = abs(raw_y2 - raw_y1)
        rotation = 90 if dx > dy else 0

        pa, pb = pin_positions(kx, ky, rotation)

        n1_kx, n1_ky = _scale(raw_x1, raw_y1)
        n2_kx, n2_ky = _scale(raw_x2, raw_y2)

        node1_pin, node2_pin = closer_pin(n1_kx, n1_ky, pa, pb)

        blocks.append(_placed_symbol(lib_id, ref, kx, ky, comp.value, rotation))

        for seg in manhattan_wires(n1_kx, n1_ky, node1_pin[0], node1_pin[1]):
            wire_segs.append(seg)
        for seg in manhattan_wires(n2_kx, n2_ky, node2_pin[0], node2_pin[1]):
            wire_segs.append(seg)

    for node, (raw_x, raw_y) in placed.items():
        kx, ky = _scale(raw_x, raw_y)
        if node == "gnd":
            gnd_counter += 1
            blocks.append(_gnd_symbol(f"#PWR0{gnd_counter}", kx, ky))

    if ckt.port_in:
        node = ckt.port_in.name
        if node in placed:
            kx, ky = _scale(*placed[node])
            blocks.append(_global_label("VIN", kx, ky, shape="input"))

    if ckt.port_out and ckt.port_out.node:
        node = ckt.port_out.node
        if node in placed:
            kx, ky = _scale(*placed[node])
            blocks.append(_global_label("VOUT", kx, ky, shape="output"))

    seen_segs = set()
    for seg in wire_segs:
        key = (round(seg[0],2), round(seg[1],2),
               round(seg[2],2), round(seg[3],2))
        rev = (key[2], key[3], key[0], key[1])
        if key not in seen_segs and rev not in seen_segs:
            seen_segs.add(key)
            blocks.append(_wire(*seg))

    blocks.append("""  (sheet_instances
    (path "/"
      (page "1")
    )
  )""")
    blocks.append(')')
    return '\n\n'.join(blocks)


def write(ckt, placed, routing, path):
    content = generate(ckt, placed, routing)
    with open(path, "w") as f:
        f.write(content)
    print(f"kicad schematic written → {path}")


if __name__ == "__main__":
    from icelang_parser import Component, PortIn, PortOut
    from intelligent_schematic_layer.graph_builder import build
    from intelligent_schematic_layer.placement_engine import place
    from intelligent_schematic_layer.wire_router import route

    ckt = CktBlock(
        name="rc_filter",
        port_in=PortIn(name="vin"),
        port_out=PortOut(name="vout", node="mc"),
        components=[
            Component(type="res", node1="vin", node2="mc", value="10k"),
            Component(type="cap", node1="mc",  node2="gnd", value="10F"),
        ]
    )
    G       = build(ckt)
    placed  = place(G, ckt)
    edges   = [(u, v, f"{d['component']}_{u}_{v}")
               for u, v, d in G.edges(data=True)]
    routing = route(placed, edges)
    write(ckt, placed, routing, "output/rc_filter.kicad_sch")
