import networkx as nx

GRID = 2.54


def build_component_graph(ckt):
    G = nx.Graph()
    n = len(ckt.components)
    for i in range(n):
        G.add_node(i)

    net_map = {}
    for i, comp in enumerate(ckt.components):
        for node in comp.nodes:
            net_map.setdefault(node, []).append(i)

    for node, comps in net_map.items():
        if node in ("gnd", "vcc", "vdd"):
            continue
        for a in range(len(comps)):
            for b in range(a + 1, len(comps)):
                if G.has_edge(comps[a], comps[b]):
                    G[comps[a]][comps[b]]["weight"] += 1
                else:
                    G.add_edge(comps[a], comps[b], weight=1)

    return G, net_map


def get_positions(G):
    n = max(G.number_of_nodes(), 1)
    if n == 0:
        return {}
    k = 3.0 + n * 0.6
    seed = (n * 97 + G.number_of_edges() * 131) % 10000
    return nx.spring_layout(G, k=k, iterations=300, seed=seed)


def apply_signal_flow(positions, ckt, net_map):
    port_in = ckt.port_in.name if ckt.port_in else None
    port_out_node = (ckt.port_out.node
                     if ckt.port_out and ckt.port_out.node else None)

    if port_in and port_in in net_map:
        input_comps = net_map[port_in]
        for i in input_comps:
            all_nets = [n for n, comps in net_map.items() if i in comps]
            signal_nets = [n for n in all_nets
                          if n not in ("gnd","vcc","vdd")]
            if len(signal_nets) <= 2:
                if i in positions:
                    positions[i][0] = min(positions[i][0], -2.0)

    if port_out_node and port_out_node in net_map:
        output_comps = net_map[port_out_node]
        for i in output_comps:
            all_nets = [n for n, comps in net_map.items() if i in comps]
            signal_nets = [n for n in all_nets
                          if n not in ("gnd","vcc","vdd")]
            if len(signal_nets) <= 2:
                if i in positions:
                    positions[i][0] = max(positions[i][0], 2.0)

    if "gnd" in net_map:
        for i in net_map["gnd"]:
            if i in positions:
                positions[i][1] = min(positions[i][1], -1.5)

    return positions


def snap_to_grid(positions):
    snapped = {}
    for i, pos in positions.items():
        x = round((pos[0] * 2) / GRID) * GRID
        y = round((pos[1] * 2) / GRID) * GRID
        snapped[i] = (round(x, 4), round(y, 4))
    return snapped


def place_components(ckt):
    G, net_map = build_component_graph(ckt)
    positions = get_positions(G)
    positions = apply_signal_flow(positions, ckt, net_map)
    positions = snap_to_grid(positions)

    for i in range(len(ckt.components)):
        if i not in positions:
            positions[i] = (0.0, 0.0)

    return positions, net_map


# for backward compatibility with older node based callers
def place(G, ckt):
    positions, _ = place_components(ckt)
    result = {}
    for i, comp in enumerate(ckt.components):
        pos = positions.get(i, (0.0, 0.0))
        for node in comp.nodes:
            if node not in result:
                result[node] = pos
    return result


if __name__ == "__main__":
    from icelang_parser import CktBlock, Component, PortIn, PortOut

    ckt = CktBlock(
        name="rc_filter",
        port_in=PortIn(name="vin"),
        port_out=PortOut(name="vout", node="mc"),
        components=[
            Component(type="res", nodes=["vin", "mc"], value="10k"),
            Component(type="cap", nodes=["mc", "gnd"], value="100n"),
        ]
    )
    positions, net_map = place_components(ckt)
    print("component positions:")
    for i, pos in positions.items():
        print(f"  comp[{i}] ({ckt.components[i].type}) -> {pos}")
