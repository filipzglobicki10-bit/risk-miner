"""Test end-to-end przez REST API: import -> wzbogacenie z (atrapy) BZP -> dokumenty -> decyzje eksperta -> analiza nowej inwestycji -> eksport.

Uruchomienie:  python3 tests/test_e2e.py
Dane BZP: atrapa tests/mock_bzp.py podaje PRAWDZIWE ogłoszenia (kopia 198 ogłoszeń z API organizatora) i odtwarza
zachowanie prawdziwego API (działające i ignorowane filtry, stronicowanie). Oczekiwane wartości sprawdzono ręcznie w treści ogłoszeń.
"""
import json
import os
import sys
import threading
import time
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import tempfile
TMP = tempfile.mkdtemp(prefix="riskminer-e2e-")
CFG = os.path.join(TMP, "config.e2e.json")
with open(CFG, "w") as f:
    json.dump({"data_dir": os.path.join(TMP, "e2e-data"), "server": {"host": "127.0.0.1", "port": 8097},
               "bzp": {"base_url": "http://127.0.0.1:8766/mo-board/api/v1/notice", "fallback_urls": [], "cache": False},
               "ted": {"enabled": False}}, f)
os.environ["RISKMINER_CONFIG"] = CFG
os.environ["RISKMINER_QUIET"] = "1"


import mock_bzp  # noqa: E402
from riskminer import server  # noqa: E402

BASE = "http://127.0.0.1:8097"


def call(path, body=None, raw=None, filename=None, method=None):
    headers = {"X-User": "tester"}
    data = None
    if raw is not None:
        data = raw
        headers["X-Filename"] = urllib.parse.quote(filename)
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method or ("POST" if data is not None else "GET"))
    with urllib.request.urlopen(req, timeout=60) as r:
        txt = r.read().decode("utf-8")
        return json.loads(txt) if "json" in r.headers.get("Content-Type", "") else txt


import urllib.parse  # noqa: E402


