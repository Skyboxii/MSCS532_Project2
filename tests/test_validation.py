"""Edge cases: invalid input must raise a clear InventoryError and change nothing."""

import unittest
from decimal import Decimal

from inventory import (DuplicateSKUError, InsufficientStockError, InventoryError, InventoryManager,
                       Product, ProductNotFoundError, ValidationError)


def make(**overrides):
    fields = dict(sku="SKU-1", name="Widget", category="Parts", price="9.99", quantity=5, reorder_point=2)
    fields.update(overrides)
    return Product(**fields)


class TestProductValidation(unittest.TestCase):
    def test_prices_are_normalized(self):
        for raw in ("9.99", 9.99, Decimal("9.99"), " 9.99 ", "9.990"):
            self.assertEqual(make(price=raw).price, Decimal("9.99"))
        self.assertEqual(str(make(price=10).price), "10.00")

    def test_bad_prices(self):
        for raw in ("abc", "", None, "NaN", "Infinity", "-0.01", "1.005", True, [1]):
            with self.subTest(price=raw), self.assertRaises(ValidationError):
                make(price=raw)

    def test_bad_counts(self):
        for field in ("quantity", "reorder_point"):
            for raw in (-1, 1.5, "5", None, True):
                with self.subTest(field=field, value=raw), self.assertRaises(ValidationError):
                    make(**{field: raw})

    def test_bad_text(self):
        for field in ("sku", "name", "category"):
            for raw in ("", "   ", None, 42):
                with self.subTest(field=field, value=raw), self.assertRaises(ValidationError):
                    make(**{field: raw})
        self.assertEqual(make(sku="  SKU-9 ").sku, "SKU-9")

    def test_errors_keep_builtin_types(self):
        # Phase 1 callers caught KeyError / ValueError; that must still work.
        self.assertTrue(issubclass(ValidationError, ValueError))
        self.assertTrue(issubclass(ProductNotFoundError, KeyError))
        self.assertTrue(issubclass(DuplicateSKUError, KeyError))
        self.assertTrue(issubclass(InsufficientStockError, ValueError))
        self.assertEqual(str(ProductNotFoundError("X")), "SKU 'X' not found")   # no extra quotes


class TestManagerErrors(unittest.TestCase):
    def setUp(self):
        self.inv = InventoryManager(seed=1)
        self.inv.add_product(make())

    def assert_unchanged(self):
        p = self.inv.get("SKU-1")
        self.assertEqual((p.price, p.quantity, p.category), (Decimal("9.99"), 5, "Parts"))
        self.assertEqual(self.inv.total_value, Decimal("49.95"))
        self.assertEqual(len(self.inv), 1)

    def test_unknown_sku(self):
        for call in (lambda: self.inv.get("NOPE"),
                     lambda: self.inv.remove_product("NOPE"),
                     lambda: self.inv.adjust_quantity("NOPE", 1),
                     lambda: self.inv.update_price("NOPE", 1),
                     lambda: self.inv.change_category("NOPE", "X"),
                     lambda: self.inv.set_reorder_point("NOPE", 1),
                     lambda: self.inv.get(None)):
            with self.assertRaises(ProductNotFoundError):
                call()
        self.assert_unchanged()

    def test_duplicate_and_wrong_type(self):
        with self.assertRaises(DuplicateSKUError):
            self.inv.add_product(make(name="Other"))
        with self.assertRaises(ValidationError):
            self.inv.add_product({"sku": "SKU-2"})
        self.assert_unchanged()

    def test_invalid_updates_change_nothing(self):
        bad = [
            (InsufficientStockError, lambda: self.inv.adjust_quantity("SKU-1", -6)),
            (ValidationError, lambda: self.inv.adjust_quantity("SKU-1", 1.5)),
            (ValidationError, lambda: self.inv.adjust_quantity("SKU-1", True)),
            (ValidationError, lambda: self.inv.update_price("SKU-1", "free")),
            (ValidationError, lambda: self.inv.update_price("SKU-1", "-5")),
            (ValidationError, lambda: self.inv.change_category("SKU-1", "  ")),
            (ValidationError, lambda: self.inv.set_reorder_point("SKU-1", -1)),
        ]
        for exc, call in bad:
            with self.subTest(exc=exc.__name__), self.assertRaises(exc):
                call()
            self.assert_unchanged()

    def test_query_validation(self):
        with self.assertRaises(ValidationError):
            self.inv.products_in_price_range(50, 10)
        with self.assertRaises(ValidationError):
            self.inv.products_in_price_range("cheap", 10)
        with self.assertRaises(ValidationError):
            self.inv.cheapest(-1)
        self.assertEqual(self.inv.products_in_price_range(0, 1), [])
        self.assertEqual(self.inv.cheapest(0), [])

    def test_sell_exact_stock_to_zero(self):
        self.assertEqual(self.inv.adjust_quantity("SKU-1", -5).quantity, 0)
        self.assertEqual(self.inv.total_value, Decimal("0"))

    def test_empty_inventory_queries(self):
        inv = InventoryManager()
        self.assertIsNone(inv.most_urgent())
        self.assertEqual(inv.low_stock(), [])
        self.assertEqual(inv.cheapest(3), [])
        self.assertEqual(inv.categories(), [])
        self.assertEqual(inv.products_in_category("Anything"), [])
        self.assertEqual(inv.total_value, Decimal("0"))

    def test_one_handler_catches_everything(self):
        for call in (lambda: self.inv.get("NOPE"), lambda: self.inv.adjust_quantity("SKU-1", -99),
                     lambda: self.inv.update_price("SKU-1", "NaN")):
            with self.assertRaises(InventoryError):
                call()


if __name__ == "__main__":
    unittest.main()
