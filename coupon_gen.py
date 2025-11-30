#!/usr/bin/env python3
"""
coupon_gen.py

Versione con logging su file. Registra richieste e risposte (header, payload,
status, body preview) in un file di log per auditing/debug.

Uso (esempi):
  python coupon_gen.py --mode full                      # log default in coupon_gen.log
  python coupon_gen.py --mode full --log mylog.txt      # log su mylog.txt
  python coupon_gen.py --mode full --log mylog.txt --log-level DEBUG
  python coupon_gen.py --mode simple --ga "GA1.2..." --out coupon.txt

Opzioni:
  --log <file>        File di log (default: coupon_gen.log)
  --log-level <lvl>   Livello di log (DEBUG, INFO, WARNING, ERROR). Default INFO.
  --log-full          Se presente, registra interi body request/response; altrimenti trunca a 2000 char.

Nota:
 - Usa con autorizzazione. Lo script invia richieste reali verso i servizi indicati.
 - Requisiti: pip install requests
"""
from typing import Optional
import argparse
import json
import sys
import time
import logging
import requests
from datetime import datetime

# ---------------------------
# Config (stessi URL e default come prima)
# ---------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)

MBX_URL = "https://mboxedge37.tt.omtrdc.net/rest/v1/delivery?client=windtre&sessionId=de71c9d5bab040ffa05c369bc6bdddfc&version=2.11.4"
VERY_C99A_URL = "https://verymobile.it/c99a4269-161c-4242-a3f0-28d44fa6ce24?"
N8N_WEBHOOK = "https://n8nanitia.app.n8n.cloud/webhook/popup-noleave"

DEFAULT_COOKIES = {
    "__uzma": "1e983c5a-1858-4f35-8139-f71f8801f3b1",
    "__uzmb": "1759947967",
    "__uzme": "6459",
    "__ssds": "0",
    "__ssuzjsr0": "a9be0cd8e",
    "__uzmaj0": "1e983c5a-1858-4f35-8139-f71f8801f3b1",
    "__uzmbj0": "1763078854",
    "__uzmlj0": "2YDCUsrHqPXue+jydYzKmk8B6wSrGrcnCVB2Kn62KR0=",
    "at_check": "true",
    "mboxEdgeCluster": "37",
    "couponGamification": "B-YV6YG1",
    "__uzmcj0": "691507039830",
    "__uzmdj0": "1764436606",
    "__uzmfj0": "7f90001e983c5a-1858-4f35-8139-f71f8801f3b12-17630788542921357751983-001e6ef264a7f80dd2570",
    "uzmxj": "7f900007428410-dc6b-4331-b2f5-c524f75288752-17630788542921357751983-2c8d15751fb83fc570",
    "__uzmc": "1814228672767",
    "__uzmd": "1764436647",
    "__uzmf": "7f90001e983c5a-1858-4f35-8139-f71f8801f3b18-17599479678794488680010-001891e451ca5452454286",
    "uzmx": "7f900007428410-dc6b-4331-b2f5-c524f75288757-17604270736624009574227-4e5a239ebba651ad232",
    "mbox": "PC#01c60f3bcc054c248e1b3ce75eaacacd.37_0#1827681451|session#de71c9d5bab040ffa05c369bc6bdddfc#1764438511",
}

COMMON_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://verymobile.it",
    "Referer": "https://verymobile.it/offerte/very-599",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# ---------------------------
# Logging setup helper
# ---------------------------
LOG_TRUNCATE_DEFAULT = 2000


def setup_logger(logfile: str, level_str: str, log_full: bool) -> logging.Logger:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logger = logging.getLogger("coupon_gen")
    logger.setLevel(level)
    # Avoid duplicate handlers if setup_logger called multiple times
    if not logger.handlers:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setLevel(level)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    # also log to console at INFO+ (console handler)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    # remove existing console handlers to prevent duplicates
    found_console = False
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler):
            found_console = True
            break
    if not found_console:
        logger.addHandler(ch)
    # store flag on logger
    logger.log_full = log_full  # type: ignore
    return logger


