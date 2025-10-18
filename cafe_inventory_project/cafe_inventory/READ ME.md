OK. So you guys will be wondering what were the changes, they are mostly quality improvements and I implemented some modularization to the code so it's split into different files instead of a single .py file. 



So the original file cafe\_inventory.py already had dataclasses, in-memory storage, helpers, and the CLI loop in one place. It supported categories, suppliers items, basic stock ops, low-stock list, and simple purchase orders. It also had print\_table, seed\_demo\_data, and a text menu. Whis is great. 



**1) Project Structure**



OK, so now it's a small package with clean layers. The benefits of that is that it will be easier to make changes, test, and swap backends without touching the UI. 



This is what it looks like now:



-cafe\_inventory/

&nbsp;- \_\_init\_\_.py           # marks this as a package

&nbsp;-domain.py             # data models + repo interface (protocol)

&nbsp;-infra.py              # in-memory repository implementation

&nbsp;-utils.py              # print\_table + seed\_demo\_data

&nbsp;-app.py                # CLI (menu) only



**2) Domain Models (dataclasses)** 



* The original models were kept, such as Category, Supplier, InventoryItem, and PurchaseOrder.
* **Added**: InventoryItem.partNumber: str
* PurchaseOrder.add\_item() was unchanged



**3) Repo Protocol (backend contract)** 



* **New**: InventoryRepo Protocol in **domain.py** describes what any backend must implement. 
* **New helper methods**:

&nbsp;            

&nbsp;            get\_item(item\_id) -> Optional\[InventoryItem]



&nbsp;            find\_by\_part\_number(part\_number) -> Optional\[InventoryItem]



&nbsp;            resolve\_item\_ref(ref) -> int (accepts ID or part number)



&nbsp;            filter\_by\_category(category\_id) -> List\[InventoryItem]



&nbsp;            filter\_by\_supplier(supplier\_id) -> List\[InventoryItem]



This keeps **app.py** (UI) independent from the concrete storage, it also enables "ID or Part#" everywhere. 



**4) In-memory backend (infra.py)**



* add\_item(..., part\_number="") added with uniqueness check (case-insensitive).
* Wildcard search with \* and ? over name and partNumber (via fnmatch).
* Fielded filters by category and supplier.
* Lookup helpers implemented: get\_item, find\_by\_part\_number, resolve\_item\_ref.



This addresses multiple testing recommendations made by Carly like ID/Part#, wildcard search, fielded queries.



**5) Utilities (utils.py)** 



* print\_table(...) unchanged.
* seed\_demo\_data(...) now seeds realistic part numbers:

&nbsp;            - ESP-1KG, MILK-1L, CROISS, SUGAR-BOX, CUPS-100.



&nbsp;This way when testing we can try “ID or Part#” immediately without manual setup.



**6) CLI (app.py)**



* “View inventory” now shows an OnHand$ column (price × stock).



* “Add item(s)” prompts for Part number (optional).



* “Search items” gets a sub-menu:



1. Name/Part# (supports \* and ?)
   
2. Item ID
   
3. Category ID
   
4. Supplier ID
   
5. Part Number



* “Record sale/usage” and “Add stock” both accept ID or Part#, warn if qty=0, and echo the new qty + OnHand$.



* “Create purchase order for an item” accepts ID or Part# and reminds you of current qty + default reorder qty before confirming.



* Quit now asks “Are you sure? (y/N)”.



This makes what we have of the UX look more polished and have clearer confirmations. Although I know we are making changes to the UI/UX this week too. 





**How to run the software**



* Just open a terminal in the parent folder and then run: **python -m cafe\_inventory.app** 
  
* You will see the menu. Try: 



2\) Add an item (give it a Part number)



3\) Search with wildcards: example: \*milk\* or CUP\*



4/5) Use ID or Part# to consume/add stock



1\) Confirm OnHand$ shows in the table



**VS CODE**



I added a .json file inside a folder named .vscode. That way you can run the program on VS Code too if you prefer that. 



&nbsp; 









