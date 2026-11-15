"""Name prefix search and rename."""

import random
import string
import unittest

from inventory import InventoryManager, Product, ValidationError


def catalog():
    inv = InventoryManager(seed=3)
    for sku, name in (("D1", "Desk Chair"), ("D2", "desk lamp"), ("D3", "Desktop PC"),
                      ("N1", "Notebook"), ("S1", "Straße Map"), ("D4", "Desk Chair")):
        inv.add_product(Product(sku, name, "Misc", "10.00", 5))
    return inv


class TestNameSearch(unittest.TestCase):
    def test_prefix_is_case_insensitive_and_ordered(self):
        inv = catalog()
        self.assertEqual([p.sku for p in inv.search_by_name("DESK")], ["D1", "D4", "D2", "D3"])
        self.assertEqual([p.sku for p in inv.search_by_name("desk ")], ["D1", "D4", "D2", "D3"])  # stripped
        self.assertEqual([p.sku for p in inv.search_by_name("desk c")], ["D1", "D4"])
        self.assertEqual([p.sku for p in inv.search_by_name("Desktop")], ["D3"])

    def test_no_match_and_boundaries(self):
        inv = catalog()
        self.assertEqual(inv.search_by_name("zebra"), [])
        self.assertEqual(inv.search_by_name("Deskz"), [])
        self.assertEqual([p.sku for p in inv.search_by_name("n")], ["N1"])

    def test_unicode_casefold(self):
        self.assertEqual([p.sku for p in catalog().search_by_name("STRASSE")], ["S1"])

    def test_limit(self):
        inv = catalog()
        self.assertEqual(len(inv.search_by_name("desk", limit=2)), 2)
        self.assertEqual(inv.search_by_name("desk", limit=0), [])
        with self.assertRaises(ValidationError):
            inv.search_by_name("desk", limit=-1)

    def test_invalid_prefix(self):
        for bad in ("", "   ", None, 5):
            with self.subTest(prefix=bad), self.assertRaises(ValidationError):
                catalog().search_by_name(bad)

    def test_rename_moves_product_in_index(self):
        inv = catalog()
        inv.rename_product("N1", "Desk Organizer")
        self.assertEqual(inv.search_by_name("note"), [])
        self.assertIn("N1", [p.sku for p in inv.search_by_name("desk o")])
        self.assertIs(inv.rename_product("N1", " Desk Organizer "), inv.get("N1"))   # no-op after strip
        with self.assertRaises(ValidationError):
            inv.rename_product("N1", "")
        self.assertEqual(inv.verify_integrity(), [])

    def test_removed_products_disappear(self):
        inv = catalog()
        inv.remove_product("D2")
        self.assertNotIn("D2", [p.sku for p in inv.search_by_name("desk")])

    def test_random_against_brute_force(self):
        rng = random.Random(9)
        inv = InventoryManager(seed=9)
        names = {}
        for i in range(500):
            name = "".join(rng.choice("abcAB ") for _ in range(rng.randint(1, 6))).strip() or "x"
            sku = f"P{i:04}"
            inv.add_product(Product(sku, name, "Misc", "1.00", 1))
            names[sku] = name
        for i in range(0, 500, 3):                       # rename a third of them
            names[f"P{i:04}"] = rng.choice(string.ascii_letters) + names[f"P{i:04}"]
            inv.rename_product(f"P{i:04}", names[f"P{i:04}"])
        for prefix in ("a", "AB", "ba", "c", "aaa", "B", "Ab a"):
            expected = sorted((n.casefold(), s) for s, n in names.items()
                              if n.casefold().startswith(prefix.casefold()))
            got = [(p.name.casefold(), p.sku) for p in inv.search_by_name(prefix)]
            self.assertEqual(got, expected, prefix)
        self.assertEqual(inv.verify_integrity(), [])


if __name__ == "__main__":
    unittest.main()
