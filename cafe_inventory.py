#Program: cafe_inventory.py
#Author(s): Group 1
#Purpose: Terminal Based inventory management system for a cafe that tracks items, stock levels, suppliers, and create purchase orders.

from dataclasses import dataclass, field # temp storage
from datetime import datetime
from typing import Dict, List, Optional
import itertools # used instead of rand to avoide repetition

#classes
@dataclass
class Category:
    categoryID: int
    name: str


@dataclass
class Supplier:
    supplierID: int
    name: str
    contactInfo: str


@dataclass
class Stock:
    currentStock: int = 0
    lastStockUpdate: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  # timestamp of last stock change


@dataclass
class InventoryItem:
    itemID: int
    name: str
    price: float
    categoryID: int
    supplierID: int
    currentStock: int = 0
    reorderLevel: int = 5      # use prompt reorder? whatcha think
    reorderQty: int = 10       # set default quantity to order

    def to_row(self) -> List[str]:
        return [
            str(self.itemID),
            self.name,
            f"${self.price:.2f}",
            str(self.categoryID),
            str(self.supplierID),
            str(self.currentStock),
            str(self.reorderLevel),
            str(self.reorderQty),
        ]


@dataclass
class PurchaseOrder:
    orderID: int
    orderDate: str
    supplierID: int
    status: str  # OPEN, SUBMITTED, RECEIVED, CANCELED
    # simple line items: {itemID: qty}
    items: Dict[int, int] = field(default_factory=dict)

    def add_item(self, item_id: int, qty: int):
        self.items[item_id] = self.items.get(item_id, 0) + max(0, qty)


#Inventory system (in-memory "database")
class InventorySystem:
    def __init__(self):
        self._item_id = itertools.count(1001)
        self._cat_id = itertools.count(1)
        self._sup_id = itertools.count(1)
        self._po_id = itertools.count(5001)

        self.categories: Dict[int, Category] = {}
        self.suppliers: Dict[int, Supplier] = {}
        self.items: Dict[int, InventoryItem] = {}
        self.orders: Dict[int, PurchaseOrder] = {}

    # Category / Supplier
    def add_category(self, name: str) -> int:
        cid = next(self._cat_id)
        self.categories[cid] = Category(categoryID=cid, name=name)
        return cid

    def add_supplier(self, name: str, contact: str) -> int:
        sid = next(self._sup_id)
        self.suppliers[sid] = Supplier(supplierID=sid, name=name, contactInfo=contact)
        return sid

    # Items
    def add_item(
        self,
        name: str,
        price: float,
        category_id: int,
        supplier_id: int,
        current_stock: int = 0,
        reorder_level: int = 5,
        reorder_qty: int = 10,
    ) -> int: #to indicate return type
        if category_id not in self.categories:
            raise ValueError("Category does not exist")
        if supplier_id not in self.suppliers:
            raise ValueError("Supplier does not exist")
        iid = next(self._item_id)
        self.items[iid] = InventoryItem(
            itemID=iid,
            name=name,
            price=price,
            categoryID=category_id,
            supplierID=supplier_id,
            currentStock=max(0, int(current_stock)),
            reorderLevel=max(0, int(reorder_level)),
            reorderQty=max(1, int(reorder_qty)),
        )
        return iid

    def search_items(self, keyword: str) -> List[InventoryItem]:
        k = keyword.lower().strip()
        return [it for it in self.items.values() if k in it.name.lower()]

    def add_stock(self, item_id: int, qty: int) -> None:
        if item_id not in self.items:
            raise ValueError("Item not found")
        self.items[item_id].currentStock += max(0, int(qty))

    def consume_stock(self, item_id: int, qty: int) -> bool:
        """If successful return true, if not / false, not enough stock""" #co
        if item_id not in self.items:
            raise ValueError("Item not found")
        qty = max(0, int(qty))
        item = self.items[item_id]
        if item.currentStock >= qty:
            item.currentStock -= qty
            return True
        return False

    def low_stock_items(self) -> List[InventoryItem]:
        return [it for it in self.items.values() if it.currentStock <= it.reorderLevel]

    # Purchase Orders
    def create_purchase_order(self, supplier_id: int) -> int:
        if supplier_id not in self.suppliers:
            raise ValueError("Supplier not found")
        oid = next(self._po_id)
        po = PurchaseOrder(
            orderID=oid,
            orderDate=datetime.now().strftime("%Y-%m-%d"),
            supplierID=supplier_id,
            status="OPEN",
        )
        self.orders[oid] = po
        return oid

    def create_order_for_item(self, item_id: int, qty: Optional[int] = None) -> int:
        """Quick order for a single item using its supplier."""
        if item_id not in self.items:
            raise ValueError("Item not found")
        item = self.items[item_id]
        po_id = self.create_purchase_order(item.supplierID)
        self.orders[po_id].add_item(item_id, qty if qty is not None else item.reorderQty)
        return po_id

    def submit_order(self, order_id: int) -> None:
        po = self._get_order(order_id)
        po.status = "SUBMITTED"

    def receive_order(self, order_id: int) -> None:
        po = self._get_order(order_id)
        for item_id, qty in po.items.items():
            if item_id in self.items:
                self.items[item_id].currentStock += qty
        po.status = "RECEIVED"

    def cancel_order(self, order_id: int) -> None:
        po = self._get_order(order_id)
        po.status = "CANCELED"

    def _get_order(self, order_id: int) -> PurchaseOrder:
        if order_id not in self.orders:
            raise ValueError("Order not found")
        return self.orders[order_id]

    # Reporting
    def inventory_table(self) -> List[List[str]]:
        header = ["ID", "Item", "Price", "CatID", "SupID", "Stock", "Reorder", "ReorderQty"] #catID and supID for simplicity
        rows = [header]
        for item in sorted(self.items.values(), key=lambda x: x.itemID):
            rows.append(item.to_row())
        return rows

    def orders_table(self) -> List[List[str]]:
        header = ["OrderID", "Date", "SupplierID", "Status", "Lines (itemID:qty)"]
        rows = [header]
        for po in sorted(self.orders.values(), key=lambda x: x.orderID):
            lines = ", ".join(f"{iid}:{qty}" for iid, qty in po.items.items()) or "-"
            rows.append([str(po.orderID), po.orderDate, str(po.supplierID), po.status, lines])
        return rows


