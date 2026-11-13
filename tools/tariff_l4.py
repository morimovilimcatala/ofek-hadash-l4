"""Write the tables of the Accountant-General's notice HOD.13.4.2.1 "לוח
תעריפי נסיעה בתחבורה ציבורית" out as L4 data (l4/takam/taarifei-nesia-common.l4),
cell for cell, so that nobody types a tariff (MMS-685).

    python3 tools/tariff_l4.py <notice>          print every block of one edition
    python3 tools/tariff_l4.py --write           rewrite the blocks in l4/takam/
    python3 tools/tariff_l4.py --check           exit 1 if a block differs

A block sits in the edition's file under a marker line

    -- tariff data akn:<table key> (tools/tariff_l4.py)

and runs to the next blank line (the block "akn:all" lists the edition's
tables); --write regenerates each block in place and
--check (run by tests/test_tariffs.py) holds every block to the corpus table
it names, and every fare table of the edition to a block.

A table is read by its header's WORDS, not its column order (the pre-reform
editions print the Jerusalem table's columns in the reverse order):

  * a fare table keyed by code (editions 11-14): "קוד דיווח" is the code; "שם
    הכרטיס" or "הערות" the card's name; a header naming "אזור" the zones the
    card covers; "מס'" a serial number, not read; every other column is a
    price, its ticket named by the header ("חופשי חודשי", "חופשי יומי",
    "נסיעה בודדת", "כרטיס תקופתי ל- 30 ימים") or, where the header prints a
    date alone ("עד - 31.01.2016"), by the title line above the table; its
    date is the day the column's prices apply FROM ("מה-", "מיום", "חדש"),
    or none for a column of the earlier prices ("עד", "ישן");
  * the reform's table by distance and code (editions 15-19): one row per
    code, its distance band, means of transport and card ("נסיעה חופשית":
    the first price is a daily free pass; "נסיעה בודדת": a single trip);
  * the reform's summary table (editions 15-18): distance bands by the
    header's ticket and its second row's means of transport;
    a row whose cells differ in number from the header's is read by the
    grid its spans lay out (MMS-702): a cell under one header column is
    that column's, a cell that runs on over a price column without
    printing an amount leaves that column no price; a row the grid cannot
    place — a price column holding two cells or one that is no price, a
    cell running over a price column that prints an amount in prose — is
    `misaligned`: its code only, no price read;
  * a zone list (editions 11-14): ring, zone, the localities as printed;
  * the equalisation table (editions 15-19): the allowance band, the
    maximal cumulative reduction, the floor "Max (F,X-R)", the monthly step.

A price printed "-" or left blank is no price (NOTHING), and so is a
column of the Haifa table that prints, in a row, a date ("1.4.16") where
its price would be. A price column whose header prints no date applies
throughout the edition. The table of the
editions' changes and edition 19's table of payroll symbols carry no
tariff and are not written here.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import akn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
L4_DIR = ROOT / "l4" / "takam"
MARK = re.compile(r"^-- tariff data akn:(\S+) \(tools/tariff_l4\.py\)$")
DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")


def notices() -> list[str]:
    """The editions of HOD.13.4.2.1 the corpus holds, oldest first."""
    found = [p.name for p in (akn.CORPUS / "takam").glob("*HOD-13-4-2-1*.xml")]
    return ["takam/" + n for n in sorted(found, key=edition)]


def edition(document: str) -> int:
    return int(re.search(r"_v(\d+)", document).group(1))


def q(s: str) -> str:
    return '"' + " ".join(s.split()).replace("\\", "\\\\").replace('"', '\\"') + '"'


def fmt(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s


def price(cell: str) -> str:
    c = cell.replace("₪", "").replace('ש"ח', "").replace(",", "").strip()
    if c in ("", "-") or DATE.fullmatch(c):
        return "NOTHING"
    if not re.fullmatch(r"\d+(\.\d+)?", c):
        raise ValueError(f"not a price: {cell!r}")
    return f"(JUST {fmt(float(c))})"


def day(m: re.Match) -> str:
    d, mo, y = (int(x) for x in m.groups())
    if y < 100:
        y += 2000
    return f"(DATE_FROM_DMY {d} {mo} {y})"


def ticket_of(text: str) -> str | None:
    t = " ".join(text.replace("-", " ").split())
    if "תקופתי" in t:
        return "`a 30-day period card`"
    if "חודשי" in t:
        return "`a monthly free pass`"
    if "יומי" in t:
        return "`a daily free pass`"
    if "בודדת" in t or "מחירי הנסיעה" in t or "לנסיעה" in t:
        return "`a single trip`"
    return None


MEANS = {
    "אוטובוס + רכבת": "`bus and train`",
    "אוטובוס": "`bus only`", "אוטובוס בלבד": "`bus only`",
    "רכבת": "`train only`", "רכבת בלבד": "`train only`",
    "משולב מלא": "`full combined`", "משולב חלקי": "`partial combined`",
}


def means_of(cell: str) -> str:
    return MEANS[" ".join(cell.split())]


def band(cell: str) -> tuple[str, str]:
    """(from km, to km) of a distance cell: "0-15", "מ-15 עד 40 ק"מ",
    "מ-225", "מעל 255"."""
    c = cell.replace('ק"מ', "").strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", c) or re.fullmatch(r"מ-\s*(\d+)\s*עד\s*(\d+)", c)
    if m:
        return m.group(1), f"(JUST {m.group(2)})"
    m = re.fullmatch(r"(?:מ-|מעל)\s*(\d+)", c)
    if m:
        return m.group(1), "NOTHING"
    raise ValueError(f"not a distance band: {cell!r}")


def kind(cells: list[list[str]]) -> str | None:
    head = [" ".join(c.split()) for c in cells[0]]
    if head[0] == "מהדורה" or head[0] == "סוג חוזה נסיעה":
        return None
    if head[0].startswith("גובה קצובת"):
        return "equalisation"
    if head[0] == "מרחק":
        return "summary"
    if any(h == "מרחק נסיעה" for h in head):
        return "banded"
    if any(h.startswith("קוד דיווח") for h in head):
        return "coded"
    if len(head) == 3 and (head[0].startswith("טבעת") or head[0].startswith("אזור")):
        return "zones"
    raise ValueError(f"unknown table: {head}")


AMOUNT = re.compile(r'\d+(?:\.\d+)?\s*(?:₪|ש"ח|שקל)')


def by_grid(head_spans, row, row_spans) -> list[list[str]] | None:
    """The cells of a row under each header column, laid out by the grid
    the spans make, or None where a cell crosses a column it does not start
    in and prints an amount there."""
    def ranges(spans):
        out, at = [], 0
        for _, width in spans:
            out.append((at, at + width))
            at += width
        return out
    cols = ranges(head_spans)
    under: list[list[str]] = [[] for _ in cols]
    for text, (s, e) in zip(row, ranges(row_spans)):
        first = next((i for i, (a, b) in enumerate(cols) if a <= s < b), None)
        if first is None:
            return None
        under[first].append(text)
        crossed = [i for i, (a, b) in enumerate(cols) if i != first and a < e and s < b]
        if crossed and AMOUNT.search(text):
            return None
        for i in crossed:
            a, b = cols[i]
            if not (s <= a and b <= e):
                return None          # a cell ending inside a column
    return under


def coded(cells, title: str, spans=None) -> list[str]:
    head = [" ".join(c.split()) for c in cells[0]]
    code = name = zones = None
    cols = []
    for i, h in enumerate(head):
        if h.startswith("קוד דיווח"):
            code = i
        elif h in ("שם הכרטיס", "הערות"):
            name = i
        elif "אזור" in h:
            zones = i
        elif h == "מס'":
            continue
        else:
            t = ticket_of(h) or ticket_of(title)
            if t is None:
                raise ValueError(f"no ticket for column {h!r} under {title!r}")
            m = DATE.search(h)
            frm = "NOTHING" if (m is None or "עד" in h or "ישן" in h) else f"(JUST {day(m)})"
            cols.append((i, f"`a fare column` (JUST {t}) NOTHING {frm}"))
    out = ["(LIST " + ", ".join(c for _, c in cols) + ")"]
    rows = []
    for n, r in enumerate(cells[1:], 1):
        if not any(x.strip() for x in r):
            continue
        if len(r) != len(head):
            # a row whose cells the corpus publishes in other number than
            # the header's columns: read by the grid its spans lay out
            # (MMS-702); a row the grid cannot place gives no price (its
            # code is at the header's end)
            under = by_grid(spans[0], r, spans[n]) if spans else None
            read = None
            if under is not None and len(under[code]) == 1 \
                    and all(len(under[i]) <= 1 for i, _ in cols):
                try:
                    read = [price(under[i][0]) if under[i] else "NOTHING" for i, _ in cols]
                except ValueError:
                    read = None
            if read is None:
                c = r[0] if code == 0 else r[-1]
                rows.append(f"`misaligned` {q(c)}")
                continue
            r = [" ".join(u) for u in under]
            prices = ", ".join(read)
            rows.append(f"`coded` {q(r[code])} {q(r[name]) if name is not None else q('')} "
                        f"{q(r[zones]) if zones is not None else q('')} (LIST {prices})")
            continue
        prices = ", ".join(price(r[i]) for i, _ in cols)
        rows.append(f"`coded` {q(r[code])} {q(r[name]) if name is not None else q('')} "
                    f"{q(r[zones]) if zones is not None else q('')} (LIST {prices})")
    return out + rows


def banded(cells) -> list[str]:
    head = [" ".join(c.split()) for c in cells[0]]
    ix = {k: next(i for i, h in enumerate(head) if h.startswith(k))
          for k in ("קוד", "ישובים", "מרחק", "כלי", "סוג כרטיס")}
    first = next(i for i, h in enumerate(head) if "יומי" in h)
    monthly = next(i for i, h in enumerate(head) if h == "תעריף חודשי")
    out = ["(LIST `a fare column` NOTHING NOTHING NOTHING, "
           "`a fare column` (JUST `a monthly free pass`) NOTHING NOTHING)"]
    rows = []
    for r in cells[1:]:
        card = " ".join(r[ix["סוג כרטיס"]].split())
        t = {"נסיעה חופשית": "`a daily free pass`", "נסיעה בודדת": "`a single trip`"}[card]
        lo, hi = band(r[ix["מרחק"]])
        rows.append(f"`banded` {q(r[ix['קוד']])} {q(r[ix['ישובים']])} {lo} {hi} "
                    f"{means_of(r[ix['כלי']])} {t} (LIST {price(r[first])}, {price(r[monthly])})")
    return out + rows


def summary(cells) -> list[str]:
    head, means = cells[0], cells[1]
    cols = []
    for i in range(1, len(head)):
        t = ticket_of(head[i])
        cols.append(f"`a fare column` (JUST {t}) (JUST {means_of(means[i])}) NOTHING")
    out = ["(LIST " + ", ".join(cols) + ")"]
    rows = []
    for r in cells[2:]:
        lo, hi = band(r[0])
        rows.append(f"`ranged` {lo} {hi} (LIST {', '.join(price(c) for c in r[1:])})")
    return out + rows


def zones(cells) -> list[str]:
    rows, ring = [], ""
    for r in cells:
        if r[0].strip():
            ring = r[0]
        rows.append(f"`a zone` {q(ring)} {q(r[1])} {q(r[2])}")
    return rows


def equalisation(cells) -> list[str]:
    rows = []
    for r in cells[1:]:
        a = r[0].replace("₪", "").replace(",", "").strip()
        m = re.fullmatch(r"(\d+)\s*ומעלה", a)
        lo, hi = (m.group(1), "NOTHING") if m else band(a)
        red = price(r[1])
        f = re.fullmatch(r"Max\s*\((\d+),\s*X-(\d+)\)", r[2].strip())
        if f and f"(JUST {f.group(2)})" != red:
            raise ValueError(f"floor {r[2]!r} subtracts other than {r[1]!r}")
        floor = f"(JUST {f.group(1)})" if f else "NOTHING"
        if not f and r[2].strip() not in ("", "-"):
            raise ValueError(f"not a floor: {r[2]!r}")
        rows.append(f"`an equalisation row` {lo} {hi} {red} {floor} {price(r[3])}")
    return rows


def tables(document: str):
    """(key, kind, title key or None, title, cells, spans) of every data table."""
    rows = [r for s in akn.sections(document) for r in s.rows]
    for i, r in enumerate(rows):
        if r.cells is None:
            continue
        k = kind(r.cells)
        if k is None:
            continue
        prev = rows[i - 1] if i else None
        title_key, title = None, ""
        if prev is not None and prev.cells is None and k == "coded":
            title_key, title = prev.key, prev.text
        yield r.key, k, title_key, title, r.cells, r.spans


def name(document: str, n: int) -> str:
    return f"`notice {edition(document)}'s fare table {n}`"


TYPE = {"coded": "`a fare table`", "banded": "`a fare table`", "summary": "`a fare table`",
        "zones": None, "equalisation": None}


def block(document: str, n: int, key: str, k: str, title_key, title: str, cells,
          spans=None) -> str:
    refs = f"akn:{key}" if title_key is None else f"akn:{title_key} akn:{key}"
    lines = [f"-- tariff data akn:{key} (tools/tariff_l4.py)", f"@ref {refs}"]
    if k in ("coded", "banded", "summary"):
        body = {"coded": lambda: coded(cells, title, spans), "banded": lambda: banded(cells),
                "summary": lambda: summary(cells)}[k]()
        lines += [f"{name(document, n)} MEANS", f"    `a fare table` {q(title)}",
                  f"        {body[0]}",
                  "        (LIST " + ",\n              ".join(body[1:]) + ")"]
    elif k == "zones":
        lines += [f"`notice {edition(document)}'s zone list {n}` MEANS",
                  "    LIST " + ",\n         ".join(zones(cells))]
    else:
        lines += [f"`notice {edition(document)}'s equalisation table` MEANS",
                  "    LIST " + ",\n         ".join(equalisation(cells))]
    return "\n".join(lines)


def blocks(document: str) -> dict[str, str]:
    """Every table's block by its key, and the block "all": the edition's
    fare tables and zone lists, listed, in the text's order."""
    out, fares, zone_lists = {}, [], []
    for n, (key, k, tk, title, cells, spans) in enumerate(tables(document), 1):
        out[key] = block(document, n, key, k, tk, title, cells, spans)
        if k == "zones":
            zone_lists.append(f"`notice {edition(document)}'s zone list {n}`")
        elif k != "equalisation":
            fares.append(name(document, n))
    v = edition(document)
    lines = ["-- tariff data akn:all (tools/tariff_l4.py)",
             f"`notice {v}'s fare tables` MEANS",
             "    LIST " + ",\n         ".join(fares)]
    if zone_lists:
        lines += [f"`notice {v}'s zone lists` MEANS",
                  "    LIST " + ",\n         ".join(zone_lists)]
    out["all"] = "\n".join(lines)
    return out


