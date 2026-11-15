"""
Interactive command-line interface for the inventory proof of concept.

    python cli.py                          # empty inventory
    python cli.py data/products.csv        # start with the sample catalog

Type `help` for the command list.  Arguments with spaces go in quotes:
    add USB-900 "USB Flash Drive 64GB" Electronics 14.99 30 10
"""

import cmd
import shlex
import sys

from inventory import (InventoryError, InventoryManager, Product, apply_movements, import_products,
                       read_movements)

COLUMNS = "{:<9} {:<22} {:<12} {:>9} {:>5} {:>8}"


class UsageError(Exception):
    """Wrong number or format of command arguments."""


def command(usage, nargs):
    """
    Decorator for do_* methods: split the argument line with shlex (so quoted
    names work), check the argument count, and turn every expected error into
    a one-line message instead of a traceback.  nargs is an int or a
    (min, max) tuple.
    """
    lo, hi = (nargs, nargs) if isinstance(nargs, int) else nargs

    def wrap(method):
        def run(self, line):
            try:
                args = shlex.split(line)
                if not lo <= len(args) <= hi:
                    raise UsageError
                method(self, *args)
            except UsageError:
                self.say(f"Usage: {usage}")
            except ValueError as e:                     # shlex quoting or int() parsing
                if isinstance(e, InventoryError):
                    self.say(f"Error: {e}")
                else:
                    self.say(f"Error: {e}. Usage: {usage}")
            except (InventoryError, OSError) as e:
                self.say(f"Error: {e}")
        run.__doc__ = f"{usage}\n        {method.__doc__}"
        return run
    return wrap


def whole(text, name):
    try:
        return int(text)
    except ValueError:
        raise UsageError from None


class InventoryShell(cmd.Cmd):
    intro = "Inventory proof of concept. Type help or ? to list commands.\n"
    prompt = "inventory> "

    def __init__(self, inventory=None, stdout=None):
        super().__init__(stdout=stdout)
        self.inv = inventory or InventoryManager()

    # -- output helpers -------------------------------------------------------

    def say(self, text=""):
        self.stdout.write(text + "\n")

    def table(self, products, empty="(none)"):
        if not products:
            self.say(f"  {empty}")
            return
        self.say("  " + COLUMNS.format("SKU", "Name", "Category", "Price", "Qty", "Reorder"))
        for p in products:
            self.say("  " + COLUMNS.format(p.sku, p.name[:22], p.category[:12], f"${p.price}",
                                           p.quantity, p.reorder_point))

    def batch_report(self, result):
        self.say(f"  {result.summary()}")
        for line, message in result.failed:
            self.say(f"    {'line ' + str(line) if line else 'row'}: {message}")

    # -- loading --------------------------------------------------------------

    @command("load PATH", 1)
    def do_load(self, path):
        """Import products from a CSV file (bad rows are reported, good rows are added)."""
        self.batch_report(import_products(self.inv, path))

    @command("movements PATH [all]", (1, 2))
    def do_movements(self, path, mode="each"):
        """Apply stock movements from a CSV file. Add `all` to roll back the whole file on any error."""
        if mode not in ("each", "all"):
            raise UsageError
        movements, parse_failures = read_movements(path)
        for line, message in parse_failures:
            self.say(f"    line {line}: {message} (not applied)")
        self.batch_report(apply_movements(self.inv, movements, all_or_nothing=(mode == "all")))

    # -- single-product changes -------------------------------------------------

    @command('add SKU "NAME" CATEGORY PRICE QTY [REORDER]', (5, 6))
    def do_add(self, sku, name, category, price, qty, reorder="0"):
        """Add a product."""
        product = Product(sku, name, category, price, whole(qty, "QTY"), whole(reorder, "REORDER"))
        self.inv.add_product(product)
        self.table([product])

    @command("remove SKU", 1)
    def do_remove(self, sku):
        """Delete a product."""
        self.say(f"  removed {self.inv.remove_product(sku).sku}")

    @command("receive SKU QTY", 2)
    def do_receive(self, sku, qty):
        """Add stock (e.g. a purchase order arrived)."""
        self.table([self.inv.adjust_quantity(sku, whole(qty, "QTY"))])

    @command("sell SKU QTY", 2)
    def do_sell(self, sku, qty):
        """Remove stock (a sale); rejected if there is not enough on hand."""
        self.table([self.inv.adjust_quantity(sku, -whole(qty, "QTY"))])

    @command("price SKU NEW_PRICE", 2)
    def do_price(self, sku, price):
        """Change a product's price."""
        self.table([self.inv.update_price(sku, price)])

    @command("move SKU CATEGORY", 2)
    def do_move(self, sku, category):
        """Move a product to another category."""
        self.table([self.inv.change_category(sku, category)])

    @command('rename SKU "NEW NAME"', 2)
    def do_rename(self, sku, name):
        """Rename a product."""
        self.table([self.inv.rename_product(sku, name)])

    @command("reorder SKU POINT", 2)
    def do_reorder(self, sku, point):
        """Set the stock level at which a product should be reordered."""
        self.table([self.inv.set_reorder_point(sku, whole(point, "POINT"))])

    # -- queries ----------------------------------------------------------------

    @command("get SKU", 1)
    def do_get(self, sku):
        """Show one product (hash table lookup)."""
        self.table([self.inv.get(sku)])

    @command("find PREFIX", 1)
    def do_find(self, prefix):
        """Products whose name starts with PREFIX, case-insensitive (name skip list)."""
        self.table(self.inv.search_by_name(prefix), empty="no names match")

    @command("range LOW HIGH", 2)
    def do_range(self, low, high):
        """Products priced from LOW to HIGH, cheapest first (price skip list)."""
        self.table(self.inv.products_in_price_range(low, high), empty="nothing in that range")

    @command("cheapest [K]", (0, 1))
    def do_cheapest(self, k="5"):
        """The K lowest-priced products (default 5)."""
        self.table(self.inv.cheapest(whole(k, "K")))

    @command("category NAME", 1)
    def do_category(self, name):
        """Products in one category (category hash table)."""
        self.table(self.inv.products_in_category(name), empty=f"no products in {name!r}")

    @command("categories", 0)
    def do_categories(self):
        """List categories with product counts."""
        for c in self.inv.categories():
            self.say(f"  {c:<14} {len(self.inv.products_in_category(c)):>3} products")

    @command("lowstock", 0)
    def do_lowstock(self):
        """Products at or below their reorder point, most urgent first (indexed heap)."""
        self.table(self.inv.low_stock(), empty="nothing needs reordering")

    @command("value", 0)
    def do_value(self):
        """Total inventory value and product count."""
        self.say(f"  {len(self.inv)} products, total value ${self.inv.total_value:,.2f}")

    @command("verify", 0)
    def do_verify(self):
        """Cross-check every index against the product table."""
        problems = self.inv.verify_integrity()
        self.say("  all indexes consistent" if not problems else "\n".join("  " + p for p in problems))

    # -- shell plumbing ---------------------------------------------------------

    def do_quit(self, line):
        """Exit the shell."""
        return True

    do_exit = do_quit

    def do_EOF(self, line):
        self.say()
        return True

    def emptyline(self):
        pass                                    # don't repeat the last command

    def default(self, line):
        self.say(f"Unknown command: {line.split()[0]}. Type help for the list.")


if __name__ == "__main__":
    shell = InventoryShell()
    for path in sys.argv[1:]:
        shell.onecmd(f'load "{path}"')
    shell.cmdloop()
