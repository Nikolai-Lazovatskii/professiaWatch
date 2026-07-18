"""Quick live check of the parser (run on a machine with normal internet):

    python -m jobwatch.debug_parse
    python -m jobwatch.debug_parse "https://www.profesia.sk/praca/bratislavsky-kraj/internship-staz/"
"""
from __future__ import annotations

import sys

from . import profesia


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else profesia.build_list_url(
        "bratislavsky-kraj", "internship-staz", count_days=31)
    session = profesia.make_session()
    print(f"GET {url}")
    html = profesia.fetch_html(session, url)
    print(f"HTML: {len(html)} bytes")
    offers = profesia.parse_list(html)
    print(f"Parsed offers: {len(offers)}\n")
    for o in offers[:20]:
        print(f"  [{o.offer_id}] {o.title}")
        print(f"      company={o.company!r} location={o.location!r}")
        print(f"      salary={o.salary!r} posted={o.posted!r}")
        print(f"      {o.url}")
    if not offers:
        print("!! 0 offers parsed — разметка сайта могла измениться, "
              "пришли этот вывод Claude для правки парсера.")


if __name__ == "__main__":
    main()
