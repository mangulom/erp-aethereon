# Aplicar migraciones de Presupuestos (para evitar 500)

Ejecuta en tu base de datos (Postgres/Supabase) los SQL de:

- `database/migrations/017_budget_control.sql`
- `database/migrations/018_budget_cdp_requester.sql`

Y si usas la carpeta `supabase/migrations`, también aplica:
- `supabase/migrations/20250101000014_budget_control.sql`
- `supabase/migrations/20250101000015_budget_cdp_requester.sql`

Tablas creadas: `budget_cdp`, `budget_commitments`, `payment_orders` (con `requester_area` en CDP).

## Ejemplos

**Supabase (Dashboard):** abre SQL Editor → pega el contenido de cada `.sql` → Run (en orden 017 luego 018).

**Postgres local (psql), ejemplo típico:**
```bash
psql "postgresql://postgres:TU_PASSWORD@localhost:5432/TU_BASE_DE_DATOS" -f database/migrations/017_budget_control.sql
psql "postgresql://postgres:TU_PASSWORD@localhost:5432/TU_BASE_DE_DATOS" -f database/migrations/018_budget_cdp_requester.sql
```

**PowerShell (local):**
```powershell
psql "postgresql://postgres:TU_PASSWORD@localhost:5432/TU_BASE_DE_DATOS" -f "database/migrations/017_budget_control.sql"
psql "postgresql://postgres:TU_PASSWORD@localhost:5432/TU_BASE_DE_DATOS" -f "database/migrations/018_budget_cdp_requester.sql"
```

**Si ya tienes `DATABASE_URL` en tu `.env` del backend:** puedes usar esa misma URL en lugar de escribirla a mano.


