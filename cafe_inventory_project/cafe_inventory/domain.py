"""
domain.py
----------
Core data models (Category, Supplier, InventoryItem, PurchaseOrder)
and the InventoryRepo interface describing how an inventory backend should behave.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

# ----- Domain models -----
@dataclass
class Category:
    """Represents a product category, e.g., Food or Beverage."""
    categoryID: int
    name: str


@dataclass
class Supplier:
    """Represents a supplier with contact info."""
    supplierID: int
    name: str
    contactInfo: str


@dataclass
class InventoryItem:
    """Represents an item in inventory (name, price, stock, reorder info)."""
    itemID: int
    name: str
    price: float
    categoryID: int
    supplierID: int
    currentStock: int = 0
    reorderLevel: int = 5
    reorderQty: int = 10
    partNumber: str = ""  # e.g., "ESP-1KG"

# domain.py — inside InventoryItem
def to_row(self) -> list[str]:
    """Row used by CLI tables (now includes Part#)."""
    return [
        str(self.itemID),
        self.name,
        (self.partNumber or ""),
        f"${self.price:.2f}",
        str(self.categoryID),
        str(self.supplierID),
        str(self.currentStock),
        str(self.reorderLevel),
        str(self.reorderQty),
    ]


@dataclass
class PurchaseOrder:
    """
    Represents a purchase order with multiple item lines (itemID→qty).
    Supports partial receiving via received dict.
    """
    orderID: int
    orderDate: str
    supplierID: int
    status: str  # OPEN, SUBMITTED, PARTIAL, RECEIVED, CANCELED
    items: Dict[int, int] = field(default_factory=dict)        # ordered qtys
    received: Dict[int, int] = field(default_factory=dict)     # received so far

    def add_item(self, item_id: int, qty: int) -> None:
        self.items[item_id] = self.items.get(item_id, 0) + max(0, int(qty))

    def receive_item(self, item_id: int, qty: int) -> int:
        """Increase received qty for item (bounded by remaining). Returns actually received."""
        ordered = self.items.get(item_id, 0)
        already = self.received.get(item_id, 0)
        remaining = max(0, ordered - already)
        to_recv = max(0, min(int(qty), remaining))
        if to_recv > 0:
            self.received[item_id] = already + to_recv
        return to_recv

    def remaining_qty(self, item_id: int) -> int:
        return max(0, self.items.get(item_id, 0) - self.received.get(item_id, 0))

    def is_fully_received(self) -> bool:
        return all(self.received.get(i, 0) >= q for i, q in self.items.items()) and bool(self.items)


# ----- Repository interface (backend contract) -----
class InventoryRepo(Protocol):
    # categories / suppliers
    def add_category(self, name: str) -> int: ...
    def add_supplier(self, name: str, contact: str) -> int: ...
    def list_categories(self) -> list[tuple[int, str]]: ...
    def list_suppliers(self) -> list[tuple[int, str]]: ...

    # lookups / search helpers
    def get_item(self, item_id: int) -> Optional[InventoryItem]: ...
    def find_by_part_number(self, part_number: str) -> Optional[InventoryItem]: ...
    def resolve_item_ref(self, ref: str) -> int: ...
    def filter_by_category(self, category_id: int) -> List[InventoryItem]: ...
    def filter_by_supplier(self, supplier_id: int) -> List[InventoryItem]: ...

    # items
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
    ) -> int: ...
    def search_items(self, keyword: str) -> List[InventoryItem]: ...
    def add_stock(self, item_id: int, qty: int) -> None: ...
    def consume_stock(self, item_id: int, qty: int) -> bool: ...
    def low_stock_items(self) -> List[InventoryItem]: ...

    # purchase orders
    def create_purchase_order(self, supplier_id: int) -> int: ...
    def create_order_for_item(self, item_id: int, qty: Optional[int] = None) -> int: ...
    def add_item_to_order(self, order_id: int, item_id: int, qty: int) -> None: ...
    def submit_order(self, order_id: int) -> None: ...
    def receive_order(self, order_id: int) -> None: ...
    def receive_order_partial(self, order_id: int, lines: Dict[int, int]) -> None: ...
    def cancel_order(self, order_id: int) -> None: ...
    def order_total(self, order_id: int) -> float: ...
    def get_order(self, order_id: int) -> PurchaseOrder: ...

    # order search
    def search_orders_by_date(self, ymd: str) -> List[int]: ...
    def search_orders_by_item_ref(self, ref: str) -> List[int]: ...

    # reporting
    def inventory_table(self) -> List[List[str]]: ...
    def orders_table(self) -> List[List[str]]: ...
