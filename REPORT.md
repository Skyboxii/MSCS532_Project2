# Dynamic Inventory Management: Proof of Concept Implementation

Skyler Troxell  
School of Computer and Information Sciences, University of the Cumberlands  
MSCS-532: Algorithms and Data Structures  
Project Deliverable 2: Proof of Concept Implementation  
November 15, 2026  
GitHub Repository: https://github.com/Skyboxii/MSCS532_Project2  

## Introduction

In Phase 1, I designed four data structures for an inventory system whose quantities, prices, and categories change constantly, and I implemented them as standalone classes. This phase turns them into a working proof of concept: an application core that validates its input, keeps every index consistent even when an update fails, loads data from files, and can be driven from a command line. The repository continues the Phase 1 commit history.

### Partial Implementation Overview

The code is organized in three layers. The bottom layer holds the data structures from Phase 1: an open-addressing hash table for SKU lookups (Knuth, 1998), a skip list ordered by price (Pugh, 1990), a hash table mapping each category to a set of SKUs, and an indexed binary min-heap keyed on quantity minus reorder point for low-stock alerts (Williams, 1964). Phase 2 added a fifth index, a second skip list keyed on the case-folded product name, which supports prefix search in O(log *n* + *k*) time without any new data structure, which is the extension the modular design was meant to allow. The middle layer is `InventoryManager`, a facade (Gamma et al., 1994) that is the only code allowed to change an index. The top layer is the application: a CSV batch loader and an interactive shell (`cli.py`). Persistence, concurrent users, and a graphical interface are out of scope for the proof of concept.

The most important addition is atomicity. In Phase 1, a product update touched up to four indexes in sequence, and an exception between two of those steps would have left them disagreeing. Each mutation now runs inside a transaction that pairs every index change with the action that reverses it, the same undo-logging idea databases use to guarantee atomicity (Haerder & Reuter, 1983):

**Undo log and a price change (inventory_manager.py, abridged)**

```python
class _UndoLog:
    def do(self, apply, undo):
        apply()                       # make one index change
        self._undo.append(undo)       # remember how to reverse it

def update_price(self, sku, new_price):
    old = self._require(sku)
    new = replace(old, price=new_price)   # validates before anything changes
    with self._atomic() as tx:
        tx.do(lambda: self._by_price.remove((old.price, sku)),
              lambda: self._by_price.insert((old.price, sku)))
        tx.do(lambda: self._by_price.insert((new.price, sku)),
              lambda: self._by_price.remove((new.price, sku)))
        self._replace_record(tx, old, new)
        self._change_value(tx, (new.price - old.price) * old.quantity)
    return new
```

If any step raises, `_atomic()` replays the recorded undo actions in reverse and re-raises the error, so callers see the whole update or none of it. A nested `_atomic()` joins the outer transaction, which is what makes the public `inventory.transaction()` block and an all-or-nothing batch load possible with no extra code. A companion method, `verify_integrity()`, cross-checks all five indexes and the running inventory value in O(*n* lg *n*) time.

### Demonstration and Testing

`demo.py` runs a scripted day of activity through the same shell a user would type into, and saves the transcript to `docs/demo_output.txt`. Its eight sections load a 25-product catalog, query every index (SKU lookup, price range, name prefix, category, cheapest items), apply sales, receipts, price changes, recategorizations, and renames, and print the low-stock report before and after a sale pushes a notebook below its reorder point. Ten deliberate errors follow, from overselling and unknown SKUs to a price with a fraction of a cent and a missing file. Each produces a one-line message, and the inventory value is identical before and after. Table 1 summarizes the 62 unit tests, which all pass in about 0.2 seconds.

