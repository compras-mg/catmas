import unittest

from scripts.build_history import (
    REQUEST_STATUS_LABELS,
    REQUEST_TYPE_LABELS,
    STAGE_LABELS,
    format_unit,
    integer,
)


class HistoryTransformHelpersTest(unittest.TestCase):
    def test_integer_preserves_nulls(self):
        self.assertIsNone(integer(""))
        self.assertIsNone(integer(None))
        self.assertEqual(integer("0012"), 12)

    def test_unit_fallback_is_auditable_without_domain_tables(self):
        label, details = format_unit(
            {
                "id": "10025",
                "codigo": "2501",
                "quantidade": "12",
                "entunidademedida_id": "7",
                "entembalagem_id": "3",
                "observacoes": "",
            }
        )
        self.assertEqual(label, "Unidade 2501")
        self.assertIn("Quantidade: 12", details)
        self.assertIn("Unidade de medida ID: 7", details)
        self.assertIn("Embalagem ID: 3", details)

    def test_every_known_request_domain_has_a_label(self):
        self.assertEqual(set(REQUEST_TYPE_LABELS), set(range(1, 11)))
        self.assertEqual(set(REQUEST_STATUS_LABELS), set(range(1, 7)))
        self.assertEqual(STAGE_LABELS, {1: "Antes", 2: "Solicitado", 3: "Analisado"})


if __name__ == "__main__":
    unittest.main()
