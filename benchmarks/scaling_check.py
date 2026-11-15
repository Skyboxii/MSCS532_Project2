"""
Quick scaling check for the proof of concept (Phase 3 will benchmark in depth).

Builds catalogs of 1,000, 10,000, and 100,000 products and measures the
average time of each operation.  If the design holds, hash-table operations
stay flat, skip-list and heap operations grow slowly (O(log n)), and the
low-stock report, which is output-sensitive, stays flat because the number
of low-stock products is held at 20.

Usage (from the repository root):  python benchmarks/scaling_check.py
"""

import csv
import os
import random
import sys
import time
import tracemalloc

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
sys.path.insert(0, ROOT)

from bench_util import stabilize_timing                         # noqa: E402
from inventory import InventoryManager, Product                  # noqa: E402

SIZES = [1_000, 10_000, 100_000]
OPS = 2_000                      # operations timed per measurement
LOW_STOCK_ITEMS = 20
WORDS = ["Desk", "Laptop", "Cable", "Mouse", "Chair", "Lamp", "Paper", "Pen", "Mug", "Bottle",
         "Hoodie", "Monitor", "Stapler", "Tape", "Shelf", "Cap", "Keyboard", "Hub", "Folder", "Map"]


def make_products(n, rng):
    products = []
    for i in range(n):
        low = i < LOW_STOCK_ITEMS                                 # exactly 20 low-stock products
        products.append(Product(
            sku=f"SKU-{i:06}",
            name=f"{rng.choice(WORDS)} {rng.choice(WORDS)} {i}",
            category=f"Category {i % 20:02}",
            price=f"{rng.randint(100, 99_999) / 100:.2f}",
            quantity=rng.randint(0, 5) if low else rng.randint(50, 500),
            reorder_point=10 if low else 0))
    return products


def per_op_us(fn, args):
    start = time.perf_counter()
    for a in args:
        fn(a)
    return (time.perf_counter() - start) / len(args) * 1e6


def measure(n):
    rng = random.Random(n)
    products = make_products(n, rng)
    inv = InventoryManager(seed=n)
    start = time.perf_counter()
    for p in products:
        inv.add_product(p)
    build_s = time.perf_counter() - start
    as_dict = {p.sku: p for p in products}

    skus = [rng.choice(products).sku for _ in range(OPS)]
    # Prices are spread over $1.00-$999.99, so a window of 10 * 99,900 / n cents
    # holds about 10 products at every n (k stays fixed while n grows).
    width = max(1, round(10 * 99_900 / n)) / 100
    lows = [rng.randint(100, 99_999 - int(width * 100)) / 100 for _ in range(OPS)]
    range_hits = sum(len(inv.products_in_price_range(f"{lo:.2f}", f"{lo + width:.2f}"))
                     for lo in lows[:200]) / 200
    row = {
        "n": n,
        "add_product_us": build_s / n * 1e6,
        "get_us": per_op_us(inv.get, skus),
        "dict_lookup_us": per_op_us(as_dict.__getitem__, skus),
        "adjust_quantity_us": per_op_us(lambda s: inv.adjust_quantity(s, 1), skus),
        "update_price_us": per_op_us(lambda s: inv.update_price(s, f"{rng.randint(100, 99_999) / 100:.2f}"),
                                     skus),
        "price_range_10_us": per_op_us(lambda lo: inv.products_in_price_range(f"{lo:.2f}",
                                                                              f"{lo + width:.2f}"), lows),
        "price_range_avg_results": range_hits,
        "name_search_10_us": per_op_us(lambda w: inv.search_by_name(w, limit=10),
                                       [rng.choice(WORDS) for _ in range(OPS)]),
        "low_stock_us": per_op_us(lambda _: inv.low_stock(), range(200)),
        "low_stock_items": len(inv.low_stock()),
    }
    if n == 10_000:                                  # tracemalloc is slow; one size is enough
        tracemalloc.start()
        probe = InventoryManager(seed=1)
        for p in products:
            probe.add_product(p)
        current, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        row["index_bytes_per_product"] = current / n
    assert not inv.verify_integrity()
    return row


if __name__ == "__main__":
    print("Power throttling disabled:", stabilize_timing())
    rows = []
    for n in SIZES:
        row = measure(n)
        rows.append(row)
        print(f"n={n:>7,}  " + "  ".join(f"{k.replace('_us', '')}={v:.2f}" if isinstance(v, float)
                                           else f"{k}={v}" for k, v in row.items() if k != "n"))
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "scaling_check.csv"), "w", newline="") as f:
        fields = list(rows[1].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