def _truncate(s: str, limit: int) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + "...(truncated)"


# ---------------------------
# Helpers (same behavior as prima, con logging)
# ---------------------------


def extract_cid_from_ga(ga_cookie_value: Optional[str]) -> Optional[str]:
    if not ga_cookie_value:
        return None
    parts = ga_cookie_value.split(".")
    if len(parts) >= 4:
        return f"{parts[2]}.{parts[3]}"
    return ga_cookie_value


def log_request(logger: logging.Logger, tag: str, method: str, url: str, headers: dict, payload: Optional[str]):
    logger.info(f"[REQ] {tag} {method} {url}")
    logger.debug(f"[REQ-HEADERS] {tag} {json.dumps(dict(headers), ensure_ascii=False)}")
    if payload is not None:
        if getattr(logger, "log_full", False):
            logger.debug(f"[REQ-BODY] {tag} {payload}")
        else:
            logger.debug(f"[REQ-BODY] {tag} {_truncate(str(payload), LOG_TRUNCATE_DEFAULT)}")


def log_response(logger: logging.Logger, tag: str, resp: requests.Response):
    logger.info(f"[RESP] {tag} {resp.status_code} {resp.url}")
    try:
        headers = dict(resp.headers)
        logger.debug(f"[RESP-HEADERS] {tag} {json.dumps(headers, ensure_ascii=False)}")
        body = resp.text
        if getattr(logger, "log_full", False):
            logger.debug(f"[RESP-BODY] {tag} {body}")
        else:
            logger.debug(f"[RESP-BODY] {tag} {_truncate(body, LOG_TRUNCATE_DEFAULT)}")
    except Exception as e:
        logger.error(f"[RESP] error serializing response: {e}")


# ---------------------------
# Calls to replicate (con logging)
# ---------------------------


def call_mbox(session: requests.Session, logger: logging.Logger, raw_body: Optional[str] = None) -> requests.Response:
    headers = dict(COMMON_HEADERS)
    headers["Content-Type"] = "text/plain"

    if raw_body:
        payload = raw_body
    else:
        payload_obj = {
            "requestId": "simulated-" + str(int(time.time())),
            "context": {
                "channel": "web",
                "userAgent": USER_AGENT,
                "address": {"url": "https://verymobile.it/offerte/very-599"},
            },
        }
        payload = json.dumps(payload_obj, separators=(",", ":"))
    log_request(logger, "mbox", "POST", MBX_URL, headers, payload)
    try:
        r = session.post(MBX_URL, data=payload, headers=headers, timeout=15)
    except Exception as e:
        logger.error(f"[mbox] request error: {e}")
        raise
    log_response(logger, "mbox", r)
    return r


def call_very_c99a(session: requests.Session, logger: logging.Logger, body_form: Optional[dict] = None) -> requests.Response:
    headers = dict(COMMON_HEADERS)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Referer"] = "https://verymobile.it/offerte/very-599"
    default_form = {
        "cid": "cczh",
        "uzl": DEFAULT_COOKIES.get("__uzmlj0", ""),
        "__uzmaj": DEFAULT_COOKIES.get("__uzma", ""),
        "__uzmbj": DEFAULT_COOKIES.get("__uzmbj0", ""),
        "__uzmlj": DEFAULT_COOKIES.get("__uzmlj0", ""),
        "__uzmcj": DEFAULT_COOKIES.get("__uzmcj0", ""),
        "__uzmdj": DEFAULT_COOKIES.get("__uzmdj0", ""),
        "__uzmfj": DEFAULT_COOKIES.get("__uzmfj0", ""),
        "uzmxj": DEFAULT_COOKIES.get("uzmxj", ""),
        "uzmx": DEFAULT_COOKIES.get("uzmx", ""),
        "dync": "uzmx",
        "url": "https://verymobile.it/offerte/very-599",
        "JSinfo": json.dumps({"j0": USER_AGENT})[:1000],
        "__uzmf": DEFAULT_COOKIES.get("__uzmf", ""),
    }
    form = dict(default_form)
    if body_form:
        form.update(body_form)
    # requests will encode the form -- log the form dict (truncated)
    payload_preview = json.dumps(form, ensure_ascii=False)
    log_request(logger, "c99a", "POST", VERY_C99A_URL, headers, payload_preview)
    try:
        r = session.post(VERY_C99A_URL, data=form, headers=headers, timeout=15)
    except Exception as e:
        logger.error(f"[c99a] request error: {e}")
        raise
    log_response(logger, "c99a", r)
    return r


