import unittest

from scripts.transform import has_long_specification


class LongSpecificationClassificationTest(unittest.TestCase):
    def test_recognizes_standard_reference_with_accents(self):
        value = "Este item possui especificação longa anexada no campo arquivos."
        self.assertEqual(has_long_specification(value), "true")

    def test_recognizes_plural_reference(self):
        value = "Consultar especificações longas no Portal de Compras."
        self.assertEqual(has_long_specification(value), "true")

    def test_recognizes_recurring_spelling_variants(self):
        values = [
            "Este item possui especificao longa anexada ao campo arquivos.",
            "Este item possui espeificacao longa anexada ao campo arquivos.",
            "Este item possui esepcificacao longa anexada ao campo arquivos.",
            "Este item possui arquivo de longa anexado ao campo arquivos.",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(has_long_specification(value), "true")

    def test_does_not_confuse_long_lifetime_with_long_specification(self):
        value = "Equipamento com tubo de longa vida útil e arquivo digital."
        self.assertEqual(has_long_specification(value), "false")

    def test_empty_value_is_not_a_long_specification(self):
        self.assertEqual(has_long_specification(None), "false")


if __name__ == "__main__":
    unittest.main()