The batch tests use a movements file of the kind an integration receives: 12 rows, three of which cannot be parsed and two of which fail when applied (an unknown SKU and a sale larger than the stock on hand). In the default reject-and-continue mode, the loader applies the 7 good rows and reports the 5 bad ones by line number. In all-or-nothing mode, the first failure rolls back every row, and the inventory is unchanged. The failure-injection tests make each internal index call fail once, in turn, during every type of update, and confirm that all 26 resulting failures leave the inventory exactly as it was. Finally, a scaling check timed each operation at 1,000 and 100,000 products. A hash-table lookup took 0.24 and 0.45 µs, a price update 10.93 and 18.69 µs, and the low-stock report 9.94 and 10.55 µs. Growing the catalog 100-fold barely changed these costs, which is consistent with O(1), O(log *n*), and output-sensitive behavior.

**Table 1.** *Unit Tests by Area*

| Test file: what the tests verify | Tests |
|---|---:|
| structures: hash table, skip list, and heap operations (Phase 1) | 12 |
| inventory_manager: 3,000 random operations vs. a brute-force model | 8 |
| validation: bad prices, counts, and text; unknown SKUs; empty inventory | 12 |
| transactions: 26 injected mid-update failures, each rolled back | 6 |
| search: prefix search, Unicode case folding, rename | 8 |
| batch: CSV rows with errors, duplicates, both batch modes | 9 |
| cli: commands, quoted arguments, one-line error messages | 7 |

### Implementation Challenges and Solutions

*An undo step that was really two steps.* The first run of the failure-injection tests found a real bug. Removing a product from a category discarded its SKU from the set and then deleted the category if the set was empty. When the second action failed, the first was never undone, because an undo action is recorded only after its step succeeds. The fix was a rule I now apply to the whole manager: every recorded step must make exactly one change. The category helpers now either delete the category or remove one SKU, never both.

*Validation gaps.* Writing edge-case tests showed that Phase 1 accepted `Decimal("Infinity")` as a price, which corrupted the running total, and accepted `True` as a quantity, because `bool` is a subclass of `int` in Python. Shared validators now require prices to be finite, non-negative, and whole cents, and require counts to be genuine integers. Because `dataclasses.replace()` re-runs validation, an invalid update fails before any index is touched, so most errors never need a rollback at all. The cents rule proved its worth immediately when it rejected a float sum of 103.69999999999999 in my own benchmark script.

*Changing error types without breaking callers.* I replaced the generic `KeyError` and `ValueError` with an `InventoryError` hierarchy that callers can catch as one type. Each new class also inherits from the old built-in type, so the Phase 1 tests passed unchanged. This is the same backward-compatibility discipline I follow when changing an integration that other systems already depend on.

*Smaller design changes.* `rename_product` keeps the new name index current, and `most_urgent()` now returns `None` on an empty inventory instead of leaking a heap error.

### Next Steps

- **Performance and optimization (Phase 3).** Benchmark each index against Python's built-in structures (my hash-table lookup is currently 8 to 12 times slower than `dict`), profile the price-range query, which slowed more than lg *n* predicts at 100,000 products, and stress-test delete-heavy workloads and catalogs of a million products.
- **Persistence, concurrency, and interfaces.** Log each committed transaction to durable storage, add locking so several registers can update stock at once, and expose the facade through a small web API, which is how I would connect it to a PHP portal at work.

## References

Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). *Design patterns: Elements of reusable object-oriented software*. Addison-Wesley.

Haerder, T., & Reuter, A. (1983). Principles of transaction-oriented database recovery. *ACM Computing Surveys, 15*(4), 287–317. https://doi.org/10.1145/289.291

Knuth, D. E. (1998). *The art of computer programming: Vol. 3. Sorting and searching* (2nd ed.). Addison-Wesley.

Pugh, W. (1990). Skip lists: A probabilistic alternative to balanced trees. *Communications of the ACM, 33*(6), 668–676. https://doi.org/10.1145/78973.78977

Williams, J. W. J. (1964). Algorithm 232: Heapsort. *Communications of the ACM, 7*(6), 347–348. https://doi.org/10.1145/512274.512284
