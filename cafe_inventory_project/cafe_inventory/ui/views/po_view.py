"""
po_view.py
----------
Purchase Orders tab:
- Create PO: pick supplier, add multiple items, submit.
- Receive PO: enter PO ID and receive full or partial.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Dict

from cafe_inventory.utils import normalize_part_number


class POView(ttk.Frame):
    def __init__(self, parent, inv_repo):
        super().__init__(parent, padding=8)
        self.inv = inv_repo
        self._build_create()
        self._build_receive()

    # -------- CREATE PO --------
    def _build_create(self):
        box = ttk.LabelFrame(self, text="Create Purchase Order", padding=8)
        box.pack(fill="x", pady=(0,8))

        row1 = ttk.Frame(box); row1.pack(fill="x")
        ttk.Label(row1, text="Supplier ID:").pack(side="left")
        self.supplier_id_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.supplier_id_var, width=8).pack(side="left", padx=6)
        ttk.Button(row1, text="List Suppliers", command=self._show_suppliers).pack(side="left", padx=4)
        ttk.Button(row1, text="Start PO", command=self.on_start_po).pack(side="left", padx=8)

        self.current_poid = None
        self.lines: Dict[int,int] = {}
        self.lines_var = tk.StringVar(value="No PO started.")
        ttk.Label(box, textvariable=self.lines_var, foreground="#555", justify="left").pack(fill="x", pady=(8,4))

        row2 = ttk.Frame(box); row2.pack(fill="x")
        ttk.Button(row2, text="Add Line", command=self.on_add_po_line).pack(side="left")
        ttk.Button(row2, text="Submit PO", command=self.on_submit_po).pack(side="left", padx=6)
        ttk.Button(row2, text="Cancel PO", command=self.on_cancel_po).pack(side="left")

    def _show_suppliers(self):
        sups = self.inv.list_suppliers() or []
        messagebox.showinfo("Suppliers", "\n".join(f"{sid}: {nm}" for sid, nm in sups) or "(none)")

    def on_start_po(self):
        try:
            sid = int((self.supplier_id_var.get() or "0").strip())
            if sid <= 0: raise ValueError
        except:
            messagebox.showwarning("Input", "Enter a valid Supplier ID."); return
        try:
            self.current_poid = self.inv.create_purchase_order(sid)
            self.lines = {}
            self._update_lines_label()
            messagebox.showinfo("PO", f"Started PO {self.current_poid}. Add lines, then Submit.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_po_line(self):
        if not self.current_poid:
            messagebox.showwarning("PO", "Start a PO first."); return
        try:
            ref = simpledialog.askstring("Add Line", "Item (ID or Part#):", parent=self)
            if not ref: return
            iid = self._resolve_ref(ref)
            it = self.inv.get_item(iid)
            if it.supplierID != self._get_po_supplier(self.current_poid):
                messagebox.showwarning("PO", f"Item supplier {it.supplierID} != PO supplier."); return
            qty_raw = simpledialog.askstring("Add Line", f"Quantity (default {it.reorderQty}):", parent=self) or ""
            qty = it.reorderQty if qty_raw.strip() == "" else max(1, int(qty_raw))
            self.inv.add_item_to_order(self.current_poid, iid, qty)
            self.lines[iid] = self.lines.get(iid, 0) + qty
            self._update_lines_label()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_submit_po(self):
        if not self.current_poid:
            messagebox.showwarning("PO", "Start a PO first."); return
        try:
            total = self.inv.order_total(self.current_poid)
            if messagebox.askyesno("Submit", f"Submit PO {self.current_poid}?\nTotal: ${total:.2f}"):
                self.inv.submit_order(self.current_poid)
                messagebox.showinfo("PO", f"PO {self.current_poid} submitted.")
                self.current_poid = None
                self.lines = {}
                self._update_lines_label()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_cancel_po(self):
        if not self.current_poid: return
        try:
            self.inv.cancel_order(self.current_poid)
            messagebox.showinfo("PO", f"PO {self.current_poid} canceled.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.current_poid = None
            self.lines = {}
            self._update_lines_label()

    def _get_po_supplier(self, poid: int) -> int:
        po = self.inv.get_order(poid)
        return int(po.supplierID)

    def _update_lines_label(self):
        if not self.current_poid:
            self.lines_var.set("No PO started.")
            return
        if not self.lines:
            self.lines_var.set(f"PO {self.current_poid}: (no lines)")
            return
        lines_s = ", ".join(f"{iid}:{qty}" for iid, qty in self.lines.items())
        total = self.inv.order_total(self.current_poid)
        self.lines_var.set(f"PO {self.current_poid} | Lines: {lines_s} | Total ${total:.2f}")

    # -------- RECEIVE PO --------
    def _build_receive(self):
        box = ttk.LabelFrame(self, text="Receive Purchase Order", padding=8)
        box.pack(fill="x")

        row1 = ttk.Frame(box); row1.pack(fill="x")
        ttk.Label(row1, text="PO ID:").pack(side="left")
        self.rec_poid_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.rec_poid_var, width=8).pack(side="left", padx=6)
        ttk.Button(row1, text="Receive FULL", command=self.on_receive_full).pack(side="left", padx=6)
        ttk.Button(row1, text="Receive PARTIAL", command=self.on_receive_partial).pack(side="left")

        self.rec_info = tk.StringVar(value="")
        ttk.Label(box, textvariable=self.rec_info, foreground="#555").pack(fill="x", pady=(8,0))

    def on_receive_full(self):
        poid = self._get_rec_id()
        if poid is None: return
        try:
            self.inv.receive_order(poid)
            st = self.inv.get_order(poid).status
            messagebox.showinfo("Receive", f"PO {poid} received. Status={st}")
            self._refresh_rec_info(poid)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_receive_partial(self):
        poid = self._get_rec_id()
        if poid is None: return
        try:
            po = self.inv.get_order(poid)
            lines = {}
            for iid, ordered in po.items.items():
                rec = po.received.get(iid, 0)
                remain = ordered - rec
                if remain <= 0: continue
                qty_raw = simpledialog.askstring("Partial Receive", f"Item {iid} remain {remain}:")
                if qty_raw is None: continue
                try:
                    q = max(0, int(qty_raw.strip() or "0"))
                except:
                    q = 0
                if q > 0:
                    lines[iid] = min(q, remain)
            if lines:
                self.inv.receive_order_partial(poid, lines)
                st = self.inv.get_order(poid).status
                messagebox.showinfo("Receive", f"PO {poid} updated. Status={st}")
            self._refresh_rec_info(poid)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _refresh_rec_info(self, poid: int):
        try:
            po = self.inv.get_order(poid)
            total = self.inv.order_total(poid)
            info = [f"PO {po.orderID} | Date {po.orderDate} | Supplier {po.supplierID} | Status {po.status} | Total ${total:.2f}",
                    "Lines:"]
            for iid, ordered in po.items.items():
                rec = po.received.get(iid,0)
                info.append(f"  {iid}: ordered {ordered}, received {rec}, remaining {ordered-rec}")
            self.rec_info.set("\n".join(info))
        except Exception:
            self.rec_info.set("")

    def _get_rec_id(self):
        raw = (self.rec_poid_var.get() or "").strip()
        try:
            return int(raw)
        except:
            messagebox.showwarning("Input", "Enter a valid PO ID.")
            return None

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
