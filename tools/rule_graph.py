"""What a rule is made of, drawn from the L4 itself.

`l4 state-graph` draws obligations and `l4 trace` draws one evaluation; neither
shows how a computed figure is BUILT. This walks a rule's body: every rule of
the same file it calls is a component, every record field it reads (`m's
`month``) is an input the text leaves to the case. Each box says which clause
of the corpus it encodes, in the text's own words, and its L4 name.

    python3 tools/rule_graph.py l4/takanon/takanon-sherut-ovdei-horaa/1.1.l4 \\
        "salary of a teaching employee" > salary.dot
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

START = re.compile(r"^(?:DECIDE\s+`([^`]+)`|`([^`]+)`\s+MEANS)")
REF = re.compile(r"akn:(\S+)")
FIELD = re.compile(r"'s\s+`([^`]+)`")
NAME = re.compile(r"`([^`]+)`")


def declarations(path: Path) -> dict[str, dict]:
    """name -> {"body": lines, "refs": the akn keys of its own @ref}. A rule
    with none (a helper inside a segment) claims no clause: inheriting the
    @ref above it labelled "salary before the percentage allowances" as
    §1.1ה, which it is not."""
    out: dict[str, dict] = {}
    cur, refs = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("@ref"):
            refs = REF.findall(line)
            cur = None
            continue
        m = START.match(line)
        if m:
            cur = m.group(1) or m.group(2)
            out.setdefault(cur, {"body": [line], "refs": refs})
            refs = []
            continue
        if cur and (line[:1] in (" ", "\t") or not line.strip()):
            out[cur]["body"].append(line)
        elif line.strip():
            cur = None
    return out


def walk(decls: dict[str, dict], root: str) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """(rules in the order reached, edges, inputs). An edge (a, b): a is
    built from b; b is a rule, or "in:<field>" for an input."""
    order, edges, inputs = [], [], []
    def go(n: str) -> None:
        if n in order:
            return
        order.append(n)
        lines = decls[n]["body"]
        head, rest = lines[0], "\n".join(lines[1:])
        # the head's own name and its parameters are not components
        body = head.split(" IS", 1)[1] if " IS" in head else ""
        body += "\n" + rest
        subs = [r for r in dict.fromkeys(NAME.findall(FIELD.sub("", body))) if r in decls and r != n]
        # an input is drawn where it is FIRST needed: a rule built from other
        # rules reaches the month or the position through them, and an arrow
        # from every box to "month" says nothing a reader can use
        if not subs:
            for f in dict.fromkeys(FIELD.findall(body)):
                edges.append((n, "in:" + f))
                if f not in inputs:
                    inputs.append(f)
        for r in subs:
            edges.append((n, r))
            go(r)
    go(root)
    return order, edges, inputs


def dot(decls, root: str, label_of) -> str:
    """GraphViz, right to left like the page: the root on the right, what it
    is made of to its left. `label_of(name, refs)` gives a box's clause as
    (the text's own words, its citation); either may be empty."""
    order, edges, inputs = walk(decls, root)
    def q(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')
    out = ['digraph {', '  graph [rankdir=RL, nodesep=0.25, ranksep=0.5, fontname="DejaVu Sans"];',
           '  node [shape=box, style="rounded,filled", fontname="DejaVu Sans", fontsize=11, '
           'fillcolor="#eef3fb", color="#9db0cf"];',
           '  edge [color="#8a94a6", arrowsize=0.6, dir=back];']
    def h(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    for i, n in enumerate(order):
        words, cite = label_of(n, decls[n]["refs"])
        lines = ([f'<FONT POINT-SIZE="13">{h(words)}</FONT>'] if words else [])
        lines.append(f'<FONT POINT-SIZE="9" COLOR="#5b6474">{h(n)}{"  ·  " + h(cite) if cite else ""}</FONT>')
        extra = ', fillcolor="#dbe6f8", penwidth=1.6' if n == root else ""
        out.append(f'  r{i} [label=<{"<BR/>".join(lines)}>{extra}];')
    for j, f in enumerate(inputs):
        out.append(f'  i{j} [label="{q(f)}", shape=ellipse, style=filled, fillcolor="#f6f1e3", color="#cdbf99"];')
    idx = {n: f"r{i}" for i, n in enumerate(order)}
    idx.update({"in:" + f: f"i{j}" for j, f in enumerate(inputs)})
    for a, b in dict.fromkeys(edges):
        out.append(f"  {idx[a]} -> {idx[b]};")
    out.append("}")
    return "\n".join(out)


if __name__ == "__main__":
    p, root = Path(sys.argv[1]), sys.argv[2]
    print(dot(declarations(p), root, lambda n, refs: ("", refs[0] if refs else "")))


# ------------------------------------------------- the site's salary diagram

HEAD_SPLIT = re.compile(r":|–| - ")


def clause_labeller(section, citations: dict[str, str]):
    """`label_of` for the corpus section a file encodes: a box gets the
    clause's own heading ("תוספת 2008") where the text gives one, else its
    first words, and its citation (§1.1ג). It climbs from the cited row to
    the paragraph that holds it, never above: the section's own first row is
    its update stamp, not a heading."""
    rows: dict[str, object] = {}
    for r in section.rows:
        rows.setdefault(r.key, r)
        for a in getattr(r, "aliases", []):
            rows.setdefault(a, r)

    def head_of(text: str) -> str:
        parts = HEAD_SPLIT.split(text, maxsplit=1)
        h = parts[0].strip()
        if h in ("הערה", "הערות") and len(parts) > 1:
            h = " ".join(parts[1].split()[:5])
        return h

    def label(name: str, refs: list[str]) -> tuple[str, str]:
        if not refs:
            return "", ""
        # a clause before a paragraph of one (a note is "/pN")
        k0 = min(refs, key=lambda k: ("/" in k, k.count("__"), len(k)))
        base = k0.split("/")[0].split("__")
        for k in [k0] + ["__".join(base[:i]) for i in range(len(base), 0, -1) if "para_" in base[i - 1]]:
            r = rows.get(k)
            if r is not None and r.text.strip():
                h = head_of(" ".join(r.text.split()))
                if 2 <= len(h) <= 40:
                    return h, citations.get(k, "")
        r = rows.get(k0)
        text = " ".join(r.text.split()) if r is not None else ""
        return ((" ".join(text.split()[:5]) + "…") if text else ""), citations.get(k0, "")
    return label


def svg(dot_src: str) -> str:
    """Drawn by GraphViz through Cairo, which shapes Hebrew right to left and
    sizes its boxes to it; the plain SVG renderer measured Hebrew as if it
    were Latin and clipped every label. "" when GraphViz is not installed."""
    import shutil
    import subprocess
    if not shutil.which("dot"):
        return ""
    r = subprocess.run(["dot", "-Tsvg:cairo"], input=dot_src, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""
