# Sito N3R1-70

Sito statico (solo HTML/CSS/JS, nessun build tool) pronto per GitHub Pages.

## 1. Caricare il sito su GitHub

1. Apri GitHub Desktop, crea (o apri) il repository per `n3r1-70.online`.
2. Copia **tutto il contenuto di questa cartella** (compresi i file nascosti
   `.nojekyll` e la cartella `.github`) dentro la cartella del repository,
   sovrascrivendo quanto già presente.
3. Commit → Push.

## 2. Attivare GitHub Pages

Nel repository su github.com: **Settings → Pages**
- Source: `Deploy from a branch`
- Branch: `main` (o `master`), cartella `/ (root)`
- Salva.

Dopo un minuto o due il sito sarà visibile su `https://<tuo-utente>.github.io/<repo>/`.

## 3. Collegare il dominio n3r1-70.online

Il file `CNAME` (già incluso, contiene `n3r1-70.online`) dice a GitHub di
servire il sito su quel dominio. Devi solo configurare il DNS dal pannello
del tuo registrar (dove hai comprato il dominio):

- Se usi il dominio "nudo" `n3r1-70.online`, crea **4 record A** che puntano a:
  ```
  185.199.108.153
  185.199.109.153
  185.199.110.153
  185.199.111.153
  ```
- Se vuoi anche `www.n3r1-70.online`, crea un record **CNAME** che punta a
  `<tuo-utente>.github.io`.

In **Settings → Pages** su GitHub, sotto "Custom domain", scrivi
`n3r1-70.online` e salva (GitHub verifica il DNS e può attivare da solo
l'HTTPS: spunta "Enforce HTTPS" quando diventa disponibile, di solito dopo
qualche minuto/ora).

## 4. Attivare l'aggiornamento automatico del feed (importante)

`iwillnotlookaway.org` non pubblica un feed RSS pubblico rilevabile: ho
quindi creato uno script (`scripts/update_feed.py`) che ogni giorno legge la
homepage del sito ed estrae i titoli più recenti in `data/iwnla-feed.json`,
che la pagina "I Will Not Look Away" e la home mostrano in automatico.

Perché lo script possa **salvare da solo** l'aggiornamento nel repository,
serve un permesso di scrittura per le GitHub Actions (disattivato di
default):

**Settings → Actions → General → Workflow permissions** → seleziona
**"Read and write permissions"** → Save.

Da quel momento, ogni giorno alle 06:00 UTC il workflow
`.github/workflows/update-feed.yml` rigenera il file e lo pubblica da solo.
Puoi anche lanciarlo a mano da **Actions → "Aggiorna feed I Will Not Look
Away" → Run workflow**, utile per il primo test dopo il caricamento.

Se in futuro iwillnotlookaway.org cambia struttura e lo script smette di
trovare articoli, non succede nulla di grave: il file `data/iwnla-feed.json`
resta quello dell'ultimo aggiornamento riuscito e il sito continua a
funzionare — segnalamelo e sistemo lo script.

## 5. Struttura del progetto

```
index.html                        Home
chi-sono.html                     Pagina "Chi sono"
libro-tecnico-di-logica.html      Scheda libro 1
libro-protocollo-kernel-70.html   Scheda libro 2
libro-questa-e-la-mia-terra.html  Scheda libro 3
iwillnotlookaway.html             Pagina del progetto + feed completo
css/style.css                     Tutto lo stile del sito
js/main.js                        Menu mobile
js/feed.js                        Carica data/iwnla-feed.json e lo mostra
data/iwnla-feed.json              Ultimi contenuti di iwillnotlookaway.org
scripts/update_feed.py            Script che rigenera il feed
.github/workflows/update-feed.yml Automazione giornaliera del feed
images/                           Logo, favicon, foto per l'hero
CNAME                             Dominio personalizzato per GitHub Pages
```

## 6. Cose da sapere / da decidere

- **Copertine dei libri**: integrate le copertine reali che hai caricato
  (`images/covers/`), sia nelle pagine di dettaglio sia come miniatura nelle
  liste "I libri".
- **Nome dell'autore**: ho tenuto lo pseudonimo N3R1 in tutto il sito senza
  usare il nome reale che compare nei file del progetto, per non esporre
  un'informazione che potresti voler restare privata (soprattutto vista la
  natura dei libri 2 e 3). Se preferisci comparire con nome e cognome, dimmi
  dove vuoi che appaia e lo aggiungo.
- **Due refusi nel testo del Libro 1** che ti segnalo per la tua revisione,
  li ho lasciati esattamente come li hai scritti tu: "una linea é ha
  iniziato" e "scegliamo di essere é ciò che" — in entrambi i casi sembra
  mancare una "e" (congiunzione) al posto di "é". Dimmi se li correggo.
- I numeri della sezione "Il progetto gemello" (8 manifesti, 27 analisi...)
  **si aggiornano da soli**, insieme alla lista degli "ultimi aggiornamenti",
  tramite lo stesso script/workflow — non serve nessuna azione in più.
