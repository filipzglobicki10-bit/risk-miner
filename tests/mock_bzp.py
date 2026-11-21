"""Atrapa API BZP do testów — PRAWDZIWE ogłoszenia, odtworzone zachowanie prawdziwego API.

Dane: samples/bzp_kopia_22_projekty.json — 198 ogłoszeń pobranych z kopii API organizatora (bzp.cytr.us)
dla 22 projektów pakietu (treść formularzy, e-maile i telefony usunięte).

Zachowanie odwzorowane na podstawie sprawdzenia prawdziwego interfejsu GET /mo-board/api/v1/notice:
  * działają filtry: NoticeType (wymagany; nieznany typ -> HTTP 400, np. ContractModificationNotice),
    NoticeNumber, PublicationDateFrom/To, OrganizationName (fragment nazwy, bez względu na wielkość liter);
  * są IGNOROWANE: OrganizationId, OrganizationNationalId, TenderId, CpvCode, BzpNumber, PageNumber;
  * sortowanie od najnowszych, stronicowanie przez SearchAfter=<objectId> (wyłącznie), PageSize domyślnie 10, maks. 500.
Dzięki temu test sprawdza strategię wyszukiwania, która działa na prawdziwym API, a nie na wygodnej atrapie.
"""
import json
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT = os.path.join(os.path.dirname(HERE), "samples", "bzp_kopia_22_projekty.json")
VALID_TYPES = {"ContractNotice", "TenderResultNotice", "AgreementUpdateNotice", "ContractPerformingNotice", "NoticeUpdateNotice",
               "CompetitionNotice", "CompetitionResultNotice", "SmallContractNotice", "TenderNotice"}


def load():
    with open(SNAPSHOT, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"] if isinstance(data, dict) else data
    return sorted(items, key=lambda n: (n.get("publicationDate") or "", n.get("objectId") or ""), reverse=True)


NOTICES = load()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if not u.path.endswith("/mo-board/api/v1/notice"):
            return self._send(404, {"error": "not found"})
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        H.calls.append(q)
        if q.get("NoticeType") not in VALID_TYPES:
            return self._send(400, {"errors": {"NoticeType": ["The value is not valid."]}})
        out = [n for n in NOTICES if n["noticeType"] == q["NoticeType"]]
        if q.get("NoticeNumber"):
            out = [n for n in out if n["noticeNumber"] == q["NoticeNumber"]]
        if q.get("OrganizationName"):
            needle = q["OrganizationName"].lower()
            out = [n for n in out if needle in (n.get("organizationName") or "").lower()]
        if q.get("PublicationDateFrom"):
            out = [n for n in out if n["publicationDate"] >= q["PublicationDateFrom"]]
        if q.get("PublicationDateTo"):
            out = [n for n in out if n["publicationDate"] <= q["PublicationDateTo"]]
        if q.get("SearchAfter"):
            ids = [n["objectId"] for n in out]
            out = out[ids.index(q["SearchAfter"]) + 1:] if q["SearchAfter"] in ids else []
        size = max(1, min(500, int(q.get("PageSize") or 10)))
        return self._send(200, out[:size])


H.calls = []


def start(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    print(f"Atrapa BZP ({len(NOTICES)} prawdziwych ogłoszeń): http://127.0.0.1:8765/mo-board/api/v1/notice")
    start().serve_forever()