def call_n8n_webhook(session: requests.Session, logger: logging.Logger, cid: Optional[str], existing_coupon: Optional[str] = None) -> Optional[dict]:
    headers = dict(COMMON_HEADERS)
    headers["Content-Type"] = "application/json"
    payload = {}
    if cid is not None:
        payload["cid"] = cid
    if existing_coupon:
        payload["coupon"] = existing_coupon
    payload_json = json.dumps(payload, ensure_ascii=False)
    log_request(logger, "n8n", "POST", N8N_WEBHOOK, headers, payload_json)
    try:
        r = session.post(N8N_WEBHOOK, json=payload, headers=headers, timeout=15)
    except Exception as e:
        logger.error(f"[n8n] connection error: {e}")
        return None
    log_response(logger, "n8n", r)
    try:
        return r.json()
    except Exception:
        logger.error("[n8n] response not JSON")
        return None


def echo_coupon_to_n8n(session: requests.Session, logger: logging.Logger, coupon: str) -> Optional[dict]:
    if not coupon:
        return None
    headers = dict(COMMON_HEADERS)
    headers["Content-Type"] = "application/json"
    payload = {"coupon": coupon}
    payload_json = json.dumps(payload, ensure_ascii=False)
    log_request(logger, "n8n-echo", "POST", N8N_WEBHOOK, headers, payload_json)
    try:
        r = session.post(N8N_WEBHOOK, json=payload, headers=headers, timeout=15)
    except Exception as e:
        logger.error(f"[n8n-echo] connection error: {e}")
        return None
    log_response(logger, "n8n-echo", r)
    try:
        return r.json()
    except Exception:
        logger.error("[n8n-echo] response not JSON")
        return None


# ---------------------------
# CLI / main
# ---------------------------


