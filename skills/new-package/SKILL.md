---
name: new-package
description: Scaffolds pkg/ + tests/ with exports-only __init__. Use when the task is create a package or project structure. Do not use for one function on an existing module.
---

Action: edit
Path: pkg/total_price.py
```python
def total_price(quantity: int, unit_price: int) -> int:
    return quantity * unit_price
```

Keep pkg/__init__.py exports-only. Next add tests/test_total_price.py
for the new function. One noun per module. A CLI uses argparse. HTTP uses
urllib. Token from the environment. No curl.
