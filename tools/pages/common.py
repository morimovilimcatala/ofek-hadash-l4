"""What every page module shares: the paths, the documents in work and how
they group, the labels, the prose helpers, and what the build loads once
(the conventions, the contradictions, the simulator's comparison).
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import akn      # noqa: E402
import calculator  # noqa: E402
import calculator_delta  # noqa: E402
import edge_traces  # noqa: E402
import contradictions  # noqa: E402
import laws  # noqa: E402
import modules  # noqa: E402
import roots  # noqa: E402
import l4src    # noqa: E402
import statute_record  # noqa: E402
import wasm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "build" / "site"
L4_OUT = ROOT / "build" / "l4"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
FINDINGS = ROOT / "findings"           # one <section>.toml per section
MANIFEST = ROOT / "corpus" / "manifest.json"
MANIFEST_DOCS = json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]
CORPUS_SITE = "https://morimovilimcatala.github.io/ofek-hadash-corpus"
REPO = "https://github.com/morimovilimcatala/ofek-hadash-l4"
TITLE = "אופק חדש ב-L4"

# what is encoded, by the corpus document it encodes; the l4/ directory
# mirrors the corpus's akn/ path without the extension
# the collections in work: every document of them, by the corpus's own list
WORK_COLLECTIONS = ("takanon", "agreements", "circulars", "circulars-sachar", "circulars-tnai-sherut", "letters", "takam", "tables")


def _documents() -> list[str]:
    docs = json.loads((Path(__file__).resolve().parent.parent.parent / "corpus" / "manifest.json")
                      .read_text(encoding="utf-8"))["documents"]
    out = ["takanon/takanon-sherut-ovdei-horaa.xml"]
    # the department's web pages, which the corpus files beside the takanon
    out += sorted(d["path"] for d in docs
                  if d["collection"] == "takanon" and d["path"] not in out)
    out += sorted(d["path"] for d in docs
                  if d["collection"] in WORK_COLLECTIONS[1:])
    return out


DOCUMENTS = _documents()

# The takanon collection holds the takanon and the conditions-of-service
# department's web pages (its home page, the Q&A, the takanon's
# introduction, lists of circulars and procedures). They are not part of the
# takanon: each is a whole document, shown and counted as a group of its own
# under the collection.
SITE_GROUP = "דפי האתר של תחום תנאי שירות"
SITE_ANCHOR = "site-pages"


def is_site_page(doc: str) -> bool:
    return doc.split("/")[0] == "takanon" and akn.is_whole(doc)


def doc_num(doc: str) -> str:
    """The short number a list shows beside a whole document's title: a
    circular's number; none for a site page, whose title is its name."""
    stem = Path(doc).stem
    if doc.startswith("circulars/"):
        return stem.split("_", 1)[-1]
    if doc.startswith("tables/") and doc_group(doc) != TABLES_OWN:
        return ""      # a portal table is named by its title, and carries no date
    return "" if is_site_page(doc) else stem[:10]

# The agreements collection, as the corpus files it: a folder per family of
# agreements. Its pages and its sidebar group the documents by family, the
# way the circulars are grouped by school year.
AGREEMENT_GROUPS = {
    "ofek-hadash": "אופק חדש",
    "oz-latmura": "עוז לתמורה",
    "teachers-general": "הסכמים כלליים לעובדי הוראה",
    "framework": "הסכמי מסגרת במגזר הציבורי",
}


# The tables collection, as the corpus files it: the salary tables the
# agreements annex, dated, at its top, and the tables the takanon's portal
# publishes in a folder of their own (MMS-610).
TABLES_OWN = "agreements-annexed"
TABLE_GROUPS = {
    TABLES_OWN: "טבלאות השכר שבנספחי ההסכמים",
    "takanon-portal": "טבלאות פורטל התקנון",
}
# the collections listed by the corpus's folders, not by year
FOLDER_GROUPS = {"agreements": AGREEMENT_GROUPS, "tables": TABLE_GROUPS}


def by_folder(coll: str) -> bool:
    return coll in FOLDER_GROUPS


def doc_group(doc: str) -> str:
    """The group a whole document is listed under: a circular's school year,
    an agreement's family or a table's folder (its folder in the corpus), or
    none."""
    parts = doc.split("/")
    coll = parts[0]
    if coll == "agreements":
        return parts[1]
    if coll == "tables":
        return parts[1] if len(parts) > 2 else TABLES_OWN
    if coll == "circulars":
        return school_year(doc)
    return ""


def group_label(coll: str, key: str) -> str:
    return FOLDER_GROUPS.get(coll, {}).get(key, key)


