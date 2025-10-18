"""
infra_sql.py
------------
SQLite implementation of the InventoryRepo protocol.

Features:
- case-insensitive UNIQUE part numbers (NULL allowed)
- wildcard search (* and ?) over name/partNumber
- purchase orders with partial/complete receiving
- reporting tables with Part# and Received%
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from .utils import normalize_part_number
from .domain import Category, Supplier, InventoryItem, PurchaseOrder, InventoryRepo


# ---------- connection helpers ----------

def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db(db_path: str) -> None:
    con = _connect(db_path)
    cur = con.cursor()

    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS categories (
            categoryID   INTEGER PRIMARY KEY,
            name         TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            supplierID   INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            contactInfo  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS items (
            itemID       INTEGER PRIMARY KEY,
            name         TEXT NOT NULL,
            price        REAL NOT NULL,
            categoryID   INTEGER NOT NULL,
            supplierID   INTEGER NOT NULL,
            currentStock INTEGER NOT NULL DEFAULT 0,
            reorderLevel INTEGER NOT NULL DEFAULT 5,
            reorderQty   INTEGER NOT NULL DEFAULT 10,
            partNumber   TEXT UNIQUE COLLATE NOCASE,
            FOREIGN KEY (categoryID) REFERENCES categories(categoryID) ON DELETE RESTRICT,
            FOREIGN KEY (supplierID) REFERENCES suppliers(supplierID) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS orders (
            orderID     INTEGER PRIMARY KEY,
            orderDate   TEXT NOT NULL,         -- YYYY-MM-DD
            supplierID  INTEGER NOT NULL,
            status      TEXT NOT NULL,
            FOREIGN KEY (supplierID) REFERENCES suppliers(supplierID) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            orderID  INTEGER NOT NULL,
            itemID   INTEGER NOT NULL,
            qty      INTEGER NOT NULL,
            PRIMARY KEY (orderID, itemID),
            FOREIGN KEY (orderID) REFERENCES orders(orderID) ON DELETE CASCADE,
            FOREIGN KEY (itemID)  REFERENCES items(itemID)  ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS order_received (
            orderID  INTEGER NOT NULL,
            itemID   INTEGER NOT NULL,
            qty      INTEGER NOT NULL,
            PRIMARY KEY (orderID, itemID),
            FOREIGN KEY (orderID) REFERENCES orders(orderID) ON DELETE CASCADE,
            FOREIGN KEY (itemID)  REFERENCES items(itemID)  ON DELETE RESTRICT
        );
        """
    )
    con.commit()
    con.close()


def _like_from_wildcard(pattern: str) -> str:
    """Convert * ? wildcards to SQL LIKE % _ and lower-case it."""
    pat = (pattern or "").strip()
    if "*" not in pat and "?" not in pat:
        pat = f"*{pat}*"
    return pat.replace("*", "%").replace("?", "_").lower()


# ---------- repo ----------

