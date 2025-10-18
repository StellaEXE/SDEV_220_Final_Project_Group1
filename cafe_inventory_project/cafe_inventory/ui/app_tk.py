"""
app_tk.py
---------
Tkinter app shell that wires all views into a Notebook.
Run:
  python -m cafe_inventory.ui.app_tk --db sqlite --db-path cafe_inventory.db --seed
"""

import argparse
import tkinter as tk
from tkinter import ttk

from cafe_inventory.infra import InMemoryInventoryRepo
from cafe_inventory.infra_sql import SqlInventoryRepo
from cafe_inventory.utils import seed_demo_data

from cafe_inventory.ui.views.inventory_view import InventoryView
from cafe_inventory.ui.views.master_data_view import MasterDataView
from cafe_inventory.ui.views.tools_view import ToolsView
from cafe_inventory.ui.views.po_view import POView


def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cafe Inventory (Tkinter UI)")
    p.add_argument("--db", choices=["sqlite", "memory"], default="sqlite")
    p.add_argument("--db-path", default="cafe_inventory.db")
    p.add_argument("--seed", action="store_true", help="Seed demo data (idempotent).")
    return p.parse_args()


def make_repo(args: argparse.Namespace):
    if args.db == "sqlite":
        inv = SqlInventoryRepo(args.db_path)
        if args.seed or not inv.list_categories():
            seed_demo_data(inv)
    else:
        inv = InMemoryInventoryRepo()
        seed_demo_data(inv)
    return inv


def main(args: argparse.Namespace) -> None:
    inv = make_repo(args)

    root = tk.Tk()
    root.title("Café Inventory System")
    root.geometry("1100x680")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    inv_tab = InventoryView(nb, inv)
    nb.add(inv_tab, text="Inventory")

    md_tab = MasterDataView(nb, inv)
    nb.add(md_tab, text="Master Data")

    po_tab = POView(nb, inv)
    nb.add(po_tab, text="Purchase Orders")

    tools_tab = ToolsView(nb, inv)
    nb.add(tools_tab, text="Tools")

    root.mainloop()


if __name__ == "__main__":
    main(get_args())