def group_order(coll: str, keys) -> list[str]:
    """Newest year first; an agreement's families, a table's folders, in the
    order above."""
    if by_folder(coll):
        known = list(FOLDER_GROUPS[coll])
        return sorted(keys, key=lambda k: (known.index(k) if k in known else len(known), k))
    return sorted(keys, reverse=True)


def chapter_name(s: akn.Section) -> str:
    """A chapter as the text heads it: the takanon's "פרק 1א' · …", an
    agreement's part by the letter it prints ("ד. הגדרות לעניין הסכם זה"),
    and an agreement's preamble or sign-off by its name."""
    if not s.chapter_num:
        return s.chapter_heading
    if s.chapter_eid.startswith("part_"):
        return f"{s.chapter_num} {s.chapter_heading}"
    return f"פרק {s.chapter_num} · {s.chapter_heading}"


def sec_ref(sec: akn.Section) -> str:
    """A section as a reader cites it: "§1.11", "§7"; an agreement's
    preamble, sign-off and annexes by their names, which carry no number."""
    return sec.num if akn.unnumbered(sec.num) else f"§{sec.num}"


def num_dir(num: str) -> str:
    """The direction a section's number is set in: a number ("§1.7א") left
    to right, a name ("נספח א'1") right to left, or its geresh lands on
    the wrong side."""
    return "rtl" if HEB.match(num) else "ltr"


# the corpus's collections, so the reader sees what is not started as well
COLLECTIONS = [
    ("takanon", "תקנון שירות עובדי הוראה"),
    ("agreements", "הסכמים קיבוציים"),
    ("circulars", "חוזרים לבעלויות"),
    ("circulars-sachar", "חוזרי שכר"),
    ("circulars-tnai-sherut", "חוזרי תנאי שירות"),
    ("letters", "מכתבים"),
    ("takam", "הוראות תכ\"ם (החשב הכללי)"),
    ("tables", "טבלאות"),
]

# The two labels every finding carries (MMS-415). KIND is what is wrong with
# the law; STAGE is what caught it. The tool's message is the evidence, not
# the category: a gap is a gap whether a warning or an example exposed it.
KINDS = {
    "gap": ("פער", "מקרה שהמסמך אינו מכריע בו"),
    "overlap": ("חפיפה", "שני כללים למקרה אחד, או כלל שלעולם אינו חל"),
    "contradiction": ("סתירה", "מה שהמסמך קובע וכללו שלו אינו מניב, או שני סעיפים שאינם מתיישבים"),
    "undefined-term": ("מונח לא מוגדר", "מונח שבשימוש ואינו מוגדר"),
    "broken-reference": ("הפניה שבורה", "סעיף, נספח או מסמך שהטקסט מפנה אליו ואינו קיים"),
    "ambiguity": ("עמימות", "ניסוח שאפשר לקרוא בשתי דרכים"),
    # the client, 2026-10-21 (MMS-534): "it should be a סוג"
    "edge-case": ("מקרה קצה", "קלט בקצה של כלל, שבו הכללים נותנים תוצאה שהטקסט לא התכוון אליה או שמסמכים חלוקים עליה"),
    # the client, 2026-11-18 (MMS-780): "can you add a new class of cliff findings?"
    "cliff": ("צוק", "סף שבו יותר עבודה מביאה פחות כסף: שעה, כיתה או אחוז משרה נוספים מורידים את השכר"),
    # the client, 2026-11-18 (MMS-783): "a cliff is just one kind of a perverse incentive"
    "perverse-incentive": ("תמריץ מעוות", "כלל שהתגובה הכדאית לו, של המורה או של המעסיק, פועלת נגד תכליתו"),
}
STAGES = {
    "writing": ("בכתיבת הכלל", "אי אפשר לכתוב את הטקסט כפי שהוא"),
    "compiling": ("בהידור", "הכללים אינם מתיישבים זה עם זה"),
    "examples": ("בהרצת הדוגמאות שבטקסט", "הכללים סותרים טבלה או דוגמה שהמסמך עצמו מביא"),
    "verification": ("באימות פורמלי", "פגם שאף דוגמה בודדת אינה מראה"),
}
# WHAT A FLAW CHANGES IN THE REAL WORLD (the client, 2026-10-20, MMS-504,
# MMS-506: "if a mistake won't tickle a court then it isn't severe" and
# "high = court will most likely rule to change the status quo"). The status
# quo is how the ministry applies the text, as its own documents in the
# corpus record it (circulars and later instruments; never a payslip). The
# same scale grades the corpus's sic marks (MMS-505). A grade is a legal
# reading like the finding's, unreviewed until the lawyer has seen it.
SEVERITY = {
    "high": ("גבוהה", "סכום, זכאות או זכות תלויים בפגם, ובית משפט צפוי לפסוק נגד האופן שבו המשרד מיישם את הטקסט היום"),
    "medium": ("בינונית", "סכום או זכות נוגעים בפגם, אבל היישום הקיים צפוי לעמוד, או שההכרעה שקולה; או שהפגם נוגע לנוהל ולא לכסף"),
    "low": ("נמוכה", "שום תוצאה אינה תלויה בפגם"),
}
REVIEW = {
    "unreviewed": "טרם נבדק על ידי עורך הדין",
    "lawyer-seen": "נבדק על ידי עורך הדין",
    "lawyer-agreed": "עורך הדין מסכים",
    "lawyer-disagreed": "עורך הדין חולק",
}

