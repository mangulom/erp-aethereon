# Puertos locales (run scripts)

Orden solicitado: `run.py` en 18001 y luego cada uno en el siguiente.

| Script | Servicio / app | Puerto por defecto |
|--------|----------------|--------------------|
| `run.py` | Identity (`services/identity`) | **18001** |
| `run_finance.py` | Finance (`services/finance`, `app.main:app`) | **18002** |
| `run_accounting.py` | Accounting (mismo app Finance) | **18003** |
| `run_budgets.py` | Budgets (mismo app Finance) | **18004** |

Variables de entorno (opcionales) permiten override (`PORT`, `IDENTITY_PORT`, `FINANCE_PORT`, `ACCOUNTING_PORT`, `BUDGETS_PORT`, etc., según cada script).

Frontend (dev): `frontend/proxy.conf.json` enruta `/api` y `/api/v1/finance` a `http://127.0.0.1:18002`.
