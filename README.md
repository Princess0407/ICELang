# ICELang

**A domain-specific language and compiler pipeline for automated KiCad schematic generation inside eSim**

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL--3.0-green)
![Status](https://img.shields.io/badge/Pipeline-Functional-brightgreen)

[What it does](#what-it-does) · [Pipeline](#pipeline) · [Usage](#usage) · [Architecture](#architecture) · [Test Circuits](#test-circuits) · [Project Structure](#project-structure) · [Tests](#tests)

---

## What it does

Drawing schematics by hand in KiCad is time-consuming and error-prone for students learning circuit design. ICELang lets you describe a circuit in a readable text format and compiles it directly to a `.kicad_sch` file and a SPICE netlist, both ready to open in eSim.

Write this:

```
circuit rc_filter:
    port in vin
    port out vout

    resistor R1 1k vin mid
    capacitor C1 220n mid gnd

    probe vout mid
```

Get this: a fully routed KiCad schematic with correct component placement, wire routing, GND symbols, and VIN/VOUT port labels.

3 out of 3 test circuits compile and open cleanly in KiCad. End-to-end pipeline success rate: 100% across RC filter, voltage divider, and signal conditioner.

---

## Pipeline

```
.ilang source file
        |
        v
   icelang_parser.py          Lark grammar, ICELangTransformer, semantic analysis
        |
        v
   AST (Python dataclasses)   CktBlock, Component, Port, Probe
        |
        v
   graph_builder.py           NetworkX graph IR, node/edge labeling
        |
        v
   placement_engine.py        Topology-aware placement:
                                series components -> horizontal signal path
                                shunt components  -> below signal node
                                driver sources    -> left of VIN
        |
        v
   wire_router.py             Manhattan routing between node coordinates
        |
        v
   output/kicad_gen.py        KiCad S-expression (.kicad_sch) generator
   output/spice_gen.py        SPICE netlist (.cir) generator
        |
        v
   .kicad_sch + .cir
```

---

## Usage

### Prerequisites

- Python 3.10+
- KiCad 8.0+ (for viewing output schematics)
- eSim 2.3 / 2.4 / 2.5

### Install dependencies

```bash
pip install lark networkx --break-system-packages
```

### Run from source

```bash
git clone https://github.com/Princess0407/ICELang.git
cd ICELang
python main.py test_circuits/rc_filter.ilang output/
```

### Run all circuits

```bash
python main.py test_circuits/rc_filter.ilang output/
python main.py test_circuits/voltage_divider.ilang output/
python main.py test_circuits/user_defined.ilang output/
```

Output files land in `output/` as `<circuit_name>.kicad_sch` and `<circuit_name>.cir`.

---

## ICELang Syntax

### Basic circuit

```
circuit <name>:
    port in <node>
    port out <node>

    <type> <ref> <value> <node1> <node2>

    probe <label> <node>
```

### Supported component types

| Keyword        | Component            | KiCad Symbol     |
| -------------- | -------------------- | ---------------- |
| `resistor`     | Resistor             | Device:R         |
| `capacitor`    | Capacitor            | Device:C         |
| `inductor`     | Inductor             | Device:L         |
| `vsource`      | Voltage source       | Device:Battery   |
| `bjt_npn`      | NPN transistor       | Device:Q_NPN_BCE |
| `bjt_pnp`      | PNP transistor       | Device:Q_PNP_BCE |
| `nmos`         | N-channel MOSFET     | Device:NMOS      |

### Custom component types via `define`

```
define filter_cap as capacitor using Device:C

circuit signal_conditioner:
    filter_cap C1 220n mid gnd
```

The registry (`registry.json`) maps custom type names to KiCad symbols and SPICE prefixes. New component types do not require code changes.

---

## Architecture

```
icelang/
├── icelang_parser.py               Lark grammar + AST transformer + semantic checks
├── component_registry.py           Loads registry.json, handles define keyword
├── pin_reader.py                   Reads pin offsets from .kicad_sym at runtime
├── main.py                         Entry point
├── registry.json                   Component type -> KiCad symbol + SPICE prefix map
│
├── intelligent_schematic_layer/
│   ├── graph_builder.py            NetworkX graph IR from parsed AST
│   ├── placement_engine.py         Topology-aware coordinate assignment
│   └── wire_router.py              Manhattan wire segment generation
│
├── output/
│   ├── kicad_gen.py                KiCad S-expression generator
│   └── spice_gen.py                SPICE netlist generator
│
└── test_circuits/
    ├── rc_filter.ilang
    ├── voltage_divider.ilang
    └── user_defined.ilang          Signal conditioner with custom component types
```

### Placement model

The placement engine classifies every component into one of three buckets before assigning coordinates:

**Series** - neither node is a power rail. These go on the horizontal signal path, left to right, spaced 5.08 world units apart.

**Shunts** - one node is a power rail (gnd, vcc, vdd). These hang vertically below their signal node at -6.35 world units. Multiple shunts on the same node spread horizontally.

**Drivers** - voltage and current sources. These sit to the left of VIN on the signal rail, oriented vertically, with their positive terminal at signal rail height and negative terminal at GND depth.

This is deterministic and topology-driven. There is no spring layout or force-directed placement, so the output is stable and predictable across circuit sizes.

---

## Test Circuits

### RC filter

```
resistor R1 1k vin mid
capacitor C1 220n mid gnd
```

Low-pass RC filter. Series resistor on signal path, capacitor shunting to GND.

### Voltage divider

```
vsource V1 9V vin gnd
resistor R1 10k vin mid
resistor R2 10k mid gnd
```

Two resistors in series forming a voltage divider, with a source driver left of VIN.

### Signal conditioner (user-defined types)

```
define filter_cap as capacitor using Device:C
define pull_down as resistor using Device:R
define series_res as resistor using Device:R

series_res R1 1k vin mid
filter_cap C1 220n mid gnd
pull_down R2 100k mid gnd
```

Demonstrates the `define` keyword and custom component types. Two shunt components on the same signal node placed symmetrically.

All three circuits produce clean schematics with correct topology, connected port labels, GND symbols, and routed wires.

---

## Tests

```bash
cd ICELang
python -m pytest tests/ -v
```

Three tests covering the critical path:

| Test | What it checks |
| ---- | -------------- |
| `test_parser_roundtrip` | Parser produces correct component count and node names from .ilang source |
| `test_placement_topology` | Series components have monotonically increasing x; shunts have negative y |
| `test_kicad_output_validity` | Generated .kicad_sch starts with `(kicad_sch` and contains expected refs |

---

## What is not yet supported

- Multi-stage circuits with more than one output probe
- Subcircuit / hierarchical blocks
- Three-terminal device auto-rotation based on topology

---

## License

GPL-3.0 — developed as part of FOSSEE Summer Internship 2026, IIT Bombay.

Built for FOSSEE eSim Summer Internship 2026 · IIT Bombay
