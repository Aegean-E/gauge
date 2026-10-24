# gauge

## ⚡ 30-Second Cold-Start Quick Reference

- **Runtime Prerequisites**: <FILL: each runtime this project needs and its minimum version>
- **Canonical Regression Shield Gate**:
  ```bash
  python -m unittest discover -s tests -t .
  ```

### 🛠️ AIKit Commands (run from the AIKit folder)
| Role | Command |
|---|---|
| Status, task and gates | `python aikit.py status gauge` |
| Phase 4: every gate | `python aikit.py check gauge` |
| Repair memory and map, then check | `python aikit.py fix gauge` |
| Resume an interrupted task | `python aikit.py resume gauge` |

## 📦 What's Inside

```text
gauge/
├── .gitignore                <- transient AIKit state excluded
├── README.md
└── .aikit/                   <- this project's memory: record, ledger, decisions
```
