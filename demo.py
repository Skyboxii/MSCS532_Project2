"""
Scripted demonstration of the inventory proof of concept.

Runs a day of inventory activity through the same command shell as cli.py,
printing each command before its output, so the demo exercises exactly the
code a user would.  Each section names the data structure doing the work.

Usage:  python demo.py                 (output is also saved to docs/demo_output.txt)
"""

import io
import os
import sys

from cli import InventoryShell

SCRIPT = [
    ("1. Load the catalog (CSV import into all five indexes)", [
        "load data/products.csv",
        "value",
        "categories",
    ]),
    ("2. Search: hash table, price skip list, name skip list, category index", [
        "get LAP-100",
        "range 20 50",
        'find "desk"',
        "category Furniture",
        "cheapest 3",
    ]),
    ("3. Dynamic updates", [
        "sell PEN-300 30",
        "receive CHR-400 6",
        "price LMP-420 29.95",
        "move MUG-600 Apparel",
        'rename HDM-220 "HDMI Cable 10ft"',
        'add USB-900 "USB Flash Drive 64GB" Electronics 14.99 30 10',
        "remove CAB-440",
        "value",
    ]),
    ("4. Low-stock report (indexed min-heap, most urgent first)", [
        "lowstock",
        "sell NBK-310 25",
        "lowstock",
    ]),
    ("5. Edge cases and error handling (nothing changes after an error)", [
        "value",
        "sell CHR-400 99",
        "get NOPE-000",
        "price LAP-100 -5",
        "price LAP-100 9.999",
        "add LAP-100 Duplicate Electronics 1.00 1",
        "add BAD-001 Widget",
        "sell PEN-300 two",
        "range 50 10",
        'find ""',
        "category Nonexistent",
        "load data/missing_file.csv",
        "value",
    ]),
    ("6. Batch of stock movements with bad rows (reject-and-continue)", [
        "movements data/movements.csv",
    ]),
    ("7. Same file again as one all-or-nothing transaction (rolled back)", [
        "value",
        "movements data/movements.csv all",
        "value",
    ]),
    ("8. Import a file with bad rows, then check every index agrees", [
        "load data/products_with_errors.csv",
        "verify",
    ]),
]


def run(out):
    shell = InventoryShell(stdout=out)
    for title, commands in SCRIPT:
        out.write(f"\n=== {title} ===\n")
        for line in commands:
            out.write(f"{shell.prompt}{line}\n")
            shell.onecmd(line)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))      # data/ paths are relative
    buffer = io.StringIO()
    run(buffer)
    text = buffer.getvalue()
    sys.stdout.write(text)
    os.makedirs("docs", exist_ok=True)
    with open(os.path.join("docs", "demo_output.txt"), "w", encoding="utf-8") as f:
        f.write(text)
