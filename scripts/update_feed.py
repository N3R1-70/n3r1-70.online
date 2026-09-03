#!/usr/bin/env python3
"""
Aggiorna data/iwnla-feed.json leggendo le pagine pubbliche di iwillnotlookaway.org.

iwillnotlookaway.org non espone un feed RSS/Atom pubblico rilevabile, quindi
questo script legge la homepage (che elenca manifesti, analisi, attualità e
opinioni) e ne estrae i link "Leggi ..." più recenti, in modo indipendente
dalle classi CSS usate (cerca tag di titolo + link, non nomi di classe).

Pensato per girare ogni giorno via GitHub Actions (vedi
.github/workflows/update-feed.yml). Se lo scraping fallisce o non trova nulla,
lo script NON sovrascrive il file esistente: esce con un messaggio e basta,
così il sito mostra sempre l'ultimo aggiornamento riuscito.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://iwillnotlookaway.org/"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "iwnla-feed.json"
MAX_ITEMS = 10
TIMEOUT = 20

MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5,
    "giugno": 6, "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10,
    "novembre": 11, "dicembre": 12,
}

DATE_RE = re.compile(
    r"(\d{1,2}\s+)?(" + "|".join(MONTHS.keys()) + r")\s+(\d{4})",
    re.IGNORECASE,
)

CATEGORY_BY_PREFIX = [
    ("op-", "Opinione"),
    ("m-", "Manifesto"),
    ("m1", "Manifesto"),
    ("nd-", "Analisi"),
]

STAT_LABELS = {
    "manifesti": "Manifesti",
    "analisi": "Analisi",
    "attualita": "Attualità",
    "opinioni": "Opinioni",
    "fonti": "Fonti verificate",
    "lingue": "Lingue",
}


def parse_date(text):
    """Estrae la data italiana più recente in un blocco di testo. Ritorna (datetime, str originale) o None."""
    match = None
    for m in DATE_RE.finditer(text or ""):
        match = m  # tiene l'ultima occorrenza trovata nel blocco
    if not match:
        return None
    day = int(match.group(1).strip()) if match.group(1) else 1
    month = MONTHS[match.group(2).lower()]
    year = int(match.group(3))
    try:
        dt = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    raw = match.group(0).strip()
    return dt, raw


def guess_category(url):
    for prefix, label in CATEGORY_BY_PREFIX:
        if f"/{prefix}" in url or url.split("/")[-1].startswith(prefix):
            return label
    return "Analisi"


def nearby_text(tag, chars=400):
    """Raccoglie il testo del contenitore più vicino attorno a un tag, per cercarci una data."""
    node = tag
    for _ in range(4):
        if node is None:
            break
        text = node.get_text(" ", strip=True)
        if text:
            return text[:chars]
        node = node.parent
    return ""


def extract_stats(html):
    """Estrae i contatori ('20 Attualità', '8 Manifesti', ...) dalla homepage."""
    soup = BeautifulSoup(html, "html.parser")
    label_to_key = {v: k for k, v in STAT_LABELS.items()}
    pattern = re.compile(r"^(\d+)\s+(" + "|".join(re.escape(v) for v in STAT_LABELS.values()) + r")$")

    stats = {}
    for tag in soup.find_all(["a", "span", "div", "li"]):
        text = tag.get_text(" ", strip=True)
        m = pattern.match(text)
        if m:
            key = label_to_key[m.group(2)]
            stats[key] = int(m.group(1))
    return stats


SECTION_LABELS = {"Manifesti", "Analisi", "Attualità", "Opinioni", "Argomenti", "Fonti verificate", "Lingue"}


def extract_items(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        label = link.get_text(strip=True)
        if not label.lower().startswith("leggi"):
            continue

        href = urljoin(base_url, link["href"])
        if href in seen_urls:
            continue

        category = guess_category(href)
        if category == "Manifesto":
            # I manifesti sono documenti sempre validi, senza data di pubblicazione:
            # non appartengono a un feed di "ultimi aggiornamenti" datato.
            continue

        heading = link.find_previous(["h1", "h2", "h3", "h4"])
        if not heading:
            continue
        title = heading.get_text(" ", strip=True)
        if not title or len(title) < 8 or title in SECTION_LABELS:
            # Titolo non trovato per il singolo elemento: quello intercettato è
            # il titolo della sezione (es. "Manifesti"), non dell'articolo. Meglio
            # scartare che pubblicare un titolo sbagliato/ripetuto.
            continue

        block_text = nearby_text(link)
        parsed = parse_date(block_text) or parse_date(title)
        if not parsed:
            # Niente data trovata: il feed deve restare pulito e datato,
            # quindi si scarta piuttosto che inventare/lasciare vuoto.
            continue

        items.append({
            "title": title,
            "url": href,
            "date": parsed[1],
            "_sort_key": parsed[0],
            "category": category,
        })
        seen_urls.add(href)

    items.sort(key=lambda it: it["_sort_key"], reverse=True)
    for it in items:
        del it["_sort_key"]
    return items


def load_existing():
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def main():
    existing = load_existing()

    try:
        resp = requests.get(SOURCE_URL, timeout=TIMEOUT, headers={
            "User-Agent": "n3r1-70-feed-bot/1.0 (+https://n3r1-70.online)"
        })
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"Errore nello scaricare {SOURCE_URL}: {exc}", file=sys.stderr)
        return 0  # non fallire la action: si tiene il feed precedente

    items = extract_items(resp.text, SOURCE_URL)
    stats = extract_stats(resp.text)

    if not items:
        print("Nessun elemento estratto: la struttura della pagina potrebbe essere cambiata. File esistente non toccato.", file=sys.stderr)
        return 0

    # Se per qualche motivo uno o più contatori non si trovano più (pagina cambiata),
    # mantiene l'ultimo valore noto invece di sparire dal sito.
    merged_stats = dict(existing.get("stats", {}))
    merged_stats.update(stats)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE_URL,
        "items": items[:MAX_ITEMS],
        "stats": merged_stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scritto {OUTPUT_PATH} con {len(payload['items'])} elementi e {len(merged_stats)} contatori.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
