import sys
import os
import uuid
sys.path.insert(0, '/home/princess/icelang')

from icelang_parser import CktBlock
from component_registry import lookup as _reg_lookup
from pin_reader import get_pin_offsets as _get_pin_offsets

SHEET_CENTRE_X = 150.0
SHEET_CENTRE_Y = 100.0
SCALE          = 5.0
SHEET_UUID     = str(uuid.uuid4())

KICAD_SYM_PATHS = [
    "/usr/share/kicad/symbols",
    "/usr/local/share/kicad/symbols",
    os.path.expanduser("~/.local/share/kicad/9.0/symbols"),
]


def _uid():
    return str(uuid.uuid4())


def _scale(x, y):
    sx = round(SHEET_CENTRE_X + x * SCALE, 4)
    sy = round(SHEET_CENTRE_Y - y * SCALE, 4)
    return sx, sy


def find_kicad_lib(lib_name):
    for base in KICAD_SYM_PATHS:
        p = os.path.join(base, f"{lib_name}.kicad_sym")
        if os.path.exists(p):
            return p
    return None


def extract_symbol(lib_name, sym_name):
    path = find_kicad_lib(lib_name)
    if not path:
        return None
    with open(path) as f:
        content = f.read()
    target = f'(symbol "{sym_name}"'
    start = content.find(target)
    if start == -1:
        return None
    depth = 0
    i = start
    while i < len(content):
        if content[i] == "(":
            depth += 1
        elif content[i] == ")":
            depth -= 1
            if depth == 0:
                sym = content[start:i+1]
                full = f"{lib_name}:{sym_name}"
                sym = sym.replace(f'(symbol "{sym_name}"', f'(symbol "{full}"', 1)
                return "\n".join("    " + l for l in sym.splitlines())
        i += 1
    return None


def get_lib_id(comp_type):
    entry = _reg_lookup(comp_type)
    return entry.get("kicad_symbol") if entry else None


def build_lib_symbols(comp_types, needs_gnd):
    parts = []
    seen = set()
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
            print("  embedded power:GND")
    if not parts:
        return "  (lib_symbols)"
    return "  (lib_symbols\n" + "\n".join(parts) + "\n  )"


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


def _wire(x1, y1, x2, y2):
    return f"""  (wire
    (pts (xy {x1} {y1}) (xy {x2} {y2}))
    (stroke (width 0) (type default))
    (uuid "{_uid()}")
  )"""


def _junction(x, y):
    return f'  (junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid "{_uid()}"))'


def generate(ckt: CktBlock) -> str:
    from intelligent_schematic_layer.placement_engine import place_components
    from intelligent_schematic_layer.wire_router import route_nets

    comp_positions, net_map = place_components(ckt)
    comp_types = [c.type for c in ckt.components]
    needs_gnd  = "gnd" in net_map

    blocks = []
    blocks.append('(kicad_sch')
    blocks.append('  (version 20240101)')
    blocks.append('  (generator "icelang")')
    blocks.append('  (generator_version "1.0")')
    blocks.append('  (paper "A4")')
    blocks.append(f'  (title_block (title "{ckt.name}"))')
    blocks.append(build_lib_symbols(comp_types, needs_gnd))

    counter  = {}
    net_pins = {}

    for i, comp in enumerate(ckt.components):
        lib_id = get_lib_id(comp.type)
        if not lib_id:
            continue

        model  = _reg_lookup(comp.type)
        prefix = model["spice_prefix"] if model else comp.type[0].upper()
        counter[prefix] = counter.get(prefix, 0) + 1
        ref = f"{prefix}{counter[prefix]}"

        raw_x, raw_y = comp_positions.get(i, (0.0, 0.0))
        kx, ky = _scale(raw_x, raw_y)

        offsets   = _get_pin_offsets(lib_id)
        pin_names = model.get("pin_names", []) if model else []

        blocks.append(_placed_symbol(lib_id, ref, kx, ky, comp.value, 0))

        for j, node in enumerate(comp.nodes):
            if j >= len(pin_names):
                continue
            pname = pin_names[j]
            off   = offsets.get(pname, (0, 0))
            pin_kx = round(kx + off[0], 4)
            pin_ky = round(ky + off[1], 4)
            net_pins.setdefault(node, []).append((pin_kx, pin_ky))

    routing = route_nets(net_pins)

    if "gnd" in net_pins and net_pins["gnd"]:
        gx, gy = net_pins["gnd"][0]
        blocks.append(_gnd_symbol("#PWR01", gx, gy))

    if ckt.port_in and ckt.port_in.name in net_pins:
        x, y = net_pins[ckt.port_in.name][0]
        blocks.append(_global_label("VIN", x, y, shape="input"))

    if ckt.port_out and ckt.port_out.node and ckt.port_out.node in net_pins:
        x, y = net_pins[ckt.port_out.node][0]
        blocks.append(_global_label("VOUT", x, y, shape="output"))

    seen = set()
    for seg in routing["wires"]:
        (x1, y1), (x2, y2) = seg
        key = (round(x1,2), round(y1,2), round(x2,2), round(y2,2))
        rev = (key[2], key[3], key[0], key[1])
        if key in seen or rev in seen:
            continue
        seen.add(key)
        blocks.append(_wire(x1, y1, x2, y2))

    for (jx, jy) in routing["junctions"]:
        blocks.append(_junction(jx, jy))

    blocks.append("""  (sheet_instances
    (path "/"
      (page "1")
    )
  )""")
    blocks.append(')')
    return '\n\n'.join(blocks)


def write(ckt, placed, routing, path):
    content = generate(ckt)
    with open(path, "w") as f:
        f.write(content)
    print(f"kicad schematic written -> {path}")
