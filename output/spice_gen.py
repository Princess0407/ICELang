import sys
sys.path.insert(0, '/home/princess/icelang')

from icelang_parser import CktBlock
from component_models import get


def generate(ckt: CktBlock) -> str:
    lines = [f"* {ckt.name}", ""]

    counter = {}
    for comp in ckt.components:
        model  = get(comp.type)
        prefix = model["spice_prefix"]
        counter[prefix] = counter.get(prefix, 0) + 1
        ref = f"{prefix}{counter[prefix]}"
        lines.append(f"{ref} {comp.node1} {comp.node2} {comp.value}")

    if ckt.port_in:
        lines.append("")
        lines.append(
            f"* test source auto-generated for port {ckt.port_in.name}"
        )
        lines.append(
            f"V_test {ckt.port_in.name} gnd PULSE(0 5 0 1n 1n 500u 1m)"
        )

    lines.extend(["", ".tran 1us 10ms", ".end"])
    return "\n".join(lines)


def write(ckt: CktBlock, path: str):
    content = generate(ckt)
    with open(path, "w") as f:
        f.write(content)
    print(f"spice written → {path}")


if __name__ == "__main__":
    from icelang_parser import Component, PortIn, PortOut

    ckt = CktBlock(
        name="rc_filter",
        port_in=PortIn(name="vin"),
        port_out=PortOut(name="vout", node="mc"),
        components=[
            Component(type="res", node1="vin", node2="mc",  value="10k"),
            Component(type="cap", node1="mc",  node2="gnd", value="10F"),
        ]
    )

    print(generate(ckt))