def wait_job(jid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = call(f"/api/jobs/{jid}")
        if j["status"] != "w toku":
            return j
        time.sleep(0.3)
    raise TimeoutError("job")


class E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mock_bzp.start(8766)
        threading.Thread(target=server.serve, daemon=True).start()
        for _ in range(50):
            try:
                call("/api/status")
                break
            except Exception:
                time.sleep(0.1)

    def test_full_flow(self):
        # 1. import pliku organizatora + automatyczne wzbogacenie
        with open(os.path.join(ROOT, "samples", "Risk_Miner_dane_projekty.xlsx"), "rb") as f:
            r = call("/api/import?enrich=1", raw=f.read(), filename="Risk_Miner_dane_projekty.xlsx")
        self.assertEqual(r["created"], 22)
        job = wait_job(r["job_id"])
        self.assertEqual(job["status"], "zakończone", job.get("log"))
        st = call("/api/status")["counts"]
        self.assertEqual(st["procurements"], 22)
        self.assertGreaterEqual(st["notices"], 80)
        projects = {p["record_id"]: p for p in call("/api/projects")}
        # strategia wyszukiwania zgodna z prawdziwym API: nigdy nie polegamy na ignorowanych filtrach
        self.assertFalse(any(k in q for q in mock_bzp.H.calls for k in ("OrganizationId", "TenderId", "OrganizationNationalId")))
        self.assertFalse(any(q.get("NoticeType") == "ContractModificationNotice" for q in mock_bzp.H.calls))
        p1 = projects["RM-2026-001"]
        m3 = projects["RM-2026-003"]["metrics"]
        # Steklin: umowa 2 131 590 zł, wypłacono 2 990 000 zł; termin 2025-08-18, wykonanie 2026-05-22 (pole 5.2 ogłoszenia o wykonaniu)
        self.assertAlmostEqual(m3["cost_dev_pct"], 2990000 / 2131590 - 1, places=4)
        self.assertEqual(m3["planned_end_date"], "2025-08-18")
        self.assertEqual(m3["actual_end_date"], "2026-05-22")
        self.assertEqual(m3["delay_days"], 277)
        self.assertEqual(m3["n_changes"], 3)
        # Sanok: wykonanie przed terminem
        self.assertEqual(projects["RM-2026-011"]["metrics"]["delay_days"], -6)
        # rekord „część 1” postępowania czteroczęściowego — liczone tylko dla tej części
        m8 = projects["RM-2026-008"]["metrics"]
        self.assertEqual(m8["scope_part"], 1)
        self.assertAlmostEqual(m8["contract_value"], 1952120.53, places=2)
        self.assertAlmostEqual(m8["final_paid"], 2375309.26, places=2)
        d8 = call(f"/api/projects/{projects['RM-2026-008']['id']}")
        self.assertFalse([e for e in d8["events"] if e["status"] != "rejected" and "[część 3]" in (e["title"] or "")])
        # przyczyny zmian umów czytane z pól formularza i klasyfikowane: grunt skalny -> R02, Wody Polskie -> R04
        d11 = call(f"/api/projects/{projects['RM-2026-011']['id']}")
        self.assertTrue(any(e["method"] == "formularz BZP" and e["risk_code"] == "R02" for e in d11["events"]))
        d3 = call(f"/api/projects/{projects['RM-2026-003']['id']}")
        self.assertTrue(any(e["method"] == "formularz BZP" and e["risk_code"] == "R04" for e in d3["events"]))
        # jakość danych: numer z rekordu nie istnieje w BZP (RM-022); dwa ogłoszenia o wykonaniu tej samej umowy (RM-002)
        ins = call("/api/insights")
        msgs = {x["record_id"]: x["message"] for x in ins["data_issues"]}
        self.assertIn("nie występuje w BZP", msgs.get("RM-2026-022", ""))
        self.assertIn("kilka ogłoszeń o wykonaniu", msgs.get("RM-2026-002", ""))
        self.assertEqual(projects["RM-2026-002"]["metrics"]["n_changes"], 1)
        # wnioski z całej bazy (klasa referencyjna)
        self.assertEqual(ins["rcf"]["cost"]["n"], 22)
        self.assertGreaterEqual(ins["rcf"]["cost"]["share_over_raw"][0], 15)
        self.assertGreater(ins["rcf"]["cost"]["p80"], ins["rcf"]["cost"]["p50"])
        self.assertTrue(ins["register"]["rows"])
        self.assertEqual(ins["bases"]["rows"][0]["basis"], "art. 455 ust. 1 pkt 1")
        # biblioteka zmian umów: każda zmiana z podstawą prawną i kategorią ryzyka
        ch = call("/api/changes")
        self.assertGreaterEqual(len(ch), 35)
        self.assertTrue(all(c["basis"] for c in ch))
        self.assertTrue(any(c["risk_code"] == "R02" and "skaln" in (c["description"] or "") for c in ch))
        # KPO bez numeru BZP: dopasowanie przybliżone wymaga weryfikacji
        d2 = call(f"/api/projects/{projects['RM-2026-002']['id']}")
        bzp_links = [l for l in d2["links"] if l["to_type"] == "bzp" and l["from_type"] == "project"]
        self.assertGreaterEqual(len(bzp_links), 1, bzp_links)
        self.assertTrue(all(l["status"] == "proposed" for l in bzp_links))
        self.assertIn("NIP", " ".join(bzp_links[0]["reasons"]))
        # 2. szczegóły projektu: źródła dla każdego zdarzenia
        d1 = call(f"/api/projects/{p1['id']}")
        self.assertTrue(d1["events"])
        for e in d1["events"]:
            self.assertTrue(e["source_id"] or e["method"] == "computed", e)
            self.assertTrue(e["quote"])
        types = {n["notice_type"] for pr in d3["procurements"] for n in pr["notices"]}
        self.assertTrue({"ContractNotice", "TenderResultNotice", "ContractPerformingNotice", "AgreementUpdateNotice"} <= types)
        self.assertEqual(sum(len(c["changes"]) for pr in d3["procurements"] for c in pr["contracts"]), 3)
        # 3. dokument: aneks -> nowe zdarzenia + sprzeczność terminu
        aneks = ("ANEKS NR 2 do umowy. Strony zgodnie postanawiają, że w związku z wystąpieniem kolizji z siecią telekomunikacyjną "
                 "przedłuża się termin realizacji umowy o 30 dni. Data wykonania umowy: 2023-05-15. "
                 "Zwiększa się wynagrodzenie wykonawcy o 45 000,00 zł z tytułu robót dodatkowych.").encode("utf-8")
        r = call(f"/api/projects/{p1['id']}/documents", raw=aneks, filename="aneks_2.txt")
        self.assertEqual(r["doc_type"], "Aneks do umowy")
        self.assertGreaterEqual(r["new_events"], 2)
        self.assertTrue(any(c["key"] == "actual_end_date" for c in r["contradictions"]), r)
        # 4. decyzje eksperta
        q = call("/api/review/queue")
        self.assertTrue(q["events"])
        ev = q["events"][0]
        call(f"/api/events/{ev['id']}/decide", {"decision": "approved", "comment": "ok"})
        rej = [e for e in q["events"] if e["method"] == "rule"][0]
        call(f"/api/events/{rej['id']}/decide", {"decision": "rejected", "comment": "fałszywy alarm"})
        lk = call(f"/api/links/{bzp_links[0]['id']}/decide", {"decision": "approved"})
        self.assertEqual(lk["status"], "approved")
        hist = call("/api/history?limit=50")
        self.assertTrue(any(h["action"] == "event.rejected" and h["actor"] == "tester" for h in hist))
        # odrzucona reguła — ten sam fragment nie wraca przy ponownej analizie
        fb = call("/api/export/events")
        self.assertTrue(any(e["id"] == rej["id"] and e["status"] == "rejected" for e in fb))
        # 5. wiedza ekspercka bez zmian w kodzie
        call("/api/knowledge/risk", {"code": "R16", "name": "Ryzyko testowe", "effects": "test", "patterns": "przewiert", "mitigations": "", "clauses": "", "checks": ""})
        k = call("/api/knowledge")
        self.assertTrue(any(x["code"] == "R16" for x in k["risks"]))
        # 6. analiza nowej inwestycji + audyt projektu umowy
        a = call("/api/analyses", {"title": "Test", "text": "x"})
        with open(os.path.join(ROOT, "samples", "opis_nowej_inwestycji.txt"), encoding="utf-8") as f:
            txt = f.read()
        with open(os.path.join(ROOT, "samples", "projekt_umowy_przyklad.txt"), "rb") as f:
            call(f"/api/analyses/{a['analysis_id']}/documents", raw=f.read(), filename="projekt_umowy_przyklad.txt")
        res = call(f"/api/analyses/{a['analysis_id']}/run", {"text": txt})["result"]
        self.assertTrue(res["dane_zrodlowe"]["similar"])
        self.assertTrue(all(s["explanation"] for s in res["dane_zrodlowe"]["similar"]))
        self.assertIn("forecast", res["obliczenia"])
        self.assertTrue(res["wnioski"]["flags"])
        self.assertTrue(res["wnioski"]["recommendations"])
        self.assertTrue(any(not c["covered"] for c in res["wnioski"]["checklist"]))
        self.assertEqual(res["input"]["features"]["subsector_main"], "Kanalizacja sanitarna")
        rcf = res["obliczenia"]["reference"]["rcf"]
        self.assertEqual(res["obliczenia"]["reference"]["months_input"], 14)
        self.assertIn("p80", rcf["result"])
        self.assertIn("p80", rcf["result"]["contract"])
        self.assertTrue(rcf["cost"]["p80_ci"])
        self.assertTrue(res["obliczenia"]["register"]["rows"])
        audit = {r["id"]: r for r in res["wnioski"]["clause_audit"]["rows"]}
        self.assertTrue(res["wnioski"]["clause_audit"]["has_contract"])
        self.assertEqual(audit["K01"]["status"], "wyłączona")        # „nie podlega waloryzacji” przy umowie na 14 mies.
        self.assertTrue(audit["K01"]["legal_gap"])
        self.assertEqual(audit["K09"]["status"], "niepełna")         # kary bez łącznego limitu
        self.assertTrue(audit["K09"]["legal_gap"])
        self.assertEqual(audit["K04"]["status"], "niepełna")         # pogoda bez obiektywnego kryterium
        self.assertEqual(audit["K03"]["status"], "brak")             # warunki gruntowe — brak, a w bazie R02 wystąpiło
        self.assertEqual(audit["K10"]["status"], "jest")
        self.assertIn("wyłącza", audit["K01"]["evidence"]["quote"] + audit["K01"]["note"])
        self.assertTrue(any(f["basis"] == "audyt klauzul" for f in res["wnioski"]["flags"]))
        # termin z umowy o dofinansowanie i start przetargu odczytane z opisu; ryzyko niezdążenia
        fd = res["obliczenia"]["reference"]["funding"]
        self.assertEqual(fd["deadline"], "2028-06-30")
        self.assertEqual(fd["start"], "2027-01-01")
        self.assertGreater(fd["p_miss"], 0.5)                       # „na papierze” zdąży, w rzeczywistości raczej nie
        self.assertLess(fd["naive_finish"], fd["deadline"])
        self.assertTrue(any("dofinansowania" in f["name"] for f in res["wnioski"]["flags"]))
        csv_txt = call(f"/api/analyses/{a['analysis_id']}/export?format=csv")
        self.assertIn("podobny_projekt", csv_txt)
        # 7. eksport i raport z testu
        rep = call("/api/report/links")
        self.assertGreater(rep["summary"]["poprawne"], 0)
        bundle = call(f"/api/projects/{p1['id']}/export")
        self.assertTrue(bundle["sources"])
        self.assertTrue(all(s.get("fetched_at") for s in bundle["sources"]))
        # 8. ponowne uruchomienie pobierania nie dubluje rekordów
        before = call("/api/status")["counts"]
        wait_job(call(f"/api/projects/{p1['id']}/enrich", {})["job_id"])
        after = call("/api/status")["counts"]
        self.assertEqual(before["notices"], after["notices"])
        # 9. monitoring
        m = call(f"/api/projects/{projects['RM-2026-002']['id']}/check", {})
        self.assertEqual(call("/api/status")["counts"]["notices"], after["notices"])
        self.assertIn("new_notices", m)
        print("\nE2E OK:", json.dumps(after, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
