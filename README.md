# Ilumina Mi Vida – Inventory Management System

A web app for tracking inventory, sales, restocks, gifts and losses, with a **tamper-evident audit log** and one-click **Excel reports**. Built with Python and Streamlit for a real organization that sells handmade bracelets, replacing manual spreadsheets and saving an estimated 6–8 hours per week for a production team of 12 people.

> **Note:** this repository contains code only. No real business data, images or credentials are included.


https://github.com/user-attachments/assets/3d60cfbb-0397-41b5-ad28-d0965c8c178c



## The problem

The team tracked stock, sales per location, gifts and thefts by hand across spreadsheets. Errors were common, corrections left no trace, and nobody could tell who changed what or when. They needed a simple tool that non-technical staff could use daily and that management could trust for accounting.

## What it does

| Module | Description |
|---|---|
| **Inventory** | Add, edit and archive products with photo, material, price and stock. Filter by code, material or description, and see sold units and accumulated revenue per item. |
| **Movements** | Register **sales** (by sale location), **restocks**, **gifts** and **losses/thefts**. Stock is validated: the system rejects any outflow larger than available stock. |
| **Materials & Locations** | Manage the catalogs the system depends on. Soft-delete and restore without breaking history. |
| **History & Audit** | Full transaction history with a per-item timeline. Wrong entries are never overwritten: they are marked as *superseded* and replaced by a corrected record with a mandatory reason. |
| **Excel Reports** | One-click `.xlsx` export: one sheet per material, revenue and loss totals, current stock, and a chronological grid of restocks, gifts, losses and sales by location. |
| **User Guide** | Built-in operating manual for staff. |

## Technical highlights

- **Tamper-evident audit log.** Every history row stores a SHA-256 hash chained to the previous one. The app re-verifies the chain and shows an integrity indicator, flagging any row altered directly in the database.
- **Non-destructive corrections.** Edits and corrections are logged with old values, new values and a reason; stock, totals and revenue are recalculated automatically.
- **Cloud persistence with resilience.** Data lives in SQLite locally and in [Turso](https://turso.tech) (libSQL) in production. A cursor wrapper reconnects automatically when a cloud stream expires.
- **Concurrency safety.** Database access is serialized with a lock to avoid conflicting writes from simultaneous users.
- **Relational design with constraints.** Tables for materials, locations, items and history, with `CHECK` constraints (non-negative prices and stock), unique names and indexes on the most queried history fields.
- **Security logging.** Sign-ins, failed attempts and sign-outs are recorded in the audit log.
- **Image handling.** Product photos are stored with generated thumbnails for fast table previews.

## Tech stack

Python · Streamlit · SQLite / libSQL (Turso) · pandas · Pillow · openpyxl · XlsxWriter

## Project structure

```
.
├── app.py                      # Streamlit UI (tabs, forms, dialogs)
├── requirements.txt
├── .streamlit/config.toml      # Streamlit configuration
└── src/
    ├── services/
    │   ├── database.py         # Connection, schema, Turso reconnection wrapper
    │   ├── inventory_service.py# Business logic: items, movements, corrections, log integrity
    │   └── export_service.py   # Excel report generation
    └── utils/
        └── image_utils.py      # Thumbnail processing
```

## Run it locally

```bash
git clone https://github.com/Juanpaestanol/Ilumina-Mi-Vida-inventario.git
cd Ilumina-Mi-Vida-inventario
pip install -r requirements.txt
streamlit run app.py
```

Before the first run, create `.streamlit/secrets.toml` with `APP_PASSWORD` and `SESSION_SALT` (see Configuration below). The database defaults to a local SQLite file (`ilumina.db`), so no cloud account is needed to try it.

## Configuration

Secrets are read from Streamlit secrets (`.streamlit/secrets.toml`, which is git-ignored) or from environment variables. Never commit real values.

```toml
# Required
APP_PASSWORD = "<shared-access-password>"
SESSION_SALT = "<long-random-string>"

# Optional: remote Turso (libSQL) database.
# If both are set the app uses Turso; otherwise it falls back to local SQLite.
TURSO_DATABASE_URL = "libsql://<your-database>.turso.io"
TURSO_AUTH_TOKEN = "<your-token>"
```

## Impact

Based on the team's own estimate, the system saves roughly **6–8 hours per week** that were previously spent on manual stock counts, spreadsheet updates and reconciling sales, gifts and losses. It also gives management a verifiable history of every change.

## What I learned

- Designing an append-only audit trail and why corrections should supersede records instead of editing them.
- Translating a non-technical team's workflow into a data model and a usable interface.
- Dealing with real-world constraints: concurrent users, unstable cloud connections and privacy of business data.


## Resumen en español

Sistema web de inventario para la organización *Ilumina Mi Vida*: registra altas, ventas por lugar, resurtidos, regalos y pérdidas; valida el stock; conserva un historial con cadena de hashes SHA-256 que detecta alteraciones; permite corregir transacciones sin borrar el original; y genera reportes consolidados en Excel. Hecho con Python, Streamlit, SQLite/Turso y pandas.

## Author

**Juan Pablo Estañol Solís** – Physicist | Data Analysis & Scientific Programming
[LinkedIn](https://www.linkedin.com/in/juan-pablo-esta%C3%B1ol-sol%C3%ADs-680191200) · [GitHub](https://github.com/Juanpaestanol)
