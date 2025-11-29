#!/usr/bin/env python3
"""
cg_to_json.py
Parse LLVM opt -passes=print-callgraph output (cg.txt) into a simple nodes/edges JSON.

Usage:
  python3 cg_to_json.py cg.txt cg.json

The script:
- Creates unique nodes for each function name it sees
- Creates directed edges source->target for each "calls function '...'" occurrence
- Skips edges to special pseudo-targets like "<<null function>>"
- De-duplicates edges and removes self-loops
- Optionally computes simple metadata (in/out degree)
"""

import json, re
from collections import defaultdict

NODE_HDR_RE = re.compile(r"^Call graph node for function:\s+'([^']+)'")
CALL_RE     = re.compile(r"calls function '([^']+)'")

SPECIAL_TARGETS = {"<<null function>>", "external node", "indirect target"}

def parse_cg(lines):
    current = None
    edges = set()
    nodes = set()

    for raw in lines:
        line = raw.rstrip("\n")

        m = NODE_HDR_RE.match(line)
        if m:
            current = m.group(1).strip()
            nodes.add(current)
            continue

        if current is not None:
            m2 = CALL_RE.search(line)
            if m2:
                callee = m2.group(1).strip()
                # Filter out special / pseudo targets
                if callee not in SPECIAL_TARGETS:
                    if callee:  # non-empty
                        nodes.add(callee)
                        if callee != current:
                            edges.add((current, callee))

        # Detect blank lines separating nodes (optional; safe to ignore)
        # if not line.strip():
        #     current = None

    return nodes, edges

def to_json(nodes, edges):
    # compute simple degree metadata
    out_deg = defaultdict(int)
    in_deg  = defaultdict(int)

    for s, t in edges:
        out_deg[s] += 1
        in_deg[t]  += 1

    j = {
        "nodes": [
            {
                "id": n,
                "name": n,
                "in_degree": in_deg.get(n, 0),
                "out_degree": out_deg.get(n, 0),
                "degree": in_deg.get(n, 0) + out_deg.get(n, 0)
            }
            for n in sorted(nodes)
        ],
        "edges": [
            {"source": s, "target": t}
            for (s, t) in sorted(edges)
        ]
    }
    return j

def main():

    inp = "cg.txt"
    outp = "cg.json"
    with open(inp, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    nodes, edges = parse_cg(lines)
    j = to_json(nodes, edges)

    with open(outp, "w", encoding="utf-8") as f:
        json.dump(j, f, indent=2)
    print(f"Wrote {outp}: {len(j['nodes'])} nodes, {len(j['edges'])} edges.")

if __name__ == "__main__":
    main()
