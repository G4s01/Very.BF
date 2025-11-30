# coupon_gen

Script Python per riprodurre il comportamento del popup per i coupon del BlackFriday 2025 di VeryMobile e ottenere/registrare i coupon generati dal backend.

Questo repository contiene `coupon_gen.py`, uno strumento CLI che:
- replica la sequenza di richieste osservata nel browser (mbox -> mbox -> /c99a -> /c99a -> webhook n8n),
- estrae il coupon restituito dal webhook e lo stampa a schermo,
- replica l'echo del coupon al webhook (come nel traffico reale),
- salva output e registra log dettagliati su file per auditing.

Prerequisiti
- Python 3.8+
- installa la dipendenza:
  pip install requests

Installazione
1. Copia `coupon_gen.py` nella cartella desiderata.
2. (Opzionale) crea un virtualenv:
   python -m venv .venv
   source .venv/bin/activate  # o .venv\Scripts\activate su Windows
3. Installa requests:
   pip install requests

Uso (esempi)
- Solo webhook (ottenere coupon):
  python coupon_gen.py --mode simple

- Sequenza completa (mbox -> c99a -> n8n) — esegue automaticamente anche l'echo del coupon:
  python coupon_gen.py --mode full

- Forzare cookie _ga (estrazione del cid):
  python coupon_gen.py --mode full --ga "GA1.2.1234567890.1764436606"

- Salvare il coupon su file:
  python coupon_gen.py --mode full --out coupon.txt

- Far eseguire l'echo manuale in simple mode:
  python coupon_gen.py --mode simple --echo

Logging
- Di default i log vengono scritti in `coupon_gen.log`.
- Opzioni:
  --log <file>        File di log (default: coupon_gen.log)
  --log-level <lvl>   Livello: DEBUG, INFO, WARNING, ERROR (default INFO)
  --log-full          Registra interi body request/response (molto verboso)

Esempio con log dettagliato:
  python coupon_gen.py --mode full --log mylog.txt --log-level DEBUG --log-full

Opzioni principali
- --mode {simple,full} : modalità di esecuzione (default: simple)
- --ga <value>         : imposta il cookie _ga (es. GA1.2.x.y) per derivare il campo `cid`
- --existing <code>    : invia un coupon esistente nel payload al webhook
- --echo               : in simple mode effettua l'echo del coupon al webhook
- --out <file>         : salva il coupon ricevuto su file
- --print-raw          : stampa il JSON raw restituito dal webhook

Sicurezza e responsabilità
- Questo script esegue richieste reali verso endpoint esterni (verymobile / mbox / n8n).
- Usalo solo con autorizzazione del responsabile/owner del servizio.
- I file di log possono contenere cookie e altri dati sensibili: custodiscili in modo appropriato (accesso controllato, .gitignore per file di log, ecc.).

Consigli operativi
- Se vuoi riprodurre esattamente il traffico browser, puoi passare i JSON raw di mbox o il cookie _ga reale; lo script supporta entrambe le opzioni (contatta il manutentore per modifiche avanzate).
- Per operazioni ripetute in ambiente di test, considera di aggiungere rotazione file per i log (RotatingFileHandler).

--- 
