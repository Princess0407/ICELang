import sys
import os
sys.path.insert(0, '/home/princess/icelang')
sys.path.insert(0, '/home/princess/icelang/intelligent_schematic_layer')

from icelang_parser import (
    Lark, parser, ICELangTransformer, analyse, grammar
)
from intelligent_schematic_layer.graph_builder import build, visualise
from intelligent_schematic_layer.placement_engine import place
from intelligent_schematic_layer.wire_router import route
from output.spice_gen import write as write_spice
from output.kicad_gen import write as write_kicad


def run(input_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)

    source = open(input_path).read()

    parser      = Lark(grammar, parser='earley')
    tree        = parser.parse(source.strip())
    transformer = ICELangTransformer()
    circuits    = transformer.transform(tree)

    for ckt in circuits:
        print(f"\n── {ckt.name} ──────────────────────────")

        errors = analyse(ckt)
        if errors:
            for e in errors:
                print(f"  ERROR: {e}")
            continue

        print(f"  semantic analysis passed")

        G       = build(ckt)
        placed  = place(G, ckt)
        edges   = [(u, v, f"{d['component']}_{u}_{v}") for u, v, d in G.edges(data=True)]
        routing = route(placed, edges)

        spice_path  = os.path.join(output_dir, f"{ckt.name}.cir")
        kicad_path  = os.path.join(output_dir, f"{ckt.name}.kicad_sch")
        graph_path  = os.path.join(output_dir, f"{ckt.name}_graph.png")

        write_spice(ckt, spice_path)
        write_kicad(ckt, placed, routing, kicad_path)
        visualise(G, title=ckt.name, save_path=graph_path)

        print(f"  outputs written to {output_dir}/")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python3 main.py <input.ilang> <output_dir>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
