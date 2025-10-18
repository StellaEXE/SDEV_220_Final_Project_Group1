"""
inventory_view.py
-----------------
Inventory tab: browse/search items, add item, add stock, record sale/usage.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Any

from cafe_inventory.utils import normalize_part_number


class InventoryView(ttk.Frame):
    def __init__(self, parent, inv_repo):
        super().__init__(parent, padding=8)
        self.inv = inv_repo
        self._build()
        self.refresh()

    # UI
    def _build(self):
        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text="Search (*, ?):").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.search_var, width=32).pack(side="left", padx=6)
        ttk.Button(top, text="Search", command=self.on_search).pack(side="left")
        ttk.Button(top, text="Clear", command=self.on_clear).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left", padx=4)

        actions = ttk.Frame(self); actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="Add Item", command=self.on_add_item).pack(side="left")
        ttk.Button(actions, text="Add Stock", command=self.on_add_stock).pack(side="left", padx=6)
        ttk.Button(actions, text="Record Sale/Usage", command=self.on_consume).pack(side="left", padx=6)

        cols = ("ID","Item","Part#","Price","CatID","SupID","Stock","Reorder","ReorderQty","OnHand$")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22)
        for c in cols:
            self.tree.heading(c, text=c, command=lambda col=c: self._sort_by(col, False))
            self.tree.column(c, width=100 if c not in ("Item","Part#") else 240, anchor="w")
        self.tree.pack(fill="both", expand=True)

        self.status = tk.StringVar(value="Ready.")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", pady=(4, 0))

    # Sort helper
    def _sort_by(self, col: str, descending: bool):
        def cast(v: str) -> Any:
            try:
                return float(v.replace("$",""))
            except Exception:
                return v
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        data.sort(key=lambda t: cast(t[0]), reverse=descending)
        for i, (_, k) in enumerate(data):
            self.tree.move(k, "", i)
        self.tree.heading(col, command=lambda: self._sort_by(col, not descending))

    # Data
    def refresh(self):
        for k in self.tree.get_children(""):
            self.tree.delete(k)
        rows = self.inv.inventory_table()
        if not rows or len(rows) < 2:
            self.status.set("No items.")
            return
        idx = {h: rows[0].index(h) for h in rows[0]}
        for r in rows[1:]:
            price = float(str(r[idx["Price"]]).replace("$",""))
            stock = int(r[idx["Stock"]])
            item_id = int(r[idx["ID"]])
            it = self.inv.get_item(item_id)
            part = getattr(it, "partNumber", "") or (r[idx["Part#"]] if "Part#" in idx else "")
            vals = (
                r[idx["ID"]], r[idx["Item"]], part, f"${price:.2f}",
                r[idx["CatID"]], r[idx["SupID"]], r[idx["Stock"]],
                r[idx["Reorder"]], r[idx["ReorderQty"]], f"${price*stock:.2f}"
            )
            self.tree.insert("", "end", values=vals)
        self.status.set(f"Loaded {len(rows)-1} items.")

    def on_search(self):
        patt = self.search_var.get().strip()
        if not patt:
            self.refresh(); return
        for k in self.tree.get_children(""):
            self.tree.delete(k)
        count = 0
        for it in self.inv.search_items(patt):
            onhand = float(it.price) * int(it.currentStock)
            self.tree.insert("", "end", values=(
                it.itemID, it.name, it.partNumber or "", f"${it.price:.2f}",
                it.categoryID, it.supplierID, it.currentStock,
                it.reorderLevel, it.reorderQty, f"${onhand:.2f}"
            ))
            count += 1
        self.status.set(f"Search: {count} match(es).")

    def on_clear(self):
        self.search_var.set("")
        self.refresh()

    # Actions
    def on_add_item(self):
        try:
            name = simpledialog.askstring("Add Item", "Name:", parent=self) or ""
            if not name.strip(): return
            price = self._ask_float("Price:")
            cats = self.inv.list_categories()
            messagebox.showinfo("Categories", "\n".join(f"{cid}: {nm}" for cid, nm in cats) or "(none)")
            cid = self._ask_int("Category ID:")
            sups = self.inv.list_suppliers()
            messagebox.showinfo("Suppliers", "\n".join(f"{sid}: {nm}" for sid, nm in sups) or "(none)")
            sid = self._ask_int("Supplier ID:")
            pn = normalize_part_number(simpledialog.askstring("Add Item","Part number (optional):",parent=self) or "")
            stock  = self._ask_int("Starting stock (blank=0):", allow_blank=True) or 0
            rlevel = self._ask_int("Reorder level (blank=5):", allow_blank=True) or 5
            rqty   = self._ask_int("Reorder qty (blank=10):", allow_blank=True) or 10
            iid = self.inv.add_item(name, float(price), cid, sid, stock, rlevel, rqty, part_number=pn)
            messagebox.showinfo("Success", f"Added item {iid}: {name}")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_stock(self):
        try:
            ref = simpledialog.askstring("Add Stock", "Item (ID or Part#):", parent=self)
            if not ref: return
            qty = self._ask_int("Quantity received:", min_v=1)
            iid = self._resolve_ref(ref)
            self.inv.add_stock(iid, qty)
            messagebox.showinfo("Success", "Stock updated.")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_consume(self):
        try:
            ref = simpledialog.askstring("Record Sale/Usage", "Item (ID or Part#):", parent=self)
            if not ref: return
            qty = self._ask_int("Quantity used/sold:", min_v=1)
            iid = self._resolve_ref(ref)
            ok = self.inv.consume_stock(iid, qty)
            if ok: messagebox.showinfo("Success", "Stock updated.")
            else:  messagebox.showwarning("Not enough", "Not enough stock.")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Helpers
    def _resolve_ref(self, ref: str) -> int:
        s = (ref or "").strip()
        if s.isdigit():
            iid = int(s)
            if self.inv.get_item(iid): return iid
            raise ValueError("Item ID not found")
        it = self.inv.find_by_part_number(normalize_part_number(s))
        if it: return it.itemID
        raise ValueError("Item part number not found")

    def _ask_int(self, title: str, min_v: int|None=None, allow_blank: bool=False) -> int|None:
        while True:
            raw = simpledialog.askstring("Input", title, parent=self)
            if raw is None: raise Exception("Cancelled")
            raw = raw.strip()
            if allow_blank and raw == "": return None
            try: val = int(raw)
            except: messagebox.showwarning("Invalid","Enter a whole number."); continue
            if min_v is not None and val < min_v:
                messagebox.showwarning("Invalid", f"Must be ≥ {min_v}"); continue
            return val

    def _ask_float(self, title: str) -> float:
        while True:
            raw = simpledialog.askstring("Input", title, parent=self)
            if raw is None: raise Exception("Cancelled")
            try: return float(raw.strip())
            except: messagebox.showwarning("Invalid","Enter a number like 12.34.")
