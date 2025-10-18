"""
CSV import/export helpers for inventory items.

- export_items_csv(inv, path)
- import_items_csv(inv, path)
"""

# FEATURE CSV Import/Export
# WHY: Provide a clear data workflow: export for analysis / import from spreadsheets
# NOTES: Validates headers and basic numeric fields; respects part number uniqueness.

import csv
from typing import List
from .domain import InventoryRepo
from .utils import normalize_part_number

ITEM_HEADERS: List[str] = [
    "itemID", "name", "price", "categoryID", "supplierID",
    "currentStock", "reorderLevel", "reorderQty", "partNumber"
]

def export_items_csv(inv: InventoryRepo, path: str) -> None:
    """
    Write current items to a CSV file with headers.
    Robust to column order changes in inv.inventory_table().
    """
    rows = inv.inventory_table()
    if not rows or len(rows) < 2:
        # write empty file with headers
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=ITEM_HEADERS).writeheader()
        return

    header = rows[0]
    # Build a name->index map to tolerate re-ordered / extra columns
    idx = {name: header.index(name) for name in header}

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ITEM_HEADERS)
        writer.writeheader()

        for row in rows[1:]:
            item_id = int(row[idx["ID"]])
            it = inv.get_item(item_id)  # to fetch accurate numeric price & partNumber
            # Some backends format price as "$xx.xx" in the table; use the domain object instead
            price = float(getattr(it, "price", 0.0))
            part_number = getattr(it, "partNumber", "") or ""

            writer.writerow({
                "itemID": item_id,
                "name": row[idx["Item"]],
                "price": price,
                "categoryID": int(row[idx["CatID"]]),
                "supplierID": int(row[idx["SupID"]]),
                "currentStock": int(row[idx["Stock"]]),
                "reorderLevel": int(row[idx["Reorder"]]),
                "reorderQty": int(row[idx["ReorderQty"]]),
                "partNumber": part_number,
            })

def import_items_csv(inv: InventoryRepo, path: str) -> int:
    """
    Read items from CSV and add them to the repository.
    Returns the number of items imported.

    Rules:
    - Expects headers ITEM_HEADERS (extra columns are ignored).
    - itemID from CSV is ignored (IDs are assigned by backend).
    - Duplicate part numbers will raise (backend enforces).
    - Category/Supplier IDs must already exist.
    """
    count = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [h for h in ITEM_HEADERS if h not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing headers: {missing}")

        for r in reader:
            # Basic normalization
            name = (r.get("name") or "").strip()
            price = float(r.get("price") or 0)
            category_id = int(r.get("categoryID") or 0)
            supplier_id = int(r.get("supplierID") or 0)
            current_stock = int(r.get("currentStock") or 0)
            reorder_level = int(r.get("reorderLevel") or 0)
            reorder_qty = int(r.get("reorderQty") or 1)
            part_number = normalize_part_number(r.get("partNumber") or "")

            if not name:
                raise ValueError("CSV row has empty 'name'")
            if price < 0 or current_stock < 0 or reorder_level < 0 or reorder_qty <= 0:
                raise ValueError(f"Invalid numeric values for item '{name}'")

            inv.add_item(
                name=name,
                price=price,
                category_id=category_id,
                supplier_id=supplier_id,
                current_stock=current_stock,
                reorder_level=reorder_level,
                reorder_qty=reorder_qty,
                part_number=part_number,
            )
            count += 1
    return count
