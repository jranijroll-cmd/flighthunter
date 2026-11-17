# FlightHunter v0.1

Monitor personale dei prezzi dei voli in **Python 3.12**, senza server o hosting
proprio. La v0.1 usa esclusivamente **dati simulati**: non consulta compagnie o
motori di ricerca e non richiede API key. I prezzi mock sono costanti; i test
simulano le variazioni per verificare gli alert.

## Avvio locale

Dalla directory del repository, con Python 3.12:

```sh
python -m flighthunter
python -m flighthunter --config config/searches.toml --history data/prices.jsonl
python -m unittest discover -s tests -v
```

Nessuna dipendenza runtime di terze parti. Su sistemi privi del database IANA dei
fusi orari occorre installare `tzdata` nel sistema o nell'ambiente Python. Il runner
Ubuntu di GitHub include il database. Facoltativamente `pip install -e .` rende
disponibile il comando `flighthunter`.

## Configurazione

Modifica `config/searches.toml`; ogni `[[searches]]` definisce:

| Campo | Significato |
| --- | --- |
| `id` | Identificativo univoco stabile della ricerca |
| `origin` | Aeroporto IATA, per esempio `FCO` |
| `destination` | `ANYWHERE` oppure aeroporto IATA |
| `currency` | Codice valuta, per esempio `EUR` |
| `departure_after_days` / `departure_before_days` | Intervallo inclusivo di giorni dalla data corrente a Roma, da 0 a 365 |
| `drop_percent` | Calo minimo rispetto all'ultima osservazione comparabile, in (0, 100] |
| `threshold` | Soglia facoltativa nella valuta della ricerca |

In v0.1 il contratto è un volo **solo andata per un adulto**, senza filtri per
bagagli o classe. ANYWHERE restituisce nel mock BCN, LIS e CDG, escludendo
l'origine: non è un catalogo completo. Il mock sceglie la prima data ammessa.
Cambiare i criteri di una ricerca richiede un nuovo `id` se si vuole separarne lo
storico. Non è prevista conversione tra valute.

## Risultati, storico e segnali

Gli adattatori convertono i risultati in `Offer`: origine/destinazione IATA,
data ISO, importo `Decimal` positivo a due decimali, valuta, provider, compagnia
e URL di prenotazione facoltativo. Le offerte fuori dai vincoli sono rifiutate;
tra duplicati della stessa esecuzione si conserva la meno costosa.

Ogni osservazione aggiunge una riga a `data/prices.jsonl`, con versione schema,
ricerca, timestamp UTC, chiave di confronto e lista `alerts`. Il confronto separa
ricerca, rotta, data di partenza, valuta, provider e compagnia:

- `percentage_drop`: `(ultimo - attuale) / ultimo * 100 >= drop_percent`;
- `new_all_time_low`: prezzo strettamente inferiore a tutti i precedenti;
- `below_threshold`: prezzo strettamente inferiore alla soglia.

La prima osservazione non genera calo o minimo storico; può generare sotto-soglia.
I segnali possono coesistere. La soglia viene segnalata a ogni osservazione sotto
soglia, senza cooldown. Output JSON su stdout e riepilogo nel job GitHub Actions;
non sono implementati invii email o notifiche push.

Lo storico è append-only, con un solo writer alla volta. Una riga corrotta causa
un errore senza cancellare lo storico. Le offerte sono raccolte prima della
scrittura, così un errore provider non salva risultati parziali della ricerca.
La scrittura su file non è una transazione contro interruzioni del processo:
conservare backup dello storico. Non eseguire più processi locali sullo stesso
file. Date diverse restano separate, anche con finestre temporali mobili.

## GitHub Actions e CET/CEST

`Tests` esegue la suite su push e pull request. `Monitor flights` permette
`workflow_dispatch` ed esecuzioni nominali alle **00:10, 06:00 e 11:00
Europe/Rome**, compresi i cambi CET/CEST:

