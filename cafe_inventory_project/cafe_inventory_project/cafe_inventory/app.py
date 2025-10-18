"""
app.py
------
Terminal (CLI) presentation layer:
- chooses an inventory backend (in-memory or SQLite)
- seeds demo data (if needed)
- shows a menu and routes actions
"""

import argparse
import os
from typing import Dict

from .logger import get_logger

# --- Backend selection: toggle via CLI flags ---
from .infra import InMemoryInventoryRepo
from .infra_sql import SqlInventoryRepo  # requires infra_sql.py present

from .utils import (
    print_table,
    seed_demo_data,
    ask_int,
    ask_float,
    ask_yes_no,
    normalize_part_number,
    Back,  # Back exception used for 'b' to go back
)
from .io_csv import export_items_csv, import_items_csv  # CSV import/export helpers


def prompt(text: str) -> str:
    """Free-text prompt that supports 'b' to go back."""
    val = input(text).strip()
    if val.lower() == "b":
        raise Back()
    return val


def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cafe_inventory",
        description="Cafe Inventory System (CLI)",
    )
    p.add_argument(
        "--db",
        choices=["sqlite", "memory"],
        default="sqlite",
        help="Choose backend: 'sqlite' (persistent) or 'memory' (ephemeral). Default: sqlite",
    )
    p.add_argument(
        "--db-path",
        default="cafe_inventory.db",
        help="SQLite file path (when --db=sqlite). Default: cafe_inventory.db",
    )
    p.add_argument(
        "--seed",
        action="store_true",
        help="Force seeding demo data (even if DB already has categories).",
    )
    return p.parse_args()


