# tests/test_inventory.py (only the two sqlite tests changed)
import os
import tempfile
import gc
import sqlite3
import pytest

from cafe_inventory.infra import InMemoryInventoryRepo
from cafe_inventory.infra_sql import SqlInventoryRepo

def seed(inv):
    c_food = inv.add_category("Food")
    s_main = inv.add_supplier("Main", "main@example.com")
    i1 = inv.add_item("Croissant", 2.5, c_food, s_main, current_stock=10, part_number="CROISSANT")
    return c_food, s_main, i1

@pytest.mark.parametrize("repo_cls", [InMemoryInventoryRepo])
def test_duplicate_part_number_inmemory(repo_cls):
    inv = repo_cls()
    c, s, _ = seed(inv)
    with pytest.raises(ValueError):
        inv.add_item("Another", 1.0, c, s, part_number="croissant")

def test_duplicate_part_number_sqlite():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        inv = SqlInventoryRepo(db)
        c, s, _ = seed(inv)
        with pytest.raises(ValueError):
            inv.add_item("Another", 1.0, c, s, part_number="croissant")
        # --- ensure all handles are closed before tempdir cleanup ---
        del inv
        gc.collect()
        # touch-and-close to ensure no lingering lock
        sqlite3.connect(db).close()

@pytest.mark.parametrize("repo_cls", [InMemoryInventoryRepo])
def test_partial_receive_inmemory(repo_cls):
    inv = repo_cls()
    c, s, i1 = seed(inv)
    po = inv.create_purchase_order(s)
    inv.add_item_to_order(po, i1, 10)
    inv.submit_order(po)
    inv.receive_order_partial(po, {i1: 4})
    assert inv.get_order(po).status == "PARTIAL"
    inv.receive_order_partial(po, {i1: 6})
    assert inv.get_order(po).status == "RECEIVED"

def test_partial_receive_sqlite():
    with tempfile.TemporaryDirectory() as td:
        db = os.path.join(td, "t.db")
        inv = SqlInventoryRepo(db)
        c, s, i1 = seed(inv)
        po = inv.create_purchase_order(s)
        inv.add_item_to_order(po, i1, 5)
        inv.submit_order(po)
        inv.receive_order_partial(po, {i1: 3})
        assert inv.get_order(po).status == "PARTIAL"
        inv.receive_order_partial(po, {i1: 2})
        assert inv.get_order(po).status == "RECEIVED"
        # --- ensure all handles are closed before tempdir cleanup ---
        del inv
        gc.collect()
        sqlite3.connect(db).close()

