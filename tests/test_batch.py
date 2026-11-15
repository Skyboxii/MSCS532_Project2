"""CSV loading and batch stock movements."""

import os
import tempfile
import unittest
from decimal import Decimal

from inventory import (InventoryManager, StockMovement, ValidationError, apply_movements,
                       import_products, read_movements, read_products)

DATA = os.path.join(os.path.dirname(__file__), os.pardir, "data")


def loaded():
    inv = InventoryManager(seed=4)
    result = import_products(inv, os.path.join(DATA, "products.csv"))
    assert result.ok, result.failed
    return inv


def write_temp(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    f.write(text)
    f.close()
    return f.name


class TestReaders(unittest.TestCase):
    def test_sample_catalog_loads(self):
        inv = loaded()
        self.assertEqual(len(inv), 25)
        self.assertEqual(inv.categories(), ["Apparel", "Electronics", "Furniture", "Gifts", "Office"])
        self.assertEqual(inv.verify_integrity(), [])

    def test_bad_product_rows_are_reported_by_line(self):
        products, failures = read_products(os.path.join(DATA, "products_with_errors.csv"))
        self.assertEqual([p.sku for p in products], ["GLU-700", "PEN-300", "SCI-740"])
        self.assertEqual([line for line, _ in failures], [3, 4, 5, 6])
        self.assertIn("sku is required", failures[0][1])
        self.assertIn("fractions of a cent", failures[3][1])

    def test_import_reports_duplicates(self):
        inv = loaded()
        result = import_products(inv, os.path.join(DATA, "products_with_errors.csv"))
        self.assertEqual(result.succeeded, ["GLU-700", "SCI-740"])
        self.assertEqual(len(result.failed), 5)
        self.assertIn("already exists", result.failed[-1][1])
        self.assertEqual(len(inv), 27)

    def test_movement_parsing(self):
        movements, failures = read_movements(os.path.join(DATA, "movements.csv"))
        self.assertEqual(len(movements), 9)
        self.assertEqual([line for line, _ in failures], [9, 11, 13])
        self.assertEqual(movements[0], StockMovement("MOU-200", 40, "PO-1042 received", 2))

    def test_missing_columns_and_bom(self):
        path = write_temp("sku,name,price\nA,B,1\n")
        try:
            with self.assertRaises(ValidationError):
                read_products(path)
        finally:
            os.remove(path)
        path = write_temp("﻿sku,change\nA,1\n")          # Excel-style byte-order mark
        try:
            movements, failures = read_movements(path)
            self.assertEqual((movements[0].sku, failures), ("A", []))
        finally:
            os.remove(path)


class TestApplyMovements(unittest.TestCase):
    def setUp(self):
        self.movements, _ = read_movements(os.path.join(DATA, "movements.csv"))

    def test_reject_and_continue(self):
        inv = loaded()
        result = apply_movements(inv, self.movements)
        self.assertEqual(len(result.succeeded), 7)
        self.assertEqual([line for line, _ in result.failed], [7, 8])     # unknown SKU, oversell
        self.assertEqual(inv.get("MOU-200").quantity, 43)
        self.assertEqual(inv.get("TAP-360").quantity, 12)                  # rejected sale left it alone
        self.assertFalse(result.rolled_back)
        self.assertEqual(inv.verify_integrity(), [])

    def test_all_or_nothing_rolls_back_everything(self):
        inv = loaded()
        before = {s: inv.get(s).quantity for s in ("MOU-200", "NBK-310", "PEN-300", "CHR-400")}
        value = inv.total_value
        result = apply_movements(inv, self.movements, all_or_nothing=True)
        self.assertTrue(result.rolled_back)
        self.assertEqual(result.succeeded, [])
        self.assertEqual(result.failed[0][0], 7)                          # stopped at the first bad row
        self.assertEqual({s: inv.get(s).quantity for s in before}, before)
        self.assertEqual(inv.total_value, value)
        self.assertEqual(inv.verify_integrity(), [])

    def test_all_or_nothing_commits_clean_batch(self):
        inv = loaded()
        good = [m for m in self.movements if m.sku not in ("XYZ-999", "TAP-360")]
        result = apply_movements(inv, good, all_or_nothing=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.summary(), "7 succeeded, 0 failed")
        self.assertEqual(inv.get("NBK-310").quantity, 35)
        self.assertEqual(inv.total_value, sum(
            (p.price * p.quantity for c in inv.categories() for p in inv.products_in_category(c)),
            Decimal("0")))

    def test_low_stock_after_batch(self):
        inv = loaded()
        apply_movements(inv, self.movements)
        low = [p.sku for p in inv.low_stock()]
        self.assertIn("NBK-310", low)          # 35 left, reorder at 40
        self.assertNotIn("MOU-200", low)       # restocked to 43
        self.assertNotIn("CHR-400", low)       # restocked to 6


if __name__ == "__main__":
    unittest.main()
