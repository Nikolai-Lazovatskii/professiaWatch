"""Fetching and parsing profesia.sk listing and offer detail pages.

Parsing is intentionally defensive: the primary anchor is the semantic
structure (offer links look like /praca/<company>/O<digits> and sit inside a
heading tag), with class-based selectors used only as best-effort extras.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

BASE = "https://www.profesia.sk"
OFFER_HREF_RE = re.compile(r"/praca/[^/?#]+/O(\d+)")

REGION_LABELS = {
    "bratislavsky-kraj": "Bratislavský kraj",
    "trnavsky-kraj": "Trnavský kraj",
}
TYPE_LABELS = {
    "internship-staz": "internship / stáž",
    "na-dohodu-brigady": "brigáda (na dohodu)",
    "skrateny-uvazok": "skrátený úväzok",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "sk,en;q=0.8",
}


@dataclass
class Offer:
    offer_id: str
    url: str
    title: str
    company: str = ""
    location: str = ""
    salary: str = ""
    posted: str = ""
    region: str = ""
    job_type: str = ""
    # filled by matcher
    score: int = 0
    matched: list[str] = field(default_factory=list)
    detail_text: str = ""


def build_list_url(region: str, job_type: str, count_days: int, page: int = 1) -> str:
    url = f"{BASE}/praca/{region}/{job_type}/?count_days={count_days}"
    if page > 1:
        url += f"&page_num={page}"
    return url


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_html(session: requests.Session, url: str, retries: int = 3) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # noqa: BLE001 - simple retry loop
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_exc}")


def _clean_url(href: str) -> str:
    """Absolute offer URL without tracking params."""
    href = href.split("?")[0].split("#")[0]
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = BASE + href
    return href


def _li_text_lines(node) -> list[str]:
    return [ln.strip() for ln in node.get_text("\n").split("\n") if ln.strip()]


def parse_list(html: str) -> list[Offer]:
    """Extract offers from a listing page.

    Primary signal: offer link inside a heading (h1-h3). Metadata is taken
    from known profesia classes when present, otherwise from the text lines
    that follow the title inside the same list item.
    """
    soup = BeautifulSoup(html, "html.parser")
    offers: list[Offer] = []
    seen: set[str] = set()

    for heading in soup.find_all(["h1", "h2", "h3"]):
        a = heading.find("a", href=OFFER_HREF_RE)
        if not a:
            continue
        m = OFFER_HREF_RE.search(a.get("href", ""))
        if not m:
            continue
        offer_id = m.group(1)
        if offer_id in seen:
            continue
        seen.add(offer_id)

        title = a.get_text(" ", strip=True)
        offer = Offer(offer_id=offer_id, url=_clean_url(a["href"]), title=title)

        container = heading.find_parent("li") or heading.parent
        if container is not None:
            emp = container.select_one(".employer")
            loc = container.select_one(".job-location")
            if emp:
                offer.company = emp.get_text(" ", strip=True)
            if loc:
                offer.location = loc.get_text(" ", strip=True)

            lines = _li_text_lines(container)
            try:
                idx = next(i for i, ln in enumerate(lines) if title in ln or ln in title)
            except StopIteration:
                idx = -1
            tail = lines[idx + 1:] if idx >= 0 else lines
            # fallbacks from positional lines: company, location
            if not offer.company and tail:
                offer.company = tail[0]
            if not offer.location and len(tail) > 1:
                offer.location = tail[1]
            for ln in tail:
                if not offer.salary and ("EUR" in ln or "€" in ln):
                    offer.salary = ln
                if not offer.posted and (ln.startswith("Pred ") or ln.startswith("Dnes")
                                         or ln.startswith("Včera")):
                    offer.posted = ln
        offers.append(offer)
    return offers


def fetch_feed(session: requests.Session, region: str, job_type: str,
               count_days: int, max_pages: int = 5, delay: float = 0.8) -> list[Offer]:
    """Fetch all pages of one region+type feed."""
    all_offers: list[Offer] = []
    known: set[str] = set()
    for page in range(1, max_pages + 1):
        url = build_list_url(region, job_type, count_days, page)
        html = fetch_html(session, url)
        page_offers = [o for o in parse_list(html) if o.offer_id not in known]
        if not page_offers:
            break
        for o in page_offers:
            o.region = REGION_LABELS.get(region, region)
            o.job_type = TYPE_LABELS.get(job_type, job_type)
            known.add(o.offer_id)
        all_offers.extend(page_offers)
        if len(page_offers) < 15:  # short page => last page
            break
        time.sleep(delay)
    return all_offers


def _jsonld_jobposting(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                return item
    return None


def fetch_detail_text(session: requests.Session, offer: Offer) -> str:
    """Full text of the offer page for keyword matching (best effort)."""
    try:
        html = fetch_html(session, offer.url)
    except RuntimeError:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    posting = _jsonld_jobposting(soup)
    if posting:
        desc = BeautifulSoup(posting.get("description", ""), "html.parser").get_text(" ", strip=True)
        parts = [posting.get("title", ""), desc]
        org = posting.get("hiringOrganization")
        if isinstance(org, dict):
            offer.company = offer.company or org.get("name", "")
        if desc:
            return " ".join(p for p in parts if p)

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)
