#!/usr/bin/env python3
"""
Aggiorna data/iwnla-feed.json leggendo le pagine pubbliche di iwillnotlookaway.org.

iwillnotlookaway.org non espone un feed RSS/Atom pubblico rilevabile, quindi
questo script legge la homepage (che elenca manifesti, analisi, attualità e
opinioni) e ne estrae i link "Leggi ..." più recenti.

Categoria e data sono derivate dalla struttura reale della pagina, non da
euristiche sull'URL:
- la categoria è il titolo di sezione (<h2>Analisi</h2>, <h2>Attualità</h2>...)
  che precede l'articolo nel documento;
- la data è il testo-data che precede il titolo dell'articolo (il "kicker",
  es. "28 luglio 2026"), cercato all'indietro nel documento — non risalendo
  i genitori del link, perché quel percorso inglobava anche la citazione
  con l'attribuzione (che spesso contiene un'altra data, quella della fonte
  citata) e quella finiva per vincere su quella vera dell'articolo.

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

# Sezioni riconosciute dagli <h2> della homepage -> etichetta di categoria da
# scrivere nel feed. La chiave è cercata come sottostringa nel testo (in
# minuscolo) dell'h2, così tollera piccole variazioni di markup.
SECTION_CATEGORY = [
    ("manifesti", "Manifesto"),
    ("analisi", "Analisi"),
    ("attualità", "Attualità"),
    ("attualita", "Attualità"),
    ("opinioni", "Opinione"),
]

STAT_LABELS = {
    "manifesti": "Manifesti",
    "analisi": "Analisi",
    "attualita": "Attualità",
    "opinioni": "Opinioni",
    "fonti": "Fonti verificate",
    "lingue": "Lingue",
}

SECTION_LABELS = {"Manifesti", "Analisi", "Attualità", "Opinioni", "Argomenti", "Fonti verificate", "Lingue"}


def parse_date(text):
    """Estrae UNA data italiana da un pezzo di testo breve (già mirato).
    Ritorna (datetime, stringa originale) o None."""
    match = DATE_RE.search(text or "")
    if not match:
        return None
    day = int(match.group(1).strip()) if match.group(1) else 1
    month = MONTHS[match.group(2).lower()]
    year = int(match.group(3))
    try:
        dt = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    return dt, match.group(0).strip()


def guess_category(heading):
    """Categoria = titolo di sezione (<h2>) più vicino PRIMA di questo articolo
    nel documento. Riflette la struttura reale della pagina invece di
    indovinare dal prefisso dell'URL (che su questo sito è ambiguo: sia
    Analisi sia Attualità usano lo slug 'nd-')."""
    h2 = heading.find_previous("h2")
    if not h2:
        return None
    text = h2.get_text(strip=True).lower()
    for key, label in SECTION_CATEGORY:
        if key in text:
            return label
    return None


def find_kicker_date(heading):
    """Cerca all'indietro nel documento, a partire dal titolo, il testo-data
    più vicino (il 'kicker' che precede ogni titolo, es. '28 luglio 2026').
    Cercare all'INDIETRO dal titolo (non in avanti, non risalendo i genitori)
    evita di intercettare la data della citazione/attribuzione che segue il
    titolo, la quale appartiene alla fonte citata e non alla data di
    pubblicazione dell'articolo."""
    node = heading.find_previous(string=DATE_RE)
    if node is None:
        return None
    return parse_date(str(node))


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

        heading = link.find_previous(["h1", "h2", "h3", "h4"])
        if not heading:
            continue

        title = heading.get_text(" ", strip=True)
        if not title or len(title) < 8 or title in SECTION_LABELS:
            # Titolo non trovato per il singolo elemento: quello intercettato è
            # il titolo della sezione (es. "Manifesti"), non dell'articolo.
            continue

        category = guess_category(heading)
        if category is None:
            # Sezione non riconosciuta: meglio scartare che scrivere una
            # categoria sbagliata.
            continue
        if category == "Manifesto":
            # I manifesti sono documenti sempre validi, senza data di
            # pubblicazione: non appartengono a un feed di "ultimi
            # aggiornamenti" datato.
            continue

        parsed = find_kicker_date(heading) or parse_date(title)
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

    # Contatori e articoli sono indipendenti: se uno dei due non si trova
    # (pagina cambiata, rete lenta...) l'altro si aggiorna comunque.
    merged_stats = dict(existing.get("stats", {}))
    merged_stats.update(stats)

    final_items = items[:MAX_ITEMS] if items else existing.get("items", [])
    if not items:
        print("Nessun articolo estratto: tengo la lista precedente, aggiorno solo i contatori se trovati.", file=sys.stderr)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE_URL,
        "items": final_items,
        "stats": merged_stats,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scritto {OUTPUT_PATH} con {len(payload['items'])} elementi e {len(merged_stats)} contatori.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