class SqlInventoryRepo(InventoryRepo):
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(db_path)

    # ---------- helpers ----------
    def _con(self) -> sqlite3.Connection:
        return _connect(self.db_path)

    # ---------- categories / suppliers ----------
    def add_category(self, name: str) -> int:
        with self._con() as con:
            cur = con.execute("INSERT INTO categories(name) VALUES (?)", (name.strip(),))
            return cur.lastrowid

    def add_supplier(self, name: str, contact: str) -> int:
        with self._con() as con:
            cur = con.execute(
                "INSERT INTO suppliers(name, contactInfo) VALUES (?, ?)",
                (name.strip(), contact.strip()),
            )
            return cur.lastrowid

    def list_categories(self) -> List[tuple[int, str]]:
        with self._con() as con:
            rows = con.execute(
                "SELECT categoryID, name FROM categories ORDER BY categoryID"
            ).fetchall()
            return [(r["categoryID"], r["name"]) for r in rows]

    def list_suppliers(self) -> List[tuple[int, str]]:
        with self._con() as con:
            rows = con.execute(
                "SELECT supplierID, name FROM suppliers ORDER BY supplierID"
            ).fetchall()
            return [(r["supplierID"], r["name"]) for r in rows]

    # ---------- items ----------
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
        with self._con() as con:
            # Ensure category/supplier exist
            if not con.execute("SELECT 1 FROM categories WHERE categoryID=?", (category_id,)).fetchone():
                raise ValueError("Category does not exist")
            if not con.execute("SELECT 1 FROM suppliers WHERE supplierID=?", (supplier_id,)).fetchone():
                raise ValueError("Supplier does not exist")

            part_number = normalize_part_number(part_number)

            # UNIQUE constraint on partNumber handles duplicates; pre-check for a nicer message
            if part_number:
                dup = con.execute(
                    "SELECT 1 FROM items WHERE LOWER(partNumber)=LOWER(?)",
                    (part_number,),
                ).fetchone()
                if dup:
                    raise ValueError("Duplicate part number")

            cur = con.execute(
                """
                INSERT INTO items(name, price, categoryID, supplierID, currentStock, reorderLevel, reorderQty, partNumber)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(), float(price), int(category_id), int(supplier_id),
                    max(0, int(current_stock)), max(0, int(reorder_level)), max(1, int(reorder_qty)),
                    part_number.strip() or None,
                ),
            )
            return cur.lastrowid

    def search_items(self, keyword: str) -> List[InventoryItem]:
        like = _like_from_wildcard(keyword)
        with self._con() as con:
            rows = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items
                WHERE LOWER(name) LIKE ? OR LOWER(COALESCE(partNumber,'')) LIKE ?
                ORDER BY itemID
                """,
                (like, like),
            ).fetchall()
            return [InventoryItem(**dict(r)) for r in rows]

    def filter_by_category(self, category_id: int) -> List[InventoryItem]:
        with self._con() as con:
            rows = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items WHERE categoryID=? ORDER BY itemID
                """,
                (int(category_id),),
            ).fetchall()
            return [InventoryItem(**dict(r)) for r in rows]

    def filter_by_supplier(self, supplier_id: int) -> List[InventoryItem]:
        with self._con() as con:
            rows = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items WHERE supplierID=? ORDER BY itemID
                """,
                (int(supplier_id),),
            ).fetchall()
            return [InventoryItem(**dict(r)) for r in rows]

    def add_stock(self, item_id: int, qty: int) -> None:
        with self._con() as con:
            if not con.execute("SELECT 1 FROM items WHERE itemID=?", (item_id,)).fetchone():
                raise ValueError("Item not found")
            con.execute(
                "UPDATE items SET currentStock = currentStock + ? WHERE itemID=?",
                (max(0, int(qty)), int(item_id)),
            )

    def consume_stock(self, item_id: int, qty: int) -> bool:
        qty = max(0, int(qty))
        with self._con() as con:
            row = con.execute("SELECT currentStock FROM items WHERE itemID=?", (item_id,)).fetchone()
            if not row:
                raise ValueError("Item not found")
            have = int(row["currentStock"])
            if have >= qty:
                con.execute("UPDATE items SET currentStock = currentStock - ? WHERE itemID=?", (qty, int(item_id)))
                return True
            return False

    def low_stock_items(self) -> List[InventoryItem]:
        with self._con() as con:
            rows = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items WHERE currentStock <= reorderLevel ORDER BY itemID
                """
            ).fetchall()
            return [InventoryItem(**dict(r)) for r in rows]

    # ---------- lookups ----------
    def get_item(self, item_id: int) -> Optional[InventoryItem]:
        with self._con() as con:
            r = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items WHERE itemID=?
                """,
                (int(item_id),),
            ).fetchone()
            return InventoryItem(**dict(r)) if r else None

    def find_by_part_number(self, part_number: str) -> Optional[InventoryItem]:
        with self._con() as con:
            r = con.execute(
                """
                SELECT itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,
                       COALESCE(partNumber,'') AS partNumber
                FROM items WHERE LOWER(partNumber)=LOWER(?)
                """,
                (normalize_part_number(part_number).strip(),),
            ).fetchone()
            return InventoryItem(**dict(r)) if r else None

    def resolve_item_ref(self, ref: str) -> int:
        s = (ref or "").strip()
        if s.isdigit():
            iid = int(s)
            if self.get_item(iid):
                return iid
            raise ValueError("Item ID not found")
        it = self.find_by_part_number(s)
        if it:
            return it.itemID
        raise ValueError("Item part number not found")

    # ---------- purchase orders ----------
    def create_purchase_order(self, supplier_id: int) -> int:
        with self._con() as con:
            if not con.execute("SELECT 1 FROM suppliers WHERE supplierID=?", (supplier_id,)).fetchone():
                raise ValueError("Supplier not found")
            today = datetime.now().strftime("%Y-%m-%d")
            cur = con.execute(
                "INSERT INTO orders(orderDate, supplierID, status) VALUES (?,?,?)",
                (today, int(supplier_id), "OPEN"),
            )
            return cur.lastrowid

    def create_order_for_item(self, item_id: int, qty: Optional[int] = None) -> int:
        it = self.get_item(item_id)
        if not it:
            raise ValueError("Item not found")
        po_id = self.create_purchase_order(it.supplierID)
        self.add_item_to_order(po_id, item_id, qty if qty is not None else it.reorderQty)
        return po_id

    def add_item_to_order(self, order_id: int, item_id: int, qty: int) -> None:
        with self._con() as con:
            # verify
            po = con.execute("SELECT supplierID FROM orders WHERE orderID=?", (order_id,)).fetchone()
            if not po:
                raise ValueError("Order not found")
            it = con.execute("SELECT supplierID FROM items WHERE itemID=?", (item_id,)).fetchone()
            if not it:
                raise ValueError("Item not found")
            if int(it["supplierID"]) != int(po["supplierID"]):
                raise ValueError("Item's supplier does not match PO supplier")
            # upsert line
            existing = con.execute(
                "SELECT qty FROM order_items WHERE orderID=? AND itemID=?",
                (order_id, item_id),
            ).fetchone()
            if existing:
                con.execute(
                    "UPDATE order_items SET qty = qty + ? WHERE orderID=? AND itemID=?",
                    (max(0, int(qty)), order_id, item_id),
                )
            else:
                con.execute(
                    "INSERT INTO order_items(orderID, itemID, qty) VALUES (?, ?, ?)",
                    (order_id, item_id, max(0, int(qty))),
                )

    def submit_order(self, order_id: int) -> None:
        with self._con() as con:
            if not con.execute("SELECT 1 FROM orders WHERE orderID=?", (order_id,)).fetchone():
                raise ValueError("Order not found")
            con.execute("UPDATE orders SET status='SUBMITTED' WHERE orderID=?", (order_id,))

    def _receive_item(self, con: sqlite3.Connection, order_id: int, item_id: int, qty: int) -> int:
        """Receive bounded qty for a specific item; return actually received."""
        # remaining = ordered - received
        row = con.execute(
            """
            SELECT
                oi.qty AS ordered,
                COALESCE(orv.qty, 0) AS received
            FROM order_items oi
            LEFT JOIN order_received orv
              ON orv.orderID=oi.orderID AND orv.itemID=oi.itemID
            WHERE oi.orderID=? AND oi.itemID=?
            """,
            (order_id, item_id),
        ).fetchone()
        if not row:
            return 0
        remaining = max(0, int(row["ordered"]) - int(row["received"]))
        take = max(0, min(int(qty), remaining))
        if take == 0:
            return 0
        # upsert order_received
        ex = con.execute(
            "SELECT qty FROM order_received WHERE orderID=? AND itemID=?",
            (order_id, item_id),
        ).fetchone()
        if ex:
            con.execute(
                "UPDATE order_received SET qty=qty+? WHERE orderID=? AND itemID=?",
                (take, order_id, item_id),
            )
        else:
            con.execute(
                "INSERT INTO order_received(orderID, itemID, qty) VALUES (?, ?, ?)",
                (order_id, item_id, take),
            )
        # bump stock
        con.execute("UPDATE items SET currentStock = currentStock + ? WHERE itemID=?", (take, item_id))
        return take

    def receive_order(self, order_id: int) -> None:
        with self._con() as con:
            # receive all remaining per line
            lines = con.execute("SELECT itemID FROM order_items WHERE orderID=?", (order_id,)).fetchall()
            if not lines:
                raise ValueError("Order not found")
            any_recv = False
            for r in lines:
                got = self._receive_item(con, order_id, int(r["itemID"]), 10**9)  # effectively 'all remaining'
                any_recv = any_recv or (got > 0)
            # update status
            status = "RECEIVED" if self._is_fully_received(con, order_id) \
                     else ("PARTIAL" if any_recv else "SUBMITTED")
            con.execute("UPDATE orders SET status=? WHERE orderID=?", (status, order_id))

    def receive_order_partial(self, order_id: int, lines: Dict[int, int]) -> None:
        with self._con() as con:
            # validate order existence
            if not con.execute("SELECT 1 FROM orders WHERE orderID=?", (order_id,)).fetchone():
                raise ValueError("Order not found")
            any_recv = False
            for iid, qty in (lines or {}).items():
                got = self._receive_item(con, order_id, int(iid), int(qty))
                any_recv = any_recv or (got > 0)
            status = "RECEIVED" if self._is_fully_received(con, order_id) \
                     else ("PARTIAL" if any_recv else "SUBMITTED")
            con.execute("UPDATE orders SET status=? WHERE orderID=?", (status, order_id))

    def cancel_order(self, order_id: int) -> None:
        with self._con() as con:
            if not con.execute("SELECT 1 FROM orders WHERE orderID=?", (order_id,)).fetchone():
                raise ValueError("Order not found")
            con.execute("UPDATE orders SET status='CANCELED' WHERE orderID=?", (order_id,))

    def _is_fully_received(self, con: sqlite3.Connection, order_id: int) -> bool:
        row = con.execute(
            """
            SELECT
              SUM(oi.qty) AS ordered,
              SUM(COALESCE(orv.qty,0)) AS received
            FROM order_items oi
            LEFT JOIN order_received orv
              ON orv.orderID=oi.orderID AND orv.itemID=oi.itemID
            WHERE oi.orderID=?
            """,
            (order_id,),
        ).fetchone()
        if not row or row["ordered"] is None:
            return False
        return int(row["received"] or 0) >= int(row["ordered"] or 0) and int(row["ordered"] or 0) > 0

    def order_total(self, order_id: int) -> float:
        with self._con() as con:
            row = con.execute(
                """
                SELECT ROUND(COALESCE(SUM(oi.qty * it.price), 2), 2) AS total
                FROM order_items oi
                JOIN items it ON it.itemID = oi.itemID
                WHERE oi.orderID=?
                """,
                (order_id,),
            ).fetchone()
            return float(row["total"] or 0.0)

    def get_order(self, order_id: int) -> PurchaseOrder:
        with self._con() as con:
            po = con.execute(
                "SELECT orderID, orderDate, supplierID, status FROM orders WHERE orderID=?",
                (order_id,),
            ).fetchone()
            if not po:
                raise ValueError("Order not found")
            items = dict(
                (r["itemID"], r["qty"])
                for r in con.execute("SELECT itemID, qty FROM order_items WHERE orderID=?", (order_id,))
            )
            rec = dict(
                (r["itemID"], r["qty"])
                for r in con.execute("SELECT itemID, qty FROM order_received WHERE orderID=?", (order_id,))
            )
            return PurchaseOrder(
                orderID=po["orderID"],
                orderDate=po["orderDate"],
                supplierID=po["supplierID"],
                status=po["status"],
                items=items,
                received=rec,
            )

    # ---------- order search ----------
    def search_orders_by_date(self, ymd: str) -> List[int]:
        with self._con() as con:
            rows = con.execute("SELECT orderID FROM orders WHERE orderDate=?", (ymd.strip(),)).fetchall()
            return [r["orderID"] for r in rows]

    def search_orders_by_item_ref(self, ref: str) -> List[int]:
        try:
            iid = self.resolve_item_ref(ref)
        except Exception:
            return []
        with self._con() as con:
            rows = con.execute(
                "SELECT orderID FROM order_items WHERE itemID=? ORDER BY orderID",
                (iid,),
            ).fetchall()
            return [r["orderID"] for r in rows]

    # ---------- reporting ----------
    def inventory_table(self) -> List[List[str]]:
        with self._con() as con:
            rows = con.execute(
                """
                SELECT itemID,
                       name,
                       COALESCE(partNumber,'') AS partNumber,
                       printf('$%.2f',price) AS price,
                       categoryID,
                       supplierID,
                       currentStock,
                       reorderLevel,
                       reorderQty
                FROM items
                ORDER BY itemID
                """
            ).fetchall()
            out = [["ID","Item","Part#","Price","CatID","SupID","Stock","Reorder","ReorderQty"]]
            for r in rows:
                out.append([
                    str(r["itemID"]),
                    r["name"],
                    r["partNumber"],
                    r["price"],
                    str(r["categoryID"]),
                    str(r["supplierID"]),
                    str(r["currentStock"]),
                    str(r["reorderLevel"]),
                    str(r["reorderQty"]),
                ])
            return out

    def orders_table(self) -> List[List[str]]:
        with self._con() as con:
            rows = con.execute(
                """
                WITH totals AS (
                  SELECT oi.orderID,
                         ROUND(SUM(oi.qty * it.price), 2) AS total,
                         SUM(oi.qty) AS ord_sum
                  FROM order_items oi
                  JOIN items it ON it.itemID=oi.itemID
                  GROUP BY oi.orderID
                ),
                recs AS (
                  SELECT orderID, SUM(qty) AS rec_sum
                  FROM order_received
                  GROUP BY orderID
                )
                SELECT o.orderID, o.orderDate, o.supplierID, o.status,
                       IFNULL(t.total, 0) AS total,
                       IFNULL(t.ord_sum, 0) AS ord_sum,
                       IFNULL(r.rec_sum, 0) AS rec_sum,
                       (
                         SELECT GROUP_CONCAT(itemID || ':' || qty, ', ')
                         FROM order_items WHERE orderID=o.orderID
                       ) AS lines
                FROM orders o
                LEFT JOIN totals t ON t.orderID=o.orderID
                LEFT JOIN recs   r ON r.orderID=o.orderID
                ORDER BY o.orderID
                """
            ).fetchall()
            out = [["OrderID", "Date", "SupplierID", "Status", "Lines (itemID:qty)", "Total$", "Received%"]]
            for r in rows:
                pct = "-"
                if (r["ord_sum"] or 0) > 0:
                    pct = f"{(float(r['rec_sum'] or 0) / float(r['ord_sum'] or 0) * 100):.0f}%"
                out.append([
                    str(r["orderID"]),
                    r["orderDate"],
                    str(r["supplierID"]),
                    r["status"],
                    r["lines"] or "-",
                    f"${float(r['total']):.2f}",
                    pct,
                ])
            return out
