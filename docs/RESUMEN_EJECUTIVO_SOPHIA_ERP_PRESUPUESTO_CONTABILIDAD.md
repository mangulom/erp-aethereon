# Resumen Ejecutivo — Sophia ERP (Finanzas, Contabilidad y Presupuesto)

**Fecha:** 2026-11-24  
**Ámbito:** Módulo financiero/contable/presupuestal (backend `backend/services/finance`, frontend Angular), flujo CDP → Compromiso → Orden de pago, integración contable básica (asientos borrador).

## 1) Objetivo alcanzado (trabajo realizado)
- Alineación de puertos y proxy: Identity 18001, Finance 18002, Accounting 18003, Budgets 18004; proxy frontend ajustado.
- Flujo presupuestal con persistencia y validaciones: CDP, Compromisos, Órdenes de pago (incl. área solicitante, proveedor, cuenta bancaria en OP).
- **FC-002**: validación de saldo de CDP al crear/actualizar compromisos.
- **FC-003 (parcial)**: endpoints y acciones UI para eliminar CDP/compromisos/OP (con restricciones) y actualización (PATCH) en backend; UI de PIA mejorada (cabecera + líneas con montos por cuenta).
- **FC-001 (implementado en borrador)**:
  - Al pasar compromiso a **devengado**: creación de asiento contable **borrador** (gasto configurable `BUDGET_DEVENGO_EXPENSE_ACCOUNT_CODE`, por pagar `BUDGET_DEVENGO_PAYABLE_ACCOUNT_CODE`, auxiliar proveedor).
  - Al marcar Orden de pago como **pagada** (con `bank_account_id` y `commitment_id`): asiento **borrador** Dr 421x/por pagar / Cr cuenta bancaria de tesorería.
- Marca visible **Sophia ERP** en frontend (puntos clave). Se añadió agente documental `docs/AGENTE_ANALISTA_FINANCIERO_CONTABLE_PRESUPUESTAL.md`.

## 2) Entregables técnicos (archivos clave)
- Migraciones: `017`–`022` (budget control, requester area, party refs, bancos, `payment_orders.bank_account_id`, `budgets.origin_area`) en `database/migrations` y copias en `supabase/migrations`.
- Seeds: `database/seeds/seed_auxiliaries_proveedores_clientes.sql`, `seed_minimo_flujo_presupuesto.sql`, `seed_ejemplo_flujo_presupuesto.sql`.
- Backend: `backend/services/finance/app/main.py`, `schemas.py` (validaciones, PATCH/DELETE, asientos automáticos en borrador, validación pago exige banco+compromiso).
- Frontend: `frontend/src/app/pages/budgets/*`, `finance/*`, proxy y textos de marca.

## 3) Estado funcional (resumen)
| Área | Estado |
|------|--------|
| Aprobación inicial (budgets) + líneas | Operativo (cabecera + `budget_lines` con montos) |
| CDP | CRUD básico + área solicitante + validaciones de borrado |
| Compromisos | CRUD/PATCH/DELETE + saldo CDP + asiento devengo (borrador) |
| Órdenes de pago | CRUD/PATCH/DELETE + cuenta bancaria + asiento pago (borrador) |
| Asientos automáticos | Solo **borrador**, requieren periodo/fiscal abierto y cuentas configuradas |
| Posteo/reverso contable automático | Pendiente (recomendado siguiente fase) |

## 4) Riesgos y dependencias
- Asientos no se publican automáticamente; riesgo de omisión si no se revisan.
- Dependencia de códigos de cuentas por entorno (`63%`, `4212%`) y de datos maestros (cuentas imputables, periodo abierto, cuenta bancaria de tesorería con cuenta contable válida).
- Pruebas end-to-end UI dependen de entorno levantado (servicios + BD + sesión); se recomienda ejecutar checklist funcional (ver sección 6).

## 5) Recomendaciones (prioridad sugerida)
1. **Corto plazo**: aplicar migraciones 021–022 en todos los entornos; ejecutar seed mínimo y, si aplica, seed de ejemplo; validar flujo completo en un caso real.
2. **Medio plazo**: política de posteo de asientos automáticos (borrador → aprobado) y trazabilidad (referencia fuerte asiento↔operación); tabla de mapeo cuenta gasto por partida/CDP (sustituir solo códigos por defecto).
3. **Medio plazo**: estornos/anulaciones coherentes (revertir efectos presupuestales y contables) y reportes de ejecución vs apropiación (usar `budget_lines` + ejecución).
4. **Calidad**: pruebas automatizadas API para reglas de saldo, estados y creación de asientos (en entorno de prueba con BD).

## 6) Checklist funcional mínimo (smoke)
1. PIA: crear presupuesto con área y agregar línea (cuenta imputable + monto).
2. CDP: crear CDP vinculado al contexto de empresa/presupuesto existente.
3. Compromiso: crear con proveedor y CDP; validar rechazo por exceso de saldo.
4. Devengo: cambiar compromiso a devengado → verificar asiento borrador.
5. OP: crear con cuenta bancaria y compromiso → marcar pagada → verificar asiento borrador.

## 7) Datos de ejemplo (referencia)
- Seed mínimo: `database/seeds/seed_minimo_flujo_presupuesto.sql`
- Seed ejemplo flujo: `database/seeds/seed_ejemplo_flujo_presupuesto.sql` (CDP-2026-001, COMP-2026-001, OP-2026-001 para la primera empresa encontrada)

---
*Documento generado como apoyo al cierre de iteración; validar cifras/fechas contra el entorno real.*