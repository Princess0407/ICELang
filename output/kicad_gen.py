import sys
import uuid
sys.path.insert(0, '/home/princess/icelang')

from icelang_parser import CktBlock
from component_models import get


def _uid() -> str:
    return str(uuid.uuid4())


def _symbol_block(ref: str, symbol: str, x: float, y: float, value: str) -> str:
    return f"""  (symbol
    (lib_id "{symbol}")
    (at {x} {y} 0)
    (unit 1)
    (in_bom yes) (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "{ref}" (at {x} {y - 1.5} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{value}" (at {x} {y + 1.5} 0) (effects (font (size 1.27 1.27))))
  )"""


def _wire_block(x1: float, y1: float, x2: float, y2: float) -> str:
    return f"""  (wire
    (pts (xy {x1} {y1}) (xy {x2} {y2}))
    (stroke (width 0) (type default))
    (uuid "{_uid()}")
  )"""


def _junction_block(x: float, y: float) -> str:
    return f"""  (junction (at {x} {y}) (diameter 0) (color 0 0 0 0) (uuid "{_uid()}"))"""


def _power_symbol(name: str, x: float, y: float) -> str:
    lib = "power:GND" if name.lower() == "gnd" else "power:VCC"
    return f"""  (symbol
    (lib_id "{lib}")
    (at {x} {y} 0)
    (unit 1)
    (in_bom yes) (on_board yes)
    (uuid "{_uid()}")
    (property "Reference" "#PWR" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))
    (property "Value" "{name.upper()}" (at {x} {y - 1.5} 0) (effects (font (size 1.27 1.27))))
  )"""


def generate(ckt: CktBlock, placed: dict, routing: dict) -> str:
    blocks = []

    blocks.append(
        f'(kicad_sch (version 20230121) (generator icelang)\n'
        f'  (paper "A4")\n'
        f'  (title_block (title "{ckt.name}"))'
    )

    counter = {}
    power_nodes = {"gnd", "vcc", "vdd"}

    for comp in ckt.components:
        model  = get(comp.type)
        symbol = model["kicad_symbol"]
        prefix = model["spice_prefix"]
        counter[prefix] = counter.get(prefix, 0) + 1
        ref = f"{prefix}{counter[prefix]}"

        node = comp.node1 if comp.node1 not in power_nodes else comp.node2
        if node in placed:
            x, y = placed[node]
        else:
            x, y = 0.0, 0.0

        blocks.append(_symbol_block(ref, symbol, x, y, comp.value))

    for node, (x, y) in placed.items():
        if node in power_nodes:
            blocks.append(_power_symbol(node, x, y))

    for label, wire in routing["wires"].items():
        for seg in wire.get("segments", []):
            (x1, y1), (x2, y2) = seg
            blocks.append(_wire_block(x1, y1, x2, y2))

    for jx, jy in routing.get("junctions", []):
        blocks.append(_junction_block(jx, jy))

    blocks.append(")")
    return "\n\n".join(blocks)


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
    edges   = [(u, v, f"{d['component']}_{u}_{v}") for u, v, d in G.edges(data=True)]
    routing = route(placed, edges)

    write(ckt, placed, routing, "output/rc_filter.kicad_sch")