def l4_file(document: str) -> Path:
    return L4_DIR / (Path(document).stem + ".l4")


def rewrite(path: Path, want: dict[str, str]) -> tuple[str, list[str]]:
    """The file with every marked block regenerated, and the problems: a
    marker naming no table, a table with no marker."""
    lines = path.read_text(encoding="utf-8").split("\n")
    out, seen, problems, i = [], set(), [], 0
    while i < len(lines):
        m = MARK.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        key = m.group(1)
        j = i
        while j < len(lines) and lines[j].strip():
            j += 1
        if key not in want:
            problems.append(f"{path.name}: a block for {key}, which is no fare table")
            out.extend(lines[i:j])
        else:
            out.extend(want[key].split("\n"))
            seen.add(key)
        i = j
    problems += [f"{path.name}: no block for the table {k}" for k in want if k not in seen]
    return "\n".join(out), problems


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("--write", "--check"):
        bad = []
        for doc in notices():
            path = l4_file(doc)
            if not path.exists():
                continue
            text, problems = rewrite(path, blocks(doc))
            bad += problems
            if text != path.read_text(encoding="utf-8"):
                if argv[0] == "--write":
                    path.write_text(text, encoding="utf-8")
                else:
                    bad.append(f"{path.name}: a block differs from the corpus table it names")
        for b in bad:
            print(b, file=sys.stderr)
        return 1 if bad else 0
    for b in blocks(argv[0]).values():
        print(b + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
