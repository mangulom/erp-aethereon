"""Aethereon Finance Service — FastAPI microservice (port 18003).

Módulo financiero completo: empresas, ejercicios/periodos fiscales, plan de
cuentas, asientos contables (borrador/publicación/reversión), presupuestos con
líneas y ejecución, tasas de impuesto, tipo de cambio y estados financieros
(balance de comprobación, estado de resultados, balance general, libro mayor).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .database import engine, get_db
from .schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    BudgetCreate,
    BudgetLineCreate,
    BudgetLineDetail,
    BudgetLineResponse,
    BudgetLineUpdate,
    BudgetResponse,
    BudgetUpdate,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    ExchangeRateCreate,
    ExchangeRateResponse,
    ExchangeRateUpdate,
    FiscalPeriodCreate,
    FiscalPeriodResponse,
    FiscalPeriodUpdate,
    FiscalYearCreate,
    FiscalYearResponse,
    FiscalYearUpdate,
    HealthResponse,
    JournalEntryCreate,
    JournalEntryLineResponse,
    JournalEntryResponse,
    TaxRateCreate,
    TaxRateResponse,
    TaxRateUpdate,
)

settings = get_settings()
bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title=settings.service_name,
    description="Servicio de finanzas y tesorería: empresas, plan de cuentas, asientos, presupuestos, impuestos, tipo de cambio y estados financieros.",
    version=settings.service_version,
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


def require_claims(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida.")
    try:
        return jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión no es válida o ha vencido.") from exc


def require_company(claims: dict, company_id: UUID) -> None:
    allowed = {str(c) for c in claims.get("companies", [])}
    if claims.get("platform_admin") is not True and str(company_id) not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a esta empresa.")


def _audit(db: Session, claims: dict, action: str, company_id: UUID, entity_type: str, entity_id: str, metadata: dict | None = None) -> None:
    db.execute(
        text("""
            INSERT INTO audit_events (company_id, actor_user_id, actor_type, action, entity_type, entity_id, metadata)
            VALUES (:company_id, :actor, 'user', :action, :entity_type, :entity_id, CAST(:metadata AS jsonb))
        """),
        {
            "company_id": company_id,
            "actor": claims.get("sub"),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "metadata": str(metadata or {}).replace("'", '"'),
        },
    )


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
def health_live() -> HealthResponse:
    return HealthResponse(status="ok", service="finance", version=settings.service_version)


@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
def health_ready(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        db.execute(text("SELECT count(*) FROM accounts"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="PostgreSQL no está disponible o falta el esquema de finanzas.") from exc
    return HealthResponse(status="ready", service="finance", version=settings.service_version)


# ---------------------------------------------------------------------------
# Companies (onboarding real: la empresa la crea el usuario, no datos de demo)
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/companies", response_model=list[CompanyResponse], tags=["companies"])
def list_companies(db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Empresas accesibles: todas las activas para administradores de plataforma, las propias para el resto."""
    allowed = [str(c) for c in claims.get("companies", [])]
    if claims.get("platform_admin") is True or not allowed:
        rows = db.execute(
            text("SELECT id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at FROM companies WHERE is_active ORDER BY legal_name"),
        ).mappings().all()
    else:
        rows = db.execute(
            text("SELECT id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at FROM companies WHERE is_active = TRUE AND id = ANY(CAST(:ids AS uuid[])) ORDER BY legal_name"),
            {"ids": allowed},
        ).mappings().all()
    return [CompanyResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/companies", response_model=CompanyResponse, status_code=201, tags=["companies"])
def create_company(payload: CompanyCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    if claims.get("platform_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores de plataforma pueden registrar empresas.")
    try:
        row = db.execute(
            text("""
                INSERT INTO companies (legal_name, trade_name, tax_id, country_code, default_currency, timezone)
                VALUES (:legal_name, :trade_name, :tax_id, :country_code, :default_currency, :timezone)
                RETURNING id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at
            """),
            payload.model_dump(),
        ).mappings().first()
        _audit(db, claims, "finance.company.created", row["id"], "company", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo registrar la empresa (¿impuesto/RUC duplicado?).") from exc
    return CompanyResponse(**dict(row))


@app.patch("/api/v1/finance/companies/{company_id}", response_model=CompanyResponse, tags=["companies"])
def update_company(company_id: UUID, payload: CompanyUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT id FROM companies WHERE id = :id"), {"id": company_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    if claims.get("platform_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores de plataforma pueden editar los datos legales de una empresa.")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"company_id": company_id})
    try:
        row = db.execute(
            text(f"UPDATE companies SET {assignments}, updated_at = now() WHERE id = :company_id RETURNING id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.company.updated", company_id, "company", str(company_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar la empresa.") from exc
    return CompanyResponse(**dict(row))


@app.delete("/api/v1/finance/companies/{company_id}", status_code=204, tags=["companies"])
def delete_company(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    if claims.get("platform_admin") is not True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores de plataforma pueden eliminar empresas.")
    row = db.execute(text("SELECT id FROM companies WHERE id = :id"), {"id": company_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    try:
        # Soft-delete protects historical accounting records and foreign keys.
        db.execute(text("UPDATE companies SET is_active = FALSE, updated_at = now() WHERE id = :id"), {"id": company_id})
        _audit(db, claims, "finance.company.deactivated", company_id, "company", str(company_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="La empresa tiene registros financieros asociados.") from exc
    return None


# ---------------------------------------------------------------------------
# Fiscal years & periods
# ---------------------------------------------------------------------------

@app.post("/api/v1/finance/fiscal-years", response_model=FiscalYearResponse, status_code=201, tags=["fiscal"])
def create_fiscal_year(payload: FiscalYearCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO fiscal_years (company_id, name, start_date, end_date)
                VALUES (:company_id, :name, :start_date, :end_date)
                RETURNING id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at
            """),
            payload.model_dump(),
        ).mappings().first()
        _audit(db, claims, "finance.fiscal_year.created", payload.company_id, "fiscal_year", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el ejercicio fiscal (¿duplicado o rango superpuesto?).") from exc
    return FiscalYearResponse(**dict(row))


@app.get("/api/v1/finance/fiscal-years", response_model=list[FiscalYearResponse], tags=["fiscal"])
def list_fiscal_years(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at FROM fiscal_years WHERE company_id = :company_id ORDER BY start_date DESC"),
        {"company_id": company_id},
    ).mappings().all()
    return [FiscalYearResponse(**dict(row)) for row in rows]


@app.get("/api/v1/finance/fiscal-years/active", response_model=FiscalYearResponse, tags=["fiscal"])
def active_fiscal_year(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Ejercicio vigente hoy; si no existe, el más reciente registrado."""
    require_company(claims, company_id)
    today = date.today()
    row = db.execute(
        text("SELECT id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at FROM fiscal_years WHERE company_id = :company_id AND start_date <= :today AND end_date >= :today ORDER BY start_date DESC LIMIT 1"),
        {"company_id": company_id, "today": today},
    ).mappings().first()
    if not row:
        row = db.execute(
            text("SELECT id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at FROM fiscal_years WHERE company_id = :company_id ORDER BY start_date DESC LIMIT 1"),
            {"company_id": company_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No hay ejercicios fiscales registrados para esta empresa.")
    return FiscalYearResponse(**dict(row))


@app.get("/api/v1/finance/fiscal-years/{fiscal_year_id}", response_model=FiscalYearResponse, tags=["fiscal"])
def get_fiscal_year(fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(
        text("SELECT id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at FROM fiscal_years WHERE id = :id"),
        {"id": fiscal_year_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, row["company_id"])
    return FiscalYearResponse(**dict(row))


@app.patch("/api/v1/finance/fiscal-years/{fiscal_year_id}", response_model=FiscalYearResponse, tags=["fiscal"])
def update_fiscal_year(fiscal_year_id: UUID, payload: FiscalYearUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id, is_closed FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, row["company_id"])
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if changes.get("is_closed"):
        drafts = db.execute(text("SELECT count(*) FROM journal_entries WHERE fiscal_year_id = :id AND status = 'draft'"), {"id": fiscal_year_id}).scalar_one()
        if drafts:
            raise HTTPException(status_code=409, detail="El ejercicio tiene asientos en borrador; publícalos o elimínalos antes de cerrar.")
    if "is_closed" in changes:
        changes["closed_at"] = datetime.now(UTC) if changes["is_closed"] else None
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"fiscal_year_id": fiscal_year_id})
    try:
        updated = db.execute(
            text(f"UPDATE fiscal_years SET {assignments}, updated_at = now() WHERE id = :fiscal_year_id RETURNING id, company_id, name, start_date, end_date, is_closed, closed_at, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.fiscal_year.updated", row["company_id"], "fiscal_year", str(fiscal_year_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el ejercicio fiscal (¿rango superpuesto?).") from exc
    return FiscalYearResponse(**dict(updated))


@app.delete("/api/v1/finance/fiscal-years/{fiscal_year_id}", status_code=204, tags=["fiscal"])
def delete_fiscal_year(fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id})
        _audit(db, claims, "finance.fiscal_year.deleted", row["company_id"], "fiscal_year", str(fiscal_year_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene periodos, asientos o presupuestos asociados.") from exc
    return None


@app.post("/api/v1/finance/fiscal-years/{fiscal_year_id}/periods", response_model=list[FiscalPeriodResponse], status_code=201, tags=["fiscal"])
def create_periods(fiscal_year_id: UUID, periods: list[FiscalPeriodCreate], db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    fy = db.execute(text("SELECT company_id, is_closed FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")
    created = []
    try:
        for item in periods:
            row = db.execute(
                text("""
                    INSERT INTO fiscal_periods (fiscal_year_id, code, name, start_date, end_date, sort_order)
                    VALUES (:fiscal_year_id, :code, :name, :start_date, :end_date, :sort_order)
                    RETURNING id, fiscal_year_id, code, name, start_date, end_date, is_closed, closed_at, sort_order, created_at, updated_at
                """),
                {"fiscal_year_id": fiscal_year_id, **item.model_dump()},
            ).mappings().first()
            created.append(row)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudieron crear los periodos (¿código duplicado?).") from exc
    return [FiscalPeriodResponse(**dict(row)) for row in created]


@app.get("/api/v1/finance/fiscal-years/{fiscal_year_id}/periods", response_model=list[FiscalPeriodResponse], tags=["fiscal"])
def list_periods(fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    fy = db.execute(text("SELECT company_id FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    rows = db.execute(
        text("SELECT id, fiscal_year_id, code, name, start_date, end_date, is_closed, closed_at, sort_order, created_at, updated_at FROM fiscal_periods WHERE fiscal_year_id = :id ORDER BY sort_order"),
        {"id": fiscal_year_id},
    ).mappings().all()
    return [FiscalPeriodResponse(**dict(row)) for row in rows]


@app.patch("/api/v1/finance/fiscal-years/{fiscal_year_id}/periods/{period_id}", response_model=FiscalPeriodResponse, tags=["fiscal"])
def update_period(fiscal_year_id: UUID, period_id: UUID, payload: FiscalPeriodUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    fy = db.execute(text("SELECT company_id, is_closed FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")
    row = db.execute(text("SELECT id, is_closed FROM fiscal_periods WHERE id = :pid AND fiscal_year_id = :fy"), {"pid": period_id, "fy": fiscal_year_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Periodo no encontrado en este ejercicio.")
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if "is_closed" in changes:
        changes["closed_at"] = datetime.now(UTC) if changes["is_closed"] else None
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"period_id": period_id})
    try:
        updated = db.execute(
            text(f"UPDATE fiscal_periods SET {assignments}, updated_at = now() WHERE id = :period_id RETURNING id, fiscal_year_id, code, name, start_date, end_date, is_closed, closed_at, sort_order, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.fiscal_period.updated", fy["company_id"], "fiscal_period", str(period_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el periodo.") from exc
    return FiscalPeriodResponse(**dict(updated))


@app.delete("/api/v1/finance/fiscal-years/{fiscal_year_id}/periods/{period_id}", status_code=204, tags=["fiscal"])
def delete_period(fiscal_year_id: UUID, period_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    fy = db.execute(text("SELECT company_id, is_closed FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")
    row = db.execute(text("SELECT id FROM fiscal_periods WHERE id = :pid AND fiscal_year_id = :fy"), {"pid": period_id, "fy": fiscal_year_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Periodo no encontrado en este ejercicio.")
    try:
        db.execute(text("DELETE FROM fiscal_periods WHERE id = :pid"), {"pid": period_id})
        _audit(db, claims, "finance.fiscal_period.deleted", fy["company_id"], "fiscal_period", str(period_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene asientos o presupuestos asociados.") from exc
    return None


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------

@app.post("/api/v1/finance/accounts", response_model=AccountResponse, status_code=201, tags=["accounts"])
def create_account(payload: AccountCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    if payload.parent_id and not db.execute(text("SELECT 1 FROM accounts WHERE id=:id AND company_id=:company_id"), {"id": payload.parent_id, "company_id": payload.company_id}).first():
        raise HTTPException(status_code=422, detail="La cuenta padre debe pertenecer a la misma empresa.")
    try:
        row = db.execute(
            text("""
                INSERT INTO accounts (company_id, code, name, account_type, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description)
                VALUES (:company_id, :code, :name, :account_type, :account_subtype, :cash_flow_category, :parent_id, :currency, :allow_posting, :is_active, :description)
                RETURNING id, company_id, code, name, account_type, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at
            """),
            payload.model_dump(),
        ).mappings().first()
        _audit(db, claims, "finance.account.created", payload.company_id, "account", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la cuenta (código duplicado o cuenta padre inválida).") from exc
    return AccountResponse(**dict(row))


@app.get("/api/v1/finance/accounts", response_model=list[AccountResponse], tags=["accounts"])
def list_accounts(
    company_id: UUID,
    account_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    require_company(claims, company_id)
    conditions = ["company_id = :company_id"]
    params: dict = {"company_id": company_id}
    if account_type:
        conditions.append("account_type = :account_type")
        params["account_type"] = account_type
    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active
    if q:
        conditions.append("(code ILIKE :q OR name ILIKE :q)")
        params["q"] = f"%{q}%"
    rows = db.execute(
        text(f"SELECT id, company_id, code, name, account_type, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at FROM accounts WHERE {' AND '.join(conditions)} ORDER BY code"),
        params,
    ).mappings().all()
    return [AccountResponse(**dict(row)) for row in rows]


@app.get("/api/v1/finance/accounts/{account_id}", response_model=AccountResponse, tags=["accounts"])
def get_account(account_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(
        text("SELECT id, company_id, code, name, account_type, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at FROM accounts WHERE id = :id"),
        {"id": account_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, row["company_id"])
    return AccountResponse(**dict(row))


@app.patch("/api/v1/finance/accounts/{account_id}", response_model=AccountResponse, tags=["accounts"])
def update_account(account_id: UUID, payload: AccountUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM accounts WHERE id = :id"), {"id": account_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, current["company_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if changes.get("parent_id") and not db.execute(text("SELECT 1 FROM accounts WHERE id=:parent_id AND company_id=:company_id"), {"parent_id": changes["parent_id"], "company_id": current["company_id"]}).first():
        raise HTTPException(status_code=422, detail="La cuenta padre debe pertenecer a la misma empresa.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"account_id": account_id})
    try:
        row = db.execute(
            text(f"UPDATE accounts SET {assignments}, updated_at = now() WHERE id = :account_id RETURNING id, company_id, code, name, account_type, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.account.updated", current["company_id"], "account", str(account_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar la cuenta.") from exc
    return AccountResponse(**dict(row))


@app.delete("/api/v1/finance/accounts/{account_id}", status_code=204, tags=["accounts"])
def delete_account(account_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM accounts WHERE id = :id"), {"id": account_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
        _audit(db, claims, "finance.account.deleted", row["company_id"], "account", str(account_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene movimientos contables o líneas de presupuesto asociados.") from exc
    return None


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------

def _entry_with_lines(db: Session, entry_id: UUID) -> dict:
    row = db.execute(
        text("SELECT id, company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description, status, currency, exchange_rate, total_debit, total_credit, posted_by, posted_at, reversed_by, reversed_at, reversal_reason, created_by, created_at, updated_at FROM journal_entries WHERE id = :id"),
        {"id": entry_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Asiento no encontrado.")
    lines = db.execute(
        text("SELECT id, journal_entry_id, account_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2, created_at, updated_at FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
        {"id": entry_id},
    ).mappings().all()
    payload = dict(row)
    payload["lines"] = [dict(line) for line in lines]
    return payload


@app.get("/api/v1/finance/journal-entries", response_model=list[JournalEntryResponse], tags=["journal"])
def list_journal_entries(
    company_id: UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    fiscal_year_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    require_company(claims, company_id)
    conditions = ["company_id = :company_id"]
    params: dict = {"company_id": company_id}
    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter
    if from_date:
        conditions.append("entry_date >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("entry_date <= :to_date")
        params["to_date"] = to_date
    if fiscal_year_id:
        conditions.append("fiscal_year_id = :fiscal_year_id")
        params["fiscal_year_id"] = fiscal_year_id
    rows = db.execute(
        text(f"SELECT id, company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description, status, currency, exchange_rate, total_debit, total_credit, posted_by, posted_at, reversed_by, reversed_at, reversal_reason, created_by, created_at, updated_at FROM journal_entries WHERE {' AND '.join(conditions)} ORDER BY entry_date DESC, entry_number DESC"),
        params,
    ).mappings().all()
    result = []
    for row in rows:
        payload = dict(row)
        lines = db.execute(
            text("SELECT id, journal_entry_id, account_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2, created_at, updated_at FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
            {"id": row["id"]},
        ).mappings().all()
        payload["lines"] = [dict(line) for line in lines]
        result.append(JournalEntryResponse(**payload))
    return result


@app.get("/api/v1/finance/journal-entries/{entry_id}", response_model=JournalEntryResponse, tags=["journal"])
def get_journal_entry(entry_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    payload = _entry_with_lines(db, entry_id)
    require_company(claims, payload["company_id"])
    return JournalEntryResponse(**payload)


@app.post("/api/v1/finance/journal-entries", response_model=JournalEntryResponse, status_code=201, tags=["journal"])
def create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    fy = db.execute(text("SELECT company_id, is_closed FROM fiscal_years WHERE id = :id"), {"id": payload.fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")
    if payload.fiscal_period_id:
        period = db.execute(text("SELECT is_closed FROM fiscal_periods WHERE id = :id AND fiscal_year_id = :fy"), {"id": payload.fiscal_period_id, "fy": payload.fiscal_year_id}).mappings().first()
        if not period:
            raise HTTPException(status_code=404, detail="Periodo fiscal no encontrado en este ejercicio.")
        if period["is_closed"]:
            raise HTTPException(status_code=409, detail="El periodo fiscal está cerrado.")
    total_debit = sum((line.debit_amount for line in payload.lines), Decimal("0"))
    total_credit = sum((line.credit_amount for line in payload.lines), Decimal("0"))
    if abs(total_debit - total_credit) >= Decimal("0.01"):
        raise HTTPException(status_code=422, detail="El asiento no está balanceado: débitos y créditos difieren.")
    if total_debit <= 0:
        raise HTTPException(status_code=422, detail="El asiento necesita al menos una línea con importe.")
    account_ids = {line.account_id for line in payload.lines}
    valid_accounts = {r[0] for r in db.execute(
        text("SELECT id FROM accounts WHERE company_id = :company_id AND id = ANY(CAST(:ids AS uuid[])) AND is_active AND allow_posting"),
        {"company_id": fy["company_id"], "ids": list(account_ids)},
    ).all()}
    if account_ids - valid_accounts:
        raise HTTPException(status_code=422, detail="Alguna línea usa una cuenta inexistente, inactiva o que no admite movimientos.")
    try:
        entry = db.execute(
            text("""
                INSERT INTO journal_entries (company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference,
                                             description, currency, exchange_rate, total_debit, total_credit, created_by)
                VALUES (:company_id, :fiscal_year_id, :fiscal_period_id, :entry_number, :entry_date, :reference,
                        :description, :currency, :exchange_rate, :total_debit, :total_credit, :created_by)
                RETURNING id, company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description,
                          status, currency, exchange_rate, total_debit, total_credit, posted_by, posted_at, reversed_by, reversed_at, reversal_reason, created_by, created_at, updated_at
            """),
            {
                "company_id": fy["company_id"],
                "fiscal_year_id": payload.fiscal_year_id,
                "fiscal_period_id": payload.fiscal_period_id,
                "entry_number": payload.entry_number,
                "entry_date": payload.entry_date,
                "reference": payload.reference,
                "description": payload.description,
                "currency": payload.currency,
                "exchange_rate": payload.exchange_rate,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "created_by": claims.get("sub"),
            },
        ).mappings().first()
        for line in payload.lines:
            db.execute(
                text("""
                    INSERT INTO journal_entry_lines (journal_entry_id, account_id, line_number, description, debit_amount, credit_amount,
                                                     currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2)
                    VALUES (:journal_entry_id, :account_id, :line_number, :description, :debit_amount, :credit_amount,
                            :currency_amount, :currency_code, :analytical_dimension_1, :analytical_dimension_2)
                """),
                {"journal_entry_id": entry["id"], **line.model_dump()},
            )
        _audit(db, claims, "finance.journal_entry.created", fy["company_id"], "journal_entry", str(entry["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo registrar el asiento (¿número duplicado?).") from exc
    return JournalEntryResponse(**_entry_with_lines(db, entry["id"]))


@app.post("/api/v1/finance/journal-entries/{entry_id}/post", response_model=JournalEntryResponse, tags=["journal"])
def post_journal_entry(entry_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id, status FROM journal_entries WHERE id = :id"), {"id": entry_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Asiento no encontrado.")
    require_company(claims, current["company_id"])
    if current["status"] != "draft":
        raise HTTPException(status_code=409, detail="Solo se pueden publicar asientos en borrador.")
    try:
        row = db.execute(
            text("""
                UPDATE journal_entries SET status = 'posted', posted_by = :actor, posted_at = now(), updated_at = now()
                WHERE id = :id
                RETURNING id, company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description,
                          status, currency, exchange_rate, total_debit, total_credit, posted_by, posted_at, reversed_by, reversed_at, reversal_reason, created_by, created_at, updated_at
            """),
            {"id": entry_id, "actor": claims.get("sub")},
        ).mappings().first()
        _audit(db, claims, "finance.journal_entry.posted", current["company_id"], "journal_entry", str(entry_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo publicar el asiento.") from exc
    return JournalEntryResponse(**_entry_with_lines(db, entry_id))


@app.post("/api/v1/finance/journal-entries/{entry_id}/reverse", response_model=JournalEntryResponse, status_code=201, tags=["journal"])
def reverse_journal_entry(entry_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Crea un asiento de reversión (borrador) con débitos/créditos intercambiados."""
    current = db.execute(
        text("SELECT id, company_id, fiscal_year_id, fiscal_period_id, entry_number, reference, description, currency, exchange_rate, total_debit, total_credit, status FROM journal_entries WHERE id = :id"),
        {"id": entry_id},
    ).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Asiento no encontrado.")
    require_company(claims, current["company_id"])
    if current["status"] != "posted":
        raise HTTPException(status_code=409, detail="Solo se pueden reversar asientos publicados.")
    lines = db.execute(
        text("SELECT account_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2 FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
        {"id": entry_id},
    ).mappings().all()
    base = f"REV-{current['entry_number']}"[:40]
    number = base
    suffix = 2
    while db.execute(text("SELECT 1 FROM journal_entries WHERE company_id = :c AND entry_number = :n"), {"c": current["company_id"], "n": number}).first():
        number = f"{base[:34]}-{suffix}"
        suffix += 1
    today = date.today()
    period = db.execute(
        text("SELECT id FROM fiscal_periods WHERE fiscal_year_id = :fy AND start_date <= :today AND end_date >= :today AND NOT is_closed LIMIT 1"),
        {"fy": current["fiscal_year_id"], "today": today},
    ).first()
    period_id = period[0] if period else current["fiscal_period_id"]
    try:
        entry = db.execute(
            text("""
                INSERT INTO journal_entries (company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference,
                                             description, currency, exchange_rate, total_debit, total_credit, created_by, status)
                VALUES (:company_id, :fy, :pid, :number, :today, :reference, :description, :currency, :exchange_rate, :debit, :credit, :actor, 'draft')
                RETURNING id, company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description,
                          status, currency, exchange_rate, total_debit, total_credit, posted_by, posted_at, reversed_by, reversed_at, reversal_reason, created_by, created_at, updated_at
            """),
            {
                "company_id": current["company_id"],
                "fy": current["fiscal_year_id"],
                "pid": period_id,
                "number": number,
                "today": today,
                "reference": current["reference"],
                "description": f"Reversión de {current['entry_number']}" + (f" — {current['description']}" if current["description"] else ""),
                "currency": current["currency"],
                "exchange_rate": current["exchange_rate"],
                "debit": current["total_credit"],
                "credit": current["total_debit"],
                "actor": claims.get("sub"),
            },
        ).mappings().first()
        for line in lines:
            db.execute(
                text("""
                    INSERT INTO journal_entry_lines (journal_entry_id, account_id, line_number, description, debit_amount, credit_amount,
                                                     currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2)
                    VALUES (:journal_entry_id, :account_id, :line_number, :description, :debit_amount, :credit_amount,
                            :currency_amount, :currency_code, :analytical_dimension_1, :analytical_dimension_2)
                """),
                {
                    "journal_entry_id": entry["id"],
                    "account_id": line["account_id"],
                    "line_number": line["line_number"],
                    "description": line["description"],
                    "debit_amount": line["credit_amount"],
                    "credit_amount": line["debit_amount"],
                    "currency_amount": line["currency_amount"],
                    "currency_code": line["currency_code"],
                    "analytical_dimension_1": line["analytical_dimension_1"],
                    "analytical_dimension_2": line["analytical_dimension_2"],
                },
            )
        _audit(db, claims, "finance.journal_entry.reversed", current["company_id"], "journal_entry", str(entry["id"]), {"reverses": str(entry_id)})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la reversión.") from exc
    return JournalEntryResponse(**_entry_with_lines(db, entry["id"]))


@app.post("/api/v1/finance/journal-entries/{entry_id}/delete-draft", status_code=204, tags=["journal"])
def delete_draft_entry(entry_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Elimina un asiento que aún no ha sido publicado."""
    current = db.execute(text("SELECT company_id, status FROM journal_entries WHERE id = :id"), {"id": entry_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Asiento no encontrado.")
    require_company(claims, current["company_id"])
    if current["status"] != "draft":
        raise HTTPException(status_code=409, detail="Solo se pueden eliminar asientos en borrador; usa la reversión para los publicados.")
    try:
        db.execute(text("DELETE FROM journal_entry_lines WHERE journal_entry_id = :id"), {"id": entry_id})
        db.execute(text("DELETE FROM journal_entries WHERE id = :id"), {"id": entry_id})
        _audit(db, claims, "finance.journal_entry.deleted", current["company_id"], "journal_entry", str(entry_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el asiento.") from exc
    return None


# ---------------------------------------------------------------------------
# Budgets & lines
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/budgets", response_model=list[BudgetResponse], tags=["budgets"])
def list_budgets(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT id, company_id, fiscal_year_id, name, description, status, currency, approved_by, approved_at, created_by, created_at, updated_at FROM budgets WHERE company_id = :company_id ORDER BY created_at DESC"),
        {"company_id": company_id},
    ).mappings().all()
    return [BudgetResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/budgets", response_model=BudgetResponse, status_code=201, tags=["budgets"])
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO budgets (company_id, fiscal_year_id, name, description, currency, created_by)
                VALUES (:company_id, :fiscal_year_id, :name, :description, :currency, :created_by)
                RETURNING id, company_id, fiscal_year_id, name, description, status, currency, approved_by, approved_at, created_by, created_at, updated_at
            """),
            {**payload.model_dump(), "created_by": claims.get("sub")},
        ).mappings().first()
        _audit(db, claims, "finance.budget.created", payload.company_id, "budget", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el presupuesto (¿nombre duplicado en el ejercicio?).") from exc
    return BudgetResponse(**dict(row))


@app.get("/api/v1/finance/budgets/{budget_id}", response_model=BudgetResponse, tags=["budgets"])
def get_budget(budget_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT id, company_id, fiscal_year_id, name, description, status, currency, approved_by, approved_at, created_by, created_at, updated_at FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, row["company_id"])
    return BudgetResponse(**dict(row))


@app.patch("/api/v1/finance/budgets/{budget_id}", response_model=BudgetResponse, tags=["budgets"])
def update_budget(budget_id: UUID, payload: BudgetUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id, status FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, row["company_id"])
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if changes.get("status") == "approved" and row["status"] not in ("draft", "approved"):
        raise HTTPException(status_code=409, detail="Solo los presupuestos en borrador o aprobados pueden avanzar de estado.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"budget_id": budget_id})
    if changes.get("status") == "approved" and row["status"] == "draft":
        changes["approved_by"] = claims.get("sub")
        changes["approved_at"] = datetime.now(UTC)
        assignments = ", ".join(f"{key} = :{key}" for key in changes)
    try:
        updated = db.execute(
            text(f"UPDATE budgets SET {assignments}, updated_at = now() WHERE id = :budget_id RETURNING id, company_id, fiscal_year_id, name, description, status, currency, approved_by, approved_at, created_by, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.budget.updated", row["company_id"], "budget", str(budget_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el presupuesto.") from exc
    return BudgetResponse(**dict(updated))


@app.delete("/api/v1/finance/budgets/{budget_id}", status_code=204, tags=["budgets"])
def delete_budget(budget_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM budget_lines WHERE budget_id = :id"), {"id": budget_id})
        db.execute(text("DELETE FROM budgets WHERE id = :id"), {"id": budget_id})
        _audit(db, claims, "finance.budget.deleted", row["company_id"], "budget", str(budget_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el presupuesto.") from exc
    return None


@app.post("/api/v1/finance/budgets/{budget_id}/lines", response_model=BudgetLineResponse, status_code=201, tags=["budgets"])
def create_budget_line(budget_id: UUID, payload: BudgetLineCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    budget = db.execute(text("SELECT company_id, fiscal_year_id, status FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, budget["company_id"])
    if budget["status"] == "closed":
        raise HTTPException(status_code=409, detail="El presupuesto está cerrado.")
    account = db.execute(text("SELECT id FROM accounts WHERE id = :id AND company_id = :c AND is_active"), {"id": payload.account_id, "c": budget["company_id"]}).first()
    if not account:
        raise HTTPException(status_code=422, detail="La cuenta no existe o está inactiva en esta empresa.")
    try:
        row = db.execute(
            text("""
                INSERT INTO budget_lines (budget_id, account_id, period_id, planned_amount)
                VALUES (:budget_id, :account_id, :period_id, :planned_amount)
                RETURNING id, budget_id, account_id, period_id, planned_amount, created_at, updated_at
            """),
            payload.model_dump() | {"budget_id": budget_id},
        ).mappings().first()
        _audit(db, claims, "finance.budget_line.created", budget["company_id"], "budget_line", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la línea (¿cuenta/periodo duplicado?).") from exc
    return BudgetLineResponse(**dict(row))


@app.get("/api/v1/finance/budgets/{budget_id}/lines", response_model=list[BudgetLineDetail], tags=["budgets"])
def list_budget_lines(budget_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    budget = db.execute(text("SELECT company_id FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, budget["company_id"])
    rows = db.execute(
        text("""
            SELECT bl.id, bl.budget_id, bl.account_id, bl.period_id, bl.planned_amount, bl.created_at, bl.updated_at,
                   a.code AS account_code, a.name AS account_name, a.account_type
            FROM budget_lines bl JOIN accounts a ON a.id = bl.account_id
            WHERE bl.budget_id = :id ORDER BY a.code
        """),
        {"id": budget_id},
    ).mappings().all()
    return [BudgetLineDetail(**dict(row)) for row in rows]


@app.patch("/api/v1/finance/budget-lines/{line_id}", response_model=BudgetLineResponse, tags=["budgets"])
def update_budget_line(line_id: UUID, payload: BudgetLineUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    line = db.execute(text("SELECT bl.budget_id, bl.id FROM budget_lines bl WHERE bl.id = :id"), {"id": line_id}).mappings().first()
    if not line:
        raise HTTPException(status_code=404, detail="Línea de presupuesto no encontrada.")
    budget = db.execute(text("SELECT company_id, status FROM budgets WHERE id = :id"), {"id": line["budget_id"]}).mappings().first()
    require_company(claims, budget["company_id"])
    if budget["status"] == "closed":
        raise HTTPException(status_code=409, detail="El presupuesto está cerrado.")
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"line_id": line_id})
    try:
        updated = db.execute(
            text(f"UPDATE budget_lines SET {assignments}, updated_at = now() WHERE id = :line_id RETURNING id, budget_id, account_id, period_id, planned_amount, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.budget_line.updated", budget["company_id"], "budget_line", str(line_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar la línea.") from exc
    return BudgetLineResponse(**dict(updated))


@app.delete("/api/v1/finance/budget-lines/{line_id}", status_code=204, tags=["budgets"])
def delete_budget_line(line_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    line = db.execute(text("SELECT bl.budget_id FROM budget_lines bl WHERE bl.id = :id"), {"id": line_id}).mappings().first()
    if not line:
        raise HTTPException(status_code=404, detail="Línea de presupuesto no encontrada.")
    budget = db.execute(text("SELECT company_id, status FROM budgets WHERE id = :id"), {"id": line["budget_id"]}).mappings().first()
    require_company(claims, budget["company_id"])
    if budget["status"] == "closed":
        raise HTTPException(status_code=409, detail="El presupuesto está cerrado.")
    try:
        db.execute(text("DELETE FROM budget_lines WHERE id = :id"), {"id": line_id})
        _audit(db, claims, "finance.budget_line.deleted", budget["company_id"], "budget_line", str(line_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar la línea.") from exc
    return None


@app.get("/api/v1/finance/budgets/{budget_id}/execution", tags=["budgets"])
def budget_execution(budget_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Progreso presupuesto vs ejecutado: cuentas con monto planificado, ejecutado, restante y % avance."""
    budget = db.execute(text("SELECT company_id, fiscal_year_id, name, status, currency FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
    if not budget:
        raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, budget["company_id"])
    lines = db.execute(
        text("SELECT bl.id, bl.account_id, bl.period_id, bl.planned_amount, a.code, a.name, a.account_type FROM budget_lines bl JOIN accounts a ON a.id = bl.account_id WHERE bl.budget_id = :id ORDER BY a.code"),
        {"id": budget_id},
    ).mappings().all()
    executed_rows = db.execute(
        text("""
            SELECT l.account_id,
                   SUM(CASE WHEN a.account_type IN ('revenue','liability','equity')
                            THEN l.credit_amount - l.debit_amount
                            ELSE l.debit_amount - l.credit_amount END) AS executed
            FROM journal_entry_lines l
            JOIN journal_entries j ON j.id = l.journal_entry_id
            JOIN accounts a ON a.id = l.account_id
            WHERE j.company_id = :company_id AND j.fiscal_year_id = :fy AND j.status = 'posted'
              AND l.account_id = ANY(CAST(:ids AS uuid[]))
            GROUP BY l.account_id
        """),
        {"company_id": budget["company_id"], "fy": budget["fiscal_year_id"], "ids": [line["account_id"] for line in lines] or [None]},
    ).all()
    executed_map = {row[0]: row[1] for row in executed_rows}
    result = []
    for line in lines:
        planned = line["planned_amount"]
        executed = executed_map.get(line["account_id"], Decimal("0"))
        remaining = planned - executed
        progress = round(float(executed / planned * 100), 1) if planned > 0 else (100.0 if executed > 0 else 0.0)
        result.append({
            "line_id": line["id"],
            "account_id": line["account_id"],
            "account_code": line["code"],
            "account_name": line["name"],
            "account_type": line["account_type"],
            "period_id": line["period_id"],
            "planned_amount": planned,
            "executed_amount": executed,
            "remaining_amount": remaining,
            "progress": progress,
        })
    total_planned = sum((line["planned_amount"] for line in lines), Decimal("0"))
    total_executed = sum((item["executed_amount"] for item in result), Decimal("0"))
    return {
        "budget_id": budget_id,
        "name": budget["name"],
        "status": budget["status"],
        "currency": budget["currency"],
        "lines": result,
        "total_planned": total_planned,
        "total_executed": total_executed,
        "total_remaining": total_planned - total_executed,
        "progress": round(float(total_executed / total_planned * 100), 1) if total_planned > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Tax rates & exchange rates
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/tax-rates", response_model=list[TaxRateResponse], tags=["tax"])
def list_tax_rates(company_id: UUID, is_active: Optional[bool] = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    conditions = ["company_id = :company_id"]
    params: dict = {"company_id": company_id}
    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active
    rows = db.execute(
        text(f"SELECT id, company_id, code, name, rate, tax_type, is_active, valid_from, valid_until, created_at, updated_at FROM tax_rates WHERE {' AND '.join(conditions)} ORDER BY code"),
        params,
    ).mappings().all()
    return [TaxRateResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/tax-rates", response_model=TaxRateResponse, status_code=201, tags=["tax"])
def create_tax_rate(payload: TaxRateCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO tax_rates (company_id, code, name, rate, tax_type, is_active, valid_from, valid_until)
                VALUES (:company_id, :code, :name, :rate, :tax_type, :is_active, :valid_from, :valid_until)
                RETURNING id, company_id, code, name, rate, tax_type, is_active, valid_from, valid_until, created_at, updated_at
            """),
            payload.model_dump(),
        ).mappings().first()
        _audit(db, claims, "finance.tax_rate.created", payload.company_id, "tax_rate", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la tasa (¿código duplicado?).") from exc
    return TaxRateResponse(**dict(row))


@app.patch("/api/v1/finance/tax-rates/{tax_rate_id}", response_model=TaxRateResponse, tags=["tax"])
def update_tax_rate(tax_rate_id: UUID, payload: TaxRateUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM tax_rates WHERE id = :id"), {"id": tax_rate_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Tasa de impuesto no encontrada.")
    require_company(claims, current["company_id"])
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"tax_rate_id": tax_rate_id})
    try:
        row = db.execute(
            text(f"UPDATE tax_rates SET {assignments}, updated_at = now() WHERE id = :tax_rate_id RETURNING id, company_id, code, name, rate, tax_type, is_active, valid_from, valid_until, created_at, updated_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.tax_rate.updated", current["company_id"], "tax_rate", str(tax_rate_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar la tasa.") from exc
    return TaxRateResponse(**dict(row))


@app.delete("/api/v1/finance/tax-rates/{tax_rate_id}", status_code=204, tags=["tax"])
def delete_tax_rate(tax_rate_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM tax_rates WHERE id = :id"), {"id": tax_rate_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Tasa de impuesto no encontrada.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM tax_rates WHERE id = :id"), {"id": tax_rate_id})
        _audit(db, claims, "finance.tax_rate.deleted", row["company_id"], "tax_rate", str(tax_rate_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar la tasa.") from exc
    return None


@app.get("/api/v1/finance/exchange-rates", response_model=list[ExchangeRateResponse], tags=["treasury"])
def list_exchange_rates(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT id, company_id, from_currency, to_currency, rate_date, rate, source, created_at FROM exchange_rates WHERE company_id = :company_id ORDER BY rate_date DESC"),
        {"company_id": company_id},
    ).mappings().all()
    return [ExchangeRateResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/exchange-rates", response_model=ExchangeRateResponse, status_code=201, tags=["treasury"])
def create_exchange_rate(payload: ExchangeRateCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO exchange_rates (company_id, from_currency, to_currency, rate_date, rate, source)
                VALUES (:company_id, :from_currency, :to_currency, :rate_date, :rate, :source)
                RETURNING id, company_id, from_currency, to_currency, rate_date, rate, source, created_at
            """),
            payload.model_dump(),
        ).mappings().first()
        _audit(db, claims, "finance.exchange_rate.created", payload.company_id, "exchange_rate", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo registrar el tipo de cambio (¿ya existe para la fecha?).") from exc
    return ExchangeRateResponse(**dict(row))


@app.patch("/api/v1/finance/exchange-rates/{rate_id}", response_model=ExchangeRateResponse, tags=["treasury"])
def update_exchange_rate(rate_id: UUID, payload: ExchangeRateUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM exchange_rates WHERE id = :id"), {"id": rate_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Tipo de cambio no encontrado.")
    require_company(claims, current["company_id"])
    changes = {key: value for key, value in payload.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"rate_id": rate_id})
    try:
        row = db.execute(
            text(f"UPDATE exchange_rates SET {assignments} WHERE id = :rate_id RETURNING id, company_id, from_currency, to_currency, rate_date, rate, source, created_at"),
            changes,
        ).mappings().first()
        _audit(db, claims, "finance.exchange_rate.updated", current["company_id"], "exchange_rate", str(rate_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el tipo de cambio.") from exc
    return ExchangeRateResponse(**dict(row))


@app.delete("/api/v1/finance/exchange-rates/{rate_id}", status_code=204, tags=["treasury"])
def delete_exchange_rate(rate_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM exchange_rates WHERE id = :id"), {"id": rate_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Tipo de cambio no encontrado.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM exchange_rates WHERE id = :id"), {"id": rate_id})
        _audit(db, claims, "finance.exchange_rate.deleted", row["company_id"], "exchange_rate", str(rate_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el tipo de cambio.") from exc
    return None


# ---------------------------------------------------------------------------
# Financial reports (solo asientos publicados, sin datos sintéticos)
# ---------------------------------------------------------------------------

class TrialBalanceRow(BaseModel):
    account_id: UUID
    code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class FinanceDocumentLineInput(BaseModel):
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    account_id: UUID
    tax_rate_id: UUID | None = None


class FinanceDocumentInput(BaseModel):
    fiscal_year_id: UUID
    fiscal_period_id: UUID | None = None
    document_type: str
    document_number: str
    party_name: str
    party_tax_id: str | None = None
    issue_date: date
    due_date: date | None = None
    currency: str = "PEN"
    exchange_rate: Decimal = Decimal("1")
    control_account_id: UUID | None = None
    tax_account_id: UUID | None = None
    related_document_id: UUID | None = None
    notes: str | None = None
    lines: list[FinanceDocumentLineInput]


class SettlementInput(BaseModel):
    amount: Decimal
    settled_at: date
    reference: str | None = None


class PaymentInput(BaseModel):
    bank_account_id: UUID
    amount: Decimal
    settled_at: date
    reference: str | None = None
    description: str | None = None


class BankAccountInput(BaseModel):
    account_id: UUID
    bank_name: str
    account_name: str
    account_number_masked: str | None = None
    currency: str = "PEN"
    is_active: bool = True


class BankStatementLineInput(BaseModel):
    transaction_date: date
    reference: str | None = None
    description: str
    amount: Decimal


class CashFlowRow(BaseModel):
    account_id: UUID
    code: str
    name: str
    account_subtype: str | None = None
    debit: Decimal
    credit: Decimal
    net_change: Decimal


def _document_lines(db: Session, company_id: UUID, document_type: str, lines: list[FinanceDocumentLineInput]) -> tuple[list[dict], Decimal, Decimal]:
    if not lines:
        raise HTTPException(status_code=422, detail="El comprobante debe incluir al menos un concepto.")
    output = []
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for index, line in enumerate(lines, start=1):
        if line.quantity <= 0 or line.unit_price < 0:
            raise HTTPException(status_code=422, detail="La cantidad debe ser positiva y el precio no puede ser negativo.")
        account = db.execute(text("SELECT id, account_type, is_active, allow_posting FROM accounts WHERE id=:id AND company_id=:company"), {"id": line.account_id, "company": company_id}).mappings().first()
        if not account or not account["is_active"] or not account["allow_posting"]:
            raise HTTPException(status_code=422, detail="Una cuenta del detalle no existe, está inactiva o no admite movimientos.")
        expected_types = {"revenue"} if document_type in ("sales_invoice", "sales_credit_note") else {"expense", "asset"}
        if account["account_type"] not in expected_types:
            raise HTTPException(status_code=422, detail="Tipo de cuenta incorrecto para este comprobante: ventas requieren ingresos; compras, gastos o activos.")
        net = (line.quantity * line.unit_price).quantize(Decimal("0.01"))
        rate = Decimal("0")
        if line.tax_rate_id:
            tax = db.execute(text("SELECT rate,is_active,valid_from,valid_until FROM tax_rates WHERE id=:id AND company_id=:company"), {"id": line.tax_rate_id, "company": company_id}).mappings().first()
            if not tax or not tax["is_active"]:
                raise HTTPException(status_code=422, detail="La tasa fiscal seleccionada no existe o está inactiva.")
            rate = tax["rate"]
        tax_amount = (net * rate / Decimal("100")).quantize(Decimal("0.01"))
        subtotal += net
        tax_total += tax_amount
        output.append({
            "line_number": index,
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "account_id": line.account_id,
            "tax_rate_id": line.tax_rate_id,
            "tax_rate": rate,
            "net_amount": net,
            "tax_amount": tax_amount,
        })
    return output, subtotal, tax_total


def _document_response(db: Session, document_id: UUID) -> dict:
    row = db.execute(text("""
        SELECT id,company_id,fiscal_year_id,fiscal_period_id,document_type,document_number,party_name,party_tax_id,
               issue_date,due_date,currency,exchange_rate,subtotal,tax_total,total,status,journal_entry_id,notes,
               control_account_id,tax_account_id,related_document_id,created_by,posted_by,posted_at,created_at,updated_at
        FROM finance_documents WHERE id=:id
    """), {"id": document_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    result = dict(row)
    result["lines"] = [dict(item) for item in db.execute(text("""
        SELECT id,document_id,line_number,description,quantity,unit_price,account_id,tax_rate_id,tax_rate,net_amount,tax_amount,created_at
        FROM finance_document_lines WHERE document_id=:id ORDER BY line_number
    """), {"id": document_id}).mappings().all()]
    paid = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM finance_document_settlements WHERE document_id=:id"), {"id": document_id}).scalar_one()
    result["paid_amount"] = paid
    result["outstanding_amount"] = result["total"] - paid
    return result


@app.get("/api/v1/finance/documents", tags=["documents"])
def list_finance_documents(
    company_id: UUID,
    document_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    require_company(claims, company_id)
    where = ["d.company_id=:company_id"]
    params: dict = {"company_id": company_id}
    if document_type:
        where.append("d.document_type=:document_type"); params["document_type"] = document_type
    if status_filter:
        where.append("d.status=:status"); params["status"] = status_filter
    if from_date:
        where.append("d.issue_date>=:from_date"); params["from_date"] = from_date
    if to_date:
        where.append("d.issue_date<=:to_date"); params["to_date"] = to_date
    if q:
        where.append("(d.document_number ILIKE :q OR d.party_name ILIKE :q OR COALESCE(d.party_tax_id,'') ILIKE :q)"); params["q"] = f"%{q}%"
    rows = db.execute(text(f"""
        SELECT d.id,d.company_id,d.fiscal_year_id,d.fiscal_period_id,d.document_type,d.document_number,d.party_name,d.party_tax_id,
               d.issue_date,d.due_date,d.currency,d.exchange_rate,d.subtotal,d.tax_total,d.total,d.status,d.journal_entry_id,d.notes,
                d.control_account_id,d.tax_account_id,d.related_document_id,d.created_by,d.posted_by,d.posted_at,d.created_at,d.updated_at,
               COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id),0) AS paid_amount
        FROM finance_documents d WHERE {' AND '.join(where)} ORDER BY d.issue_date DESC,d.document_number DESC
    """), params).mappings().all()
    result=[]
    for item in rows:
        d=dict(item); d["outstanding_amount"]=d["total"]-d["paid_amount"]; result.append(d)
    return result


@app.get("/api/v1/finance/documents/{document_id}", tags=["documents"])
def get_finance_document(document_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    result = _document_response(db, document_id)
    require_company(claims, result["company_id"])
    return result


@app.post("/api/v1/finance/documents", status_code=201, tags=["documents"])
def create_finance_document(payload: FinanceDocumentInput, company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    if payload.document_type not in {"sales_invoice","purchase_bill","sales_credit_note","purchase_credit_note"}:
        raise HTTPException(status_code=422, detail="Tipo de comprobante inválido.")
    if payload.exchange_rate <= 0:
        raise HTTPException(status_code=422, detail="El tipo de cambio debe ser positivo.")
    credit_note = payload.document_type in ("sales_credit_note", "purchase_credit_note")
    if credit_note:
        expected_original = "sales_invoice" if payload.document_type == "sales_credit_note" else "purchase_bill"
        source = db.execute(text("SELECT id,total,status,company_id,document_type FROM finance_documents WHERE id=:id"), {"id": payload.related_document_id}).mappings().first() if payload.related_document_id else None
        if not source or source["company_id"] != company_id or source["status"] != "posted" or source["document_type"] != expected_original:
            raise HTTPException(status_code=422, detail="La nota de crédito debe referenciar una factura original contabilizada del mismo tipo y empresa.")
    elif payload.related_document_id:
        raise HTTPException(status_code=422, detail="Solo las notas de crédito pueden referenciar un comprobante original.")
    year = db.execute(text("SELECT company_id,is_closed,start_date,end_date FROM fiscal_years WHERE id=:id"), {"id":payload.fiscal_year_id}).mappings().first()
    if not year or year["company_id"] != company_id:
        raise HTTPException(status_code=422, detail="Ejercicio fiscal inexistente o de otra empresa.")
    if year["is_closed"] or not (year["start_date"] <= payload.issue_date <= year["end_date"]):
        raise HTTPException(status_code=409, detail="El ejercicio está cerrado o la fecha está fuera del ejercicio.")
    if payload.fiscal_period_id:
        period = db.execute(text("SELECT is_closed,start_date,end_date FROM fiscal_periods WHERE id=:id AND fiscal_year_id=:fy"), {"id":payload.fiscal_period_id,"fy":payload.fiscal_year_id}).mappings().first()
        if not period or period["is_closed"] or not (period["start_date"] <= payload.issue_date <= period["end_date"]):
            raise HTTPException(status_code=409, detail="Periodo inválido, cerrado o no corresponde a la fecha.")
    lines, subtotal, tax_total = _document_lines(db, company_id, payload.document_type, payload.lines)
    total = subtotal + tax_total
    if credit_note:
        already_credited = db.execute(text("SELECT COALESCE(SUM(total),0) FROM finance_documents WHERE related_document_id=:source AND status<>'void'"), {"source": payload.related_document_id}).scalar_one()
        if total + already_credited > source["total"]:
            raise HTTPException(status_code=422, detail="El total de la nota de crédito supera el saldo disponible de la factura original.")
    try:
        doc = db.execute(text("""
        INSERT INTO finance_documents(company_id,fiscal_year_id,fiscal_period_id,document_type,document_number,party_name,party_tax_id,
                issue_date,due_date,currency,exchange_rate,subtotal,tax_total,total,notes,control_account_id,tax_account_id,related_document_id,created_by)
            VALUES(:company_id,:fiscal_year_id,:fiscal_period_id,:document_type,:document_number,:party_name,:party_tax_id,
                :issue_date,:due_date,:currency,:exchange_rate,:subtotal,:tax_total,:total,:notes,:control_account_id,:tax_account_id,:related_document_id,:actor)
            RETURNING id
        """), {**payload.model_dump(exclude={"lines"}),"company_id":company_id,"subtotal":subtotal,"tax_total":tax_total,"total":total,"actor":claims.get("sub")}).scalar_one()
        for line in lines:
            db.execute(text("""
                INSERT INTO finance_document_lines(document_id,line_number,description,quantity,unit_price,account_id,tax_rate_id,tax_rate,net_amount,tax_amount)
                VALUES(:document_id,:line_number,:description,:quantity,:unit_price,:account_id,:tax_rate_id,:tax_rate,:net_amount,:tax_amount)
            """), {"document_id":doc,**line})
        _audit(db,claims,"finance.document.created",company_id,"finance_document",str(doc))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo crear el comprobante; verifica su número y relaciones.") from exc
    return _document_response(db,doc)


@app.patch("/api/v1/finance/documents/{document_id}", tags=["documents"])
def update_finance_document(document_id: UUID, payload: FinanceDocumentInput, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id,status FROM finance_documents WHERE id=:id"), {"id":document_id}).mappings().first()
    if not current: raise HTTPException(status_code=404,detail="Comprobante no encontrado.")
    require_company(claims,current["company_id"])
    if current["status"] != "draft": raise HTTPException(status_code=409,detail="Solo se pueden modificar comprobantes en borrador.")
    if payload.document_type not in {"sales_invoice","purchase_bill","sales_credit_note","purchase_credit_note"}:
        raise HTTPException(status_code=422,detail="Tipo de comprobante inválido.")
    year = db.execute(text("SELECT company_id,is_closed,start_date,end_date FROM fiscal_years WHERE id=:id"), {"id":payload.fiscal_year_id}).mappings().first()
    if not year or year["company_id"] != current["company_id"]:
        raise HTTPException(status_code=422, detail="Ejercicio fiscal inexistente o de otra empresa.")
    if year["is_closed"] or not (year["start_date"] <= payload.issue_date <= year["end_date"]):
        raise HTTPException(status_code=409, detail="El ejercicio está cerrado o la fecha está fuera del ejercicio.")
    if payload.fiscal_period_id:
        period = db.execute(text("SELECT is_closed,start_date,end_date FROM fiscal_periods WHERE id=:id AND fiscal_year_id=:fy"), {"id":payload.fiscal_period_id,"fy":payload.fiscal_year_id}).mappings().first()
        if not period or period["is_closed"] or not (period["start_date"] <= payload.issue_date <= period["end_date"]):
            raise HTTPException(status_code=409, detail="Periodo inválido, cerrado o no corresponde a la fecha.")
    if payload.exchange_rate <= 0:
        raise HTTPException(status_code=422, detail="El tipo de cambio debe ser positivo.")
    is_credit_note = payload.document_type in ("sales_credit_note", "purchase_credit_note")
    if is_credit_note:
        expected_original = "sales_invoice" if payload.document_type == "sales_credit_note" else "purchase_bill"
        source = db.execute(text("SELECT id,total,status,company_id,document_type FROM finance_documents WHERE id=:id"), {"id":payload.related_document_id}).mappings().first() if payload.related_document_id else None
        if not source or source["company_id"] != current["company_id"] or source["status"] != "posted" or source["document_type"] != expected_original:
            raise HTTPException(status_code=422, detail="La nota de crédito debe referenciar una factura original contabilizada del mismo tipo y empresa.")
    elif payload.related_document_id:
        raise HTTPException(status_code=422, detail="Solo las notas de crédito pueden referenciar un comprobante original.")
    lines,subtotal,tax_total=_document_lines(db,current["company_id"],payload.document_type,payload.lines); total=subtotal+tax_total
    if is_credit_note:
        already_credited = db.execute(text("SELECT COALESCE(SUM(total),0) FROM finance_documents WHERE related_document_id=:source AND status<>'void' AND id<>:current_id"), {"source": payload.related_document_id, "current_id": document_id}).scalar_one()
        if total + already_credited > source["total"]:
            raise HTTPException(status_code=422, detail="El total de las notas de crédito supera el saldo disponible de la factura original.")
    try:
        db.execute(text("""
            UPDATE finance_documents SET fiscal_year_id=:fiscal_year_id,fiscal_period_id=:fiscal_period_id,document_type=:document_type,
                document_number=:document_number,party_name=:party_name,party_tax_id=:party_tax_id,issue_date=:issue_date,due_date=:due_date,
                currency=:currency,exchange_rate=:exchange_rate,subtotal=:subtotal,tax_total=:tax_total,total=:total,notes=:notes,
                control_account_id=:control_account_id,tax_account_id=:tax_account_id,related_document_id=:related_document_id,updated_at=now()
            WHERE id=:id
        """), {**payload.model_dump(exclude={"lines"}),"subtotal":subtotal,"tax_total":tax_total,"total":total,"id":document_id})
        db.execute(text("DELETE FROM finance_document_lines WHERE document_id=:id"), {"id":document_id})
        for line in lines:
            db.execute(text("INSERT INTO finance_document_lines(document_id,line_number,description,quantity,unit_price,account_id,tax_rate_id,tax_rate,net_amount,tax_amount) VALUES(:document_id,:line_number,:description,:quantity,:unit_price,:account_id,:tax_rate_id,:tax_rate,:net_amount,:tax_amount)"), {"document_id":document_id,**line})
        _audit(db,claims,"finance.document.updated",current["company_id"],"finance_document",str(document_id)); db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo actualizar el borrador.") from exc
    return _document_response(db,document_id)


@app.delete("/api/v1/finance/documents/{document_id}", status_code=204, tags=["documents"])
def delete_finance_document(document_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current=db.execute(text("SELECT company_id,status FROM finance_documents WHERE id=:id"),{"id":document_id}).mappings().first()
    if not current: raise HTTPException(status_code=404,detail="Comprobante no encontrado.")
    require_company(claims,current["company_id"])
    if current["status"] != "draft": raise HTTPException(status_code=409,detail="Un comprobante contabilizado no se elimina; debe reversarse.")
    try:
        db.execute(text("DELETE FROM finance_document_lines WHERE document_id=:id"),{"id":document_id})
        db.execute(text("DELETE FROM finance_documents WHERE id=:id"),{"id":document_id})
        _audit(db,claims,"finance.document.deleted",current["company_id"],"finance_document",str(document_id)); db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo eliminar el borrador.") from exc


@app.get("/api/v1/finance/documents/{document_id}/settlements", tags=["documents"])
def list_document_settlements(document_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    doc = db.execute(text("SELECT company_id FROM finance_documents WHERE id=:id"), {"id": document_id}).mappings().first()
    if not doc: raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    require_company(claims, doc["company_id"])
    rows = db.execute(text("SELECT id,document_id,amount,settled_at,reference,created_by,created_at FROM finance_document_settlements WHERE document_id=:id ORDER BY settled_at,id"), {"id": document_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/finance/documents/{document_id}/settlements", status_code=201, tags=["documents"])
def create_document_settlement(document_id: UUID, payload: SettlementInput, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    doc = db.execute(text("SELECT company_id,status,total,issue_date,due_date FROM finance_documents WHERE id=:id"), {"id": document_id}).mappings().first()
    if not doc: raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    require_company(claims, doc["company_id"])
    if doc["status"] != "posted": raise HTTPException(status_code=409, detail="Solo se aplican pagos a comprobantes contabilizados.")
    if payload.amount <= 0: raise HTTPException(status_code=422, detail="El importe del pago debe ser mayor que cero.")
    paid = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM finance_document_settlements WHERE document_id=:id"), {"id": document_id}).scalar_one()
    outstanding = doc["total"] - paid
    if payload.amount > outstanding: raise HTTPException(status_code=422, detail="El importe excede el saldo pendiente.")
    if payload.settled_at < doc["issue_date"]: raise HTTPException(status_code=422, detail="La fecha de pago no puede preceder a la emisión.")
    try:
        row = db.execute(text("INSERT INTO finance_document_settlements(document_id,amount,settled_at,reference,created_by) VALUES(:document_id,:amount,:settled_at,:reference,:actor) RETURNING id,document_id,amount,settled_at,reference,created_by,created_at"), {**payload.model_dump(), "document_id": document_id, "actor": claims.get("sub")}).mappings().first()
        _audit(db, claims, "finance.document.payment_allocated", doc["company_id"], "finance_document", str(document_id), {"amount": str(payload.amount)})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudo aplicar el pago.") from exc
    return {**dict(row), "outstanding_amount": outstanding - payload.amount, "allocation_only": True}


@app.delete("/api/v1/finance/documents/{document_id}/settlements/{settlement_id}", status_code=204, tags=["documents"])
def delete_document_settlement(document_id: UUID, settlement_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    doc = db.execute(text("SELECT company_id,status FROM finance_documents WHERE id=:id"), {"id": document_id}).mappings().first()
    if not doc: raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    require_company(claims, doc["company_id"])
    if doc["status"] != "posted": raise HTTPException(status_code=409, detail="El comprobante debe estar contabilizado.")
    result = db.execute(text("DELETE FROM finance_document_settlements WHERE id=:s AND document_id=:d"), {"s": settlement_id, "d": document_id})
    if not result.rowcount: raise HTTPException(status_code=404, detail="Aplicación de pago no encontrada.")
    db.commit()


@app.post("/api/v1/finance/documents/{document_id}/payments", status_code=201, tags=["documents","treasury"])
def create_document_payment(document_id: UUID, payload: PaymentInput, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Registra el movimiento bancario y aplica el pago al comprobante en una sola transacción."""
    doc=db.execute(text("SELECT * FROM finance_documents WHERE id=:id"),{"id":document_id}).mappings().first()
    if not doc: raise HTTPException(status_code=404,detail="Comprobante no encontrado.")
    require_company(claims,doc["company_id"])
    if doc["status"]!="posted": raise HTTPException(status_code=409,detail="Solo se pagan comprobantes contabilizados.")
    if payload.amount<=0: raise HTTPException(status_code=422,detail="El importe debe ser mayor que cero.")
    bank=db.execute(text("""
        SELECT b.id,b.company_id,b.account_id,b.currency,b.is_active,a.account_type,a.account_subtype,a.is_active AS account_active,a.allow_posting
        FROM finance_bank_accounts b JOIN accounts a ON a.id=b.account_id WHERE b.id=:id
    """),{"id":payload.bank_account_id}).mappings().first()
    if not bank or bank["company_id"]!=doc["company_id"] or not bank["is_active"] or not bank["account_active"] or not bank["allow_posting"] or bank["account_subtype"] not in ("cash","bank"):
        raise HTTPException(status_code=422,detail="Selecciona una cuenta bancaria/caja activa de esta empresa.")
    if bank["currency"]!=doc["currency"]: raise HTTPException(status_code=422,detail="La moneda de la cuenta bancaria debe coincidir con la del comprobante.")
    paid=db.execute(text("SELECT COALESCE(SUM(amount),0) FROM finance_document_settlements WHERE document_id=:id"),{"id":document_id}).scalar_one()
    credited=db.execute(text("SELECT COALESCE(SUM(total),0) FROM finance_documents WHERE related_document_id=:id AND status='posted'"),{"id":document_id}).scalar_one()
    outstanding=doc["total"]-paid-credited
    if payload.amount>outstanding: raise HTTPException(status_code=422,detail="El pago excede el saldo pendiente.")
    year=db.execute(text("SELECT is_closed,start_date,end_date FROM fiscal_years WHERE id=:id"),{"id":doc["fiscal_year_id"]}).mappings().first()
    period=db.execute(text("SELECT id FROM fiscal_periods WHERE fiscal_year_id=:fy AND start_date<=:d AND end_date>=:d AND NOT is_closed LIMIT 1"),{"fy":doc["fiscal_year_id"],"d":payload.settled_at}).first()
    if not year or year["is_closed"] or not (year["start_date"]<=payload.settled_at<=year["end_date"]): raise HTTPException(status_code=409,detail="La fecha de pago está fuera de un ejercicio abierto.")
    if not period: raise HTTPException(status_code=409,detail="No existe un periodo abierto para la fecha de pago.")
    is_receivable=doc["document_type"] in ("sales_invoice","sales_credit_note")
    control_account=doc["control_account_id"]
    if not control_account: raise HTTPException(status_code=422,detail="El comprobante no tiene cuenta de control configurada.")
    # Receivable settlement: Dr bank / Cr AR. Payable settlement: Dr AP / Cr bank.
    lines=([{"account_id":bank["account_id"],"debit":payload.amount,"credit":Decimal("0"),"description":"Cobro"},{"account_id":control_account,"debit":Decimal("0"),"credit":payload.amount,"description":doc["party_name"]}] if is_receivable else [{"account_id":control_account,"debit":payload.amount,"credit":Decimal("0"),"description":doc["party_name"]},{"account_id":bank["account_id"],"debit":Decimal("0"),"credit":payload.amount,"description":"Pago"}])
    entry_no=f"PAY-{payload.settled_at:%Y%m%d}-{str(uuid4())[:8]}"
    try:
        entry_id=db.execute(text("""
            INSERT INTO journal_entries(company_id,fiscal_year_id,fiscal_period_id,entry_number,entry_date,reference,description,currency,exchange_rate,total_debit,total_credit,created_by)
            VALUES(:company,:fy,:period,:number,:date,:reference,:description,:currency,:rate,:amount,:amount,:actor) RETURNING id
        """),{"company":doc["company_id"],"fy":doc["fiscal_year_id"],"period":period[0],"number":entry_no,"date":payload.settled_at,"reference":payload.reference,"description":payload.description or f"Pago de {doc['document_number']} · {doc['party_name']}","currency":doc["currency"],"rate":doc["exchange_rate"],"amount":payload.amount,"actor":claims.get("sub")}).scalar_one()
        for index,line in enumerate(lines,1):
            db.execute(text("INSERT INTO journal_entry_lines(journal_entry_id,account_id,line_number,description,debit_amount,credit_amount) VALUES(:entry,:account,:line,:description,:debit,:credit)"),{"entry":entry_id,"account":line["account_id"],"line":index,"description":line["description"],"debit":line["debit"],"credit":line["credit"]})
        db.execute(text("UPDATE journal_entries SET status='posted',posted_by=:actor,posted_at=now(),updated_at=now() WHERE id=:id"),{"actor":claims.get("sub"),"id":entry_id})
        settlement=db.execute(text("INSERT INTO finance_document_settlements(document_id,amount,settled_at,reference,created_by) VALUES(:doc,:amount,:date,:reference,:actor) RETURNING id,document_id,amount,settled_at,reference,created_by,created_at"),{"doc":document_id,"amount":payload.amount,"date":payload.settled_at,"reference":payload.reference,"actor":claims.get("sub")}).mappings().first()
        _audit(db,claims,"finance.document.payment_posted",doc["company_id"],"finance_document",str(document_id),{"journal_entry_id":str(entry_id),"amount":str(payload.amount)})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo registrar el pago y su asiento contable.") from exc
    return {**dict(settlement),"journal_entry_id":entry_id,"outstanding_amount":outstanding-payload.amount}


@app.get("/api/v1/finance/bank-accounts", tags=["treasury"])
def list_bank_accounts(company_id: UUID, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    require_company(claims,company_id)
    rows=db.execute(text("""SELECT b.id,b.company_id,b.account_id,b.bank_name,b.account_name,b.account_number_masked,b.currency,b.is_active,b.created_at,b.updated_at,a.code AS account_code,a.name AS ledger_account_name FROM finance_bank_accounts b JOIN accounts a ON a.id=b.account_id WHERE b.company_id=:c ORDER BY b.account_name"""),{"c":company_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/finance/bank-accounts", status_code=201, tags=["treasury"])
def create_bank_account(company_id: UUID, payload: BankAccountInput, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    require_company(claims,company_id)
    account=db.execute(text("SELECT account_subtype,is_active,allow_posting FROM accounts WHERE id=:id AND company_id=:c"),{"id":payload.account_id,"c":company_id}).mappings().first()
    if not account or account["account_subtype"] not in ("cash","bank") or not account["is_active"] or not account["allow_posting"]:
        raise HTTPException(status_code=422,detail="La cuenta contable debe ser activa, imputable y de subtipo caja o banco.")
    try:
        row=db.execute(text("INSERT INTO finance_bank_accounts(company_id,account_id,bank_name,account_name,account_number_masked,currency,is_active) VALUES(:company,:account,:bank,:name,:number,:currency,:active) RETURNING id,company_id,account_id,bank_name,account_name,account_number_masked,currency,is_active,created_at,updated_at"),{"company":company_id,**payload.model_dump()}).mappings().first()
        _audit(db,claims,"finance.bank_account.created",company_id,"bank_account",str(row["id"]));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo crear la cuenta bancaria.") from exc
    return dict(row)


@app.patch("/api/v1/finance/bank-accounts/{bank_account_id}", tags=["treasury"])
def update_bank_account(bank_account_id: UUID, payload: BankAccountInput, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    current=db.execute(text("SELECT company_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not current: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,current["company_id"])
    account=db.execute(text("SELECT account_subtype FROM accounts WHERE id=:id AND company_id=:c"),{"id":payload.account_id,"c":current["company_id"]}).mappings().first()
    if not account or account["account_subtype"] not in ("cash","bank"): raise HTTPException(status_code=422,detail="Selecciona una cuenta de caja o banco de esta empresa.")
    try:
        row=db.execute(text("UPDATE finance_bank_accounts SET account_id=:account,bank_name=:bank,account_name=:name,account_number_masked=:number,currency=:currency,is_active=:active,updated_at=now() WHERE id=:id RETURNING id,company_id,account_id,bank_name,account_name,account_number_masked,currency,is_active,created_at,updated_at"),{"id":bank_account_id,"account":payload.account_id,"bank":payload.bank_name,"name":payload.account_name,"number":payload.account_number_masked,"currency":payload.currency,"active":payload.is_active}).mappings().first()
        _audit(db,claims,"finance.bank_account.updated",current["company_id"],"bank_account",str(bank_account_id));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo actualizar la cuenta bancaria.") from exc
    return dict(row)


@app.get("/api/v1/finance/bank-accounts/{bank_account_id}/statement-lines", tags=["treasury"])
def list_bank_statement_lines(bank_account_id: UUID, status_filter: str|None=Query(default=None,alias="status"), db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    bank=db.execute(text("SELECT company_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not bank: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,bank["company_id"])
    sql="SELECT id,bank_account_id,transaction_date,reference,description,amount,status,journal_entry_id,created_at FROM finance_bank_statement_lines WHERE bank_account_id=:id"
    params={"id":bank_account_id}
    if status_filter: sql+=" AND status=:status";params["status"]=status_filter
    rows=db.execute(text(sql+" ORDER BY transaction_date DESC,id"),params).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/finance/bank-accounts/{bank_account_id}/statement-lines", status_code=201, tags=["treasury"])
def create_bank_statement_line(bank_account_id: UUID, payload: BankStatementLineInput, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    bank=db.execute(text("SELECT company_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not bank: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,bank["company_id"])
    if payload.amount==0: raise HTTPException(status_code=422,detail="El movimiento bancario no puede ser cero.")
    try:
        row=db.execute(text("INSERT INTO finance_bank_statement_lines(bank_account_id,transaction_date,reference,description,amount) VALUES(:bank,:date,:reference,:description,:amount) RETURNING id,bank_account_id,transaction_date,reference,description,amount,status,journal_entry_id,created_at"),{"bank":bank_account_id,**payload.model_dump()}).mappings().first()
        _audit(db,claims,"finance.bank_statement_line.created",bank["company_id"],"bank_statement_line",str(row["id"]));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo registrar el movimiento; revisa si ya existe.") from exc
    return dict(row)


@app.post("/api/v1/finance/bank-accounts/{bank_account_id}/statement-lines/{line_id}/match", tags=["treasury"])
def match_bank_statement_line(bank_account_id: UUID, line_id: UUID, journal_entry_id: UUID, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    bank=db.execute(text("SELECT company_id,account_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not bank: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,bank["company_id"])
    line=db.execute(text("SELECT * FROM finance_bank_statement_lines WHERE id=:line AND bank_account_id=:bank"),{"line":line_id,"bank":bank_account_id}).mappings().first()
    if not line: raise HTTPException(status_code=404,detail="Movimiento de extracto no encontrado.")
    if line["status"]!="unmatched": raise HTTPException(status_code=409,detail="Solo se concilian movimientos sin conciliar.")
    entry=db.execute(text("SELECT id,company_id,entry_date,status FROM journal_entries WHERE id=:id"),{"id":journal_entry_id}).mappings().first()
    if not entry or entry["company_id"]!=bank["company_id"] or entry["status"]!="posted" or entry["entry_date"]!=line["transaction_date"]:
        raise HTTPException(status_code=422,detail="El asiento debe estar contabilizado, pertenecer a la empresa y tener la misma fecha.")
    ledger_net=db.execute(text("SELECT COALESCE(SUM(debit_amount-credit_amount),0) FROM journal_entry_lines WHERE journal_entry_id=:entry AND account_id=:account"),{"entry":journal_entry_id,"account":bank["account_id"]}).scalar_one()
    if ledger_net!=line["amount"]: raise HTTPException(status_code=422,detail="El movimiento neto del asiento en la cuenta bancaria no coincide con el extracto.")
    db.execute(text("UPDATE finance_bank_statement_lines SET status='matched',journal_entry_id=:entry WHERE id=:id"),{"entry":journal_entry_id,"id":line_id})
    db.commit()
    return {"id":line_id,"status":"matched","journal_entry_id":journal_entry_id}


@app.post("/api/v1/finance/bank-accounts/{bank_account_id}/statement-lines/{line_id}/unmatch", tags=["treasury"])
def unmatch_bank_statement_line(bank_account_id: UUID,line_id: UUID,db:Session=Depends(get_db),claims:dict=Depends(require_claims)):
    bank=db.execute(text("SELECT company_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not bank: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,bank["company_id"])
    result=db.execute(text("UPDATE finance_bank_statement_lines SET status='unmatched',journal_entry_id=NULL WHERE id=:line AND bank_account_id=:bank AND status='matched'"),{"line":line_id,"bank":bank_account_id})
    if not result.rowcount: raise HTTPException(status_code=404,detail="Movimiento conciliado no encontrado.")
    db.commit();return {"id":line_id,"status":"unmatched"}


@app.post("/api/v1/finance/documents/{document_id}/post", tags=["documents"])
def post_finance_document(document_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    doc=db.execute(text("SELECT * FROM finance_documents WHERE id=:id"),{"id":document_id}).mappings().first()
    if not doc: raise HTTPException(status_code=404,detail="Comprobante no encontrado.")
    require_company(claims,doc["company_id"])
    if doc["status"] != "draft": raise HTTPException(status_code=409,detail="Solo se contabilizan comprobantes en borrador.")
    lines=db.execute(text("SELECT * FROM finance_document_lines WHERE document_id=:id ORDER BY line_number"),{"id":document_id}).mappings().all()
    if not lines: raise HTTPException(status_code=422,detail="No hay conceptos que contabilizar.")
    is_sales=doc["document_type"] in ("sales_invoice","sales_credit_note")
    sign=Decimal("-1") if doc["document_type"] in ("sales_credit_note","purchase_credit_note") else Decimal("1")
    accounts=db.execute(text("SELECT id,account_type,account_subtype FROM accounts WHERE company_id=:c AND is_active AND allow_posting"),{"c":doc["company_id"]}).mappings().all()
    by_id={row["id"]:(row["account_type"],row["account_subtype"]) for row in accounts}
    party_type="asset" if is_sales else "liability"
    party_account=doc["control_account_id"]
    required_party_subtype = "receivable" if is_sales else "payable"
    if not party_account or by_id.get(party_account, (None,None))[0] != party_type or by_id.get(party_account, (None,None))[1] != required_party_subtype:
        raise HTTPException(status_code=422,detail=f"Selecciona una cuenta de {'cuentas por cobrar' if is_sales else 'cuentas por pagar'} del tipo {party_type} en el comprobante.")
    journal_lines=[]
    total=doc["total"]
    if is_sales:
        journal_lines.append({"account_id":party_account,"debit_amount":total,"credit_amount":Decimal('0'),"description":doc["party_name"]})
    else:
        journal_lines.append({"account_id":party_account,"debit_amount":Decimal('0'),"credit_amount":total,"description":doc["party_name"]})
    for line in lines:
        account_data=by_id.get(line["account_id"])
        if not account_data: raise HTTPException(status_code=422,detail="Una cuenta del comprobante ya no está habilitada.")
        acct_type=account_data[0]
        amount=line["net_amount"]
        # Sales documents post revenue to credit; purchase bills post expense to debit.
        if is_sales:
            debit,credit=Decimal('0'),amount
        else:
            debit,credit=amount,Decimal('0')
        journal_lines.append({"account_id":line["account_id"],"debit_amount":max(debit,Decimal('0')),"credit_amount":max(credit,Decimal('0')),"description":line["description"]})
        if line["tax_amount"]:
            tax_account=doc["tax_account_id"]
            required_tax_type="liability" if is_sales else "asset"
            if not tax_account or by_id.get(tax_account, (None,None))[0] != required_tax_type or by_id.get(tax_account, (None,None))[1] != "tax": raise HTTPException(status_code=422,detail="Selecciona una cuenta fiscal del subtipo impuesto y tipo contable correcto.")
            tax=line["tax_amount"]
            if is_sales: debit,credit=Decimal('0'),tax
            else: debit,credit=tax,Decimal('0')
            journal_lines.append({"account_id":tax_account,"debit_amount":max(debit,Decimal('0')),"credit_amount":max(credit,Decimal('0')),"description":"Impuesto " + line["description"]})
    # A credit note reverses every debit/credit side of its corresponding invoice type.
    if sign < 0:
        for item in journal_lines:
            item["debit_amount"],item["credit_amount"]=item["credit_amount"],item["debit_amount"]
    debit_total=sum((x["debit_amount"] for x in journal_lines),Decimal('0'))
    credit_total=sum((x["credit_amount"] for x in journal_lines),Decimal('0'))
    if abs(debit_total-credit_total)>=Decimal('0.01'):
        raise HTTPException(status_code=422,detail="El comprobante genera un asiento desbalanceado; revisa cuentas de concepto e impuestos.")
    entry_number=f"DOC-{doc['document_number']}"[:40]
    if db.execute(text("SELECT 1 FROM journal_entries WHERE company_id=:c AND entry_number=:n"),{"c":doc["company_id"],"n":entry_number}).first(): entry_number=f"DOC-{str(document_id)[:32]}"
    try:
        entry_id=db.execute(text("""
            INSERT INTO journal_entries(company_id,fiscal_year_id,fiscal_period_id,entry_number,entry_date,reference,description,currency,exchange_rate,total_debit,total_credit,created_by)
            VALUES(:company_id,:fiscal_year_id,:fiscal_period_id,:entry_number,:entry_date,:reference,:description,:currency,:exchange_rate,:debit,:credit,:actor) RETURNING id
        """),{"company_id":doc["company_id"],"fiscal_year_id":doc["fiscal_year_id"],"fiscal_period_id":doc["fiscal_period_id"],"entry_number":entry_number,"entry_date":doc["issue_date"],"reference":doc["document_number"],"description":f"Contabilización {doc['document_type']} {doc['document_number']} · {doc['party_name']}","currency":doc["currency"],"exchange_rate":doc["exchange_rate"],"debit":debit_total,"credit":credit_total,"actor":claims.get("sub")}).scalar_one()
        for index,item in enumerate(journal_lines,1):
            db.execute(text("INSERT INTO journal_entry_lines(journal_entry_id,account_id,line_number,description,debit_amount,credit_amount) VALUES(:entry,:account,:line,:description,:debit,:credit)"),{"entry":entry_id,"account":item["account_id"],"line":index,"description":item["description"],"debit":item["debit_amount"],"credit":item["credit_amount"]})
        db.execute(text("UPDATE journal_entries SET status='posted',posted_by=:actor,posted_at=now(),updated_at=now() WHERE id=:id"),{"actor":claims.get("sub"),"id":entry_id})
        db.execute(text("UPDATE finance_documents SET status='posted',journal_entry_id=:entry,posted_by=:actor,posted_at=now(),updated_at=now() WHERE id=:id"),{"entry":entry_id,"actor":claims.get("sub"),"id":document_id})
        _audit(db,claims,"finance.document.posted",doc["company_id"],"finance_document",str(document_id),{"journal_entry_id":str(entry_id)}); db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo contabilizar el comprobante.") from exc
    return _document_response(db,document_id)


@app.get("/api/v1/finance/reports/trial-balance", response_model=list[TrialBalanceRow], tags=["reports"])
def trial_balance(
    company_id: UUID,
    fiscal_year_id: UUID,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    """Balances de asientos publicados por cuenta, en moneda de empresa."""
    require_company(claims, company_id)
    if not db.execute(text("SELECT 1 FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id, "company_id": company_id}).first():
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(
        text("""
            SELECT a.id AS account_id, a.code, a.name, a.account_type,
                   COALESCE(SUM(l.debit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS debit,
                   COALESCE(SUM(l.credit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS credit
            FROM accounts a
            LEFT JOIN journal_entry_lines l ON l.account_id = a.id
            LEFT JOIN journal_entries j ON j.id = l.journal_entry_id
                AND j.company_id = a.company_id AND j.fiscal_year_id = :fiscal_year_id AND j.status = 'posted'
            WHERE a.company_id = :company_id AND a.allow_posting
            GROUP BY a.id, a.code, a.name, a.account_type
            ORDER BY a.code
        """),
        {"company_id": company_id, "fiscal_year_id": fiscal_year_id},
    ).mappings().all()
    result = []
    for row in rows:
        debit, credit = row["debit"], row["credit"]
        if debit == 0 and credit == 0:
            continue
        result.append(TrialBalanceRow(
            account_id=row["account_id"], code=row["code"], name=row["name"], account_type=row["account_type"],
            debit=debit, credit=credit, balance=debit - credit,
        ))
    return result


@app.get("/api/v1/finance/reports/trial-balance-detailed", tags=["reports"])
def trial_balance_detailed(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Saldos de apertura, movimientos del ejercicio y saldos de cierre."""
    require_company(claims, company_id)
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id, "company_id": company_id}).mappings().first()
    if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(text("""
        SELECT a.id AS account_id,a.code,a.name,a.account_type,
          COALESCE(SUM(l.debit_amount) FILTER (WHERE j.entry_date < :start_date),0) AS opening_debit,
          COALESCE(SUM(l.credit_amount) FILTER (WHERE j.entry_date < :start_date),0) AS opening_credit,
          COALESCE(SUM(l.debit_amount) FILTER (WHERE j.entry_date BETWEEN :start_date AND :end_date),0) AS period_debit,
          COALESCE(SUM(l.credit_amount) FILTER (WHERE j.entry_date BETWEEN :start_date AND :end_date),0) AS period_credit
        FROM accounts a
        LEFT JOIN journal_entry_lines l ON l.account_id=a.id
        LEFT JOIN journal_entries j ON j.id=l.journal_entry_id AND j.company_id=a.company_id AND j.status='posted' AND j.entry_date<=:end_date
        WHERE a.company_id=:company_id AND a.allow_posting
        GROUP BY a.id,a.code,a.name,a.account_type ORDER BY a.code
    """), {"start_date":fy["start_date"],"end_date":fy["end_date"],"company_id":company_id}).mappings().all()
    result=[]
    for row in rows:
        opening_net=row["opening_debit"]-row["opening_credit"]
        closing_net=opening_net+row["period_debit"]-row["period_credit"]
        if not any((row["opening_debit"],row["opening_credit"],row["period_debit"],row["period_credit"])): continue
        result.append({**dict(row),"opening_balance":opening_net,"closing_debit":max(closing_net,Decimal("0")),"closing_credit":max(-closing_net,Decimal("0"))})
    totals={k:sum((r[k] for r in result),Decimal("0")) for k in ("opening_debit","opening_credit","period_debit","period_credit","closing_debit","closing_credit")}
    return {"rows":result,"totals":totals,"balanced":abs(totals["closing_debit"]-totals["closing_credit"])<Decimal("0.01"),"currency":"PEN"}


@app.get("/api/v1/finance/reports/income-statement", tags=["reports"])
def income_statement(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Estado de resultados: ingresos menos gastos del ejercicio (asientos publicados)."""
    require_company(claims, company_id)
    fiscal_year = db.execute(text("SELECT id FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id, "company_id": company_id}).first()
    if not fiscal_year:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(
        text("""
            SELECT a.id AS account_id, a.code, a.name, a.account_type,
                   COALESCE(SUM(l.debit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS debit,
                   COALESCE(SUM(l.credit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS credit
            FROM accounts a
            LEFT JOIN journal_entry_lines l ON l.account_id = a.id
            LEFT JOIN journal_entries j ON j.id = l.journal_entry_id
                AND j.company_id = a.company_id AND j.fiscal_year_id = :fy AND j.status = 'posted'
            WHERE a.company_id = :company_id AND a.account_type IN ('revenue','expense') AND a.allow_posting
            GROUP BY a.id, a.code, a.name, a.account_type
            ORDER BY a.account_type, a.code
        """),
        {"company_id": company_id, "fy": fiscal_year_id},
    ).mappings().all()
    revenue, expenses = [], []
    for row in rows:
        net = row["credit"] - row["debit"] if row["account_type"] == "revenue" else row["debit"] - row["credit"]
        item = {
            "account_id": row["account_id"], "code": row["code"], "name": row["name"],
            "account_type": row["account_type"], "debit": str(row["debit"]), "credit": str(row["credit"]),
            "net": str(net),
        }
        if row["account_type"] == "revenue":
            revenue.append(item)
        else:
            expenses.append(item)
    total_revenue = sum((Decimal(item["net"]) for item in revenue), Decimal("0"))
    total_expenses = sum((Decimal(item["net"]) for item in expenses), Decimal("0"))
    return {
        "revenue": revenue,
        "expenses": expenses,
        "total_revenue": str(total_revenue),
        "total_expenses": str(total_expenses),
        "net_result": str(total_revenue - total_expenses),
        "currency": "PEN",
    }


@app.get("/api/v1/finance/reports/balance-sheet", tags=["reports"])
def balance_sheet(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Balance general del ejercicio: activos, pasivos, patrimonio y resultado del periodo."""
    require_company(claims, company_id)
    fy = db.execute(text("SELECT end_date FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id, "company_id": company_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(
        text("""
            SELECT a.id AS account_id, a.code, a.name, a.account_type,
                   COALESCE(SUM(l.debit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS debit,
                   COALESCE(SUM(l.credit_amount) FILTER (WHERE j.id IS NOT NULL), 0) AS credit
            FROM accounts a
            LEFT JOIN journal_entry_lines l ON l.account_id = a.id
            LEFT JOIN journal_entries j ON j.id = l.journal_entry_id
                AND j.company_id = a.company_id AND j.entry_date <= :as_of AND j.status = 'posted'
            WHERE a.company_id = :company_id AND a.account_type IN ('asset','liability','equity') AND a.allow_posting
            GROUP BY a.id, a.code, a.name, a.account_type
            ORDER BY a.account_type, a.code
        """),
        {"company_id": company_id, "as_of": fy["end_date"]},
    ).mappings().all()

    def section_balance(row) -> Decimal:
        if row["account_type"] == "asset":
            return row["debit"] - row["credit"]
        return row["credit"] - row["debit"]

    assets, liabilities, equity = [], [], []
    for row in rows:
        item = {
            "account_id": row["account_id"], "code": row["code"], "name": row["name"],
            "account_type": row["account_type"], "debit": str(row["debit"]), "credit": str(row["credit"]),
            "balance": str(section_balance(row)),
        }
        if row["account_type"] == "asset":
            assets.append(item)
        elif row["account_type"] == "liability":
            liabilities.append(item)
        else:
            equity.append(item)
    total_assets = sum((Decimal(item["balance"]) for item in assets), Decimal("0"))
    total_liabilities = sum((Decimal(item["balance"]) for item in liabilities), Decimal("0"))
    total_equity = sum((Decimal(item["balance"]) for item in equity), Decimal("0"))
    income = income_statement(company_id, fiscal_year_id, db, claims)
    net_result = Decimal(income["net_result"])
    liabilities_plus_equity = total_liabilities + total_equity + net_result
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "net_result": str(net_result),
        "totals": {
            "assets": str(total_assets),
            "liabilities": str(total_liabilities),
            "equity": str(total_equity),
            "liabilities_plus_equity": str(liabilities_plus_equity),
        },
        "balanced": abs(total_assets - liabilities_plus_equity) < Decimal("0.01"),
        "currency": "PEN",
    }


@app.get("/api/v1/finance/reports/general-ledger", tags=["reports"])
def general_ledger(company_id: UUID, fiscal_year_id: UUID, account_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Libro mayor de una cuenta: movimientos publicados con saldo corrido."""
    require_company(claims, company_id)
    account = db.execute(
        text("SELECT id, code, name, account_type, currency FROM accounts WHERE id = :id AND company_id = :company_id"),
        {"id": account_id, "company_id": company_id},
    ).mappings().first()
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada en esta empresa.")
    rows = db.execute(
        text("""
            SELECT j.entry_number, j.entry_date, j.reference, l.line_number, l.description, l.debit_amount, l.credit_amount
            FROM journal_entry_lines l
            JOIN journal_entries j ON j.id = l.journal_entry_id
            WHERE j.company_id = :company_id AND j.fiscal_year_id = :fy AND j.status = 'posted' AND l.account_id = :account_id
            ORDER BY j.entry_date, j.entry_number, l.line_number
        """),
        {"company_id": company_id, "fy": fiscal_year_id, "account_id": account_id},
    ).mappings().all()
    balance = Decimal("0")
    entries = []
    for row in rows:
        movement = row["debit_amount"] - row["credit_amount"]
        balance += movement
        entries.append({
            "entry_number": row["entry_number"],
            "entry_date": row["entry_date"].isoformat(),
            "reference": row["reference"],
            "line_number": row["line_number"],
            "description": row["description"],
            "debit": str(row["debit_amount"]),
            "credit": str(row["credit_amount"]),
            "movement": str(movement),
            "balance": str(balance),
        })
    return {
        "account": {"id": account["id"], "code": account["code"], "name": account["name"], "account_type": account["account_type"], "currency": account["currency"]},
        "entries": entries,
        "final_balance": str(balance),
        "currency": "PEN",
    }


@app.get("/api/v1/finance/reports/receivables-aging", tags=["reports"])
def receivables_aging(company_id: UUID, as_of: date | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    return _documents_aging(company_id, "receivables", as_of or date.today(), db, claims)


@app.get("/api/v1/finance/reports/payables-aging", tags=["reports"])
def payables_aging(company_id: UUID, as_of: date | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    return _documents_aging(company_id, "payables", as_of or date.today(), db, claims)


def _documents_aging(company_id: UUID, kind: str, as_of: date, db: Session, claims: dict) -> dict:
    """Antigüedad de comprobantes contabilizados usando aplicaciones y notas vinculadas."""
    require_company(claims, company_id)
    base_type = "sales_invoice" if kind == "receivables" else "purchase_bill"
    docs = db.execute(text("""
        SELECT d.id,d.document_number,d.party_name,d.issue_date,d.due_date,d.total,d.currency,
          COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id AND s.settled_at<=:as_of),0) AS paid,
          COALESCE((SELECT SUM(c.total) FROM finance_documents c WHERE c.related_document_id=d.id AND c.status='posted' AND c.issue_date<=:as_of),0) AS credited
        FROM finance_documents d
        WHERE d.company_id=:company_id AND d.document_type=:document_type AND d.status='posted' AND d.issue_date<=:as_of
        ORDER BY COALESCE(d.due_date,d.issue_date),d.document_number
    """), {"company_id":company_id,"document_type":base_type,"as_of":as_of}).mappings().all()
    totals={"current":Decimal("0"),"days_1_30":Decimal("0"),"days_31_60":Decimal("0"),"days_61_90":Decimal("0"),"over_90":Decimal("0"),"total":Decimal("0")}
    result=[]
    for doc in docs:
        outstanding=max(Decimal("0"),doc["total"]-doc["paid"]-doc["credited"])
        if outstanding<=0: continue
        due=doc["due_date"] or doc["issue_date"]
        overdue=max(0,(as_of-due).days)
        bucket="current" if overdue<=0 else "days_1_30" if overdue<=30 else "days_31_60" if overdue<=60 else "days_61_90" if overdue<=90 else "over_90"
        buckets={key:Decimal("0") for key in totals if key!="total"}
        buckets[bucket]=outstanding
        totals[bucket]+=outstanding; totals["total"]+=outstanding
        result.append({"id":doc["id"],"document_number":doc["document_number"],"party_name":doc["party_name"],"issue_date":doc["issue_date"],"due_date":doc["due_date"],"days_overdue":overdue,"total":doc["total"],"paid_amount":doc["paid"],"credited_amount":doc["credited"],"outstanding_amount":outstanding,"currency":doc["currency"],"buckets":buckets})
    return {"kind":kind,"company_id":company_id,"as_of":as_of,"rows":result,"totals":totals,"basis":"comprobantes contabilizados menos aplicaciones de pago y notas de crédito contabilizadas"}


@app.get("/api/v1/finance/reports/cash-flow", tags=["reports"])
def cash_flow_statement(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Variación de efectivo por actividad; exige marcar cuentas de caja/banco y clasificar contrapartidas."""
    require_company(claims, company_id)
    if not db.execute(text("SELECT 1 FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id, "company_id": company_id}).first():
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:company_id"), {"id": fiscal_year_id,"company_id": company_id}).mappings().first()
    if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    entry_rows = db.execute(text("""
        SELECT j.id AS entry_id,j.entry_number,j.entry_date,l.account_id,l.debit_amount,l.credit_amount,
               a.code,a.name,a.account_subtype,a.cash_flow_category
        FROM journal_entries j JOIN journal_entry_lines l ON l.journal_entry_id=j.id
        JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:company_id AND j.status='posted' AND j.entry_date BETWEEN :start_date AND :end_date
        ORDER BY j.entry_date,j.entry_number,l.line_number
    """), {"company_id":company_id,"start_date":fy["start_date"],"end_date":fy["end_date"]}).mappings().all()
    by_entry: dict[UUID,list[dict]]={}
    for row in entry_rows: by_entry.setdefault(row["entry_id"],[]).append(dict(row))
    totals={"operating":Decimal("0"),"investing":Decimal("0"),"financing":Decimal("0"),"unclassified":Decimal("0")}
    cash_accounts: dict[UUID,dict]={}
    details=[]
    for entry_id,lines in by_entry.items():
        cash_lines=[line for line in lines if line["account_subtype"] in ("cash","bank")]
        if not cash_lines: continue
        counterparts=[line for line in lines if line["account_subtype"] not in ("cash","bank")]
        categories={line["cash_flow_category"] for line in counterparts if line["cash_flow_category"]}
        category=next(iter(categories)) if len(categories)==1 and all(line["cash_flow_category"] for line in counterparts) else "unclassified"
        for line in cash_lines:
            change=line["debit_amount"]-line["credit_amount"]
            totals[category]+=change
            acc=cash_accounts.setdefault(line["account_id"],{"account_id":line["account_id"],"code":line["code"],"name":line["name"],"subtype":line["account_subtype"],"net_change":Decimal("0")})
            acc["net_change"]+=change
            details.append({"date":line["entry_date"].isoformat(),"entry_number":line["entry_number"],"account_code":line["code"],"account_name":line["name"],"cash_change":str(change),"category":category})
    return {
        "company_id":company_id,"fiscal_year_id":fiscal_year_id,"start_date":fy["start_date"],"end_date":fy["end_date"],
        "currency":"PEN","method":"direct_from_posted_journals",
        "categories":{key:str(value) for key,value in totals.items()},
        "net_change":str(sum(totals.values(),Decimal("0"))),
        "classification_note":"Las líneas de efectivo se clasifican por cash_flow_category de sus contrapartidas; las que no tienen clasificación van a unclassified.",
        "accounts":[{**item,"net_change":str(item["net_change"])} for item in cash_accounts.values()],
        "details":details,
    }


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/summary", tags=["reports"])
def summary(company_id: UUID | None = None, fiscal_year_id: UUID | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Resumen ejecutivo basado solo en movimientos publicados reales."""
    if company_id is None:
        platform_admin = claims.get("platform_admin") is True
        allowed = {str(c) for c in claims.get("companies", [])}
        if platform_admin:
            company_id = None
        elif allowed:
            company_id = UUID(next(iter(allowed)))
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a empresa.")
    if company_id is not None:
        require_company(claims, company_id)
    params: dict = {}
    company_filter_j = ""
    company_filter_a = ""
    company_filter_d = ""
    if company_id:
        params["company_id"] = company_id
        company_filter_j = "AND j.company_id = :company_id"
        company_filter_a = "AND company_id = :company_id"
        company_filter_d = "AND company_id = :company_id"
    year_filter = ""
    if fiscal_year_id:
        year_filter = "AND j.fiscal_year_id = :fiscal_year_id"
        params["fiscal_year_id"] = fiscal_year_id
    revenue = db.execute(
        text(f"""
            SELECT COALESCE(SUM(l.credit_amount - l.debit_amount), 0)
            FROM journal_entry_lines l
            JOIN journal_entries j ON j.id = l.journal_entry_id
            JOIN accounts a ON a.id = l.account_id
            WHERE a.account_type = 'revenue' AND j.status = 'posted' {year_filter} {company_filter_j}
        """),
        params,
    ).scalar_one()
    expenses = db.execute(
        text(f"""
            SELECT COALESCE(SUM(l.debit_amount - l.credit_amount), 0)
            FROM journal_entry_lines l
            JOIN journal_entries j ON j.id = l.journal_entry_id
            JOIN accounts a ON a.id = l.account_id
            WHERE a.account_type = 'expense' AND j.status = 'posted' {year_filter} {company_filter_j}
        """),
        params,
    ).scalar_one()
    pending = db.execute(
        text(f"SELECT count(*) FROM journal_entries WHERE status = 'draft' {company_filter_d}"),
        params,
    ).scalar_one()
    accounts_count = db.execute(
        text(f"SELECT count(*) FROM accounts WHERE is_active {company_filter_a}"),
        params,
    ).scalar_one()
    return {
        "revenue": str(revenue),
        "expenses": str(expenses),
        "net_result": str(revenue - expenses),
        "draft_entries": pending,
        "active_accounts": accounts_count,
        "currency": "PEN",
        "has_data": bool(revenue or expenses or pending),
    }