# table printer
def print_table(rows: List[List[str]]) -> None:
    if not rows:
        print("(no data)")
        return
    widths = [max(len(str(col)) for col in col_vals) for col_vals in zip(*rows)]
    for r, row in enumerate(rows):
        line = " | ".join(str(val).ljust(widths[i]) for i, val in enumerate(row))
        print(line)
        if r == 0:
            print("-+-".join("-" * w for w in widths))

# data for testing and demonstration
def seed_demo_data(inv: InventorySystem):
    # categories
    c_food = inv.add_category("Food")
    c_bev = inv.add_category("Beverage")
    c_sup = inv.add_category("Supply")
    # suppliers
    s_main = inv.add_supplier("Main Distributor", "sales@maindist.com / (555) 123-4567")
    s_bakery = inv.add_supplier("Sunrise Bakery", "orders@sunrise.com / (555) 222-3456")
    # items
    inv.add_item("Espresso Beans (1kg)", 16.50, c_bev, s_main, current_stock=8, reorder_level=5, reorder_qty=6)
    inv.add_item("Milk (1L)", 1.20, c_bev, s_main, current_stock=12, reorder_level=8, reorder_qty=12)
    inv.add_item("Croissant", 2.40, c_food, s_bakery, current_stock=6, reorder_level=6, reorder_qty=24)
    inv.add_item("Sugar Packets (box)", 4.99, c_sup, s_main, current_stock=3, reorder_level=5, reorder_qty=10)
    inv.add_item("Cups (100ct)", 6.99, c_sup, s_main, current_stock=15, reorder_level=10, reorder_qty=10)








def main():

    inv = InventorySystem()
    seed_demo_data(inv)


# 4 decreases stock
    menu = """
Café Inventory System
1) View inventory
2) Add item(s) to inventory
3) Search items
4) Record sale/usage
5) Add stock 
6) View low-stock items
7) Create purchase order for an item
8) View purchase orders
9) Receive a purchase order
0) Quit
Choose: """
    while True:

        try:
            choice = input(menu).strip()
        except (EOFError, KeyboardInterrupt):
            break

        try:
            if choice == "1":
                print_table(inv.inventory_table())

            elif choice == "2":
                name = input("Item name: ").strip()
                price = float(input("Price: ").strip())
                print_table([["ID", "Category"]] + [[cid, c.name] for cid, c in inv.categories.items()])
                category_id = int(input("CategoryID: ").strip())
                print_table([["ID", "Supplier"]] + [[sid, s.name] for sid, s in inv.suppliers.items()])
                supplier_id = int(input("SupplierID: ").strip())
                stock = int(input("Starting stock (default 0): ") or "0")
                rlevel = int(input("Reorder level (default 5): ") or "5")
                rqty = int(input("Reorder qty (default 10): ") or "10")
                iid = inv.add_item(name, price, category_id, supplier_id, stock, rlevel, rqty)
                print(f"Added item {iid} - {name}")

            elif choice == "3":
                q = input("Search keyword: ").strip()
                results = inv.search_items(q)
                if not results:
                    print("No matches.")
                else:
                    rows = [["ID", "Item", "Price", "CatID", "SupID", "Stock", "Reorder", "ReorderQty"]]
                    for it in results:
                        rows.append(it.to_row())
                    print_table(rows)

            elif choice == "4":
                iid = int(input("ItemID to consume: ").strip())
                qty = int(input("Quantity used/sold: ").strip())
                ok = inv.consume_stock(iid, qty)
                if ok:
                    print("Stock updated.")
                else:
                    have = inv.items[iid].currentStock if iid in inv.items else 0
                    print(f"Not enough stock. Available: {have}")

            elif choice == "5":
                iid = int(input("ItemID to add stock to: ").strip())
                qty = int(input("Quantity received: ").strip())
                inv.add_stock(iid, qty)
                print("Stock updated.")

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
                        # optional: submit them
                        for poid in created:
                            inv.submit_order(poid)
                        print(f"Created and submitted {len(created)} purchase orders.")

            elif choice == "7":
                iid = int(input("ItemID to order: ").strip())
                qty_in = input("Quantity (blank = default reorder qty): ").strip()
                qty = int(qty_in) if qty_in else None
                poid = inv.create_order_for_item(iid, qty)
                inv.submit_order(poid)
                print(f"Created order {poid} and set to SUBMITTED.")

            elif choice == "8":
                print_table(inv.orders_table())

            elif choice == "9":
                oid = int(input("OrderID to receive: ").strip())
                inv.receive_order(oid)
                print("Order received and stock updated.")

            elif choice == "0":
                print("Goodbye!")
                break

            else:
                print("Invalid choice. Try again.")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()