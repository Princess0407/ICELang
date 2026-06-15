import sys
import os
import uuid
sys.path.insert(0, '/home/princess/icelang')

from icelang_parser import CktBlock
from component_models import MODELS

SHEET_CENTRE_X = 150.0
SHEET_CENTRE_Y = 100.0
SCALE          = 5.0
SHEET_UUID     = str(uuid.uuid4())

KICAD_SYM_PATHS = [
    "/usr/share/kicad/symbols",
    "/usr/local/share/kicad/symbols",
    os.path.expanduser("~/.local/share/kicad/9.0/symbols"),
    os.path.expanduser("~/.local/share/kicad/symbols"),
]


def _uid() -> str:
    return str(uuid.uuid4())


def _scale(x: float, y: float) -> tuple:
    sx = round(SHEET_CENTRE_X + x * SCALE, 4)
    sy = round(SHEET_CENTRE_Y - y * SCALE, 4)  # negate y — KiCad y increases downward
    return sx, sy


def find_kicad_lib(lib_name: str) -> str:
    for base in KICAD_SYM_PATHS:
        path = os.path.join(base, f"{lib_name}.kicad_sym")
        if os.path.exists(path):
            return path
    return None


def extract_symbol(lib_name: str, sym_name: str) -> str:
    path = find_kicad_lib(lib_name)
    if not path:
        print(f"  WARNING: library {lib_name} not found")
        return None

    with open(path, "r") as f:
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

                # only rename top-level symbol name
             # "R" -> "Device:R"  (sub-symbols R_0_1, R_1_1 stay unchanged)
                sym = sym.replace(
                    f'(symbol "{sym_name}"',
                    f'(symbol "{full_name}"',
                    1
                )

                indented = "\n".join("    " + l for l in sym.splitlines())
                return indented
        i += 1
    return None


def build_lib_symbols(comp_types: list, needs_gnd: bool) -> str:
    type_to_lib = {
        "res":   ("Device", "R"),
        "cap":   ("Device", "C"),
        "ind":   ("Device", "L"),
        "diode": ("Device", "D"),
        "bjt":   ("Device", "Q_NPN_BCE"),
        "mos":   ("Device", "NMOS"),
        "vol":   ("Device", "Battery"),
    }

    parts = []
    seen  = set()

    for ct in comp_types:
        if ct in type_to_lib and ct not in seen:
            lib_name, sym_name = type_to_lib[ct]
            sym = extract_symbol(lib_name, sym_name)
            if sym:
                parts.append(sym)
                seen.add(ct)
                print(f"  embedded symbol {lib_name}:{sym_name}")

    if needs_gnd:
        sym = extract_symbol("power", "GND")
        if sym:
            parts.append(sym)
            print(f"  embedded symbol power:GND")

    if not parts:
        return "  (lib_symbols)"

    return "  (lib_symbols\n" + "\n".join(parts) + "\n  )"


def _placed_symbol(lib_id: str, ref: str,
                   x: float, y: float,
                   value: str, rotation: int = 0) -> str:
    return f"""  (symbol
    (lib_id "{lib_id}")
    (at {x} {y} {rotation})
    (unit 1)
    (in_bom yes)
    (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "{ref}"
      (at {round(x + 2.032, 4)} {y} 90)
      (effects (font (size 1.27 1.27)))
    )
    (property "Value" "{value}"
      (at {round(x - 2.032, 4)} {y} 90)
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


def _gnd_symbol(ref: str, x: float, y: float) -> str:
    return f"""  (symbol
    (lib_id "power:GND")
    (at {x} {y} 0)
    (unit 1)
    (in_bom yes)
    (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "{ref}"
      (at {x} {round(y + 2.0, 4)} 0)
      (effects (font (size 1.27 1.27)) hide)
    )
    (property "Value" "GND"
      (at {x} {round(y + 3.5, 4)} 0)
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


def _global_label(name: str, x: float, y: float,
                  shape: str = "input") -> str:
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


def _wire(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"""  (wire
    (pts (xy {x1} {y1}) (xy {x2} {y2}))
    (stroke (width 0) (type default))
    (uuid "{_uid()}")
  )"""


def _junction(x: float, y: float) -> str:
    return (f'  (junction (at {x} {y}) '
            f'(diameter 0) (color 0 0 0 0) (uuid "{_uid()}"))')


TYPE_TO_LIB = {
    "res":   "Device:R",
    "cap":   "Device:C",
    "ind":   "Device:L",
    "diode": "Device:D",
    "bjt":   "Device:Q_NPN_BCE",
    "mos":   "Device:NMOS",
    "vol":   "Device:Battery",
}


def generate(ckt: CktBlock, placed: dict, routing: dict) -> str:
    blocks = []

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
        lib_id = TYPE_TO_LIB.get(comp.type)
        if not lib_id:
            continue

        model  = MODELS.get(comp.type)
        prefix = model["spice_prefix"] if model else comp.type[0].upper()
        counter[prefix] = counter.get(prefix, 0) + 1
        ref    = f"{prefix}{counter[prefix]}"

        # place component at midpoint between its two nodes
        raw_x1, raw_y1 = placed.get(comp.node1, (0.0, 0.0))
        raw_x2, raw_y2 = placed.get(comp.node2, (0.0, 0.0))
        mid_x = (raw_x1 + raw_x2) / 2
        mid_y = (raw_y1 + raw_y2) / 2
        x, y  = _scale(mid_x, mid_y)

        # orient component based on direction between nodes
        dx = raw_x2 - raw_x1
        dy = raw_y2 - raw_y1
        rotation = 0 if abs(dy) > abs(dx) else 90

        blocks.append(_placed_symbol(lib_id, ref, x, y, comp.value, rotation))

    for node, (raw_x, raw_y) in placed.items():
        x, y = _scale(raw_x, raw_y)
        if node == "gnd":
            gnd_counter += 1
            blocks.append(_gnd_symbol(f"#PWR0{gnd_counter}", x, y))

    if ckt.port_in:
        node = ckt.port_in.name
        if node in placed:
            raw_x, raw_y = placed[node]
            x, y = _scale(raw_x, raw_y)
            blocks.append(_global_label("VIN", x, y, shape="input"))

    if ckt.port_out and ckt.port_out.node:
        node = ckt.port_out.node
        if node in placed:
            raw_x, raw_y = placed[node]
            x, y = _scale(raw_x, raw_y)
            blocks.append(_global_label("VOUT", x, y, shape="output"))

    for label, wire in routing["wires"].items():
        for seg in wire.get("segments", []):
            (wx1, wy1), (wx2, wy2) = seg
            sx1, sy1 = _scale(wx1, wy1)
            sx2, sy2 = _scale(wx2, wy2)
            blocks.append(_wire(sx1, sy1, sx2, sy2))

    for jx, jy in routing.get("junctions", []):
        sx, sy = _scale(jx, jy)
        blocks.append(_junction(sx, sy))

    blocks.append("""  (sheet_instances
    (path "/"
      (page "1")
    )
  )""")

    blocks.append(')')
    return '\n\n'.join(blocks)


def write(ckt: CktBlock, placed: dict, routing: dict, path: str):
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
            Component(type="res", node1="vin", node2="mc",  value="10k"),
            Component(type="cap", node1="mc",  node2="gnd", value="10F"),
        ]
    )

    G       = build(ckt)
    placed  = place(G, ckt)
    edges   = [(u, v, f"{d['component']}_{u}_{v}")
               for u, v, d in G.edges(data=True)]
    routing = route(placed, edges)
    write(ckt, placed, routing, "output/rc_filter.kicad_sch")
