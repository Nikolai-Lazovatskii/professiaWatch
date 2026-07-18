"""Offline self-test: parser + matcher + full pipeline on embedded fixtures.

    python -m jobwatch.selftest
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

# use an isolated data dir before importing state-dependent modules
os.environ["JOBWATCH_DATA"] = tempfile.mkdtemp(prefix="jobwatch-selftest-")

from . import profesia  # noqa: E402
from .check import run_check  # noqa: E402
from .config import load_config  # noqa: E402
from .matcher import Matcher, normalize  # noqa: E402
from .notifier import _chunks, format_digest  # noqa: E402

LIST_INTERN = """
<html><body><ul>
<li class="list-row">
 <h2><a id="offer1000001" class="title" href="/praca/acme-tech/O1000001?search_id=abc">
   Stážista v IT oddelení – DevOps tím</a></h2>
 <span class="employer">Acme Tech s.r.o.</span>
 <span class="job-location">Bratislava</span>
 <span class="label-group"><a href="/praca/acme-tech/O1000001">800 EUR/mesiac</a></span>
 <span class="info"><strong>Pred 2 hodinami</strong></span>
</li>
<li>
 <h2><a href="/praca/big-corp/O1000002?search_id=abc">Stáž v HR oddelení</a></h2>
 Big Corp a.s.
 Trnava
 <strong>Pred 30 minútami</strong>
</li>
</ul>
<div class="sidebar"><a href="/praca/other/O9999999">HOT ponuka mimo zoznamu</a></div>
</body></html>
"""

LIST_BRIGADY = """
<html><body><ul>
<li class="list-row">
 <h2><a id="offer1000003" class="title" href="/praca/webhouse/O1000003?search_id=x">
   Brigáda: správa serverov a Python skripty</a></h2>
 <span class="employer">WebHouse s.r.o.</span>
 <span class="job-location">Trnava</span>
 <span class="label-group"><a href="/praca/webhouse/O1000003">9 EUR/hod.</a></span>
 <span class="info"><strong>Pred 1 hodinou</strong></span>
</li>
<li class="list-row">
 <h2><a id="offer1000004" class="title" href="/praca/shop/O1000004?search_id=x">
   Predavač/ka v obchode s oblečením</a></h2>
 <span class="employer">Shop s.r.o.</span>
 <span class="job-location">Bratislava</span>
</li>
</ul></body></html>
"""

LIST_EMPTY = "<html><body><ul></ul></body></html>"

DETAILS = {
    "O1000001": {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": "Stážista v IT oddelení – DevOps tím",
        "description": "<p>Docker, CI/CD pipeline v GitHub Actions, Linux servery, "
                       "monitoring Grafana. Vhodné pre študenta informatiky.</p>",
        "hiringOrganization": {"@type": "Organization", "name": "Acme Tech s.r.o."},
    },
    "O1000002": {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": "Stáž v HR oddelení",
        "description": "<p>Administratívna podpora HR, komunikácia s kandidátmi.</p>",
        "hiringOrganization": {"@type": "Organization", "name": "Big Corp a.s."},
    },
    "O1000003": {
        "@context": "https://schema.org", "@type": "JobPosting",
        "title": "Brigáda: správa serverov a Python skripty",
        "description": "<p>Údržba Linux serverov, bash a Python skripty, PostgreSQL.</p>",
        "hiringOrganization": {"@type": "Organization", "name": "WebHouse s.r.o."},
    },
}


def fake_fetch_html(session, url, retries=3):  # noqa: ARG001
    for oid, posting in DETAILS.items():
        if f"/{oid}" in url:
            return (f"<html><body><script type='application/ld+json'>"
                    f"{json.dumps(posting)}</script></body></html>")
    if "page_num" in url:
        return LIST_EMPTY
    if "internship-staz" in url:
        return LIST_INTERN if "bratislavsky" in url else LIST_EMPTY
    if "na-dohodu-brigady" in url:
        return LIST_BRIGADY if "trnavsky" in url else LIST_EMPTY
    return LIST_EMPTY


def check(name: str, cond: bool) -> bool:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")
    return cond


def main() -> None:
    ok = True
    print("== 1. parser ==")
    offers = profesia.parse_list(LIST_INTERN)
    ok &= check("2 offers from list (sidebar link ignored)", len(offers) == 2)
    o1 = offers[0]
    ok &= check("offer id", o1.offer_id == "1000001")
    ok &= check("clean url", o1.url == "https://www.profesia.sk/praca/acme-tech/O1000001")
    ok &= check("title", "DevOps" in o1.title)
    ok &= check("company via class", o1.company == "Acme Tech s.r.o.")
    ok &= check("location via class", o1.location == "Bratislava")
    ok &= check("salary", "EUR" in o1.salary)
    o2 = offers[1]
    ok &= check("fallback company (no classes)", o2.company == "Big Corp a.s.")
    ok &= check("fallback location (no classes)", o2.location == "Trnava")

    print("== 2. matcher ==")
    cfg = load_config()
    m = Matcher(cfg)
    ok &= check("normalize diacritics", normalize("Vývojár PROGRAMÁTOR") == "vyvojar programator")
    s, hits = m.score("DevOps stážista: Docker, Linux, CI/CD")
    ok &= check(f"IT text scores >= 2 (got {s}: {hits})", s >= 2)
    s2, _ = m.score("Predaj oblečenia v obchode")
    ok &= check(f"non-IT text scores < 2 (got {s2})", s2 < 2)
    ok &= check("negative title blocks", m.title_blocked("Predavač/ka v obchode") is not None)
    ok &= check("normal title not blocked", m.title_blocked("IT stážista") is None)
    ok &= check("'ai' word boundary", m.score("AI/ML tím")[0] >= 2 and "aim high" not in
               " ".join(m.score("aim high")[1]))

    print("== 3. full pipeline (fixtures, dry run) ==")
    real_fetch = profesia.fetch_html
    profesia.fetch_html = fake_fetch_html
    try:
        matches = run_check(dry_run=True, write_state=False, log=lambda *a: None)
    finally:
        profesia.fetch_html = real_fetch
    ids = sorted(o.offer_id for o in matches)
    ok &= check(f"matches = IT intern + IT brigáda (got {ids})", ids == ["1000001", "1000003"])
    ok &= check("HR intern filtered out", "1000002" not in ids)
    digest = format_digest(matches, scanned=4, day_str="18.07.2026")
    ok &= check("digest contains link", 'href="https://www.profesia.sk/praca/acme-tech/O1000001"'
               in digest)
    ok &= check("digest groups internships", "Стажировки" in digest)
    ok &= check("chunking respects limit", all(len(c) <= 4000 for c in _chunks(digest * 40)))

    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