def main(argv):
    parser = argparse.ArgumentParser(description="Emula il popup coupon e stampa il coupon restituito (con logging su file).")
    parser.add_argument("--mode", choices=["simple", "full"], default="simple")
    parser.add_argument("--ga", help="Valore cookie _ga (es. GA1.2.1234567890.1764436606).")
    parser.add_argument("--existing", help="Passa coupon esistente nel payload (campo 'coupon').")
    parser.add_argument("--echo", action="store_true", help="Invia (echo) il coupon ricevuto al webhook n8n con body {'coupon': '...'} (in simple mode richiede --echo).")
    parser.add_argument("--out", help="Salva il coupon ricevuto su file (una riga).")
    parser.add_argument("--print-raw", action="store_true", help="Stampa il JSON raw restituito dal webhook.")
    parser.add_argument("--log", default="coupon_gen.log", help="File di log (default coupon_gen.log).")
    parser.add_argument("--log-level", default="INFO", help="Livello di log: DEBUG, INFO, WARNING, ERROR")
    parser.add_argument("--log-full", action="store_true", help="Registra interi body request/response (potrebbe essere molto verboso).")
    args = parser.parse_args(argv)

    logger = setup_logger(args.log, args.log_level, args.log_full)
    logger.info("=== Avvio coupon_gen ===")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # set cookies di default
    for name, value in DEFAULT_COOKIES.items():
        session.cookies.set(name, value, domain="verymobile.it", path="/")
        session.cookies.set(name, value, domain=".verymobile.it", path="/")

    if args.ga:
        session.cookies.set("_ga", args.ga, domain="verymobile.it", path="/")
        session.cookies.set("_ga", args.ga, domain=".verymobile.it", path="/")
        logger.info(f"Cookie _ga impostato da CLI: {args.ga}")

    ga_val = session.cookies.get("_ga", None)
    cid = extract_cid_from_ga(ga_val) if ga_val else None
    logger.info(f"[info] cookie _ga: {ga_val!r} -> cid derived: {cid!r}")

    coupon = None

    try:
        if args.mode == "simple":
            logger.info("[mode] simple - chiama solo n8n")
            resp = call_n8n_webhook(session, logger, cid, existing_coupon=args.existing)
            if resp is None:
                logger.error("Nessuna risposta valida da n8n.")
                print("Nessuna risposta valida da n8n.")
                sys.exit(1)
            if args.print_raw:
                print(json.dumps(resp, indent=2, ensure_ascii=False))
            coupon = resp.get("Coupon") or resp.get("coupon") or resp.get("CouponCode")
            if coupon:
                logger.info(f"Coupon ricevuto: {coupon}")
                print("\n--- COUPON RICEVUTO ---")
                print(coupon)
            else:
                logger.warning(f"Nessun campo 'Coupon' nella risposta. Keys: {list(resp.keys())}")
                print("Nessun campo 'Coupon' nella risposta. Keys:", list(resp.keys()))
            if coupon and args.echo:
                echo_coupon_to_n8n(session, logger, coupon)

        else:
            logger.info("[mode] full - sequenza mbox -> mbox -> c99a -> c99a -> n8n (echo incluso)")
            print("[full] eseguo sequenza simulata: mbox -> mbox -> c99a -> c99a -> n8n")
            try:
                call_mbox(session, logger)
                time.sleep(0.4)
                call_mbox(session, logger)
                time.sleep(0.4)
                call_very_c99a(session, logger)
                time.sleep(0.25)
                call_very_c99a(session, logger, body_form={"et": "82"})
                time.sleep(0.25)
            except Exception as e:
                logger.error(f"[full] errore durante sequenza simulata: {e}")
                print("[full] warning: errore durante sequenza simulata:", e)

            # ricalcolo cid
            ga_val = session.cookies.get("_ga", None)
            cid = extract_cid_from_ga(ga_val) if ga_val else cid
            logger.info(f"[full] dopo sequenza cookie _ga: {ga_val!r} -> cid: {cid!r}")

            resp = call_n8n_webhook(session, logger, cid, existing_coupon=args.existing)
            if resp is None:
                logger.error("[full] n8n non ha risposto correttamente.")
                print("[full] n8n non ha risposto correttamente.")
                sys.exit(1)
            if args.print_raw:
                print(json.dumps(resp, indent=2, ensure_ascii=False))

            coupon = resp.get("Coupon") or resp.get("coupon") or resp.get("CouponCode")
            if coupon:
                logger.info(f"Coupon ricevuto: {coupon}")
                print("\n--- COUPON RICEVUTO ---")
                print(coupon)
                # echo automatico come nelle richieste originali
                echo_resp = echo_coupon_to_n8n(session, logger, coupon)
                if echo_resp is not None:
                    logger.info(f"[full] echo response keys: {list(echo_resp.keys())}")
            else:
                logger.warning(f"Nessun campo 'Coupon' nella risposta. Keys: {list(resp.keys())}")
                print("Nessun campo 'Coupon' nella risposta. Keys:", list(resp.keys()))

    finally:
        logger.info("=== Fine esecuzione ===")

    # salva su file se richiesto
    if args.out:
        if coupon:
            try:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(coupon + "\n")
                logger.info(f"Coupon salvato in: {args.out}")
                print(f"(Coupon salvato in: {args.out})")
            except Exception as e:
                logger.error(f"Errore scrittura file: {e}")
                print("Errore scrittura file:", e)
        else:
            logger.warning("Nessun coupon da salvare.")

if __name__ == "__main__":
    main(sys.argv[1:])