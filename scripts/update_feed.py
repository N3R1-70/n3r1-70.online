#!/usr/bin/env python3
"""
Aggiorna data/iwnla-feed.json leggendo:
- il feed RSS di iwillnotlookaway.org (https://iwillnotlookaway.org/feed.xml)
  per gli articoli: ogni <item> porta due tag <category> — uno è la lingua
  (IT, EN, FR...) e l'altro è la categoria editoriale in maiuscolo (ANALISI,
  ATTUALITÀ, OPINIONE, MANIFESTO) — quindi niente più bisogno di indovinare
  la categoria dal prefisso dell'URL o dalla sezione della pagina. La data
  (pubDate) è un timestamp RFC 822 preciso, non un testo libero misto a
  citazioni, quindi niente più rischio di confondere la data dell'articolo
  con una data citata nel corpo del testo.
- la homepage di iwillnotlookaway.org per i contatori (Manifesti, Analisi,
  Attualità, Opinioni, Fonti verificate, Lingue), che non sono nel feed.

Pensato per girare ogni giorno via GitHub Actions (vedi
.github/workflows/update-feed.yml). Se una delle due fonti fallisce,
lo script NON sovrascrive quella parte del file esistente: aggiorna solo
quello che è riuscito a leggere.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FEED_URL = "https://iwillnotlookaway.org/feed.xml"
SOURCE_URL = "https://iwillnotlookaway.org/"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "iwnla-feed.json"
MAX_ITEMS = 10
TIMEOUT = 20
LANGUAGE_FILTER = "IT"

# Categoria dichiarata nel feed (maiuscolo) -> etichetta da scrivere nel feed
# del sito. "Manifesto" viene comunque escluso più sotto: i manifesti sono
# documenti sempre validi, senza data di pubblicazione, e non appartengono
# a un feed di "ultimi aggiornamenti" datato.
CATEGORY_MAP = {
    "ANALISI": "Analisi",
    "ATTUALITÀ": "Attualità",
    "OPINIONE": "Opinione",
    "MANIFESTO": "Manifesto",
}

MONTHS_IT = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio",
    6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre",
    11: "novembre", 12: "dicembre",
}

STAT_LABELS = {
    "manifesti": "Manifesti",
    "analisi": "Analisi",
    "attualita": "Attualità",
    "opinioni": "Opinioni",
    "fonti": "Fonti verificate",
    "lingue": "Lingue",
}

TITLE_LANG_SUFFIX_RE = re.compile(r"\s*\[" + LANGUAGE_FILTER + r"\]\s*$")


def format_italian_date(dt):
    return f"{dt.day} {MONTHS_IT[dt.month]} {dt.year}"


def extract_items_from_feed(xml_text):
    """Estrae gli articoli in italiano dal feed RSS, con categoria e data
    già strutturate (niente più euristiche sul markup della homepage)."""
    root = ET.fromstring(xml_text)
    items = []

    for item in root.findall(".//item"):
        categories = [c.text.strip() for c in item.findall("category") if c.text]
        if LANGUAGE_FILTER not in categories:
            continue

        category = None
        for c in categories:
            if c in CATEGORY_MAP:
                category = CATEGORY_MAP[c]
                break
        if category is None or category == "Manifesto":
            continue

        title_el = item.find("title")
        link_el = item.find("link")
        pubdate_el = item.find("pubDate")
        if title_el is None or link_el is None or pubdate_el is None:
            continue
        if not title_el.text or not link_el.text or not pubdate_el.text:
            continue

        try:
            dt = parsedate_to_datetime(pubdate_el.text)
        except (TypeError, ValueError):
            continue

        title = TITLE_LANG_SUFFIX_RE.sub("", title_el.text).strip()

        items.append({
            "title": title,
            "url": link_el.text.strip(),
            "date": format_italian_date(dt),
            "_sort_key": dt,
            "category": category,
        })

    items.sort(key=lambda it: it["_sort_key"], reverse=True)
    for it in items:
        del it["_sort_key"]
    return items


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


def load_existing():
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def fetch(url):
    return requests.get(url, timeout=TIMEOUT, headers={
        "User-Agent": "n3r1-70-feed-bot/1.0 (+https://n3r1-70.online)"
    })


def main():
    existing = load_existing()

    items = []
    try:
        feed_resp = fetch(FEED_URL)
        feed_resp.raise_for_status()
        items = extract_items_from_feed(feed_resp.text)
    except Exception as exc:  # noqa: BLE001
        print(f"Errore nel leggere {FEED_URL}: {exc}", file=sys.stderr)

    stats = {}
    try:
        home_resp = fetch(SOURCE_URL)
        home_resp.raise_for_status()
        stats = extract_stats(home_resp.text)
    except Exception as exc:  # noqa: BLE001
        print(f"Errore nello scaricare {SOURCE_URL}: {exc}", file=sys.stderr)

    if not items and not stats:
        print("Né feed né homepage hanno prodotto dati: tengo il file precedente invariato.", file=sys.stderr)
        return 0

    # Contatori e articoli sono indipendenti: se una delle due fonti fallisce,
    # l'altra si aggiorna comunque.
    merged_stats = dict(existing.get("stats", {}))
    merged_stats.update(stats)

    final_items = items[:MAX_ITEMS] if items else existing.get("items", [])
    if not items:
        print("Nessun articolo estratto dal feed: tengo la lista precedente.", file=sys.stderr)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": FEED_URL,
        "items": final_items,
        "stats": merged_stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scritto {OUTPUT_PATH} con {len(payload['items'])} elementi e {len(merged_stats)} contatori.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
