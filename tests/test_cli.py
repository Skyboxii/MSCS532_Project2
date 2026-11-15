"""The command-line shell: commands, quoting, and error messages."""

import io
import os
import unittest

from cli import InventoryShell

ROOT = os.path.join(os.path.dirname(__file__), os.pardir)


class TestShell(unittest.TestCase):
    def setUp(self):
        self.out = io.StringIO()
        self.shell = InventoryShell(stdout=self.out)
        self.run_cmd(f'load "{os.path.join(ROOT, "data", "products.csv")}"')

    def run_cmd(self, line):
        self.out.seek(0)
        self.out.truncate()
        self.shell.onecmd(line)
        return self.out.getvalue()

    def test_load_and_value(self):
        self.assertIn("25 products, total value $29,446.70", self.run_cmd("value"))

    def test_quoted_names(self):
        out = self.run_cmd('add USB-900 "USB Flash Drive 64GB" Electronics 14.99 30 10')
        self.assertIn("USB Flash Drive 64GB", out)
        self.assertEqual(self.shell.inv.get("USB-900").reorder_point, 10)
        self.assertIn("USB-900", self.run_cmd('find "usb f"'))

    def test_updates(self):
        self.assertIn("110", self.run_cmd("sell PEN-300 30"))
        self.assertIn("$29.95", self.run_cmd("price LMP-420 29.95"))
        self.run_cmd("move MUG-600 Apparel")
        self.assertIn("MUG-600", self.run_cmd("category Apparel"))
        self.assertIn("removed CAB-440", self.run_cmd("remove CAB-440"))
        self.assertIn("all indexes consistent", self.run_cmd("verify"))

    def test_errors_are_one_line_messages(self):
        cases = {
            "sell CHR-400 5": "Error: insufficient stock for CHR-400: have 0, need 5",
            "get NOPE": "Error: SKU 'NOPE' not found",
            "price LAP-100 abc": "Error: price must be a number",
            "add LAP-100 Dup Electronics 1.00 1": "Error: SKU 'LAP-100' already exists",
            "add ONLY-TWO args": "Usage: add",
            "sell PEN-300 two": "Usage: sell SKU QTY",
            "range 50 10": "Error: low (50.00) is greater than high (10.00)",
            'find "unclosed': "Error: No closing quotation",
            "load no/such/file.csv": "Error: [Errno 2]",
            "frobnicate": "Unknown command: frobnicate",
            "movements data/movements.csv sometimes": "Usage: movements PATH [all]",
        }
        for line, expected in cases.items():
            with self.subTest(command=line):
                out = self.run_cmd(line)
                self.assertIn(expected, out)
                self.assertNotIn("Traceback", out)
        self.assertIn("25 products, total value $29,446.70", self.run_cmd("value"))   # unchanged

    def test_movements_modes(self):
        path = os.path.join(ROOT, "data", "movements.csv")
        out = self.run_cmd(f'movements "{path}" all')
        self.assertIn("batch rolled back", out)
        self.assertIn("25 products, total value $29,446.70", self.run_cmd("value"))
        out = self.run_cmd(f'movements "{path}"')
        self.assertIn("7 succeeded, 2 failed", out)
        self.assertIn("line 7: SKU 'XYZ-999' not found", out)

    def test_lowstock_order(self):
        out = self.run_cmd("lowstock").splitlines()
        skus = [line.split()[0] for line in out[1:]]
        # quantity - reorder point: -7, -4, -3, -2, and 0 (CAB-440 is exactly AT its reorder point)
        self.assertEqual(skus, ["MOU-200", "BTL-610", "TAP-360", "CHR-400", "CAB-440"])

    def test_quit_and_empty_line(self):
        self.assertTrue(self.shell.onecmd("quit"))
        self.assertFalse(self.shell.onecmd(""))


if __name__ == "__main__":
    unittest.main()
