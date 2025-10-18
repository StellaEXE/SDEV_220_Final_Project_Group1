"""
infra.py
--------
In-memory implementation of the InventoryRepo protocol.

Use this backend for fast testing or when you don't need persistence.
It mirrors the SQLite backend behavior, including:
- case-insensitive, unique part numbers
- wildcard search (* and ?) over name/part number
- purchase orders with partial/complete receiving
- reporting tables with Part# column and received %
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import itertools
import re

from .utils import normalize_part_number
from .domain import Category, Supplier, InventoryItem, PurchaseOrder, InventoryRepo


def _wildcard_to_regex(pattern: str) -> re.Pattern:
    """
    Convert shell-like wildcards to a case-insensitive regex:
    * -> .*
    ? -> .
    If no wildcard present, wrap with *...* semantics.
    """
    pat = (pattern or "").strip()
    if "*" not in pat and "?" not in pat:
        pat = f"*{pat}*"
    # escape everything, then replace escaped wildcards
    esc = re.escape(pat)
    esc = esc.replace(r"\*", ".*").replace(r"\?", ".")
    return re.compile(rf"^{esc}$", flags=re.IGNORECASE)


class InMemoryInventoryRepo(InventoryRepo):
    def __init__(self):
        self._item_id = itertools.count(1001)
        self._cat_id = itertools.count(1)
        self._sup_id = itertools.count(1)
        self._po_id = itertools.count(5001)

        self.categories: Dict[int, Category] = {}
        self.suppliers: Dict[int, Supplier] = {}
        self.items: Dict[int, InventoryItem] = {}
        self.orders: Dict[int, PurchaseOrder] = {}

    # ---------- categories / suppliers ----------

    def add_category(self, name: str) -> int:
        cid = next(self._cat_id)
        self.categories[cid] = Category(categoryID=cid, name=name.strip())
        return cid

    def add_supplier(self, name: str, contact: str) -> int:
        sid = next(self._sup_id)
        self.suppliers[sid] = Supplier(supplierID=sid, name=name.strip(), contactInfo=contact.strip())
        return sid

    def list_categories(self) -> List[tuple[int, str]]:
        return [(cid, c.name) for cid, c in sorted(self.categories.items(), key=lambda kv: kv[0])]

    def list_suppliers(self) -> List[tuple[int, str]]:
        return [(sid, s.name) for sid, s in sorted(self.suppliers.items(), key=lambda kv: kv[0])]

    # ---------- items ----------

    def _assert_cat_sup(self, category_id: int, supplier_id: int) -> None:
        if category_id not in self.categories:
            raise ValueError("Category does not exist")
        if supplier_id not in self.suppliers:
            raise ValueError("Supplier does not exist")

    def _assert_unique_part_number(self, part_number: str) -> None:
        pn = normalize_part_number(part_number)
        if not pn:
            return
        for it in self.items.values():
            if normalize_part_number(it.partNumber) == pn:
                raise ValueError("Duplicate part number")

    def add_item(
        self,
        name: str,
        price: float,
        category_id: int,
        supplier_id: int,
        current_stock: int = 0,
        reorder_level: int = 5,
        reorder_qty: int = 10,
        part_number: str = "",
    ) -> int:
        self._assert_cat_sup(category_id, supplier_id)
        part_number = normalize_part_number(part_number)
        self._assert_unique_part_number(part_number)

        iid = next(self._item_id)
        self.items[iid] = InventoryItem(
            itemID=iid,
            name=name.strip(),
            price=float(price),
            categoryID=int(category_id),
            supplierID=int(supplier_id),
            currentStock=max(0, int(current_stock)),
            reorderLevel=max(0, int(reorder_level)),
            reorderQty=max(1, int(reorder_qty)),
            partNumber=part_number,
        )
        return iid

    def _match_wild(self, text: str, rx: re.Pattern) -> bool:
        return bool(rx.match(text or ""))

    def search_items(self, keyword: str) -> List[InventoryItem]:
        rx = _wildcard_to_regex(keyword)
        out: List[InventoryItem] = []
        for it in sorted(self.items.values(), key=lambda x: x.itemID):
            if self._match_wild(it.name, rx) or self._match_wild(it.partNumber or "", rx):
                out.append(it)
        return out

    def filter_by_category(self, category_id: int) -> List[InventoryItem]:
        return [it for it in sorted(self.items.values(), key=lambda x: x.itemID) if it.categoryID == int(category_id)]

    def filter_by_supplier(self, supplier_id: int) -> List[InventoryItem]:
        return [it for it in sorted(self.items.values(), key=lambda x: x.itemID) if it.supplierID == int(supplier_id)]

    def add_stock(self, item_id: int, qty: int) -> None:
        if item_id not in self.items:
            raise ValueError("Item not found")
        self.items[item_id].currentStock += max(0, int(qty))

    def consume_stock(self, item_id: int, qty: int) -> bool:
        if item_id not in self.items:
            raise ValueError("Item not found")
        qty = max(0, int(qty))
        it = self.items[item_id]
        if it.currentStock >= qty:
            it.currentStock -= qty
            return True
        return False

    def low_stock_items(self) -> List[InventoryItem]:
        return [it for it in sorted(self.items.values(), key=lambda x: x.itemID) if it.currentStock <= it.reorderLevel]

    # ---------- lookups ----------

    def get_item(self, item_id: int) -> Optional[InventoryItem]:
        return self.items.get(int(item_id))

    def find_by_part_number(self, part_number: str) -> Optional[InventoryItem]:
        pn = normalize_part_number(part_number)
        if not pn:
            return None
        for it in self.items.values():
            if normalize_part_number(it.partNumber) == pn:
                return it
        return None

    def resolve_item_ref(self, ref: str) -> int:
        s = (ref or "").strip()
        if s.isdigit():
            iid = int(s)
            if iid in self.items:
                return iid
            raise ValueError("Item ID not found")
        it = self.find_by_part_number(s)
        if it:
            return it.itemID
        raise ValueError("Item part number not found")

    # ---------- purchase orders ----------

    def _get_order(self, order_id: int) -> PurchaseOrder:
        if order_id not in self.orders:
            raise ValueError("Order not found")
        return self.orders[order_id]

    def create_purchase_order(self, supplier_id: int) -> int:
        if supplier_id not in self.suppliers:
            raise ValueError("Supplier not found")
        oid = next(self._po_id)
        po = PurchaseOrder(
            orderID=oid,
            orderDate=datetime.now().strftime("%Y-%m-%d"),
            supplierID=int(supplier_id),
            status="OPEN",
        )
        self.orders[oid] = po
        return oid

    def create_order_for_item(self, item_id: int, qty: Optional[int] = None) -> int:
        if item_id not in self.items:
            raise ValueError("Item not found")
        sup = self.items[item_id].supplierID
        poid = self.create_purchase_order(sup)
        self.add_item_to_order(poid, item_id, qty if qty is not None else self.items[item_id].reorderQty)
        return poid

    def add_item_to_order(self, order_id: int, item_id: int, qty: int) -> None:
        if order_id not in self.orders:
            raise ValueError("Order not found")
        if item_id not in self.items:
            raise ValueError("Item not found")
        po = self.orders[order_id]
        it = self.items[item_id]
        if it.supplierID != po.supplierID:
            raise ValueError("Item's supplier does not match PO supplier")
        po.add_item(item_id, qty)

    def submit_order(self, order_id: int) -> None:
        po = self._get_order(order_id)
        po.status = "SUBMITTED"

    def receive_order(self, order_id: int) -> None:
        """
        Receive all remaining quantities for each line.
        Updates item stock and PO status (RECEIVED | PARTIAL | SUBMITTED).
        """
        po = self._get_order(order_id)
        any_recv = False
        for item_id, ordered in po.items.items():
            already = po.received.get(item_id, 0)
            remaining = max(0, ordered - already)
            if remaining > 0 and item_id in self.items:
                self.items[item_id].currentStock += remaining
                po.received[item_id] = already + remaining
                any_recv = True

        total_ordered = sum(po.items.values()) or 0
        total_received = sum(po.received.values()) or 0
        if total_ordered > 0 and total_received >= total_ordered:
            po.status = "RECEIVED"
        elif any_recv:
            po.status = "PARTIAL"
        else:
            if po.status == "OPEN":
                po.status = "SUBMITTED"

    def receive_order_partial(self, order_id: int, lines: Dict[int, int]) -> None:
        """
        Receive given quantities per item line (bounded by remaining).
        """
        po = self._get_order(order_id)
        any_recv = False
        for item_id, qty in (lines or {}).items():
            if item_id not in po.items:
                # ignore unknown line silently (could raise ValueError instead)
                continue
            ordered = po.items[item_id]
            already = po.received.get(item_id, 0)
            remain = max(0, ordered - already)
            take = max(0, min(int(qty), remain))
            if take > 0 and item_id in self.items:
                self.items[item_id].currentStock += take
                po.received[item_id] = already + take
                any_recv = True

        total_ordered = sum(po.items.values()) or 0
        total_received = sum(po.received.values()) or 0
        if total_ordered > 0 and total_received >= total_ordered:
            po.status = "RECEIVED"
        elif any_recv:
            po.status = "PARTIAL"
        else:
            # no change; keep or set to SUBMITTED
            if po.status == "OPEN":
                po.status = "SUBMITTED"

    def cancel_order(self, order_id: int) -> None:
        po = self._get_order(order_id)
        po.status = "CANCELED"

    def order_total(self, order_id: int) -> float:
        po = self._get_order(order_id)
        total = 0.0
        for iid, qty in po.items.items():
            it = self.items.get(iid)
            if it:
                total += float(it.price) * int(qty)
        return round(total, 2)

    def get_order(self, order_id: int) -> PurchaseOrder:
        return self._get_order(order_id)

    # ---------- order search ----------

    def search_orders_by_date(self, ymd: str) -> List[int]:
        ymd = (ymd or "").strip()
        out = []
        for oid, po in sorted(self.orders.items(), key=lambda kv: kv[0]):
            if po.orderDate == ymd:
                out.append(oid)
        return out

    def search_orders_by_item_ref(self, ref: str) -> List[int]:
        try:
            iid = self.resolve_item_ref(ref)
        except Exception:
            return []
        out = []
        for oid, po in sorted(self.orders.items(), key=lambda kv: kv[0]):
            if iid in po.items:
                out.append(oid)
        return out

    # ---------- reporting ----------

    def inventory_table(self) -> List[List[str]]:
        header = ["ID", "Item", "Part#", "Price", "CatID", "SupID", "Stock", "Reorder", "ReorderQty"]
        rows = [header]
        for item in sorted(self.items.values(), key=lambda x: x.itemID):
            rows.append(item.to_row())  # includes Part#
        return rows

    def orders_table(self) -> List[List[str]]:
        """
        Columns:
        OrderID | Date | SupplierID | Status | Lines (itemID:qty) | Total$ | Received%
        """
        header = ["OrderID", "Date", "SupplierID", "Status", "Lines (itemID:qty)", "Total$", "Received%"]
        rows = [header]
        for oid, po in sorted(self.orders.items(), key=lambda kv: kv[0]):
            lines = ", ".join(f"{iid}:{qty}" for iid, qty in po.items.items()) or "-"
            total = self.order_total(oid)
            ord_sum = sum(po.items.values()) or 0
            rec_sum = sum(po.received.values()) or 0
            pct = "-" if ord_sum == 0 else f"{(rec_sum / ord_sum) * 100:.0f}%"
            rows.append([
                str(oid),
                po.orderDate,
                str(po.supplierID),
                po.status,
                lines,
                f"${total:.2f}",
                pct,
            ])
        return rows