def main(args: argparse.Namespace) -> None:
    logger = get_logger()
    logger.info(f"START app db={args.db} path={getattr(args, 'db_path', '')} seed={args.seed}")

    # Backend selection via flags
    if args.db == "sqlite":
        inv = SqlInventoryRepo(args.db_path)
        # Seed if forced or empty
        if args.seed or not inv.list_categories():
            seed_demo_data(inv)
            logger.info("Seeded demo data (sqlite)")
    else:
        inv = InMemoryInventoryRepo()
        seed_demo_data(inv)
        logger.info("Seeded demo data (memory)")

    menu = """
Café Inventory System
1) View inventory
2) Add item(s) to inventory
3) Search items
4) Record sale/usage
5) Add stock
6) View low-stock items
7) Create purchase order (multi-item)
8) View purchase orders
9) Receive a purchase order (ID/Date/Item; supports partial)
10) Export items to CSV
11) Import items from CSV
12) Add Category
13) Add Supplier
0) Quit
(Use 'b' in sub-menus to go back)
Choose: """
    while True:
        try:
            choice = input(menu).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            logger.info("EXIT via signal")
            break

        try:
            # -------------------------
            # 1) View inventory (+ OnHand$)
            # -------------------------
            if choice == "1":
                rows = inv.inventory_table()
                # add OnHand$ using header lookups (robust even if columns move)
                header = rows[0]
                try:
                    price_idx = header.index("Price")
                    stock_idx = header.index("Stock")
                except ValueError:
                    # fallback: just print what we have
                    print_table(rows)
                else:
                    header.append("OnHand$")
                    for i in range(1, len(rows)):
                        price = float(rows[i][price_idx].replace("$", ""))
                        stock = int(rows[i][stock_idx])
                        rows[i].append(f"${price * stock:.2f}")
                    print_table(rows)

            # -------------------------
            # 2) Add item
            # -------------------------
            elif choice == "2":
                try:
                    name = prompt("Item name (b=back): ")
                    price = ask_float("Price", min_v=0.0)

                    # categories
                    cats = inv.list_categories()
                    print_table([["ID", "Category"]] + cats)
                    category_id = ask_int("CategoryID (b=back)", min_v=1)

                    # suppliers
                    sups = inv.list_suppliers()
                    print_table([["ID", "Supplier"]] + sups)
                    supplier_id = ask_int("SupplierID (b=back)", min_v=1)

                    raw_pn = input("Part number (e.g., ESP-1KG) [optional]: ").strip()
                    part_number = normalize_part_number(raw_pn)

                    stock = ask_int("Starting stock", default=0, min_v=0)
                    rlevel = ask_int("Reorder level", default=5, min_v=0)
                    rqty = ask_int("Reorder qty", default=10, min_v=1)

                    iid = inv.add_item(
                        name, price, category_id, supplier_id,
                        stock, rlevel, rqty, part_number=part_number
                    )
                    print(f"Added item {iid} - {name} (Part#: {part_number or '-'})")
                    logger.info(f"ADD_ITEM id={iid} name={name} pn={part_number}")
                except Back:
                    print("Back.")
                    continue
                except Exception as e:
                    print(f"Error: {e}")
                    logger.exception("ADD_ITEM failed")

            # -------------------------
            # 3) Search items (wildcards supported)
            # -------------------------
            elif choice == "3":
                try:
                    print("\nSearch by:")
                    print(" 1) Name/Part# (supports * and ?; 'b' to go back)")
                    print(" 2) Item ID")
                    print(" 3) Category ID")
                    print(" 4) Supplier ID")
                    print(" 5) Part Number")
                    choice_s = prompt("Choose: ")

                    rows = [["ID","Item","Part#","Price","CatID","SupID","Stock","Reorder","ReorderQty"]]
                    if choice_s == "1":
                        q = prompt("Pattern (e.g., *milk* or CUP*): ")
                        for it in inv.search_items(q):
                            rows.append(it.to_row())
                    elif choice_s == "2":
                        iid = ask_int("Item ID", min_v=1)
                        it = inv.get_item(iid)
                        if it:
                            rows.append(it.to_row())
                    elif choice_s == "3":
                        cid = ask_int("Category ID", min_v=1)
                        for it in inv.filter_by_category(cid):
                            rows.append(it.to_row())
                    elif choice_s == "4":
                        sid = ask_int("Supplier ID", min_v=1)
                        for it in inv.filter_by_supplier(sid):
                            rows.append(it.to_row())
                    elif choice_s == "5":
                        pn = prompt("Part Number: ")
                        it = inv.find_by_part_number(pn)
                        if it:
                            rows.append(it.to_row())
                    else:
                        print("Invalid choice.")
                        rows = []

                    if rows and len(rows) > 1:
                        print_table(rows)
                    else:
                        print("No matches.")
                except Back:
                    print("Back.")
                    continue

            # -------------------------
            # 4) Record sale/usage
            # -------------------------
            elif choice == "4":
                try:
                    ref = prompt("Item (ID or Part#) to consume (b=back): ")
                    qty = ask_int("Quantity used/sold", min_v=1)
                    iid = inv.resolve_item_ref(ref)

                    ok = inv.consume_stock(iid, qty)
                    if ok:
                        it = inv.get_item(iid)
                        print(f"Stock updated. New qty: {it.currentStock} | On-hand: ${it.price * it.currentStock:.2f}")
                        logger.info(f"CONSUME item={iid} qty={qty}")
                    else:
                        have = inv.get_item(iid).currentStock if inv.get_item(iid) else 0
                        print(f"Not enough stock. Available: {have}")
                except Back:
                    print("Back.")
                    continue
                except Exception as e:
                    print(f"Error: {e}")
                    logger.exception("CONSUME failed")

            # -------------------------
            # 5) Add stock
            # -------------------------
            elif choice == "5":
                try:
                    ref = prompt("Item (ID or Part#) to add stock to (b=back): ")
                    qty = ask_int("Quantity received", min_v=1)
                    iid = inv.resolve_item_ref(ref)

                    inv.add_stock(iid, qty)
                    it = inv.get_item(iid)
                    print(f"Stock updated. New qty: {it.currentStock} | On-hand: ${it.price * it.currentStock:.2f}")
                    logger.info(f"ADD_STOCK item={iid} qty={qty}")
                except Back:
                    print("Back.")
                    continue
                except Exception as e:
                    print(f"Error: {e}")
                    logger.exception("ADD_STOCK failed")

            # -------------------------
            # 6) View low-stock items
            # -------------------------
            elif choice == "6":
                low = inv.low_stock_items()
                if not low:
                    print("All items above reorder level.")
                else:
                    print("Low stock items:")
                    rows = [["ID", "Item", "Stock", "ReorderLevel", "DefaultOrderQty"]]
                    for it in low:
                        rows.append([str(it.itemID), it.name, str(it.currentStock), str(it.reorderLevel), str(it.reorderQty)])
                    print_table(rows)
                    do_order = input("Create orders for all low items? (y/N): ").strip().lower()
                    if do_order == "y":
                        created = []
                        for it in low:
                            po_id = inv.create_order_for_item(it.itemID)
                            created.append(po_id)
                        for poid in created:
                            inv.submit_order(poid)
                        print(f"Created and submitted {len(created)} purchase orders.")
                        logger.info(f"LOW_STOCK_AUTO_ORDERS count={len(created)}")

            # -------------------------
            # 7) Create purchase order (multi-item)
            # -------------------------
            elif choice == "7":
                try:
                    sups = inv.list_suppliers()
                    print_table([["ID", "Supplier"]] + sups)
                    supplier_id = ask_int("Create PO for SupplierID (b=back)", min_v=1)
                    poid = inv.create_purchase_order(supplier_id)
                    print(f"Started PO {poid}. Add items (type 'done' when finished).")

                    while True:
                        ref = input(" Item (ID or Part#) [done=submit, c=cancel]: ").strip()
                        if ref.lower() == "done":
                            po = inv.get_order(poid)
                            total = inv.order_total(poid)
                            lines = ", ".join(f"{iid}:{qty}" for iid, qty in po.items.items()) or "-"
                            print(f"\nPO {poid} Summary")
                            print(f" SupplierID: {po.supplierID}")
                            print(f" Lines: {lines}")
                            print(f" Total: ${total:.2f}")
                            confirm = input("Submit PO now? (y/N): ").strip().lower()
                            if confirm == "y":
                                inv.submit_order(poid)
                                print(f"PO {poid} submitted.")
                                logger.info(f"PO_SUBMIT id={poid}")
                            else:
                                inv.cancel_order(poid)
                                print("PO canceled.")
                                logger.info(f"PO_CANCEL id={poid}")
                            break
                        if ref.lower() == "c":
                            inv.cancel_order(poid)
                            print("PO canceled.")
                            logger.info(f"PO_CANCEL id={poid}")
                            break

                        try:
                            iid = inv.resolve_item_ref(ref)
                            it = inv.get_item(iid)
                            if it.supplierID != supplier_id:
                                print(f" Item's supplier ({it.supplierID}) != PO supplier ({supplier_id}). Skipped.")
                                continue
                            print(f"  Current qty: {it.currentStock} | Default reorder qty: {it.reorderQty}")
                            qty_in = input("  Quantity (blank = default reorder qty): ").strip()
                            qty = it.reorderQty if qty_in == "" else max(1, int(qty_in))
                            inv.add_item_to_order(poid, iid, qty)
                            print(f"  Added line: {iid}:{qty} | Running Total: ${inv.order_total(poid):.2f}")
                        except Exception as e:
                            print(f"  Error: {e}")
                            logger.exception("PO_ADD_LINE failed")
                except Back:
                    print("Back.")
                    continue

            # -------------------------
            # 8) View purchase orders
            # -------------------------
            elif choice == "8":
                print_table(inv.orders_table())

            # -------------------------
            # 9) Receive a purchase order (ID/Date/Item; supports partial)
            # -------------------------
            elif choice == "9":
                try:
                    print("\nFind PO by:")
                    print(" 1) Order ID")
                    print(" 2) Date (YYYY-MM-DD)")
                    print(" 3) Item (ID or Part#)")
                    pick = prompt("Choose: ")

                    candidates: list[int] = []
                    if pick == "1":
                        oid = ask_int("Order ID", min_v=1)
                        candidates = [oid]
                    elif pick == "2":
                        ymd = prompt("Date (YYYY-MM-DD): ")
                        candidates = inv.search_orders_by_date(ymd)
                    elif pick == "3":
                        ref = prompt("Item (ID or Part#): ")
                        candidates = inv.search_orders_by_item_ref(ref)
                    else:
                        print("Invalid choice.")
                        continue

                    if not candidates:
                        print("No matching purchase orders.")
                        continue

                    print("Matching POs:")
                    for oid in candidates:
                        po = inv.get_order(oid)
                        total = inv.order_total(oid)
                        print(f"  PO {oid} | Date {po.orderDate} | Supplier {po.supplierID} | Status {po.status} | Total ${total:.2f}")

                    oid = ask_int("Enter PO ID to receive (b=back)", min_v=1)
                    po = inv.get_order(oid)
                    print("\nPO Lines:")
                    for iid, ordered in po.items.items():
                        rec = po.received.get(iid, 0)
                        remain = ordered - rec
                        it = inv.get_item(iid)
                        name = it.name if it else f"Item {iid}"
                        print(f"  {iid} - {name}: ordered {ordered}, received {rec}, remaining {remain}")

                    mode = prompt("Receive mode: 1) Full remaining  2) Partial (b=back): ")
                    if mode == "1":
                        inv.receive_order(oid)
                        print(f"PO {oid} received (full or partial based on remaining). New status: {inv.get_order(oid).status}")
                        logger.info(f"PO_RECEIVE_FULL id={oid}")
                    elif mode == "2":
                        lines: Dict[int, int] = {}
                        print("Enter quantities to receive per line (blank = 0).")
                        for iid, ordered in po.items.items():
                            rec = po.received.get(iid, 0)
                            remain = ordered - rec
                            qty_in = input(f"  {iid} remaining {remain}: ").strip()
                            if qty_in == "":
                                q = 0
                            else:
                                try:
                                    q = max(0, int(qty_in))
                                except:
                                    q = 0
                            if q > 0:
                                lines[iid] = min(q, remain)
                        if lines:
                            inv.receive_order_partial(oid, lines)
                            print(f"PO {oid} updated. New status: {inv.get_order(oid).status}")
                            logger.info(f"PO_RECEIVE_PARTIAL id={oid} lines={lines}")
                        else:
                            print("No quantities entered; nothing received.")
                    else:
                        print("Invalid choice.")
                        continue

                except Back:
                    print("Back.")
                    continue
                except Exception as e:
                    print(f"Error: {e}")
                    logger.exception("PO_RECEIVE failed")

            # -------------------------
            # 10) Export items to CSV
            # -------------------------
            elif choice == "10":
                path = input("Export path (e.g., items_export.csv): ").strip() or "items_export.csv"
                try:
                    export_items_csv(inv, path)
                    abs_path = os.path.abspath(path)
                    print(f"Exported items to: {abs_path}\n(Note: this path is relative to where you run the program.)")
                    logger.info(f"CSV_EXPORT path={abs_path}")
                except Exception as e:
                    print(f"Error exporting CSV: {e}")
                    logger.exception("CSV_EXPORT failed")

            # -------------------------
            # 11) Import items from CSV
            # -------------------------
            elif choice == "11":
                path = input("Import path (e.g., items_import.csv): ").strip() or "items_import.csv"
                try:
                    added = import_items_csv(inv, path)
                    print(f"Imported {added} item(s) from {path}")
                    logger.info(f"CSV_IMPORT path={os.path.abspath(path)} count={added}")
                except Exception as e:
                    print(f"Error importing CSV: {e}")
                    logger.exception("CSV_IMPORT failed")

            # -------------------------
            # 12) Add Category
            # -------------------------
            elif choice == "12":
                try:
                    name = prompt("New category name (b=back): ")
                    cid = inv.add_category(name)
                    print(f"Added category {cid}: {name}")
                    logger.info(f"ADD_CATEGORY id={cid} name={name}")
                except Back:
                    print("Back.")
                    continue

            # -------------------------
            # 13) Add Supplier
            # -------------------------
            elif choice == "13":
                try:
                    name = prompt("New supplier name (b=back): ")
                    contact = input("Contact info (email/phone): ").strip()
                    sid = inv.add_supplier(name, contact)
                    print(f"Added supplier {sid}: {name} ({contact})")
                    logger.info(f"ADD_SUPPLIER id={sid} name={name}")
                except Back:
                    print("Back.")
                    continue

            # -------------------------
            # 0) Quit (confirm)
            # -------------------------
            elif choice == "0":
                if ask_yes_no("Are you sure you want to quit?", default="n"):
                    print("Goodbye!")
                    logger.info("EXIT via menu")
                    break

            else:
                print("Invalid choice. Try again.")

        except Exception as e:
            print(f"Error: {e}")



if __name__ == "__main__":
    main(get_args())