| Ora Roma | UTC CET | UTC CEST |
| --- | --- | --- |
| 00:10 | 23:10 del giorno precedente | 22:10 del giorno precedente |
| 06:00 | 05:00 | 04:00 |
| 11:00 | 10:00 | 09:00 |

Il workflow registra sei candidati UTC. `schedule.py` usa `zoneinfo` per
selezionare i tre corretti. Converte l'istante nominale del cron, non l'ora effettiva
di avvio: ritardi fino a 12 ore non spostano lo slot e la data locale. Ritardi
superiori non sono supportati; GitHub non espone qui l'istante originale e un
ritardo oltre 24 ore non è distinguibile. La suite verifica tutti i giorni del
2026, inclusi i due cambi d'ora e la mezzanotte sul giorno UTC precedente.

Ogni slot ha un `run_id` locale persistito per evitare doppie osservazioni al
rerun. Le esecuzioni manuali sono intenzionalmente aggiuntive. Il gruppo di
concorrenza serializza i job; le esecuzioni non valide non scrivono dati.

Il bot committa il JSONL nel branch predefinito usando il `GITHUB_TOKEN` temporaneo
e il permesso `contents: write`. Non occorre alcuna chiave personale. Per attivare:

1. Conservare i workflow nel branch predefinito e abilitare GitHub Actions.
2. Consentire al token Actions di scrivere contenuti; eventuali regole di branch
   devono consentire i commit del bot, altrimenti il job fallirà nel salvataggio.
3. Eseguire una volta `Monitor flights` dalla scheda Actions e verificare il commit
   dello storico e il riepilogo del job.

GitHub può ritardare o saltare i job schedulati: non offre garanzia di puntualità
o recupero degli slot mancati. Nei repository pubblici inattivi può disabilitare
lo schedule dopo 60 giorni. Il checkout e il salvataggio usano il branch
predefinito. Un conflitto con modifiche concorrenti allo storico fa fallire il
push senza sovrascrivere dati remoti. Lo storico cresce nel repository: può
servire archiviarlo periodicamente. Repository pubblico significa anche storico
pubblico. Il costo dipende dai limiti gratuiti dell'account GitHub Actions,
soprattutto per repository privati; non sono richiesti servizi di hosting.

## Architettura ed estensioni

```text
config TOML → Search → FlightProvider → Offer normalizzate
                                      ↓
                           confronto storico → JSONL + alert
```

- `config.py`, `models.py`: validazione e modello comune.
- `providers/base.py`: contratto astratto `FlightProvider.search(search, today)`.
- `providers/mock.py`: implementazione iniziale senza rete.
- `monitor.py`, `history.py`: orchestrazione, confronto e persistenza.
- `schedule.py`, `cli.py`: selezione temporale e ingresso da CLI/Actions.

Per aggiungere Skyscanner, Duffel, Google Flights o PanFlights, creare un adapter
che implementi `FlightProvider` e normalizzi il payload in `Offer`, quindi
registrarlo nella configurazione e nel punto di costruzione della CLI. Gli
adapter devono dichiarare esplicitamente capacità non supportate, gestire
paginazione, timeout, retry limitati e rate limit. Dove ANYWHERE non è disponibile,
separare scoperta destinazioni e ricerche sulle singole rotte. Nessuno di questi
provider è già integrato o rappresentato come operativo.

Le verifiche dirette sui siti delle compagnie possono essere aggiunte come
servizio separato `verify(offer)`, con esito, timestamp e prezzo verificato; non
sovrascrivere il prezzo osservato dal provider. Per un confronto affidabile futuro
estendere la chiave con tratta completa, classe, bagagli, tasse e passeggeri,
e versionare lo schema JSONL. Accessi reali richiedono valutazione di API,
autorizzazioni e condizioni del servizio; non si presume che esista un'API
pubblica o supporto ANYWHERE per ciascun servizio.

Qualsiasi credenziale futura va letta da variabili d'ambiente o GitHub Actions
Secrets, mai dal TOML o dai file versionati. `.env` è ignorato. Non inserire token
negli URL di prenotazione, nello storico o nei log.
