"""
tools_view.py
-------------
Tools tab: CSV import/export.
"""

import os
from tkinter import ttk, messagebox, filedialog


from cafe_inventory.io_csv import export_items_csv, import_items_csv


class ToolsView(ttk.Frame):
    def __init__(self, parent, inv_repo):
        super().__init__(parent, padding=8)
        self.inv = inv_repo
        self._build()

    def _build(self):
        box = ttk.LabelFrame(self, text="CSV Import / Export", padding=10)
        box.pack(fill="x", padx=6, pady=6)

        ttk.Button(box, text="Export items to CSV...", command=self.on_export).pack(side="left", padx=4)
        ttk.Button(box, text="Import items from CSV...", command=self.on_import).pack(side="left", padx=4)

        note = ttk.Label(
            box,
            text=("Tip: Export somewhere easy to find. Import expects headers:\n"
                  "itemID,name,price,categoryID,supplierID,currentStock,reorderLevel,reorderQty,partNumber"),
            justify="left", foreground="#555", wraplength=820
        )
        note.pack(fill="x", pady=(8,0))

    def on_export(self):
        path = filedialog.asksaveasfilename(
            title="Export Items to CSV", defaultextension=".csv",
            filetypes=[("CSV Files","*.csv"), ("All Files","*.*")]
        )
        if not path: return
        try:
            export_items_csv(self.inv, path)
            messagebox.showinfo("Export Complete", f"Exported to:\n{os.path.abspath(path)}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def on_import(self):
        path = filedialog.askopenfilename(
            title="Import Items from CSV",
            filetypes=[("CSV Files","*.csv"), ("All Files","*.*")]
        )
        if not path: return
        try:
            added = import_items_csv(self.inv, path)
            messagebox.showinfo("Import Complete", f"Imported {added} item(s).")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))
