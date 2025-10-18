"""
master_data_view.py
-------------------
Master Data tab: Categories & Suppliers (view + add).
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


class MasterDataView(ttk.Frame):
    def __init__(self, parent, inv_repo):
        super().__init__(parent, padding=8)
        self.inv = inv_repo
        self._build()
        self.refresh_cats()
        self.refresh_sups()

    def _build(self):
        container = ttk.Frame(self); container.pack(fill="both", expand=True)

        left = ttk.LabelFrame(container, text="Categories", padding=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctop = ttk.Frame(left); ctop.pack(fill="x")
        ttk.Button(ctop, text="Add Category", command=self.on_add_category).pack(side="left")
        ttk.Button(ctop, text="Refresh", command=self.refresh_cats).pack(side="left", padx=6)
        self.tree_cat = ttk.Treeview(left, columns=("ID","Name"), show="headings", height=14)
        self.tree_cat.heading("ID", text="ID"); self.tree_cat.column("ID", width=80, anchor="w")
        self.tree_cat.heading("Name", text="Name"); self.tree_cat.column("Name", width=260, anchor="w")
        self.tree_cat.pack(fill="both", expand=True, pady=(6,0))

        right = ttk.LabelFrame(container, text="Suppliers", padding=8)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        stop = ttk.Frame(right); stop.pack(fill="x")
        ttk.Button(stop, text="Add Supplier", command=self.on_add_supplier).pack(side="left")
        ttk.Button(stop, text="Refresh", command=self.refresh_sups).pack(side="left", padx=6)
        self.tree_sup = ttk.Treeview(right, columns=("ID","Name","Contact"), show="headings", height=14)
        for c,w in (("ID",80),("Name",200),("Contact",320)):
            self.tree_sup.heading(c, text=c); self.tree_sup.column(c, width=w, anchor="w")
        self.tree_sup.pack(fill="both", expand=True, pady=(6,0))

        self.status = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status, anchor="w").pack(fill="x", pady=(6,0))

    def refresh_cats(self):
        for i in self.tree_cat.get_children(""): self.tree_cat.delete(i)
        cats = self.inv.list_categories() or []
        for cid, name in cats:
            self.tree_cat.insert("", "end", values=(cid, name))
        self._update_status()

    def refresh_sups(self):
        for i in self.tree_sup.get_children(""): self.tree_sup.delete(i)
        sups = self.inv.list_suppliers() or []
        # If you want contact shown, implement list_suppliers_full() in repos.
        for sid, name in sups:
            self.tree_sup.insert("", "end", values=(sid, name, ""))  # contact not listed by repo
        self._update_status()

    def _update_status(self):
        self.status.set(f"Categories: {len(self.tree_cat.get_children(''))} | "
                        f"Suppliers: {len(self.tree_sup.get_children(''))}")

    def on_add_category(self):
        try:
            name = simpledialog.askstring("Add Category", "Name:", parent=self) or ""
            if not name.strip(): return
            cid = self.inv.add_category(name.strip())
            messagebox.showinfo("Success", f"Added category {cid}: {name}")
            self.refresh_cats()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_add_supplier(self):
        try:
            name = simpledialog.askstring("Add Supplier", "Name:", parent=self) or ""
            if not name.strip(): return
            contact = simpledialog.askstring("Add Supplier", "Contact info (email/phone):", parent=self) or ""
            sid = self.inv.add_supplier(name.strip(), contact.strip())
            messagebox.showinfo("Success", f"Added supplier {sid}: {name}")
            self.refresh_sups()
        except Exception as e:
            messagebox.showerror("Error", str(e))
