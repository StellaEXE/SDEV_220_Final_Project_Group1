"""
utils.py
--------
Shared helpers for CLI:
- Back exception (for 'b' to go back)
- input validators (ask_int/ask_float/ask_yes_no)
- table printer
- seed_demo_data (now idempotent for SQLite)
- normalize_part_number
"""

from __future__ import annotations
from typing import List, Optional, Any

# -------- navigation exception --------
class Back(Exception):
    """Raised when user types 'b' to go back in sub-menus."""
    pass

# -------- input helpers --------
def _read(prompt: str) -> str:
    s = input(f"{prompt}: ").strip()
    if s.lower() == "b":
        raise Back()
    return s

def ask_int(prompt: str, default: Optional[int] = None, min_v: Optional[int] = None, max_v: Optional[int] = None) -> int:
    while True:
        raw = input(f"{prompt}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        if raw.lower() == "b":
            raise Back()
        if raw == "" and default is not None:
            val = default
        else:
            try:
                val = int(raw)
            except Exception:
                print("Please enter a whole number.")
                continue
        if min_v is not None and val < min_v:
            print(f"Must be ≥ {min_v}")
            continue
        if max_v is not None and val > max_v:
            print(f"Must be ≤ {max_v}")
            continue
        return val

def ask_float(prompt: str, default: Optional[float] = None, min_v: Optional[float] = None, max_v: Optional[float] = None) -> float:
    while True:
        raw = input(f"{prompt}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        if raw.lower() == "b":
            raise Back()
        if raw == "" and default is not None:
            val = default
        else:
            try:
                val = float(raw)
            except Exception:
                print("Please enter a number (e.g., 12.34).")
                continue
        if min_v is not None and val < min_v:
            print(f"Must be ≥ {min_v}")
            continue
        if max_v is not None and val > max_v:
            print(f"Must be ≤ {max_v}")
            continue
        return val

def ask_yes_no(prompt: str, default: str = "n") -> bool:
    d = default.lower()
    hint = "[Y/n]" if d == "y" else "[y/N]"
    while True:
        raw = input(f"{prompt} {hint}: ").strip().lower()
        if raw == "":
            raw = d
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer y or n.")

# -------- formatting --------
def print_table(rows: List[List[Any]]) -> None:
    if not rows:
        print("(no data)")
        return
    srows = [[str(c) for c in r] for r in rows]
    widths = [max(len(col) for col in col_vals) for col_vals in zip(*srows)]
    for r, row in enumerate(srows):
        line = " | ".join(val.ljust(widths[i]) for i, val in enumerate(row))
        print(line)
        if r == 0:
            print("-+-".join("-" * w for w in widths))

# -------- part number normalization --------
def normalize_part_number(pn: str) -> str:
    """
    Normalize part numbers to a consistent, case-insensitive format:
    - uppercase
    - internal whitespace -> single dash
    - strip surrounding whitespace
    """
    s = (pn or "").strip()
    if not s:
        return ""
    # collapse all inner whitespace to single dash
    parts = s.split()
    base = "-".join(parts)
    return base.upper()

# -------- demo data (IDEMPOTENT) --------
def seed_demo_data(inv) -> None:
    """
    Seed demo data in an idempotent way:
    - categories: skip if name already exists
    - suppliers:  skip if name already exists
    - items:      skip if part number already exists
    Works with both InMemoryInventoryRepo and SqlInventoryRepo.
    """

    # categories -> check by name
    existing_cats = {name for (_cid, name) in (inv.list_categories() or [])}
    def ensure_cat(name: str) -> int:
        if name in existing_cats:
            # find its id
            for cid, nm in inv.list_categories():
                if nm == name:
                    return cid
        cid = inv.add_category(name)
        existing_cats.add(name)
        return cid

    # suppliers -> check by name
    existing_sups = {name for (_sid, name) in (inv.list_suppliers() or [])}
    def ensure_sup(name: str, contact: str) -> int:
        if name in existing_sups:
            for sid, nm in inv.list_suppliers():
                if nm == name:
                    return sid
        sid = inv.add_supplier(name, contact)
        existing_sups.add(name)
        return sid

    c_food = ensure_cat("Food")
    c_bev  = ensure_cat("Beverage")
    c_sup  = ensure_cat("Supply")

    s_main    = ensure_sup("Main Distributor", "sales@maindist.com / (555) 123-4567")
    s_bakery  = ensure_sup("Sunrise Bakery", "orders@sunrise.com / (555) 222-3456")

    # items -> check by part number (normalized)
    def ensure_item(name: str, price: float, cid: int, sid: int, stock: int, rlevel: int, rqty: int, part_number: str) -> None:
        pn = normalize_part_number(part_number)
        if pn:
            it = inv.find_by_part_number(pn)
            if it:
                return  # already present
        inv.add_item(
            name=name,
            price=price,
            category_id=cid,
            supplier_id=sid,
            current_stock=stock,
            reorder_level=rlevel,
            reorder_qty=rqty,
            part_number=pn,
        )

    # give part numbers so duplicates are detectable and CSV is consistent
    ensure_item("Espresso Beans (1kg)", 16.50, c_bev, s_main,   stock=8,  rlevel=5, rqty=6,  part_number="ESP-1KG")
    ensure_item("Milk (1L)",             1.20,  c_bev, s_main,   stock=12, rlevel=8, rqty=12, part_number="MILK-1L")
    ensure_item("Croissant",             2.40,  c_food, s_bakery, stock=6,  rlevel=6, rqty=24, part_number="CROISSANT")
    ensure_item("Sugar Packets (box)",   4.99,  c_sup, s_main,    stock=3,  rlevel=5, rqty=10, part_number="SUGAR-PKT")
    ensure_item("Cups (100ct)",          6.99,  c_sup, s_main,    stock=15, rlevel=10, rqty=10, part_number="CUPS-100")