esc = html.escape


def he(text: str) -> str:
    """Corpus text, marked as Hebrew."""
    return f'<span lang="he" dir="rtl">{esc(text)}</span>'


def en(text: str) -> str:
    """Our own English (a note) inside the Hebrew site: isolated, so its
    punctuation and numbers keep their order."""
    return f'<bdi lang="en" dir="ltr">{esc(text)}</bdi>'


HEB = re.compile(r"[\u05d0-\u05ea]")
LAT = re.compile(r"[A-Za-z]")
IDENT = re.compile(r"`[^`]*`")
FID = re.compile(r"F-[0-9A-Za-z][0-9A-Za-z._\u05d0-\u05ea-]*[0-9A-Za-z\u05d0-\u05ea]")
LTR_RUN = re.compile(r"`[^`]*`|\bF-[0-9A-Za-z][0-9A-Za-z._\u05d0-\u05ea-]*[0-9A-Za-z\u05d0-\u05ea]|§[0-9][0-9A-Za-z\u05d0-\u05ea.()]*[0-9A-Za-z\u05d0-\u05ea)]|§[0-9]|#[A-Z]+")


def is_hebrew(text: str) -> bool:
    """A finding's prose is Hebrew when Hebrew letters outnumber Latin ones
    outside the L4 identifiers (`…`) it names."""
    bare = IDENT.sub("", text)
    return len(HEB.findall(bare)) > len(LAT.findall(bare))


def prose(text: str, link_ids: bool = False) -> str:
    """A finding's own words, in whichever language they are written. In
    Hebrew prose an L4 identifier, a section number ("§1.1ב") and a keyword
    ("#ASSERT") stay left to right, isolated."""
    if not is_hebrew(text):
        return en(text)
    out, last = [], 0
    for m in LTR_RUN.finditer(text):
        out.append(esc(text[last:m.start()]))
        run = m.group(0)
        fid = run.strip("`")
        if FID.fullmatch(fid):
            ref = f'<bdi dir="ltr" class="fref">{esc(fid)}</bdi>'
            out.append(f'<a href="#{esc(fid)}">{ref}</a>' if link_ids else ref)
            last = m.end()
            continue
        out.append(f'<bdi dir="ltr" lang="en"><code>{esc(run[1:-1])}</code></bdi>' if run.startswith("`")
                   else f'<bdi dir="ltr">{esc(run)}</bdi>')
        last = m.end()
    out.append(esc(text[last:]))
    return f'<span lang="he" dir="rtl">{"".join(out)}</span>'


READ_BY = {"Claude (L4 encoder)": "Claude (מקודד ה־L4)"}


def who(read_by: str) -> str:
    """Whose reading a finding is, in Hebrew where the site knows the name."""
    if read_by in READ_BY:
        return f'<span lang="he" dir="rtl">{esc(READ_BY[read_by])}</span>'
    return prose(read_by)

def rel(target: str, here: str) -> str:
    return "../" * here.count("/") + target

def school_year(doc: str) -> str:
    return Path(doc).stem.split("_")[0][:7]


# The salary rule the calculator asks: §1.1's.
SALARY = ("takanon/takanon-sherut-ovdei-horaa.xml", "1.1")


# the calculator runs L4's evaluator built to WebAssembly (toolchain/build-wasm.sh),
# fetched from its pinned release (toolchain/fetch-wasm.sh, MMS-776); without
# it there is no calculator, rather than one that cannot run
CALCULATOR = wasm.fetch() is not None

DELTA = calculator_delta.load()

CONTRA = contradictions.load()

CONVENTIONS = ROOT / "conventions.toml"

def load_conventions() -> dict:
    return tomllib.loads(CONVENTIONS.read_text(encoding="utf-8")) if CONVENTIONS.exists() else {}

CONVENTION_TITLES = {c["id"]: c["title"] for c in load_conventions().get("convention", [])}
