"""Testy jednostkowe kluczowych elementów: parser formularza BZP, kwantyle ważone, audyt klauzul.

Uruchomienie:  python3 tests/test_units.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from riskminer import bzp, clauses, forecast  # noqa: E402


class FormParser(unittest.TestCase):
    TEXT = """SEKCJA V ZMIANY UMOWY
Część 2
5.4.2.) Numer zmiany: 1
5.4.3.) Podstawa prawna zmiany: art. 455 ust. 1 pkt 4 ustawy
5.4.4.) Przyczyny dokonania zmiany: Natrafiono na grunt skalny kategorii V na odcinku 300 m.
5.4.6.) Wartość zmiany: 120 500,00 PLN
5.2.) Termin wykonania umowy: 2026-05-22
2026-06-03 Biuletyn Zamówień Publicznych Ogłoszenie nr 2026/BZP 00276065/01 z dnia 2026-06-03
"""

    def test_fields_parts_and_footer(self):
        fields = bzp.parse_form(self.TEXT)
        by = {f["num"].rstrip(".)").rstrip("."): f for f in fields}
        self.assertEqual(by["5.4.3"]["part"], 2)
        self.assertEqual(by["5.2"]["value"], "2026-05-22")       # stopka nie dokleja się do ostatniego pola
        self.assertNotIn("Biuletyn", by["5.2"]["value"])

    def test_legal_basis(self):
        key, meaning = bzp.basis_meaning("art. 455 ust. 1 pkt 4 ustawy")
        self.assertEqual(key, "art. 455 ust. 1 pkt 4")
        self.assertIn("nieprzewidywalne", meaning)

    def test_masking(self):
        self.assertNotIn("jan@gmina.pl", bzp.mask_personal("kontakt: jan@gmina.pl, tel. 600 100 200"))


class LiveHtmlFormat(unittest.TestCase):
    """BZP na żywo podaje pola jako <h3>etykieta: </h3> wartość — wartość nie może zlać się z kolejną etykietą."""
    HTML = ('<div><h3 class="mb-0">5.1.) Data zmiany umowy: <span class="normal">2024-10-09</span></h3>'
            '<h3 class="mb-0">5.2.) Podstawa prawna zmiany umowy/umowy ramowej: </h3>art. 455 ust. 1 pkt 3 ustawy'
            '<h3 class="mb-0">5.3.) Przyczyny dokonania zmian umowy/umowy ramowej: </h3>    W związku ze zwiększeniem zakresu robót'
            '<h3 class="mb-0">5.4.) Krótki opis zmiany umowy/umowy ramowej: </h3>    W § 1 ust. 2 dodaje się pkt 3)'
            '<h3 class="mb-0">5.5.1.) Wartość zmiany: <span class="normal">758084,56</span></h3></div>')

    def test_change_fields_from_h3_markup(self):
        from riskminer.util import strip_html
        st = bzp.extract_structured("AgreementUpdateNotice", strip_html(self.HTML))
        self.assertEqual(len(st["changes"]), 1)
        c = st["changes"][0]
        self.assertEqual(c["legal_basis"], "art. 455 ust. 1 pkt 3")
        self.assertEqual(c["value"], 758084.56)
        self.assertEqual(c["date"], "2024-10-09")
        self.assertTrue(c["reason"].startswith("W związku ze zwiększeniem"))
        self.assertNotIn("Przyczyny", c.get("basis") or "")


class InvestmentDescription(unittest.TestCase):
    """Opis nowej inwestycji pisany przez użytkownika: kwoty skrótem i okres realizacji obok gwarancji."""

    def test_short_amounts(self):
        from riskminer.analysis import detect_value
        self.assertEqual(detect_value("Wartość szacunkowa 2,4 mln zł brutto."), 2_400_000)
        self.assertEqual(detect_value("budżet 950 tys. zł"), 950_000)
        self.assertEqual(detect_value("Koszt ok. 12 500 000 zł."), 12_500_000)
        self.assertEqual(detect_value("oczyszczalnia na 2 tys. RLM, koszt 8 mln zł"), 8_000_000)

    def test_months_ignore_warranty(self):
        self.assertEqual(clauses.detect_months("Realizacja 10 miesięcy."), 10)
        self.assertEqual(clauses.detect_months("Wykonawca udziela gwarancji na okres 60 miesięcy od dnia odbioru. "
                                               "Termin realizacji 14 miesięcy od dnia zawarcia umowy."), 14)
        self.assertIsNone(clauses.detect_months("Rękojmia za wady wynosi 60 miesięcy od dnia odbioru."))


class Quantiles(unittest.TestCase):
    def test_equal_weights_median(self):
        self.assertAlmostEqual(forecast.wquantile([(1, 1), (2, 1), (3, 1)], 0.5), 2)

    def test_weights_shift_quantile(self):
        lo = forecast.wquantile([(0.0, 1), (1.0, 1)], 0.5)
        hi = forecast.wquantile([(0.0, 1), (1.0, 9)], 0.5)
        self.assertGreater(hi, lo)

    def test_n_eff(self):
        self.assertAlmostEqual(forecast.n_eff([1, 1, 1, 1]), 4)
        self.assertLess(forecast.n_eff([1, 0.01, 0.01]), 1.1)


class ClauseAudit(unittest.TestCase):
    def pages(self, text):
        return [{"page": 1, "doc": "ppu.txt", "text": text}]

    def test_waloryzacja_excluded_is_legal_gap(self):
        t = "§ 1. Umowa. § 2. Termin realizacji: 14 miesięcy od dnia zawarcia umowy. § 3. Wynagrodzenie nie podlega waloryzacji. Zamawiający i Wykonawca."
        a = {r["id"]: r for r in clauses.audit(self.pages(t))["rows"]}
        self.assertEqual(a["K01"]["status"], "wyłączona")
        self.assertTrue(a["K01"]["legal_gap"])

    def test_short_contract_no_mandatory_indexation(self):
        t = "§ 1. Umowa. § 2. Termin realizacji: 4 miesiące od dnia zawarcia umowy. § 3. Zamawiający i Wykonawca."
        a = {r["id"]: r for r in clauses.audit(self.pages(t), months=4)["rows"]}
        self.assertFalse(a["K01"]["required"])

    def test_penalties_with_limit_ok(self):
        t = ("§ 1. Umowa. § 2. Zamawiający i Wykonawca. § 6. Kary umowne: 0,2% za dzień zwłoki. "
             "Łączna maksymalna wysokość kar umownych nie może przekroczyć 20% wynagrodzenia.")
        a = {r["id"]: r for r in clauses.audit(self.pages(t))["rows"]}
        self.assertEqual(a["K09"]["status"], "jest")
        self.assertFalse(a["K09"]["legal_gap"])

    def test_no_contract_text(self):
        a = clauses.audit(self.pages("Gmina planuje budowę sieci kanalizacji, termin realizacji 14 miesięcy."))
        self.assertFalse(a["has_contract"])
        self.assertTrue(all(r["status"] == "nie oceniono" for r in a["rows"]))
        self.assertEqual(a["months"], 14)

    def test_quote_positions_survive_folding(self):
        t = "§ 1. „Umowa” … § 2. Zamawiający i Wykonawca … § 3. Wynagrodzenie podlega waloryzacji wg wskaźnika GUS."
        self.assertEqual(len(clauses.fold_keep(t)), len(t))
        a = {r["id"]: r for r in clauses.audit(self.pages(t), months=14)["rows"]}
        self.assertIn("waloryzacji", a["K01"]["evidence"]["quote"])


class Voivodeship(unittest.TestCase):
    def test_inflected_forms(self):
        from riskminer.analysis import detect_voivodeship as d
        self.assertEqual(d("Inwestycja w województwie wielkopolskim."), "wielkopolskie")
        self.assertEqual(d("gmina z województwa zachodniopomorskiego"), "zachodniopomorskie")
        self.assertEqual(d("woj. kujawsko-pomorskie"), "kujawsko-pomorskie")
        self.assertEqual(d("na terenie województwa pomorskiego"), "pomorskie")
        self.assertEqual(d("województwo dolnośląskie"), "dolnośląskie")
        self.assertEqual(d("Łódzkie, powiat zgierski"), "łódzkie")
        self.assertIsNone(d("droga wojewódzka nr 196"))


class SecurityAndUrlValidation(unittest.TestCase):
    def test_blocks_non_http_and_local_urls(self):
        from riskminer.pipeline import validate_public_url
        for bad in ("file:///etc/passwd", "ftp://example.com/a.pdf", "http://localhost:8080/", "http://127.0.0.1/secret", "http://169.254.169.254/latest/meta-data/"):
            with self.assertRaises(ValueError, msg=bad):
                validate_public_url(bad)

    def test_bzp_auto_fallback_when_live_fails(self):
        from riskminer import config
        cfg = config.get()["bzp"]
        old = (cfg["base_url"], list(cfg["fallback_urls"]), cfg["cache"], cfg.get("timeout_s"))
        try:
            bzp._live_down_until = 0.0
            cfg["base_url"] = "http://127.0.0.1:1/unreachable"
            cfg["fallback_urls"] = []
            cfg["cache"] = False
            cfg["timeout_s"] = 1
            items, url, _ = bzp.search("ContractNotice", NoticeNumber="2023/BZP 00271948/01")
            self.assertEqual(len(items), 1)
            self.assertIn("tryb awaryjny", url)
            self.assertTrue(bzp.fallback_active())
        finally:
            cfg["base_url"], cfg["fallback_urls"], cfg["cache"], cfg["timeout_s"] = old
            bzp._live_down_until = 0.0


if __name__ == "__main__":
    unittest.main(verbosity=2)
