import networkx as nx
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from icelang_parser import CktBlock

GRID = 2.54


def get_positions(G: nx.Graph) -> dict:
    return nx.spring_layout(G, k=3.0, iterations=200, seed=42)


def apply_signal_flow(positions: dict, G: nx.Graph) -> dict:
    port_in_nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("node_type") in ("port_in", "signal")
    ]

    port_out_nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("node_type") == "port_out"
    ]

    ground_nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("node_type") == "ground"
    ]

    for n in port_in_nodes:
        positions[n][0] = -3.0

    for n in port_out_nodes:
        positions[n][0] = 3.0

    for n in ground_nodes:
        positions[n][1] = -3.0

    return positions


def snap_to_grid(positions: dict) -> dict:
    snapped = {}

    for node, pos in positions.items():
        x = round((pos[0] * 5) / GRID) * GRID
        y = round((pos[1] * 5) / GRID) * GRID
        snapped[node] = (round(x, 4), round(y, 4))

    return snapped


def place(G: nx.Graph, ckt: CktBlock) -> dict:
    positions = get_positions(G)
    positions = apply_signal_flow(positions, G)
    positions = snap_to_grid(positions)
    return positions


if __name__ == "__main__":
    from icelang_parser import (
        CktBlock,
        Component,
        PortIn,
        PortOut,
    )
    from graph_builder import build

    ckt = CktBlock(
        name="rc_filter",
        port_in=PortIn(name="vin"),
        port_out=PortOut(name="vout", node="mc"),
        components=[
            Component(
                type="res",
                node1="vin",
                node2="mc",
                value="10k",
            ),
            Component(
                type="cap",
                node1="mc",
                node2="gnd",
                value="10F",
            ),
        ],
    )

    G = build(ckt)
    placed = place(G, ckt)

    print("-------> Placed Positions")

    for node, (x, y) in placed.items():
        print(f"{node:10} -> x={x:7.3f}  y={y:7.3f}")

