# MSCS 532 Project – Dynamic Inventory Management (Phase 2: Proof of Concept)

A proof of concept for an inventory system that handles constant changes to
product quantities, prices, categories, and names. Phase 1 designed and built
the core data structures; Phase 2 (this deliverable) turns them into a working,
tested application core with atomic updates, validation, search, batch
loading, and a command-line interface. The full write-up is in
[REPORT.md](REPORT.md).

Phase 1 repository: https://github.com/Skyboxii/MSCS532_Project (this
repository continues its history).

## Design

`InventoryManager` is a facade over five indexes, all built from scratch, that
it keeps in sync on every change:

| Index | Structure | Key → value | Supports | Cost |
|-------|-----------|-------------|----------|------|
| Products | `HashTable` (open addressing, linear probing) | SKU → `Product` | lookup, add, remove, update | O(1) average |
| Price | `SkipList` | (price, SKU) | price change, range query, cheapest-k | O(log n) expected; range O(log n + k) |
| Name *(new)* | `SkipList` | (casefolded name, SKU) | prefix search, rename | O(log n + k) |
| Category | `HashTable` of sets | category → {SKU} | list category, recategorize | O(1) average per change |
| Stock alerts | `IndexedMinHeap` | SKU → quantity − reorder point | quantity change, low-stock report | O(log n) update; report O(k log k) |

## What Phase 2 added

| Area | Change |
|------|--------|
| Atomic updates | Every mutation records an undo action per index change; any failure rolls the whole operation back. `inventory.transaction()` groups several operations into one all-or-nothing unit. |
| Integrity | `verify_integrity()` cross-checks all five indexes and the running total value. |
| Validation | `InventoryError` hierarchy (`ValidationError`, `ProductNotFoundError`, `DuplicateSKUError`, `InsufficientStockError`), still compatible with `KeyError`/`ValueError`. Prices must be finite, non-negative, and whole cents; counts must be real integers (not `bool`). |
| Search | Case-insensitive name prefix search and `rename_product`, using a second skip list. |
| Batch loading | CSV import of products and stock movements, with line-numbered error reports; movements apply either row by row (reject and continue) or as one transaction. |
| Interface | `cli.py` interactive shell; `demo.py` scripted walkthrough (output in `docs/demo_output.txt`). |
| Scaling check | `benchmarks/scaling_check.py` times every operation at 1k, 10k, and 100k products. |

## Layout

```
inventory/
    hash_table.py         HashTable (open addressing)
    skip_list.py          SkipList (ordered map)
    indexed_heap.py       IndexedMinHeap (with invariant check)
    product.py            Product record and field validators
    exceptions.py         InventoryError hierarchy
    inventory_manager.py  InventoryManager facade, undo log, integrity check
    batch.py              CSV readers, import_products, apply_movements
cli.py                    interactive command shell
demo.py                   scripted demonstration (writes docs/demo_output.txt)
data/                     sample catalog, movements, and a file with bad rows
benchmarks/               scaling_check.py and timing helper
results/                  scaling-check output
tests/                    62 unit tests
```

## Usage

Requires Python 3.8+ and the standard library only.

```bash
python demo.py                         # scripted walkthrough of every feature
python cli.py data/products.csv        # interactive shell with the sample catalog
python -m unittest -v                  # 62 tests
python benchmarks/scaling_check.py     # ~1 minute
```

Example shell session:

```
inventory> find desk
inventory> range 20 50
inventory> sell PEN-300 30
inventory> movements data/movements.csv          # bad rows reported, good rows applied
inventory> movements data/movements.csv all      # one transaction: any bad row undoes all
inventory> lowstock
inventory> verify
```

```python
from inventory import InventoryManager, Product, InsufficientStockError

inv = InventoryManager()
inv.add_product(Product("MOU-200", "Wireless Mouse", "Electronics", "24.50", 3, reorder_point=10))
with inv.transaction():                     # both changes or neither
    inv.adjust_quantity("MOU-200", 40)
    inv.update_price("MOU-200", "19.99")
inv.search_by_name("wire")
try:
    inv.adjust_quantity("MOU-200", -100)
except InsufficientStockError as e:
    print(e)                                # insufficient stock for MOU-200: have 43, need 100
```

## Testing

| Test file | Tests | Covers |
|-----------|------:|--------|
| `test_structures.py` | 12 | hash table, skip list, indexed heap (Phase 1) |
| `test_inventory_manager.py` | 8 | facade operations; 3,000 random operations checked against a brute-force model |
| `test_validation.py` | 12 | invalid prices, counts, text, unknown SKUs, empty inventory |
| `test_transactions.py` | 6 | 26 injected mid-update failures, each fully rolled back; nested transactions |
| `test_search.py` | 8 | prefix search, Unicode case folding, rename, random names vs. brute force |
| `test_batch.py` | 9 | CSV parsing with bad rows, duplicates, both batch modes |
| `test_cli.py` | 7 | shell commands, quoting, one-line error messages |

## Scaling check (average µs per operation)

| n | get | dict lookup | adjust qty | update price | price range (k≈10) | name search (10) | low-stock (20 items) |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 1,000 | 0.24 | 0.02 | 6.06 | 10.93 | 6.34 | 5.85 | 9.94 |
| 10,000 | 0.23 | 0.03 | 7.73 | 13.26 | 7.64 | 4.74 | 10.03 |
| 100,000 | 0.45 | 0.06 | 8.44 | 18.69 | 15.21 | 5.42 | 10.55 |

About 725 bytes of memory per product across all indexes (n = 10,000).

## Next steps (Phase 3)

Benchmark against built-in structures and optimize (e.g. `dict`-backed
product table, cached skip-list levels), measure tombstone build-up under
delete-heavy workloads, explore the price-range slowdown at 100k products,
and add persistence and concurrency control.
