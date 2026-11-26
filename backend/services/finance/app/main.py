"""Aethereon Finance Service — FastAPI microservice (port 18003).

Módulo financiero completo: empresas, ejercicios/periodos fiscales, plan de
cuentas, asientos contables (borrador/publicación/reversión), presupuestos con
líneas y ejecución, tasas de impuesto, tipo de cambio y estados financieros
(balance de comprobación, estado de resultados, balance general, libro mayor).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import csv
import io
import logging
from typing import Optional
from uuid import UUID, uuid4
import hashlib
import json

import jwt
import math
from fastapi import FastAPI, Depends, HTTPException, Request, Query, UploadFile, File, status
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
    AuxiliaryCreate,
    AuxiliaryResponse,
    AuxiliaryUpdate,
    BudgetCreate,
    BudgetLineCreate,
    BudgetLineDetail,
    BudgetLineResponse,
    BudgetLineUpdate,
    BudgetResponse,
    BudgetUpdate,
    BudgetTransferCreate,
    BudgetTransferResponse,
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
    CostCenterCreate,
    CostCenterResponse,
    CostCenterUpdate,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    AssetCategoryCreate,
    AssetCategoryResponse,
    AssetCategoryUpdate,
    FixedAssetCreate,
    FixedAssetResponse,
    FixedAssetUpdate,
    AssetDepreciationLineResponse,
    PaymentTermCreate,
    PaymentTermResponse,
    PaymentTermUpdate,
    WithholdingTypeCreate,
    WithholdingTypeResponse,
    WithholdingTypeUpdate,
    InvoiceSeriesCreate,
    InvoiceSeriesResponse,
    InvoiceSeriesUpdate,
    PurchaseRegisterEntryCreate,
    PurchaseRegisterEntryResponse,
    SalesRegisterEntryCreate,
    SalesRegisterEntryResponse,
    ClosingEntryCreate,
    ClosingEntryResponse,
    OpeningBalanceCreate,
    OpeningBalanceResponse,
    BudgetCDPCreate, BudgetCDPResponse,
    BudgetCommitmentCreate, BudgetCommitmentResponse,
    PaymentOrderCreate, PaymentOrderResponse,
    FinanceBankCreate, FinanceBankResponse,
)

settings = get_settings()
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("aethereon.finance.health")


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
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        logger.error("Database readiness check failed: error_type=%s sqlstate=%s", type(original).__name__ if original else type(exc).__name__, sqlstate)
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
    fy = db.execute(text("SELECT company_id, is_closed, start_date, end_date FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    acct_count = db.execute(text("SELECT COUNT(*) FROM accounts WHERE company_id = :cid AND is_active"), {"cid": fy["company_id"]}).scalar_one()
    if acct_count == 0:
        raise HTTPException(status_code=409, detail="No se puede crear asientos: debe crear/importar el Plan de Cuentas primero.")
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")
    if not periods:
        raise HTTPException(status_code=422, detail="Debes indicar al menos un periodo.")
    for item in periods:
        if item.end_date < item.start_date:
            raise HTTPException(status_code=422, detail=f"El periodo {item.code} termina antes de su fecha de inicio.")
        if item.start_date < fy["start_date"] or item.end_date > fy["end_date"]:
            raise HTTPException(status_code=422, detail=f"Las fechas del periodo {item.code} deben estar dentro del ejercicio {fy['start_date']}–{fy['end_date']}.")
        overlap = db.execute(text("SELECT code FROM fiscal_periods WHERE fiscal_year_id=:fy AND start_date<=:end_date AND end_date>=:start_date LIMIT 1"),
                             {"fy": fiscal_year_id, "start_date": item.start_date, "end_date": item.end_date}).scalar()
        if overlap:
            raise HTTPException(status_code=409, detail=f"El periodo {item.code} se solapa con el periodo existente {overlap}.")
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

@app.get("/api/v1/finance/auxiliaries",response_model=list[AuxiliaryResponse],tags=["auxiliaries"])
def list_auxiliaries(company_id:UUID,auxiliary_type:str|None=None,is_active:bool|None=None,q:str|None=None,db:Session=Depends(get_db),claims:dict=Depends(require_claims)):
    require_company(claims,company_id)
    conditions=["company_id=:company_id"];params:dict={"company_id":company_id}
    if auxiliary_type:conditions.append("auxiliary_type=:auxiliary_type");params["auxiliary_type"]=auxiliary_type
    if is_active is not None:conditions.append("is_active=:is_active");params["is_active"]=is_active
    if q:conditions.append("(code ILIKE :q OR name ILIKE :q OR COALESCE(tax_id,'') ILIKE :q OR COALESCE(email,'') ILIKE :q)");params["q"]=f"%{q}%"
    rows=db.execute(text(f"SELECT id,company_id,code,name,auxiliary_type,tax_id,user_id,email,phone,address,is_active,created_at,updated_at FROM finance_auxiliaries WHERE {' AND '.join(conditions)} ORDER BY code"),params).mappings().all()
    return [AuxiliaryResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/auxiliaries",response_model=AuxiliaryResponse,status_code=201,tags=["auxiliaries"])
def create_auxiliary(payload:AuxiliaryCreate,db:Session=Depends(get_db),claims:dict=Depends(require_claims)):
    require_company(claims,payload.company_id)
    if payload.user_id and not db.execute(text("SELECT 1 FROM users WHERE id=:id AND is_active"),{"id":payload.user_id}).first():
        raise HTTPException(status_code=422,detail="El usuario vinculado no existe o está inactivo.")
    try:
        row=db.execute(text("""
            INSERT INTO finance_auxiliaries(company_id,code,name,auxiliary_type,tax_id,user_id,email,phone,address,is_active)
            VALUES(:company_id,:code,:name,:auxiliary_type,:tax_id,:user_id,:email,:phone,:address,:is_active)
            RETURNING id,company_id,code,name,auxiliary_type,tax_id,user_id,email,phone,address,is_active,created_at,updated_at
        """),payload.model_dump()).mappings().first()
        _audit(db,claims,"finance.auxiliary.created",payload.company_id,"finance_auxiliary",str(row["id"]));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo crear el auxiliar; verifica que el código no esté duplicado en la empresa.") from exc
    return AuxiliaryResponse(**dict(row))


@app.patch("/api/v1/finance/auxiliaries/{auxiliary_id}",response_model=AuxiliaryResponse,tags=["auxiliaries"])
def update_auxiliary(auxiliary_id:UUID,payload:AuxiliaryUpdate,db:Session=Depends(get_db),claims:dict=Depends(require_claims)):
    current=db.execute(text("SELECT company_id FROM finance_auxiliaries WHERE id=:id"),{"id":auxiliary_id}).mappings().first()
    if not current:raise HTTPException(status_code=404,detail="Auxiliar no encontrado.")
    require_company(claims,current["company_id"])
    changes=payload.model_dump(exclude_unset=True)
    if not changes:raise HTTPException(status_code=400,detail="Sin cambios para aplicar.")
    if changes.get("user_id") and not db.execute(text("SELECT 1 FROM users WHERE id=:id AND is_active"),{"id":changes["user_id"]}).first():
        raise HTTPException(status_code=422,detail="El usuario vinculado no existe o está inactivo.")
    assignments=", ".join(f"{key}=:{key}" for key in changes);changes["id"]=auxiliary_id
    try:
        row=db.execute(text(f"UPDATE finance_auxiliaries SET {assignments},updated_at=now() WHERE id=:id RETURNING id,company_id,code,name,auxiliary_type,tax_id,user_id,email,phone,address,is_active,created_at,updated_at"),changes).mappings().first()
        _audit(db,claims,"finance.auxiliary.updated",current["company_id"],"finance_auxiliary",str(auxiliary_id));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo actualizar el auxiliar.") from exc
    return AuxiliaryResponse(**dict(row))


@app.delete("/api/v1/finance/auxiliaries/{auxiliary_id}",status_code=204,tags=["auxiliaries"])
def deactivate_auxiliary(auxiliary_id:UUID,db:Session=Depends(get_db),claims:dict=Depends(require_claims)):
    row=db.execute(text("SELECT company_id,is_active FROM finance_auxiliaries WHERE id=:id"),{"id":auxiliary_id}).mappings().first()
    if not row:raise HTTPException(status_code=404,detail="Auxiliar no encontrado.")
    require_company(claims,row["company_id"])
    db.execute(text("UPDATE finance_auxiliaries SET is_active=FALSE,updated_at=now() WHERE id=:id"),{"id":auxiliary_id})
    _audit(db,claims,"finance.auxiliary.deactivated",row["company_id"],"finance_auxiliary",str(auxiliary_id));db.commit()

PCGE_BASIC_TEMPLATE = [
    {"code":"1","name":"ACTIVO","type":"asset","group":True,"parent":None},
    {"code":"10","name":"Efectivo y equivalentes de efectivo","type":"asset","group":True,"parent":"1"},
    {"code":"101","name":"Caja","type":"asset","group":False,"parent":"10","subtype":"cash"},
    {"code":"104","name":"Cuentas corrientes en instituciones financieras","type":"asset","group":False,"parent":"10","subtype":"bank"},
    {"code":"12","name":"Cuentas por cobrar comerciales - terceros","type":"asset","group":True,"parent":"1"},
    {"code":"121","name":"Facturas, boletas y otros comprobantes por cobrar","type":"asset","group":False,"parent":"12","subtype":"receivable"},
    {"code":"20","name":"Mercaderías","type":"asset","group":True,"parent":"1"},
    {"code":"201","name":"Mercaderías","type":"asset","group":False,"parent":"20","subtype":"inventory"},
    {"code":"33","name":"Propiedad, planta y equipo","type":"asset","group":True,"parent":"1"},
    {"code":"331","name":"Terrenos","type":"asset","group":False,"parent":"33","subtype":"fixed_asset","cash_flow_category":"investing"},
    {"code":"333","name":"Maquinaria y equipo de explotación","type":"asset","group":False,"parent":"33","subtype":"fixed_asset","cash_flow_category":"investing"},
    {"code":"3","name":"PATRIMONIO NETO","type":"equity","group":True,"parent":None},
    {"code":"50","name":"Capital","type":"equity","group":True,"parent":"3"},
    {"code":"501","name":"Capital social","type":"equity","group":False,"parent":"50","subtype":"equity"},
    {"code":"4","name":"PASIVO","type":"liability","group":True,"parent":None},
    {"code":"40","name":"Tributos, contraprestaciones y aportes por pagar","type":"liability","group":True,"parent":"4"},
    {"code":"401","name":"Gobierno central - tributos por pagar","type":"liability","group":False,"parent":"40","subtype":"tax"},
    {"code":"42","name":"Cuentas por pagar comerciales - terceros","type":"liability","group":True,"parent":"4"},
    {"code":"421","name":"Facturas, boletas y otros comprobantes por pagar","type":"liability","group":False,"parent":"42","subtype":"payable"},
    {"code":"6","name":"GASTOS POR NATURALEZA","type":"expense","group":True,"parent":None},
    {"code":"63","name":"Gastos de servicios prestados por terceros","type":"expense","group":True,"parent":"6"},
    {"code":"631","name":"Transporte, correos y gastos de viaje","type":"expense","group":False,"parent":"63","subtype":"expense","cash_flow_category":"operating"},
    {"code":"636","name":"Servicios básicos","type":"expense","group":False,"parent":"63","subtype":"expense","cash_flow_category":"operating"},
    {"code":"7","name":"INGRESOS","type":"revenue","group":True,"parent":None},
    {"code":"70","name":"Ventas","type":"revenue","group":True,"parent":"7"},
    {"code":"701","name":"Ventas de mercaderías","type":"revenue","group":False,"parent":"70","subtype":"income","cash_flow_category":"operating"},
]

ACCOUNT_TEMPLATES = [{
    "code": "pe-pcge-basic",
    "name": "Plan peruano básico (PCGE)",
    "description": "Estructura inicial editable de cuentas peruanas comunes.",
    "country_code": "PE",
    "accounts": PCGE_BASIC_TEMPLATE,
}]


@app.get("/api/v1/finance/account-templates", tags=["accounts"])
def list_account_templates(claims: dict = Depends(require_claims)):
    return [{"code":t["code"],"name":t["name"],"description":t["description"],"country_code":t["country_code"],"account_count":len(t["accounts"]),"accounts":[{"code":item["code"],"name":item["name"],"account_type":item["type"],"is_group":item["group"],"parent_code":item["parent"]} for item in t["accounts"]]} for t in ACCOUNT_TEMPLATES]


@app.post("/api/v1/finance/account-templates/{template_code}/apply", tags=["accounts"])
def apply_account_template(template_code: str, company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims,company_id)
    template = next((item for item in ACCOUNT_TEMPLATES if item["code"] == template_code), None)
    if not template:raise HTTPException(status_code=404,detail="Plantilla de plan contable no encontrada.")
    company=db.execute(text("SELECT default_currency FROM companies WHERE id=:id AND is_active"),{"id":company_id}).mappings().first()
    if not company:raise HTTPException(status_code=404,detail="Empresa activa no encontrada.")
    created=[];skipped=[];mapping={}
    try:
        # Serialize account-plan replacement per company and prevent concurrent duplicate imports.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:company_id AS text), 739182))"), {"company_id": company_id})
        old_accounts=db.execute(text("SELECT id,code FROM accounts WHERE company_id=:company_id FOR UPDATE"),{"company_id":company_id}).all()
        old_ids=[r[0] for r in old_accounts]
        if old_ids:
            refs = [
                ("asientos contables", "SELECT count(*) FROM journal_entry_lines WHERE account_id = ANY(CAST(:ids AS uuid[]))"),
                ("líneas de comprobantes", "SELECT count(*) FROM finance_document_lines WHERE account_id = ANY(CAST(:ids AS uuid[]))"),
                ("cuentas de control/impuesto de comprobantes", "SELECT count(*) FROM finance_documents WHERE control_account_id = ANY(CAST(:ids AS uuid[])) OR tax_account_id = ANY(CAST(:ids AS uuid[]))"),
                ("partidas presupuestarias", "SELECT count(*) FROM budget_lines WHERE account_id = ANY(CAST(:ids AS uuid[]))"),
                ("cuentas bancarias", "SELECT count(*) FROM finance_bank_accounts WHERE account_id = ANY(CAST(:ids AS uuid[]))"),
                ("jerarquías o referencias externas", "SELECT count(*) FROM accounts child WHERE child.parent_id = ANY(CAST(:ids AS uuid[])) AND child.id <> ALL(CAST(:ids AS uuid[]))"),
            ]
            dependencies=[]
            for label,sql in refs:
                count=db.execute(text(sql),{"ids":old_ids}).scalar_one()
                if count: dependencies.append(f"{label}: {count}")
            # Defense in depth: discover any current or future FK into accounts not covered above.
            known_fk_columns={("accounts","parent_id"),("journal_entry_lines","account_id"),("finance_document_lines","account_id"),
                              ("finance_documents","control_account_id"),("finance_documents","tax_account_id"),
                              ("budget_lines","account_id"),("finance_bank_accounts","account_id")}
            fk_rows=db.execute(text("""
            SELECT tc.table_schema,tc.table_name,kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_catalog=tc.constraint_catalog AND ccu.constraint_schema=tc.constraint_schema AND ccu.constraint_name=tc.constraint_name
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_catalog=tc.constraint_catalog AND kcu.constraint_schema=tc.constraint_schema AND kcu.constraint_name=tc.constraint_name
            WHERE tc.constraint_type='FOREIGN KEY' AND ccu.table_schema='public' AND ccu.table_name='accounts' AND ccu.column_name='id'
            """)).all()
            for fk in fk_rows:
                schema_name,table_name,column_name=fk
                if schema_name != "public" or (table_name,column_name) in known_fk_columns: continue
                # Identifiers come only from PostgreSQL catalog metadata and are quoted.
                qtable='"'+table_name.replace('"','""')+'"'; qcol='"'+column_name.replace('"','""')+'"'
                count=db.execute(text(f"SELECT count(*) FROM {qtable} WHERE {qcol}=ANY(CAST(:ids AS uuid[]))"),{"ids":old_ids}).scalar_one()
                if count: dependencies.append(f"referencias en {table_name}.{column_name}: {count}")
            if dependencies:
                raise HTTPException(status_code=409,detail="No se reemplazó el plan de cuentas porque tiene dependencias: "+"; ".join(dependencies)+". Los datos existentes se conservaron.")
            # Safe only after checking every application-level account reference above.
            db.execute(text("DELETE FROM accounts WHERE id = ANY(CAST(:ids AS uuid[]))"),{"ids":old_ids})
        for item in template["accounts"]:
            parent_id=mapping.get(item["parent"]) if item["parent"] else None
            if item["parent"] and parent_id is None:
                raise HTTPException(status_code=409,detail=f"No se pudo resolver la cuenta padre {item['parent']} para {item['code']}.")
            row=db.execute(text("""
                INSERT INTO accounts(company_id,code,name,account_type,is_group,parent_id,account_subtype,cash_flow_category,currency,allow_posting,is_active,description)
                VALUES(:company_id,:code,:name,:account_type,:is_group,:parent_id,:account_subtype,:cash_flow_category,:currency,:allow_posting,TRUE,:description)
                RETURNING id
            """),{"company_id":company_id,"code":item["code"],"name":item["name"],"account_type":item["type"],"is_group":item["group"],"parent_id":parent_id,"account_subtype":item.get("subtype"),"cash_flow_category":item.get("cash_flow_category"),"currency":company["default_currency"],"allow_posting":not item["group"],"description":None}).scalar_one()
            mapping[item["code"]]=row;created.append(item["code"])
        _audit(db,claims,"finance.account_template.applied",company_id,"account_template",template_code,{"created":len(created),"replaced":len(old_ids),"skipped":0})
        db.commit()
    except HTTPException:
        db.rollback();raise
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo aplicar la plantilla; no se hicieron cambios parciales.") from exc
    return {"template_code":template_code,"company_id":company_id,"created_codes":created,"replaced_count":len(old_ids),"skipped_existing_codes":skipped,"created_count":len(created),"skipped_count":len(skipped)}


def _normalize_import_header(value: object) -> str:
    import unicodedata
    raw = "".join(c for c in unicodedata.normalize("NFKD", str(value or "").strip().lower()) if not unicodedata.combining(c))
    return "".join(c for c in raw if c.isalnum())


def _parse_account_import(filename: str, content: bytes) -> list[dict]:
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5 MB.")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if ext == "csv":
            decoded = content.decode("utf-8-sig")
            sample = decoded[:4096]
            try: dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error: dialect = csv.excel
            table = list(csv.reader(io.StringIO(decoded), dialect))
        elif ext in ("xlsx", "xlsm"):
            from openpyxl import load_workbook
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = book.active
            table = [list(row) for row in sheet.iter_rows(values_only=True)]
            book.close()
        else:
            raise HTTPException(status_code=415, detail="Formato no soportado. Usa .csv o .xlsx.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="No se pudo leer el archivo. Revisa que sea un CSV UTF-8 o un Excel válido.") from exc
    table = [r for r in table if any(v is not None and str(v).strip() for v in r)]
    if not table:
        raise HTTPException(status_code=422, detail="El archivo no contiene filas.")
    aliases = {
        "code": {"code", "codigo", "accountcode", "codigocuenta"},
        "name": {"name", "nombre", "accountname", "nombrecuenta", "descripcion"},
        "account_type": {"accounttype", "tipo", "tipocuenta", "type"},
        "is_group": {"isgroup", "grupo", "esgrupo", "group"},
        "parent_code": {"parentcode", "codigopadre", "padre", "parent"},
        "account_subtype": {"accountsubtype", "subtipo", "subtipocuenta"},
        "cash_flow_category": {"cashflowcategory", "categoriaflujo", "categoriaflujoefectivo"},
        "currency": {"currency", "moneda"},
        "allow_posting": {"allowposting", "imputable", "permiteasientos"},
        "description": {"description", "observacion", "notas"},
    }
    headers = [_normalize_import_header(x) for x in table[0]]
    mapping = {key: next((i for i, h in enumerate(headers) if h in names), None) for key, names in aliases.items()}
    if mapping["code"] is None or mapping["name"] is None:
        raise HTTPException(status_code=422, detail="Faltan columnas obligatorias: código y nombre. Consulta la plantilla de importación.")
    records = []
    for line_no, row in enumerate(table[1:], start=2):
        def cell(key, default=None):
            idx = mapping.get(key)
            return row[idx] if idx is not None and idx < len(row) else default
        code = str(cell("code", "") or "").strip()
        name = str(cell("name", "") or "").strip()
        if not code and not name: continue
        if not code or not name:
            raise HTTPException(status_code=422, detail=f"Fila {line_no}: código y nombre son obligatorios.")
        raw_type = str(cell("account_type", "asset") or "asset").strip().lower()
        type_alias = {"activo":"asset", "pasivo":"liability", "patrimonio":"equity", "ingreso":"revenue", "ingresos":"revenue", "gasto":"expense", "gastos":"expense"}
        account_type = type_alias.get(raw_type, raw_type)
        if account_type not in {"asset", "liability", "equity", "revenue", "expense"}:
            raise HTTPException(status_code=422, detail=f"Fila {line_no}: tipo de cuenta inválido '{raw_type}'.")
        def as_bool(value, default):
            if value is None or str(value).strip() == "": return default
            v = str(value).strip().lower()
            if v in {"1", "true", "si", "sí", "yes", "grupo"}: return True
            if v in {"0", "false", "no", "imputable", "posting"}: return False
            raise HTTPException(status_code=422, detail=f"Fila {line_no}: valor booleano inválido '{value}'.")
        parent = str(cell("parent_code", "") or "").strip() or None
        group = as_bool(cell("is_group"), False)
        if group and parent and as_bool(cell("allow_posting"), False):
            raise HTTPException(status_code=422, detail=f"Fila {line_no}: un grupo no puede permitir asientos.")
        records.append({"line": line_no, "code": code, "name": name, "account_type": account_type,
                        "is_group": group, "parent_code": parent,
                        "account_subtype": str(cell("account_subtype", "") or "").strip() or None,
                        "cash_flow_category": str(cell("cash_flow_category", "") or "").strip() or None,
                        "currency": str(cell("currency", "") or "").strip().upper() or None,
                        "allow_posting": as_bool(cell("allow_posting"), not group),
                        "description": str(cell("description", "") or "").strip() or None})
    if not records:
        raise HTTPException(status_code=422, detail="No se encontraron cuentas para importar.")
    codes = [r["code"] for r in records]
    if len(set(codes)) != len(codes):
        dup = next(c for c in codes if codes.count(c) > 1)
        raise HTTPException(status_code=422, detail=f"Código duplicado en el archivo: {dup}.")
    if len(records) > 2000:
        raise HTTPException(status_code=413, detail="El archivo supera el máximo de 2,000 cuentas.")
    by_code = {r["code"]: r for r in records}
    for r in records:
        if r["parent_code"]:
            parent = by_code.get(r["parent_code"])
            if not parent or not parent["is_group"]:
                raise HTTPException(status_code=422, detail=f"Fila {r['line']}: el padre {r['parent_code']} debe existir en el archivo y ser grupo.")
            seen = {r["code"]}; cursor = parent
            while cursor:
                if cursor["code"] in seen:
                    raise HTTPException(status_code=422, detail=f"Jerarquía circular detectada en código {r['code']}.")
                seen.add(cursor["code"]); cursor = by_code.get(cursor["parent_code"]) if cursor["parent_code"] else None
        if r["is_group"] and r["allow_posting"]:
            raise HTTPException(status_code=422, detail=f"Fila {r['line']}: una cuenta de grupo no puede admitir asientos.")
    return records


@app.get("/api/v1/finance/accounts/import-template", tags=["accounts"])
def account_import_template():
    return {"columns": ["code", "name", "account_type", "is_group", "parent_code", "account_subtype", "cash_flow_category", "currency", "allow_posting", "description"],
            "example": [{"code":"1","name":"ACTIVO","account_type":"asset","is_group":True,"parent_code":None,"account_subtype":None,"cash_flow_category":None,"currency":"PEN","allow_posting":False,"description":None},
                        {"code":"10","name":"Efectivo","account_type":"asset","is_group":True,"parent_code":"1","account_subtype":None,"cash_flow_category":None,"currency":"PEN","allow_posting":False,"description":None},
                        {"code":"101","name":"Caja","account_type":"asset","is_group":False,"parent_code":"10","account_subtype":"cash","cash_flow_category":"operating","currency":"PEN","allow_posting":True,"description":None}],
            "account_types": ["asset", "liability", "equity", "revenue", "expense"],
            "supported_formats": ["csv", "xlsx"]}


@app.post("/api/v1/finance/accounts/import/preview", tags=["accounts"])
async def preview_account_import(company_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    records = _parse_account_import(file.filename or "accounts.csv", await file.read())
    existing = {r[0] for r in db.execute(text("SELECT code FROM accounts WHERE company_id=:c"), {"c": company_id}).all()}
    codes = {r["code"] for r in records}
    conflicts = sorted(existing & codes)
    return {"file_name": file.filename, "total_rows": len(records), "new_count": len(records) - len(conflicts), "conflict_count": len(conflicts),
            "conflicting_codes": conflicts[:100], "will_skip_existing": True, "preview": records[:100]}


@app.post("/api/v1/finance/accounts/import", tags=["accounts"])
async def import_accounts(company_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    company = db.execute(text("SELECT default_currency FROM companies WHERE id=:c AND is_active"), {"c": company_id}).mappings().first()
    if not company: raise HTTPException(status_code=404, detail="Empresa activa no encontrada.")
    records = _parse_account_import(file.filename or "accounts.csv", await file.read())
    existing_rows = db.execute(text("SELECT code,id,is_group FROM accounts WHERE company_id=:c"), {"c": company_id}).all()
    existing = {r[0]: {"id": r[1], "is_group": r[2]} for r in existing_rows}
    to_create = [r for r in records if r["code"] not in existing]
    conflicts = [r["code"] for r in records if r["code"] in existing]
    all_codes = {r["code"]: r for r in records}
    for r in to_create:
        if r["parent_code"] in existing and not existing[r["parent_code"]]["is_group"]:
            raise HTTPException(status_code=409, detail=f"La cuenta padre existente {r['parent_code']} no es un grupo.")
    mapping = {code: item["id"] for code, item in existing.items()}
    created = []
    try:
        pending = {r["code"]: r for r in to_create}
        while pending:
            ready = [r for r in pending.values() if not r["parent_code"] or r["parent_code"] in mapping]
            if not ready:
                raise HTTPException(status_code=409, detail="No se puede resolver la jerarquía de cuentas contra los códigos ya existentes.")
            for r in ready:
                parent_id = mapping.get(r["parent_code"]) if r["parent_code"] else None
                row_id = db.execute(text("""
                    INSERT INTO accounts(company_id,code,name,account_type,is_group,parent_id,account_subtype,cash_flow_category,currency,allow_posting,is_active,description)
                    VALUES(:company_id,:code,:name,:account_type,:is_group,:parent_id,:account_subtype,:cash_flow_category,:currency,:allow_posting,TRUE,:description)
                    RETURNING id
                """), {"company_id":company_id,"code":r["code"],"name":r["name"],"account_type":r["account_type"],"is_group":r["is_group"],
                       "parent_id":parent_id,"account_subtype":r["account_subtype"],"cash_flow_category":r["cash_flow_category"],
                       "currency":r["currency"] or company["default_currency"],"allow_posting":r["allow_posting"],"description":r["description"]}).scalar_one()
                mapping[r["code"]] = row_id; created.append(r["code"]); pending.pop(r["code"])
        _audit(db,claims,"finance.accounts.imported",company_id,"account_import",file.filename or "upload",{"created":len(created),"skipped":len(conflicts)})
        db.commit()
    except HTTPException:
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="No se pudo importar el plan; la transacción fue revertida.") from exc
    return {"company_id":company_id,"created_count":len(created),"created_codes":created,"skipped_existing_count":len(conflicts),"skipped_existing_codes":conflicts}


@app.post("/api/v1/finance/accounts/import/from-company", tags=["accounts"])
def import_accounts_from_company(company_id: UUID, source_company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id); require_company(claims, source_company_id)
    if company_id == source_company_id: raise HTTPException(status_code=422,detail="Selecciona otra empresa como origen.")
    source_company = db.execute(text("SELECT default_currency FROM companies WHERE id=:id AND is_active"),{"id":source_company_id}).mappings().first()
    target_company = db.execute(text("SELECT default_currency FROM companies WHERE id=:id AND is_active"),{"id":company_id}).mappings().first()
    if not source_company or not target_company: raise HTTPException(status_code=404,detail="Empresa origen o destino no encontrada.")
    rows=db.execute(text("SELECT code,name,account_type,is_group,parent_id,account_subtype,cash_flow_category,allow_posting,description FROM accounts WHERE company_id=:c ORDER BY code"),{"c":source_company_id}).mappings().all()
    if not rows: raise HTTPException(status_code=422,detail="La empresa origen no tiene cuentas para copiar.")
    old_to_code={str(r["parent_id"]):r["code"] for r in rows if r["parent_id"]}
    records=[{"line":i+1,"code":r["code"],"name":r["name"],"account_type":r["account_type"],"is_group":r["is_group"],"parent_code":old_to_code.get(str(r["parent_id"])) if r["parent_id"] else None,"account_subtype":r["account_subtype"],"cash_flow_category":r["cash_flow_category"],"currency":target_company["default_currency"],"allow_posting":r["allow_posting"],"description":r["description"]} for i,r in enumerate(rows)]
    existing_rows=db.execute(text("SELECT code,id,is_group FROM accounts WHERE company_id=:c"),{"c":company_id}).all()
    existing={r[0]:{"id":r[1],"is_group":r[2]} for r in existing_rows}; conflicts=[r["code"] for r in records if r["code"] in existing]
    mapping={k:v["id"] for k,v in existing.items()}; pending={r["code"]:r for r in records if r["code"] not in existing}; created=[]
    try:
        while pending:
            ready=[r for r in pending.values() if not r["parent_code"] or r["parent_code"] in mapping]
            if not ready: raise HTTPException(status_code=409,detail="No se pudo resolver la jerarquía del plan de origen.")
            for r in ready:
                if r["parent_code"] in existing and not existing[r["parent_code"]]["is_group"]: raise HTTPException(status_code=409,detail=f"La cuenta padre existente {r['parent_code']} no es un grupo.")
                new_id=db.execute(text("""INSERT INTO accounts(company_id,code,name,account_type,is_group,parent_id,account_subtype,cash_flow_category,currency,allow_posting,is_active,description)
                    VALUES(:c,:code,:name,:type,:grp,:parent,:sub,:flow,:currency,:posting,TRUE,:description) RETURNING id"""),
                    {"c":company_id,"code":r["code"],"name":r["name"],"type":r["account_type"],"grp":r["is_group"],"parent":mapping.get(r["parent_code"]) if r["parent_code"] else None,"sub":r["account_subtype"],"flow":r["cash_flow_category"],"currency":r["currency"],"posting":r["allow_posting"],"description":r["description"]}).scalar_one()
                mapping[r["code"]]=new_id;created.append(r["code"]);pending.pop(r["code"])
        _audit(db,claims,"finance.accounts.copied",company_id,"account_import",str(source_company_id),{"created":len(created),"skipped":len(conflicts)})
        db.commit()
    except HTTPException: db.rollback(); raise
    except SQLAlchemyError as exc: db.rollback(); raise HTTPException(status_code=409,detail="No se pudo copiar el plan; la transacción fue revertida.") from exc
    return {"company_id":company_id,"source_company_id":source_company_id,"created_count":len(created),"created_codes":created,"skipped_existing_count":len(conflicts),"skipped_existing_codes":conflicts}


@app.get("/api/v1/finance/accounts/source-companies", tags=["accounts"])
def list_account_source_companies(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows=db.execute(text("SELECT c.id,c.legal_name,c.trade_name,count(a.id) account_count FROM companies c JOIN accounts a ON a.company_id=c.id WHERE c.is_active AND c.id<>:c GROUP BY c.id,c.legal_name,c.trade_name HAVING count(a.id)>0 ORDER BY c.legal_name"),{"c":company_id}).mappings().all()
    return [dict(r) for r in rows]

@app.post("/api/v1/finance/accounts", response_model=AccountResponse, status_code=201, tags=["accounts"])
def create_account(payload: AccountCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    if payload.parent_id and not db.execute(text("SELECT 1 FROM accounts WHERE id=:id AND company_id=:company_id AND is_group=TRUE"), {"id": payload.parent_id, "company_id": payload.company_id}).first():
        raise HTTPException(status_code=422, detail="La cuenta padre debe ser un grupo de la misma empresa.")
    if payload.is_group and payload.allow_posting:
        raise HTTPException(status_code=422,detail="Una cuenta de grupo no puede admitir asientos.")
    try:
        row = db.execute(
            text("""
                INSERT INTO accounts (company_id, code, name, account_type, is_group, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description)
                VALUES (:company_id, :code, :name, :account_type, :is_group, :account_subtype, :cash_flow_category, :parent_id, :currency, :allow_posting, :is_active, :description)
                RETURNING id, company_id, code, name, account_type, is_group, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at
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
        text(f"SELECT id, company_id, code, name, account_type, is_group, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at FROM accounts WHERE {' AND '.join(conditions)} ORDER BY code"),
        params,
    ).mappings().all()
    return [AccountResponse(**dict(row)) for row in rows]


@app.get("/api/v1/finance/accounts/{account_id}", response_model=AccountResponse, tags=["accounts"])
def get_account(account_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(
        text("SELECT id, company_id, code, name, account_type, is_group, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at FROM accounts WHERE id = :id"),
        {"id": account_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, row["company_id"])
    return AccountResponse(**dict(row))


@app.patch("/api/v1/finance/accounts/{account_id}", response_model=AccountResponse, tags=["accounts"])
def update_account(account_id: UUID, payload: AccountUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id,is_group,allow_posting FROM accounts WHERE id = :id"), {"id": account_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, current["company_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if changes.get("parent_id") and not db.execute(text("SELECT 1 FROM accounts WHERE id=:parent_id AND company_id=:company_id"), {"parent_id": changes["parent_id"], "company_id": current["company_id"]}).first():
        raise HTTPException(status_code=422, detail="La cuenta padre debe pertenecer a la misma empresa.")
    if changes.get("parent_id") and not db.execute(text("SELECT 1 FROM accounts WHERE id=:parent_id AND company_id=:company_id AND is_group=TRUE"), {"parent_id": changes["parent_id"], "company_id": current["company_id"]}).first():
        raise HTTPException(status_code=422, detail="La cuenta padre debe ser un grupo de la misma empresa.")
    is_group = changes.get("is_group", current["is_group"])
    allow_posting = changes.get("allow_posting", current["allow_posting"])
    if is_group and allow_posting:
        raise HTTPException(status_code=422,detail="Una cuenta de grupo no puede admitir asientos.")
    if not is_group and db.execute(text("SELECT 1 FROM accounts WHERE parent_id=:id LIMIT 1"), {"id":account_id}).first():
        raise HTTPException(status_code=409,detail="No se puede convertir en imputable una cuenta que tiene subcuentas.")
    assignments = ", ".join(f"{key} = :{key}" for key in changes)
    changes.update({"account_id": account_id})
    try:
        row = db.execute(
            text(f"UPDATE accounts SET {assignments}, updated_at = now() WHERE id = :account_id RETURNING id, company_id, code, name, account_type, is_group, account_subtype, cash_flow_category, parent_id, currency, allow_posting, is_active, description, created_at, updated_at"),
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
    row = db.execute(text("SELECT company_id,code FROM accounts WHERE id = :id FOR UPDATE"), {"id": account_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    require_company(claims, row["company_id"])
    try:
        dependencies = [
            ("asientos contables", "SELECT count(*) FROM journal_entry_lines WHERE account_id=:id"),
            ("líneas de comprobantes", "SELECT count(*) FROM finance_document_lines WHERE account_id=:id"),
            ("cabeceras de comprobantes", "SELECT count(*) FROM finance_documents WHERE control_account_id=:id OR tax_account_id=:id"),
            ("partidas presupuestarias", "SELECT count(*) FROM budget_lines WHERE account_id=:id"),
            ("cuentas bancarias", "SELECT count(*) FROM finance_bank_accounts WHERE account_id=:id"),
            ("subcuentas", "SELECT count(*) FROM accounts WHERE parent_id=:id"),
        ]
        blockers=[]
        for label,sql in dependencies:
            count=db.execute(text(sql),{"id":account_id}).scalar_one()
            if count: blockers.append(f"{label}: {count}")
        if blockers:
            raise HTTPException(status_code=409,detail="No se puede eliminar la cuenta "+row["code"]+"; tiene referencias: "+"; ".join(blockers)+".")
        db.execute(text("DELETE FROM accounts WHERE id = :id"), {"id": account_id})
        _audit(db, claims, "finance.account.deleted", row["company_id"], "account", str(account_id))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene movimientos contables o líneas de presupuesto asociados.") from exc
    return None


@app.delete("/api/v1/finance/accounts", tags=["accounts"])
def delete_account_plan(company_id: UUID, confirm_name: str, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Elimina el plan entero solo con nombre exacto y si ninguna cuenta tiene referencias."""
    require_company(claims, company_id)
    company=db.execute(text("SELECT legal_name,trade_name FROM companies WHERE id=:c AND is_active"),{"c":company_id}).mappings().first()
    if not company: raise HTTPException(status_code=404,detail="Empresa activa no encontrada.")
    visible_name=company["trade_name"] or company["legal_name"]
    if confirm_name not in {company["legal_name"],visible_name}:
        raise HTTPException(status_code=422,detail="El texto de confirmación debe coincidir exactamente con el nombre de la empresa activa.")
    try:
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:company_id AS text), 739182))"),{"company_id":company_id})
        rows=db.execute(text("SELECT id FROM accounts WHERE company_id=:c FOR UPDATE"),{"c":company_id}).all()
        ids=[r[0] for r in rows]
        if not ids:
            db.commit()
            return {"company_id":company_id,"deleted_count":0,"deleted":True}
        refs=[
            ("asientos contables","SELECT count(*) FROM journal_entry_lines WHERE account_id=ANY(CAST(:ids AS uuid[]))"),
            ("líneas de comprobantes","SELECT count(*) FROM finance_document_lines WHERE account_id=ANY(CAST(:ids AS uuid[]))"),
            ("cuentas de control/impuesto de comprobantes","SELECT count(*) FROM finance_documents WHERE control_account_id=ANY(CAST(:ids AS uuid[])) OR tax_account_id=ANY(CAST(:ids AS uuid[]))"),
            ("partidas presupuestarias","SELECT count(*) FROM budget_lines WHERE account_id=ANY(CAST(:ids AS uuid[]))"),
            ("cuentas bancarias","SELECT count(*) FROM finance_bank_accounts WHERE account_id=ANY(CAST(:ids AS uuid[]))"),
            ("relaciones padre-hijo fuera del plan","SELECT count(*) FROM accounts child WHERE child.parent_id=ANY(CAST(:ids AS uuid[])) AND child.id<>ALL(CAST(:ids AS uuid[]))"),
        ]
        blockers=[]
        for label,sql in refs:
            n=db.execute(text(sql),{"ids":ids}).scalar_one()
            if n: blockers.append(f"{label}: {n}")
        known={("accounts","parent_id"),("journal_entry_lines","account_id"),("finance_document_lines","account_id"),
               ("finance_documents","control_account_id"),("finance_documents","tax_account_id"),
               ("budget_lines","account_id"),("finance_bank_accounts","account_id")}
        foreign_keys=db.execute(text("""
            SELECT tc.table_schema,tc.table_name,kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_catalog=tc.constraint_catalog AND ccu.constraint_schema=tc.constraint_schema AND ccu.constraint_name=tc.constraint_name
            JOIN information_schema.key_column_usage kcu ON kcu.constraint_catalog=tc.constraint_catalog AND kcu.constraint_schema=tc.constraint_schema AND kcu.constraint_name=tc.constraint_name
            WHERE tc.constraint_type='FOREIGN KEY' AND ccu.table_schema='public' AND ccu.table_name='accounts' AND ccu.column_name='id'
        """)).all()
        for schema_name,table_name,column_name in foreign_keys:
            if schema_name!='public' or (table_name,column_name) in known: continue
            qt='"'+table_name.replace('"','""')+'"'; qc='"'+column_name.replace('"','""')+'"'
            n=db.execute(text(f"SELECT count(*) FROM {qt} WHERE {qc}=ANY(CAST(:ids AS uuid[]))"),{"ids":ids}).scalar_one()
            if n: blockers.append(f"referencias en {table_name}.{column_name}: {n}")
        if blockers:
            raise HTTPException(status_code=409,detail="No se eliminó el plan porque hay registros dependientes: "+"; ".join(blockers)+". No se modificó ningún dato.")
        deleted=db.execute(text("DELETE FROM accounts WHERE id=ANY(CAST(:ids AS uuid[]))"),{"ids":ids}).rowcount
        _audit(db,claims,"finance.account_plan.deleted",company_id,"account_plan",str(company_id),{"deleted_count":deleted})
        db.commit()
        return {"company_id":company_id,"deleted_count":deleted,"deleted":True}
    except HTTPException:
        db.rollback();raise
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo eliminar el plan. La transacción fue revertida y no se dejaron registros parciales.") from exc


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
        text("SELECT id, journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2, created_at, updated_at FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
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
            text("SELECT id, journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2, created_at, updated_at FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
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
        text("SELECT id FROM accounts WHERE company_id = :company_id AND id = ANY(CAST(:ids AS uuid[])) AND is_active AND allow_posting AND NOT is_group"),
        {"company_id": fy["company_id"], "ids": list(account_ids)},
    ).all()}
    if account_ids - valid_accounts:
        raise HTTPException(status_code=422, detail="Alguna línea usa una cuenta inexistente, inactiva o que no admite movimientos.")
    auxiliary_ids={line.auxiliary_id for line in payload.lines if line.auxiliary_id}
    if auxiliary_ids:
        valid_auxiliaries={row[0] for row in db.execute(text("SELECT id FROM finance_auxiliaries WHERE company_id=:company_id AND is_active AND id=ANY(CAST(:ids AS uuid[]))"),{"company_id":fy["company_id"],"ids":list(auxiliary_ids)}).all()}
        if auxiliary_ids-valid_auxiliaries:raise HTTPException(status_code=422,detail="Una línea utiliza un auxiliar inexistente, inactivo o de otra empresa.")
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
                    INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount,
                                                     currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2)
                    VALUES (:journal_entry_id, :account_id, :auxiliary_id, :line_number, :description, :debit_amount, :credit_amount,
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
        text("SELECT account_id, auxiliary_id, line_number, description, debit_amount, credit_amount, currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2 FROM journal_entry_lines WHERE journal_entry_id = :id ORDER BY line_number"),
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
                    INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount,
                                                     currency_amount, currency_code, analytical_dimension_1, analytical_dimension_2)
                    VALUES (:journal_entry_id, :account_id, :auxiliary_id, :line_number, :description, :debit_amount, :credit_amount,
                            :currency_amount, :currency_code, :analytical_dimension_1, :analytical_dimension_2)
                """),
                {
                    "journal_entry_id": entry["id"],
                    "account_id": line["account_id"],
                    "auxiliary_id": line["auxiliary_id"],
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
        text("SELECT id, company_id, fiscal_year_id, name, description, status, currency, origin_area, approved_by, approved_at, created_by, created_at, updated_at FROM budgets WHERE company_id = :company_id ORDER BY created_at DESC"),
        {"company_id": company_id},
    ).mappings().all()
    return [BudgetResponse(**dict(row)) for row in rows]


@app.post("/api/v1/finance/budgets", response_model=BudgetResponse, status_code=201, tags=["budgets"])
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO budgets (company_id, fiscal_year_id, name, description, currency, origin_area, created_by)
                VALUES (:company_id, :fiscal_year_id, :name, :description, :currency, :origin_area, :created_by)
                RETURNING id, company_id, fiscal_year_id, name, description, status, currency, origin_area, approved_by, approved_at, created_by, created_at, updated_at
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
    row = db.execute(text("SELECT id, company_id, fiscal_year_id, name, description, status, currency, origin_area, approved_by, approved_at, created_by, created_at, updated_at FROM budgets WHERE id = :id"), {"id": budget_id}).mappings().first()
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
            text(f"UPDATE budgets SET {assignments}, updated_at = now() WHERE id = :budget_id RETURNING id, company_id, fiscal_year_id, name, description, status, currency, origin_area, approved_by, approved_at, created_by, created_at, updated_at"),
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
    auxiliary_id: UUID
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
    bank_id: UUID | None = None
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
        SELECT id,company_id,fiscal_year_id,fiscal_period_id,document_type,document_number,party_name,party_tax_id,auxiliary_id,
               issue_date,due_date,currency,exchange_rate,subtotal,tax_total,total,status,journal_entry_id,notes,
               control_account_id,tax_account_id,related_document_id,created_by,posted_by,posted_at,created_at,updated_at
        FROM finance_documents WHERE id=:id
    """), {"id": document_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Comprobante no encontrado.")
    result = dict(row)
    result["lines"] = [dict(item) for item in db.execute(text("""
        SELECT id,document_id,line_number,description,quantity,unit_price,account_id,auxiliary_id,tax_rate_id,tax_rate,net_amount,tax_amount,created_at
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
    auxiliary_id: UUID | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    currency: str | None = None,
    sort: str = Query(default="issue_date_desc", pattern="^(issue_date_desc|issue_date_asc|total_desc|total_asc|document_number)$"),
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
    if auxiliary_id:
        where.append("d.auxiliary_id=:auxiliary_id"); params["auxiliary_id"] = auxiliary_id
    if min_amount is not None:
        where.append("d.total>=:min_amount"); params["min_amount"] = min_amount
    if max_amount is not None:
        where.append("d.total<=:max_amount"); params["max_amount"] = max_amount
    if currency:
        where.append("d.currency=:currency"); params["currency"] = currency
    order = {"issue_date_desc": "d.issue_date DESC,d.document_number DESC", "issue_date_asc": "d.issue_date ASC,d.document_number ASC", "total_desc": "d.total DESC", "total_asc": "d.total ASC", "document_number": "d.document_number ASC"}[sort]
    rows = db.execute(text(f"""
        SELECT d.id,d.company_id,d.fiscal_year_id,d.fiscal_period_id,d.document_type,d.document_number,d.party_name,d.party_tax_id,d.auxiliary_id,fa.code AS auxiliary_code,fa.name AS auxiliary_name,
               d.issue_date,d.due_date,d.currency,d.exchange_rate,d.subtotal,d.tax_total,d.total,d.status,d.journal_entry_id,d.notes,
                d.control_account_id,d.tax_account_id,d.related_document_id,d.created_by,d.posted_by,d.posted_at,d.created_at,d.updated_at,
               COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id),0) AS paid_amount
         FROM finance_documents d LEFT JOIN finance_auxiliaries fa ON fa.id=d.auxiliary_id WHERE {' AND '.join(where)} ORDER BY {order}
    """), params).mappings().all()
    result=[]
    for item in rows:
        d=dict(item); d["outstanding_amount"]=d["total"]-d["paid_amount"]; result.append(d)
    return result


@app.get("/api/v1/finance/documents-summary", tags=["documents"])
def documents_summary(
    company_id: UUID,
    document_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    q: str | None = None,
    auxiliary_id: UUID | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    currency: str | None = None,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    """Agregados de la consulta filtrada: cantidad, total, impuesto y pendiente."""
    require_company(claims, company_id)
    where = ["d.company_id=:company_id"]
    params: dict = {"company_id": company_id}
    if document_type: where.append("d.document_type=:document_type"); params["document_type"] = document_type
    if status_filter: where.append("d.status=:status"); params["status"] = status_filter
    if from_date: where.append("d.issue_date>=:from_date"); params["from_date"] = from_date
    if to_date: where.append("d.issue_date<=:to_date"); params["to_date"] = to_date
    if q: where.append("(d.document_number ILIKE :q OR d.party_name ILIKE :q OR COALESCE(d.party_tax_id,'') ILIKE :q)"); params["q"] = f"%{q}%"
    if auxiliary_id: where.append("d.auxiliary_id=:auxiliary_id"); params["auxiliary_id"] = auxiliary_id
    if min_amount is not None: where.append("d.total>=:min_amount"); params["min_amount"] = min_amount
    if max_amount is not None: where.append("d.total<=:max_amount"); params["max_amount"] = max_amount
    if currency: where.append("d.currency=:currency"); params["currency"] = currency
    row = db.execute(text(f"""
        SELECT count(*) n, COALESCE(SUM(d.subtotal),0) subtotal, COALESCE(SUM(d.tax_total),0) tax, COALESCE(SUM(d.total),0) total,
               COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s JOIN finance_documents dd ON dd.id=s.document_id WHERE {' AND '.join(w.replace('d.', 'dd.') for w in where)}),0) paid
        FROM finance_documents d WHERE {' AND '.join(where)}
    """), params).mappings().first()
    return {"count": row["n"], "subtotal": str(row["subtotal"]), "tax_total": str(row["tax"]), "total": str(row["total"]), "paid_total": str(row["paid"]), "outstanding_total": str(Decimal(str(row["total"])) - Decimal(str(row["paid"]))), "currency": "PEN"}


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
    required_auxiliary_type = "customer" if payload.document_type in ("sales_invoice","sales_credit_note") else "supplier"
    auxiliary = db.execute(text("SELECT id,name,tax_id,auxiliary_type,is_active FROM finance_auxiliaries WHERE id=:id AND company_id=:company_id"), {"id":payload.auxiliary_id,"company_id":company_id}).mappings().first()
    if not auxiliary or not auxiliary["is_active"] or auxiliary["auxiliary_type"] != required_auxiliary_type:
        raise HTTPException(status_code=422,detail=f"Selecciona un auxiliar activo de tipo {required_auxiliary_type} para el comprobante.")
    if auxiliary["name"] != payload.party_name or (auxiliary["tax_id"] or None) != (payload.party_tax_id or None):
        raise HTTPException(status_code=422,detail="El nombre y RUC del comprobante deben coincidir con el auxiliar seleccionado.")
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
        INSERT INTO finance_documents(company_id,fiscal_year_id,fiscal_period_id,document_type,document_number,party_name,party_tax_id,auxiliary_id,
                issue_date,due_date,currency,exchange_rate,subtotal,tax_total,total,notes,control_account_id,tax_account_id,related_document_id,created_by)
            VALUES(:company_id,:fiscal_year_id,:fiscal_period_id,:document_type,:document_number,:party_name,:party_tax_id,:auxiliary_id,
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
    required_auxiliary_type = "customer" if payload.document_type in ("sales_invoice","sales_credit_note") else "supplier"
    auxiliary = db.execute(text("SELECT id,name,tax_id,auxiliary_type,is_active FROM finance_auxiliaries WHERE id=:id AND company_id=:company_id"), {"id":payload.auxiliary_id,"company_id":current["company_id"]}).mappings().first()
    if not auxiliary or not auxiliary["is_active"] or auxiliary["auxiliary_type"] != required_auxiliary_type:
        raise HTTPException(status_code=422,detail=f"Selecciona un auxiliar activo de tipo {required_auxiliary_type} para el comprobante.")
    if auxiliary["name"] != payload.party_name or (auxiliary["tax_id"] or None) != (payload.party_tax_id or None):
        raise HTTPException(status_code=422,detail="El nombre y RUC del comprobante deben coincidir con el auxiliar seleccionado.")
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
                document_number=:document_number,party_name=:party_name,party_tax_id=:party_tax_id,auxiliary_id=:auxiliary_id,issue_date=:issue_date,due_date=:due_date,
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
    lines=([{"account_id":bank["account_id"],"auxiliary_id":None,"debit":payload.amount,"credit":Decimal("0"),"description":"Cobro"},{"account_id":control_account,"auxiliary_id":doc["auxiliary_id"],"debit":Decimal("0"),"credit":payload.amount,"description":doc["party_name"]}] if is_receivable else [{"account_id":control_account,"auxiliary_id":doc["auxiliary_id"],"debit":payload.amount,"credit":Decimal("0"),"description":doc["party_name"]},{"account_id":bank["account_id"],"auxiliary_id":None,"debit":Decimal("0"),"credit":payload.amount,"description":"Pago"}])
    entry_no=f"PAY-{payload.settled_at:%Y%m%d}-{str(uuid4())[:8]}"
    try:
        entry_id=db.execute(text("""
            INSERT INTO journal_entries(company_id,fiscal_year_id,fiscal_period_id,entry_number,entry_date,reference,description,currency,exchange_rate,total_debit,total_credit,created_by)
            VALUES(:company,:fy,:period,:number,:date,:reference,:description,:currency,:rate,:amount,:amount,:actor) RETURNING id
        """),{"company":doc["company_id"],"fy":doc["fiscal_year_id"],"period":period[0],"number":entry_no,"date":payload.settled_at,"reference":payload.reference,"description":payload.description or f"Pago de {doc['document_number']} · {doc['party_name']}","currency":doc["currency"],"rate":doc["exchange_rate"],"amount":payload.amount,"actor":claims.get("sub")}).scalar_one()
        for index,line in enumerate(lines,1):
            db.execute(text("INSERT INTO journal_entry_lines(journal_entry_id,account_id,auxiliary_id,line_number,description,debit_amount,credit_amount) VALUES(:entry,:account,:auxiliary,:line,:description,:debit,:credit)"),{"entry":entry_id,"account":line["account_id"],"auxiliary":line["auxiliary_id"],"line":index,"description":line["description"],"debit":line["debit"],"credit":line["credit"]})
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
    rows=db.execute(text("""SELECT b.id,b.company_id,b.account_id,b.bank_id,b.bank_name,b.account_name,b.account_number_masked,b.currency,b.is_active,b.created_at,b.updated_at,a.code AS account_code,a.name AS ledger_account_name FROM finance_bank_accounts b JOIN accounts a ON a.id=b.account_id WHERE b.company_id=:c ORDER BY b.account_name"""),{"c":company_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/finance/bank-accounts", status_code=201, tags=["treasury"])
def create_bank_account(company_id: UUID, payload: BankAccountInput, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    require_company(claims,company_id)
    account=db.execute(text("SELECT account_subtype,is_active,allow_posting FROM accounts WHERE id=:id AND company_id=:c"),{"id":payload.account_id,"c":company_id}).mappings().first()
    if not account or account["account_subtype"] not in ("cash","bank") or not account["is_active"] or not account["allow_posting"]:
        raise HTTPException(status_code=422,detail="La cuenta contable debe ser activa, imputable y de subtipo caja o banco.")
    try:
        row=db.execute(text("INSERT INTO finance_bank_accounts(company_id,account_id,bank_id,bank_name,account_name,account_number_masked,currency,is_active) VALUES(:company,:account,:bank_id,:bank,:name,:number,:currency,:active) RETURNING id,company_id,account_id,bank_id,bank_name,account_name,account_number_masked,currency,is_active,created_at,updated_at"),{"company":company_id,**payload.model_dump()}).mappings().first()
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
        row=db.execute(text("UPDATE finance_bank_accounts SET account_id=:account,bank_id=:bank_id,bank_name=:bank,account_name=:name,account_number_masked=:number,currency=:currency,is_active=:active,updated_at=now() WHERE id=:id RETURNING id,company_id,account_id,bank_id,bank_name,account_name,account_number_masked,currency,is_active,created_at,updated_at"),{"id":bank_account_id,"account":payload.account_id,"bank_id":payload.bank_id,"bank":payload.bank_name,"name":payload.account_name,"number":payload.account_number_masked,"currency":payload.currency,"active":payload.is_active}).mappings().first()
        _audit(db,claims,"finance.bank_account.updated",current["company_id"],"bank_account",str(bank_account_id));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo actualizar la cuenta bancaria.") from exc
    return dict(row)


@app.delete("/api/v1/finance/bank-accounts/{bank_account_id}", status_code=204, tags=["treasury"])
def delete_bank_account(bank_account_id: UUID, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    current=db.execute(text("SELECT company_id FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id}).mappings().first()
    if not current: raise HTTPException(status_code=404,detail="Cuenta bancaria no encontrada.")
    require_company(claims,current["company_id"])
    try:
        db.execute(text("DELETE FROM finance_bank_accounts WHERE id=:id"),{"id":bank_account_id})
        _audit(db,claims,"finance.bank_account.deleted",current["company_id"],"bank_account",str(bank_account_id));db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo eliminar la cuenta bancaria (tiene movimientos).") from exc
    return None


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
    accounts=db.execute(text("SELECT id,account_type,account_subtype FROM accounts WHERE company_id=:c AND is_active AND allow_posting AND NOT is_group"),{"c":doc["company_id"]}).mappings().all()
    by_id={row["id"]:(row["account_type"],row["account_subtype"]) for row in accounts}
    party_type="asset" if is_sales else "liability"
    party_account=doc["control_account_id"]
    required_party_subtype = "receivable" if is_sales else "payable"
    if not party_account or by_id.get(party_account, (None,None))[0] != party_type or by_id.get(party_account, (None,None))[1] != required_party_subtype:
        raise HTTPException(status_code=422,detail=f"Selecciona una cuenta de {'cuentas por cobrar' if is_sales else 'cuentas por pagar'} del tipo {party_type} en el comprobante.")
    journal_lines=[]
    total=doc["total"]
    if is_sales:
        journal_lines.append({"account_id":party_account,"auxiliary_id":doc["auxiliary_id"],"debit_amount":total,"credit_amount":Decimal('0'),"description":doc["party_name"]})
    else:
        journal_lines.append({"account_id":party_account,"auxiliary_id":doc["auxiliary_id"],"debit_amount":Decimal('0'),"credit_amount":total,"description":doc["party_name"]})
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
        journal_lines.append({"account_id":line["account_id"],"auxiliary_id":line.get("auxiliary_id"),"debit_amount":max(debit,Decimal('0')),"credit_amount":max(credit,Decimal('0')),"description":line["description"]})
        if line["tax_amount"]:
            tax_account=doc["tax_account_id"]
            required_tax_type="liability" if is_sales else "asset"
            if not tax_account or by_id.get(tax_account, (None,None))[0] != required_tax_type or by_id.get(tax_account, (None,None))[1] != "tax": raise HTTPException(status_code=422,detail="Selecciona una cuenta fiscal del subtipo impuesto y tipo contable correcto.")
            tax=line["tax_amount"]
            if is_sales: debit,credit=Decimal('0'),tax
            else: debit,credit=tax,Decimal('0')
            journal_lines.append({"account_id":tax_account,"auxiliary_id":None,"debit_amount":max(debit,Decimal('0')),"credit_amount":max(credit,Decimal('0')),"description":"Impuesto " + line["description"]})
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
            db.execute(text("INSERT INTO journal_entry_lines(journal_entry_id,account_id,auxiliary_id,line_number,description,debit_amount,credit_amount) VALUES(:entry,:account,:auxiliary,:line,:description,:debit,:credit)"),{"entry":entry_id,"account":item["account_id"],"auxiliary":item.get("auxiliary_id"),"line":index,"description":item["description"],"debit":item["debit_amount"],"credit":item["credit_amount"]})
        db.execute(text("UPDATE journal_entries SET status='posted',posted_by=:actor,posted_at=now(),updated_at=now() WHERE id=:id"),{"actor":claims.get("sub"),"id":entry_id})
        db.execute(text("UPDATE finance_documents SET status='posted',journal_entry_id=:entry,posted_by=:actor,posted_at=now(),updated_at=now() WHERE id=:id"),{"entry":entry_id,"actor":claims.get("sub"),"id":document_id})
        # Populate accounting books: diario, mayor, compras, ventas, caja
        doc_type = doc["document_type"]
        entry_date = doc["issue_date"]
        for item in journal_lines:
            acct_subtype = by_id.get(item["account_id"], (None, None))[1]
            base = {
                "company_id": doc["company_id"],
                "entry_id": entry_id,
                "entry_date": entry_date,
                "auxiliary_id": item.get("auxiliary_id"),
                "account_id": item["account_id"],
                "debit": item["debit_amount"],
                "credit": item["credit_amount"],
                "description": item["description"],
            }
            db.execute(text("""
                INSERT INTO accounting_daily_journal (company_id, journal_entry_id, journal_date, auxiliary_id, account_id, debit_amount, credit_amount, description)
                VALUES (:company_id, :entry_id, :entry_date, :auxiliary_id, :account_id, :debit, :credit, :description)
            """), base)
            db.execute(text("""
                INSERT INTO accounting_general_ledger (company_id, journal_entry_id, account_id, journal_date, auxiliary_id, debit_amount, credit_amount, description)
                VALUES (:company_id, :entry_id, :account_id, :entry_date, :auxiliary_id, :debit, :credit, :description)
            """), base)
            if doc_type in ("purchase_bill", "purchase_credit_note"):
                db.execute(text("""
                    INSERT INTO accounting_purchase_journal (company_id, journal_entry_id, journal_date, auxiliary_id, account_id, debit_amount, credit_amount, description)
                    VALUES (:company_id, :entry_id, :entry_date, :auxiliary_id, :account_id, :debit, :credit, :description)
                """), base)
            elif doc_type in ("sales_invoice", "sales_credit_note"):
                db.execute(text("""
                    INSERT INTO accounting_sales_journal (company_id, journal_entry_id, journal_date, auxiliary_id, account_id, debit_amount, credit_amount, description)
                    VALUES (:company_id, :entry_id, :entry_date, :auxiliary_id, :account_id, :debit, :credit, :description)
                """), base)
            if acct_subtype in ("cash", "bank"):
                amount = item["debit_amount"] if item["debit_amount"] > 0 else item["credit_amount"]
                direction = "debit" if item["debit_amount"] > 0 else "credit"
                db.execute(text("""
                    INSERT INTO accounting_cash_book (company_id, journal_entry_id, journal_date, auxiliary_id, account_id, amount, direction, description)
                    VALUES (:company_id, :entry_id, :entry_date, :auxiliary_id, :account_id, :amount, :direction, :description)
                """), {"company_id": doc["company_id"], "entry_id": entry_id, "entry_date": entry_date, "auxiliary_id": item.get("auxiliary_id"), "account_id": item["account_id"], "amount": amount, "direction": direction, "description": item["description"]})
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


# ---------------------------------------------------------------------------
# Advanced reports: KPIs, budget vs actual, expense/revenue analysis,
# auxiliary balances, tax summary
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/reports/financial-kpis", tags=["reports"])
def financial_kpis(company_id: UUID, fiscal_year_id: UUID | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Indicadores financieros reales: liquidez, endeudamiento, rentabilidad y cobro."""
    require_company(claims, company_id)
    fy = None
    if fiscal_year_id:
        fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:c"), {"id": fiscal_year_id, "company_id": company_id}).mappings().first()
        if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    as_of = fy["end_date"] if fy else date.today()
    def bal(types, sign):
        row = db.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN a.account_type IN :types THEN l.debit_amount - l.credit_amount ELSE 0 END),0) AS debit,
                   COALESCE(SUM(CASE WHEN a.account_type IN :types THEN l.credit_amount - l.debit_amount ELSE 0 END),0) AS credit
            FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
            WHERE j.company_id=:c AND j.status='posted' AND j.entry_date<=:as_of
        """), {"types": tuple(types), "c": company_id, "as_of": as_of}).mappings().first()
        return sign * (row["debit"] - row["credit"])
    assets = bal(("asset",), 1); liabilities = bal(("liability",), -1); equity = bal(("equity",), -1)
    row = db.execute(text("""
        SELECT COALESCE(SUM(l.credit_amount-l.debit_amount),0) rev, COALESCE(SUM(l.debit_amount-l.credit_amount),0) exp
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:c AND j.status='posted' AND a.account_type IN ('revenue','expense')
        """ + (f"AND j.fiscal_year_id=:fy" if fy else "AND j.entry_date<=:as_of")),
        {"c": company_id, "fy": fiscal_year_id, "as_of": as_of}).mappings().first()
    revenue, expenses = Decimal(row["rev"] or 0), Decimal(row["exp"] or 0)
    net = revenue - expenses
    current = bal(("asset",), 1)  # fallback when no subtype data
    def subtype_sum(subtypes, sign):
        r = db.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN a.account_subtype IN ANY(CAST(:subs AS text[])) THEN l.debit_amount - l.credit_amount ELSE 0 END),0) d,
                   COALESCE(SUM(CASE WHEN a.account_subtype IN ANY(CAST(:subs AS text[])) THEN l.credit_amount - l.debit_amount ELSE 0 END),0) c
            FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
            WHERE j.company_id=:c AND j.status='posted' AND j.entry_date<=:as_of
        """), {"subs": list(subtypes), "c": company_id, "as_of": as_of}).mappings().first()
        return sign * (r["d"] - r["c"])
    cash_bank = subtype_sum(("cash","bank"), 1)
    receivables = subtype_sum(("receivable",), 1)
    payables = subtype_sum(("payable",), -1)
    inventory = subtype_sum(("inventory",), 1)
    current_assets = receivables + inventory + cash_bank
    def ratio(num, den): return float(num/den) if den else None
    return {
        "as_of": as_of, "currency": "PEN",
        "liquidity": {"current_ratio": ratio(current_assets, payables), "quick_ratio": ratio(receivables + cash_bank, payables), "cash_ratio": ratio(cash_bank, payables)},
        "leverage": {"debt_ratio": ratio(liabilities, assets), "debt_to_equity": ratio(liabilities, equity), "equity_ratio": ratio(equity, assets)},
        "profitability": {"net_margin": ratio(net, revenue) if revenue else None, "return_on_assets": ratio(net, assets) if assets else None, "return_on_equity": ratio(net, equity) if equity else None},
        "efficiency": {"receivables_turnover": ratio(revenue, receivables) if receivables else None, "payables_turnover": ratio(expenses, payables) if payables else None},
        "totals": {"assets": str(assets), "liabilities": str(liabilities), "equity": str(equity), "revenue": str(revenue), "expenses": str(expenses), "net_result": str(net), "cash_bank": str(cash_bank), "receivables": str(receivables), "payables": str(payables), "inventory": str(inventory)},
    }


@app.get("/api/v1/finance/reports/budget-vs-actual", tags=["reports"])
def budget_vs_actual(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Consolidado de todos los presupuestos del ejercicio vs ejecutado, con varianza."""
    require_company(claims, company_id)
    if not db.execute(text("SELECT 1 FROM fiscal_years WHERE id=:id AND company_id=:c"), {"id": fiscal_year_id, "c": company_id}).first():
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    budgets = db.execute(text("SELECT id,name,status FROM budgets WHERE company_id=:c AND fiscal_year_id=:fy ORDER BY name"), {"c": company_id, "fy": fiscal_year_id}).mappings().all()
    out = []
    for b in budgets:
        lines = db.execute(text("SELECT bl.account_id, bl.planned_amount, a.code, a.name, a.account_type FROM budget_lines bl JOIN accounts a ON a.id=bl.account_id WHERE bl.budget_id=:id"), {"id": b["id"]}).mappings().all()
        acc_ids = [l["account_id"] for l in lines]
        executed = {}
        if acc_ids:
            for r in db.execute(text("""
                SELECT l.account_id, SUM(CASE WHEN a.account_type IN ('revenue','liability','equity') THEN l.credit_amount-l.debit_amount ELSE l.debit_amount-l.credit_amount END) v
                FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
                WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND l.account_id=ANY(CAST(:ids AS uuid[])) GROUP BY l.account_id
            """), {"c": company_id, "fy": fiscal_year_id, "ids": acc_ids}).all():
                executed[str(r[0])] = r[1]
        items = []
        for l in lines:
            planned = l["planned_amount"]; exec_ = executed.get(str(l["account_id"]), Decimal("0"))
            var = exec_ - planned
            pct = round(float(exec_/planned*100), 1) if planned else (100.0 if exec_ else 0.0)
            items.append({"line_id": None, "account_id": l["account_id"], "account_code": l["code"], "account_name": l["name"], "account_type": l["account_type"], "planned_amount": planned, "executed_amount": exec_, "variance": var, "variance_pct": pct, "favorable": var <= 0 if l["account_type"] == "expense" else var >= 0})
        tp = sum((i["planned_amount"] for i in items), Decimal("0")); te = sum((i["executed_amount"] for i in items), Decimal("0"))
        out.append({"budget_id": b["id"], "name": b["name"], "status": b["status"], "lines": items, "total_planned": tp, "total_executed": te, "total_variance": te - tp, "progress": round(float(te/tp*100), 1) if tp else 0.0})
    return {"company_id": company_id, "fiscal_year_id": fiscal_year_id, "budgets": out, "currency": "PEN"}


@app.get("/api/v1/finance/reports/expense-analysis", tags=["reports"])
def expense_analysis(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Gastos por cuenta y por mes del ejercicio, con participación y ranking."""
    require_company(claims, company_id)
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:c"), {"id": fiscal_year_id, "c": company_id}).mappings().first()
    if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(text("""
        SELECT a.code,a.name,a.account_type, EXTRACT(MONTH FROM j.entry_date) m, SUM(l.debit_amount-l.credit_amount) amt
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND a.account_type='expense' AND j.entry_date BETWEEN :s AND :e
        GROUP BY a.code,a.name,a.account_type, EXTRACT(MONTH FROM j.entry_date) ORDER BY a.code, m
    """), {"c": company_id, "fy": fiscal_year_id, "s": fy["start_date"], "e": fy["end_date"]}).mappings().all()
    by_account: dict[str, dict] = {}
    for r in rows:
        key = f"{r['code']}|{r['name']}"
        item = by_account.setdefault(key, {"code": r["code"], "name": r["name"], "total": Decimal("0"), "months": {i: Decimal("0") for i in range(1, 13)}})
        item["months"][int(r["m"])] = item["months"].get(int(r["m"]), Decimal("0")) + r["amt"]; item["total"] += r["amt"]
    items = [{"code": v["code"], "name": v["name"], "total": v["total"], "months": [float(v["months"][m]) for m in range(1, 13)]} for v in by_account.values()]
    items.sort(key=lambda x: x["total"], reverse=True)
    grand = sum((i["total"] for i in items), Decimal("0"))
    for i in items: i["share"] = round(float(i["total"]/grand*100), 1) if grand else 0.0
    return {"company_id": company_id, "fiscal_year_id": fiscal_year_id, "total": grand, "items": items, "currency": "PEN"}


@app.get("/api/v1/finance/reports/revenue-analysis", tags=["reports"])
def revenue_analysis(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Ingresos por auxiliar (cliente) y concentración cartera."""
    require_company(claims, company_id)
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:c"), {"id": fiscal_year_id, "c": company_id}).mappings().first()
    if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(text("""
        SELECT COALESCE(fa.code,'S/A') code, COALESCE(fa.name,'Sin auxiliar') name, SUM(l.credit_amount-l.debit_amount) amt
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id=l.auxiliary_id
        WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND a.account_type='revenue' AND j.entry_date BETWEEN :s AND :e
        GROUP BY fa.code, fa.name ORDER BY amt DESC
    """), {"c": company_id, "fy": fiscal_year_id, "s": fy["start_date"], "e": fy["end_date"]}).mappings().all()
    total = sum((r["amt"] for r in rows), Decimal("0"))
    items = [{"code": r["code"], "name": r["name"], "amount": r["amt"], "share": round(float(r["amt"]/total*100), 1) if total else 0.0} for r in rows]
    top5 = sum((i["amount"] for i in items[:5]), Decimal("0"))
    hhi = sum((Decimal(str(i["share"]))**2 for i in items)) if items else Decimal("0")
    return {"company_id": company_id, "fiscal_year_id": fiscal_year_id, "total": total, "items": items, "top5_share": round(float(top5/total*100), 1) if total else 0.0, "hhi": float(hhi), "currency": "PEN"}


@app.get("/api/v1/finance/reports/auxiliary-balance", tags=["reports"])
def auxiliary_balance(company_id: UUID, as_of: date | None = None, auxiliary_type: str | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Saldo por auxiliar a una fecha: facturado, cobrado/pagado y pendiente."""
    require_company(claims, company_id)
    as_of = as_of or date.today()
    sql = """
        SELECT fa.id, fa.code, fa.name, fa.auxiliary_type,
          COALESCE((SELECT SUM(d.total) FROM finance_documents d WHERE d.auxiliary_id=fa.id AND d.status='posted' AND d.issue_date<=:as_of AND d.document_type IN ('sales_invoice','sales_credit_note')),0) billed,
          COALESCE((SELECT SUM(d.total) FROM finance_documents d WHERE d.auxiliary_id=fa.id AND d.status='posted' AND d.issue_date<=:as_of AND d.document_type IN ('purchase_bill','purchase_credit_note')),0) purchased,
          COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s JOIN finance_documents d ON d.id=s.document_id WHERE d.auxiliary_id=fa.id AND s.settled_at<=:as_of),0) settled
        FROM finance_auxiliaries fa WHERE fa.company_id=:c AND fa.is_active=TRUE
    """
    params: dict = {"c": company_id, "as_of": as_of}
    if auxiliary_type: sql += " AND fa.auxiliary_type=:t"; params["t"] = auxiliary_type
    sql += " ORDER BY fa.name"
    rows = db.execute(text(sql), params).mappings().all()
    items = []
    for r in rows:
        net = Decimal(str(r["billed"])) - Decimal(str(r["settled"]))
        if not net and not r["purchased"]: continue
        items.append({"id": r["id"], "code": r["code"], "name": r["name"], "auxiliary_type": r["auxiliary_type"], "billed": r["billed"], "purchased": r["purchased"], "settled": r["settled"], "receivable": max(net, Decimal("0")), "payable": max(-net, Decimal("0"))})
    return {"company_id": company_id, "as_of": as_of, "items": items, "currency": "PEN"}


@app.get("/api/v1/finance/reports/tax-summary", tags=["reports"])
def tax_summary(company_id: UUID, fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Resumen mensual de base imponible e IGV por ventas y compras contabilizadas."""
    require_company(claims, company_id)
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id AND company_id=:c"), {"id": fiscal_year_id, "c": company_id}).mappings().first()
    if not fy: raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    rows = db.execute(text("""
        SELECT EXTRACT(MONTH FROM d.issue_date) m, d.document_type, SUM(d.subtotal) base, SUM(d.tax_total) tax, SUM(d.total) total
        FROM finance_documents d WHERE d.company_id=:c AND d.status='posted' AND d.issue_date BETWEEN :s AND :e
        GROUP BY EXTRACT(MONTH FROM d.issue_date), d.document_type
    """), {"c": company_id, "s": fy["start_date"], "e": fy["end_date"]}).mappings().all()
    months = []
    for m in range(1, 13):
        sales = next((r for r in rows if int(r["m"]) == m and r["document_type"] == "sales_invoice"), None)
        purchases = next((r for r in rows if int(r["m"]) == m and r["document_type"] == "purchase_bill"), None)
        months.append({
            "month": m,
            "sales_base": sales["base"] if sales else Decimal("0"), "sales_tax": sales["tax"] if sales else Decimal("0"),
            "purchase_base": purchases["base"] if purchases else Decimal("0"), "purchase_tax": purchases["tax"] if purchases else Decimal("0"),
        })
    for m in months: m["net_tax"] = m["sales_tax"] - m["purchase_tax"]
    return {
        "company_id": company_id, "fiscal_year_id": fiscal_year_id, "currency": "PEN",
        "months": [{**m, "sales_base": str(m["sales_base"]), "sales_tax": str(m["sales_tax"]), "purchase_base": str(m["purchase_base"]), "purchase_tax": str(m["purchase_tax"]), "net_tax": str(m["net_tax"])} for m in months],
        "totals": {
            "sales_base": str(sum((m["sales_base"] for m in months), Decimal("0"))), "sales_tax": str(sum((m["sales_tax"] for m in months), Decimal("0"))),
            "purchase_base": str(sum((m["purchase_base"] for m in months), Decimal("0"))), "purchase_tax": str(sum((m["purchase_tax"] for m in months), Decimal("0"))),
            "net_tax": str(sum((m["net_tax"] for m in months), Decimal("0"))),
        },
    }


@app.get("/api/v1/finance/reports/account-movements", tags=["reports"])
def account_movements(
    company_id: UUID,
    fiscal_year_id: UUID | None = None,
    account_id: UUID | None = None,
    auxiliary_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
    q: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_claims),
):
    """Consulta avanzada de movimientos: filtros por cuenta, auxiliar, fechas, montos y texto."""
    require_company(claims, company_id)
    where = ["j.company_id=:company_id", "j.status='posted'"]
    params: dict = {"company_id": company_id}
    if fiscal_year_id: where.append("j.fiscal_year_id=:fy"); params["fy"] = fiscal_year_id
    if account_id: where.append("l.account_id=:account_id"); params["account_id"] = account_id
    if auxiliary_id: where.append("l.auxiliary_id=:aux"); params["aux"] = auxiliary_id
    if from_date: where.append("j.entry_date>=:from"); params["from"] = from_date
    if to_date: where.append("j.entry_date<=:to"); params["to"] = to_date
    if min_amount is not None: where.append("ABS(l.debit_amount-l.credit_amount)>=:min_amt"); params["min_amt"] = min_amount
    if max_amount is not None: where.append("ABS(l.debit_amount-l.credit_amount)<=:max_amt"); params["max_amt"] = max_amount
    if q: where.append("(l.description ILIKE :q OR j.reference ILIKE :q OR j.entry_number ILIKE :q OR a.name ILIKE :q OR a.code ILIKE :q OR COALESCE(fa.name,'') ILIKE :q)"); params["q"] = f"%{q}%"
    total = db.execute(text(f"SELECT count(*) FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id LEFT JOIN finance_auxiliaries fa ON fa.id=l.auxiliary_id WHERE {' AND '.join(where)}"), params).scalar_one()
    rows = db.execute(text(f"""
        SELECT j.entry_number,j.entry_date,j.reference,l.line_number,l.description,l.debit_amount,l.credit_amount,
               a.code account_code,a.name account_name,a.account_type,fa.code aux_code,fa.name aux_name,fa.auxiliary_type
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id=l.auxiliary_id
        WHERE {' AND '.join(where)} ORDER BY j.entry_date DESC, j.entry_number DESC, l.line_number
        LIMIT :lim OFFSET :off
    """), {**params, "lim": limit, "off": offset}).mappings().all()
    agg = db.execute(text(f"""
        SELECT COALESCE(SUM(l.debit_amount),0) debit, COALESCE(SUM(l.credit_amount),0) credit
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id
        WHERE {' AND '.join(where)}
    """), params).mappings().first()
    return {
        "company_id": company_id, "total": total, "limit": limit, "offset": offset,
        "totals": {"debit": str(agg["debit"]), "credit": str(agg["credit"]), "net": str(agg["debit"] - agg["credit"])},
        "rows": [dict(r) for r in rows], "currency": "PEN",
    }


@app.get("/api/v1/finance/reports/auxiliary-ledger", tags=["reports"])
def auxiliary_ledger(company_id: UUID, auxiliary_id: UUID, from_date: date | None = None, to_date: date | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Mayor auxiliar: todos los movimientos de un tercero con saldo corrido."""
    require_company(claims, company_id)
    aux = db.execute(text("SELECT id,code,name,auxiliary_type FROM finance_auxiliaries WHERE id=:id AND company_id=:c"), {"id": auxiliary_id, "c": company_id}).mappings().first()
    if not aux: raise HTTPException(status_code=404, detail="Auxiliar no encontrado.")
    where = ["j.company_id=:c", "j.status='posted'", "l.auxiliary_id=:aux"]
    params: dict = {"c": company_id, "aux": auxiliary_id}
    if from_date: where.append("j.entry_date>=:f"); params["f"] = from_date
    if to_date: where.append("j.entry_date<=:t"); params["t"] = to_date
    rows = db.execute(text(f"""
        SELECT j.entry_number,j.entry_date,j.reference,l.description,l.debit_amount,l.credit_amount,a.code,a.name
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE {' AND '.join(where)} ORDER BY j.entry_date, j.entry_number, l.line_number
    """), params).mappings().all()
    balance = Decimal("0"); entries = []
    for r in rows:
        balance += r["debit_amount"] - r["credit_amount"]
        entries.append({"entry_number": r["entry_number"], "entry_date": r["entry_date"].isoformat(), "reference": r["reference"], "description": r["description"], "account_code": r["code"], "account_name": r["name"], "debit": str(r["debit_amount"]), "credit": str(r["credit_amount"]), "balance": str(balance)})
    return {"auxiliary": {"id": aux["id"], "code": aux["code"], "name": aux["name"], "auxiliary_type": aux["auxiliary_type"]}, "entries": entries, "final_balance": str(balance), "currency": "PEN"}


# ---------------------------------------------------------------------------
# Budget year-end projection (run-rate by line)
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/budgets/{budget_id}/projection", tags=["budgets"])
def budget_projection(budget_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Proyección de cierre de ejercicio por línea usando la tasa de ejecución actual."""
    budget = db.execute(text("SELECT company_id,fiscal_year_id,name,status FROM budgets WHERE id=:id"), {"id": budget_id}).mappings().first()
    if not budget: raise HTTPException(status_code=404, detail="Presupuesto no encontrado.")
    require_company(claims, budget["company_id"])
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id"), {"id": budget["fiscal_year_id"]}).mappings().first()
    today = date.today()
    total_days = max((fy["end_date"] - fy["start_date"]).days, 1)
    elapsed_days = min(max((today - fy["start_date"]).days, 1), total_days)
    elapsed_pct = round(elapsed_days / total_days * 100, 1)
    lines = db.execute(text("SELECT bl.account_id, bl.planned_amount, a.code, a.name, a.account_type FROM budget_lines bl JOIN accounts a ON a.id=bl.account_id WHERE bl.budget_id=:id ORDER BY a.code"), {"id": budget_id}).mappings().all()
    acc_ids = [l["account_id"] for l in lines]
    executed: dict = {}
    if acc_ids:
        for r in db.execute(text("""
            SELECT l.account_id, SUM(CASE WHEN a.account_type IN ('revenue','liability','equity') THEN l.credit_amount-l.debit_amount ELSE l.debit_amount-l.credit_amount END) v
            FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
            WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND l.account_id=ANY(CAST(:ids AS uuid[]))
            GROUP BY l.account_id
        """), {"c": budget["company_id"], "fy": budget["fiscal_year_id"], "ids": acc_ids}).all():
            executed[str(r[0])] = Decimal(str(r[1] or 0))
    out = []
    for l in lines:
        planned = Decimal(str(l["planned_amount"] or 0))
        exe = executed.get(str(l["account_id"]), Decimal("0"))
        projected = max(exe / elapsed_pct * 100, exe) if elapsed_pct > 0 else exe
        progress = float(exe / planned * 100) if planned else 0.0
        if planned <= 0:
            risk = "no_budget"
        elif l["account_type"] == "expense" and progress > elapsed_pct + 20:
            risk = "over_run"
        elif progress >= elapsed_pct - 10:
            risk = "on_track"
        elif progress >= elapsed_pct - 30:
            risk = "watch"
        else:
            risk = "at_risk"
        out.append({"account_id": l["account_id"], "account_code": l["code"], "account_name": l["name"], "account_type": l["account_type"],
                    "planned_amount": planned, "executed_amount": exe, "projected_year_end": projected,
                    "projected_variance": planned - projected, "execution_pct": round(progress, 1), "risk": risk})
    tp = sum((i["planned_amount"] for i in out), Decimal("0"))
    te = sum((i["executed_amount"] for i in out), Decimal("0"))
    tproj = sum((i["projected_year_end"] for i in out), Decimal("0"))
    return {"budget_id": budget_id, "name": budget["name"], "status": budget["status"], "currency": "PEN",
            "as_of": today, "elapsed_pct": elapsed_pct, "lines": out,
            "totals": {"planned": tp, "executed": te, "projected_year_end": tproj, "projected_variance": tp - tproj,
                       "execution_pct": round(float(te / tp * 100), 1) if tp else 0.0,
                       "projected_pct": round(float(tproj / tp * 100), 1) if tp else 0.0},
            "has_data": bool(out and te)}


# ---------------------------------------------------------------------------
# AI engine: monthly series, linear regression, open portfolio (no ML deps)
# ---------------------------------------------------------------------------

def _monthly_series(db, company_id: UUID, fiscal_year_id: UUID, kind: str) -> list:
    """Serie mensual (1..12) del ejercicio: revenue, expense, receipts o payments."""
    if kind == "revenue":
        clause, expr = "a.account_type='revenue'", "l.credit_amount-l.debit_amount"
    elif kind == "expense":
        clause, expr = "a.account_type='expense'", "l.debit_amount-l.credit_amount"
    elif kind == "receipts":
        clause, expr = "a.account_subtype IN ('cash','bank')", "CASE WHEN l.debit_amount>l.credit_amount THEN l.debit_amount-l.credit_amount ELSE 0 END"
    else:
        clause, expr = "a.account_subtype IN ('cash','bank')", "CASE WHEN l.credit_amount>l.debit_amount THEN l.credit_amount-l.debit_amount ELSE 0 END"
    rows = db.execute(text(f"""
        SELECT EXTRACT(MONTH FROM j.entry_date) m, SUM({expr}) v
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND {clause}
        GROUP BY EXTRACT(MONTH FROM j.entry_date)
    """), {"c": company_id, "fy": fiscal_year_id}).all()
    series = [Decimal("0")] * 12
    for r in rows:
        series[int(r[0]) - 1] = Decimal(str(r[1] or 0))
    return series


def _regress(ys: list) -> tuple:
    """Mínimos cuadrados sobre la serie: (pendiente, intercepte, r2) en floats."""
    vals = [float(y) for y in ys]
    n = len(vals)
    if n < 2:
        return 0.0, (vals[0] if vals else 0.0), 0.0
    xs = list(range(1, n + 1))
    mx = sum(xs) / n; my = sum(vals) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, vals)); sxx = sum((x - mx) ** 2 for x in xs)
    b = sxy / sxx if sxx else 0.0; a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in vals); ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, vals))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return b, a, r2


def _seasonal_index(ys: list) -> list:
    """Índice estacional por mes = actual / promedio (serie de un ejercicio)."""
    vals = [float(y) for y in ys]
    mean = sum(vals) / len(vals) if vals else 0.0
    if mean <= 0:
        return [1.0] * 12
    return [v / mean for v in vals]


def _next_months(count: int) -> list:
    hoy = date.today(); y, m = hoy.year, hoy.month
    out = []
    for _ in range(count):
        m += 1
        if m > 12: m, y = 1, y + 1
        out.append(f"{y}-{m:02d}")
    return out


def _open_ar_ap(db, company_id: UUID):
    """Cartera pendiente publicada: documentos con saldo abierto y su vencimiento."""
    return db.execute(text("""
        SELECT d.id, d.auxiliary_id, fa.code aux_code, fa.name aux_name, d.currency, d.document_type,
               d.issue_date, d.due_date, d.total,
               COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id),0) paid,
               d.total - COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id),0) open_amount
        FROM finance_documents d LEFT JOIN finance_auxiliaries fa ON fa.id=d.auxiliary_id
        WHERE d.company_id=:c AND d.status='posted'
          AND d.total - COALESCE((SELECT SUM(s.amount) FROM finance_document_settlements s WHERE s.document_id=d.id),0) > 0.005
        ORDER BY d.due_date
    """), {"c": company_id}).mappings().all()


def _cash_balance(db, company_id: UUID, as_of: date) -> Decimal:
    """Saldo de caja y bancos al corte según contabilidad (debitos - creditos acumulado)."""
    row = db.execute(text("""
        SELECT COALESCE(SUM(CASE WHEN a.account_subtype IN ('cash','bank') THEN l.debit_amount-l.credit_amount ELSE 0 END),0) v
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:c AND j.status='posted' AND j.entry_date<=:as_of
    """), {"c": company_id, "as_of": as_of}).scalar_one()
    return Decimal(str(row or 0))


@app.get("/api/v1/finance/ai/forecast-cashflow", tags=["ai"])
def ai_forecast_cashflow(company_id: UUID, fiscal_year_id: UUID | None = None, horizon: int = Query(default=6, le=12), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Pronóstico de caja: regresión+estacionalidad sobre recaudos/pagos más cronograma de cartera pendiente."""
    require_company(claims, company_id)
    fy_id = fiscal_year_id
    if not fy_id:
        fy_id = db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c AND start_date<=:t AND end_date>=:t ORDER BY start_date DESC LIMIT 1"), {"c": company_id, "t": date.today()}).scalar()
        fy_id = fy_id or db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c ORDER BY start_date DESC LIMIT 1"), {"c": company_id}).scalar()
    rec = _monthly_series(db, company_id, fy_id, "receipts")
    pay = _monthly_series(db, company_id, fy_id, "payments")
    b_r, a_r, r2_r = _regress(rec); b_p, a_p, r2_p = _regress(pay)
    s_r = _seasonal_index(rec); s_p = _seasonal_index(pay)
    months = _next_months(horizon)
    hist_net = [float(rec[i] - pay[i]) for i in range(12)]
    mean_net = sum(hist_net) / 12
    std_net = (sum((v - mean_net) ** 2 for v in hist_net) / 12) ** 0.5
    open_items = list(_open_ar_ap(db, company_id))
    port_rec = {m: 0.0 for m in months}; port_pay = {m: 0.0 for m in months}
    for it in open_items:
        due = it["due_date"] or it["issue_date"]
        key = next((m for m in months if due <= date.fromisoformat(m + "-28")), months[-1])
        amt = float(it["open_amount"]); dt = it["document_type"]
        if dt in ("sales_invoice", "purchase_credit_note"): port_rec[key] += amt
        elif dt in ("purchase_bill", "sales_credit_note"): port_pay[key] += amt
    f_rec, f_pay = [], []
    for i, m in enumerate(months):
        x = 13 + i; month_no = int(m[5:])
        f_rec.append(max(a_r + b_r * x, 0.0) * s_r[month_no - 1] + port_rec[m])
        f_pay.append(max(a_p + b_p * x, 0.0) * s_p[month_no - 1] + port_pay[m])
    net = [f_rec[i] - f_pay[i] for i in range(horizon)]
    opening = _cash_balance(db, company_id, date.today())
    cum = []; run = float(opening)
    for v in net: run += v; cum.append(run)
    band = 1.28 * std_net
    alerts = []
    if not any(rec) and not any(pay):
        alerts.append({"code": "no_data", "severity": "low", "message": "Sin movimientos de caja publicados: la proyección usa solo la cartera pendiente."})
    if r2_r < 0.3 and r2_p < 0.3:
        alerts.append({"code": "low_confidence", "severity": "medium", "message": "Serie histórica errática (R² bajo): interprete la tendencia con cautela."})
    for i, c in enumerate(cum):
        if c < 0:
            alerts.append({"code": "negative_cash", "severity": "high", "message": f"Caja proyectada negativa en {months[i]}: {c:,.2f} PEN."})
            break
    total_open = sum(float(i["open_amount"]) for i in open_items)
    avg_rec = sum(float(r) for r in rec) / 12
    if avg_rec > 0 and total_open > avg_rec * 2:
        alerts.append({"code": "high_receivables", "severity": "medium", "message": f"Cartera pendiente ({total_open:,.2f}) supera 2 meses de recaudo promedio."})
    return {
        "company_id": company_id, "fiscal_year_id": fy_id, "currency": "PEN", "horizon_months": horizon,
        "opening_cash": str(round(opening, 2)), "months": months,
        "receipts": [str(round(v, 2)) for v in f_rec], "payments": [str(round(v, 2)) for v in f_pay],
        "net": [str(round(v, 2)) for v in net], "cumulative": [str(round(v, 2)) for v in cum],
        "band": {"low": [str(round(v - band, 2)) for v in net], "high": [str(round(v + band, 2)) for v in net], "confidence": "80%"},
        "portfolio_effect": {"receipts": {m: str(round(port_rec[m], 2)) for m in months}, "payments": {m: str(round(port_pay[m], 2)) for m in months}},
        "model": {"method": "trend-lineal + estacionalidad simple + cronograma de cartera", "r2_receipts": round(r2_r, 3), "r2_payments": round(r2_p, 3)},
        "alerts": alerts, "has_data": bool(any(rec) or any(pay) or open_items),
    }


@app.get("/api/v1/finance/ai/forecast-results", tags=["ai"])
def ai_forecast_results(company_id: UUID, fiscal_year_id: UUID | None = None, horizon: int = Query(default=6, le=12), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Pronóstico de ingresos, gastos y resultado neto a futuro más proyección de cierre de ejercicio."""
    require_company(claims, company_id)
    fy_id = fiscal_year_id
    if not fy_id:
        fy_id = db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c AND start_date<=:t AND end_date>=:t ORDER BY start_date DESC LIMIT 1"), {"c": company_id, "t": date.today()}).scalar()
        fy_id = fy_id or db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c ORDER BY start_date DESC LIMIT 1"), {"c": company_id}).scalar()
    fy = db.execute(text("SELECT start_date,end_date FROM fiscal_years WHERE id=:id"), {"id": fy_id}).mappings().first()
    rev = _monthly_series(db, company_id, fy_id, "revenue")
    exp = _monthly_series(db, company_id, fy_id, "expense")
    b_r, a_r, r2_r = _regress(rev); b_e, a_e, r2_e = _regress(exp)
    s_r = _seasonal_index(rev); s_e = _seasonal_index(exp)
    months = _next_months(horizon)
    f_rev, f_exp = [], []
    for i, m in enumerate(months):
        x = 13 + i; mn = int(m[5:])
        f_rev.append(max(a_r + b_r * x, 0.0) * s_r[mn - 1])
        f_exp.append(max(a_e + b_e * x, 0.0) * s_e[mn - 1])
    f_net = [f_rev[i] - f_exp[i] for i in range(horizon)]
    cum = []; run = 0.0
    for v in f_net: run += v; cum.append(run)
    actual_rev = sum(float(v) for v in rev); actual_exp = sum(float(v) for v in exp)
    remaining = max(0, math.ceil((fy["end_date"] - date.today()).days / 30.44)) if fy else 0
    avg_rev = sum(f_rev) / horizon if horizon else 0.0
    avg_exp = sum(f_exp) / horizon if horizon else 0.0
    ye_rev = actual_rev + avg_rev * remaining
    ye_exp = actual_exp + avg_exp * remaining
    margin_actual = (actual_rev - actual_exp) / actual_rev * 100 if actual_rev else 0.0
    margin_proj = (ye_rev - ye_exp) / ye_rev * 100 if ye_rev else 0.0
    alerts = []
    if not any(rev) and not any(exp):
        alerts.append({"code": "no_data", "severity": "low", "message": "Sin ingresos ni gastos publicados: la proyección es puramente indicativa."})
    if margin_proj < margin_actual - 1:
        alerts.append({"code": "margin_erosion", "severity": "medium", "message": f"El margen proyectado ({margin_proj:.1f}%) cae respecto del actual ({margin_actual:.1f}%)."})
    if b_e > 0 and actual_exp > 0 and (b_e * 12) > actual_exp * 0.05:
        alerts.append({"code": "expense_growth", "severity": "medium", "message": f"Los gastos muestran tendencia alcista (~{b_e:,.0f} PEN/mes)."})
    if r2_r < 0.3 and r2_e < 0.3:
        alerts.append({"code": "low_confidence", "severity": "low", "message": "R² bajo en ambas series: use el escenario como referencia, no como certeza."})
    return {
        "company_id": company_id, "fiscal_year_id": fy_id, "currency": "PEN", "horizon_months": horizon,
        "months": months,
        "revenue": [str(round(v, 2)) for v in f_rev], "expenses": [str(round(v, 2)) for v in f_exp], "net": [str(round(v, 2)) for v in f_net],
        "cumulative_net": [str(round(v, 2)) for v in cum],
        "ytd": {"revenue": str(round(actual_rev, 2)), "expenses": str(round(actual_exp, 2)), "net": str(round(actual_rev - actual_exp, 2)), "net_margin_pct": round(margin_actual, 1)},
        "year_end_projection": {"revenue": str(round(ye_rev, 2)), "expenses": str(round(ye_exp, 2)), "net": str(round(ye_rev - ye_exp, 2)), "net_margin_pct": round(margin_proj, 1), "months_remaining": remaining},
        "model": {"method": "trend-lineal + índice estacional mensual", "r2_revenue": round(r2_r, 3), "r2_expenses": round(r2_e, 3)},
        "alerts": alerts, "has_data": bool(any(rev) or any(exp)),
    }


@app.get("/api/v1/finance/ai/predict-collections", tags=["ai"])
def ai_predict_collections(company_id: UUID, weeks: int = Query(default=8, le=16), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Cobros esperados por semana desde la cartera pendiente, con rezago histórico por auxiliar."""
    require_company(claims, company_id)
    today = date.today()
    open_items = list(_open_ar_ap(db, company_id))
    lag_rows = db.execute(text("""
        SELECT d.auxiliary_id, AVG(s.settled_at - d.issue_date)::float lag_days,
               count(*) paid_n, SUM(s.amount) paid_total
        FROM finance_document_settlements s JOIN finance_documents d ON d.id=s.document_id
        WHERE d.company_id=:c GROUP BY d.auxiliary_id
    """), {"c": company_id}).mappings().all()
    lag: dict = {}
    for r in lag_rows:
        lag[str(r["auxiliary_id"])] = {"lag_days": float(r["lag_days"] or 0), "paid_n": int(r["paid_n"]), "paid_total": float(r["paid_total"] or 0)}
    def week_start(idx):
        d = today + timedelta(days=7 * idx)
        return d
    week_labels = [week_start(i).isoformat() for i in range(weeks)]
    week_amount = [0.0] * weeks
    week_count = [0] * weeks
    by_aux = []
    for it in open_items:
        if it["document_type"] not in ("sales_invoice", "sales_credit_note"):
            continue
        aid = str(it["auxiliary_id"]) if it["auxiliary_id"] else None
        info = lag.get(aid)
        expected = it["issue_date"] + timedelta(days=info["lag_days"]) if info else (it["due_date"] or it["issue_date"])
        if expected < today:
            expected = today
        idx = min(int((expected - today).days / 7), weeks - 1)
        amt = float(it["open_amount"])
        week_amount[idx] += amt; week_count[idx] += 1
        paid_total = info["paid_total"] if info else 0.0
        open_all = amt + paid_total
        prob = min(max(paid_total / open_all, 0.3), 0.98) if open_all else 0.7
        by_aux.append({"auxiliary_id": it["auxiliary_id"], "code": it["aux_code"], "name": it["aux_name"],
                       "open_amount": str(round(amt, 2)), "expected_week": expected.isoformat(),
                       "probability": round(prob, 2), "avg_lag_days": round(info["lag_days"], 1) if info else None,
                       "risk": "low" if (info is None or info["lag_days"] <= 30) else ("medium" if info["lag_days"] <= 60 else "high")})
    by_aux.sort(key=lambda x: float(x["open_amount"]), reverse=True)
    overdue = sum(float(i["open_amount"]) for i in open_items if (i["due_date"] or i["issue_date"]) < today)
    alerts = []
    if not open_items:
        alerts.append({"code": "no_open", "severity": "low", "message": "No hay cartera pendiente publicada."})
    elif overdue > 0:
        alerts.append({"code": "overdue", "severity": "high" if overdue > sum(week_amount) else "medium", "message": f"Cartera vencida: {overdue:,.2f} PEN requiere gestión de cobranza."})
    return {
        "company_id": company_id, "currency": "PEN", "weeks": week_labels,
        "expected": [str(round(v, 2)) for v in week_amount], "documents_count": week_count,
        "total_expected": str(round(sum(week_amount), 2)), "overdue_amount": str(round(overdue, 2)),
        "by_auxiliary": by_aux[:50], "method": "cronograma de cartera + rezago histórico de cobro por auxiliar",
        "alerts": alerts, "has_data": bool(open_items),
    }


@app.get("/api/v1/finance/ai/anomalies", tags=["ai"])
def ai_anomalies(company_id: UUID, fiscal_year_id: UUID | None = None, z_threshold: float = Query(default=2.5, le=4.0), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Anomalías contables: montos atípicos (z-score), asientos de fin de semana, duplicados y montos redondos."""
    require_company(claims, company_id)
    fy_id = fiscal_year_id
    if not fy_id:
        fy_id = db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c AND start_date<=:t AND end_date>=:t ORDER BY start_date DESC LIMIT 1"), {"c": company_id, "t": date.today()}).scalar()
        fy_id = fy_id or db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c ORDER BY start_date DESC LIMIT 1"), {"c": company_id}).scalar()
    rows = db.execute(text("""
        SELECT j.entry_number, j.entry_date, j.reference, l.description, a.code, a.name,
               l.debit_amount, l.credit_amount, fa.code aux_code, fa.name aux_name
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id=l.auxiliary_id
        WHERE j.company_id=:c AND j.status='posted' AND j.fiscal_year_id=:fy
        ORDER BY j.entry_date
    """), {"c": company_id, "fy": fy_id}).mappings().all()
    amounts = [float(abs(r["debit_amount"] - r["credit_amount"])) for r in rows]
    nz = [v for v in amounts if v > 0]
    mean = sum(nz) / len(nz) if nz else 0.0
    std = (sum((v - mean) ** 2 for v in nz) / len(nz)) ** 0.5 if nz else 0.0
    out = []
    for r, amt in zip(rows, amounts):
        ctx = f"{r['code']} {r['name']} | {r['entry_number']} | {r['reference'] or (r['description'] or '')[:60]}"
        if std > 0 and amt > 0 and abs((amt - mean) / std) >= z_threshold:
            z = (amt - mean) / std
            out.append({"type": "amount_outlier", "severity": "high" if abs(z) >= 3.5 else "medium",
                        "message": f"Monto atípico (z={z:.1f}): {amt:,.2f} PEN en {ctx}", "date": r["entry_date"].isoformat(), "amount": str(round(amt, 2)), "z": round(z, 2)})
        if amt >= 5000 and amt % 1000 == 0:
            out.append({"type": "round_amount", "severity": "low",
                        "message": f"Monto redondo {amt:,.2f} PEN en {ctx} (verificar soporte)", "date": r["entry_date"].isoformat(), "amount": str(round(amt, 2))})
        if r["entry_date"].weekday() >= 5:
            out.append({"type": "weekend_entry", "severity": "low",
                        "message": f"Asiento publicado en fin de semana: {ctx}", "date": r["entry_date"].isoformat()})
    dup = db.execute(text("""
        SELECT d.party_tax_id, d.total, d.issue_date, count(*) n, array_agg(d.document_number) nums
        FROM finance_documents d WHERE d.company_id=:c AND d.status='posted' AND d.party_tax_id IS NOT NULL
        GROUP BY d.party_tax_id, d.total, d.issue_date HAVING count(*)>1
    """), {"c": company_id}).mappings().all()
    for d in dup:
        out.append({"type": "duplicate_document", "severity": "high",
                    "message": f"Posible duplicado: {', '.join(d['nums'])} por {float(d['total']):,.2f} PEN el {d['issue_date']} (RUC {d['party_tax_id']})",
                    "date": d["issue_date"].isoformat(), "amount": str(round(float(d["total"]), 2))})
    out.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))
    counts: dict = {}
    for a in out:
        counts[a["type"]] = counts.get(a["type"], 0) + 1
    return {"company_id": company_id, "currency": "PEN", "total": len(out), "counts": counts,
            "anomalies": out[:200], "z_threshold": z_threshold, "lines_reviewed": len(rows),
            "has_data": bool(rows)}


@app.get("/api/v1/finance/ai/insights", tags=["ai"])
def ai_insights(company_id: UUID, fiscal_year_id: UUID | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Insights generados sobre datos reales: liquidez, momentum, concentración, cartera, presupuesto e impuestos."""
    require_company(claims, company_id)
    fy_id = fiscal_year_id
    if not fy_id:
        fy_id = db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c AND start_date<=:t AND end_date>=:t ORDER BY start_date DESC LIMIT 1"), {"c": company_id, "t": date.today()}).scalar()
        fy_id = fy_id or db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c ORDER BY start_date DESC LIMIT 1"), {"c": company_id}).scalar()
    today = date.today()
    rec = [float(x) for x in _monthly_series(db, company_id, fy_id, "receipts")]
    pay = [float(x) for x in _monthly_series(db, company_id, fy_id, "payments")]
    rev = [float(x) for x in _monthly_series(db, company_id, fy_id, "revenue")]
    exp = [float(x) for x in _monthly_series(db, company_id, fy_id, "expense")]
    insights = []
    def add(cat, title, detail, impact, metric=None, rec_text=""):
        insights.append({"category": cat, "title": title, "detail": detail, "impact": impact, "metric": metric, "recommendation": rec_text})
    cash = float(_cash_balance(db, company_id, today))
    payables = float(db.execute(text("""
        SELECT COALESCE(SUM(CASE WHEN a.account_subtype='payable' THEN l.credit_amount-l.debit_amount ELSE 0 END),0)
        FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        WHERE j.company_id=:c AND j.status='posted' AND j.entry_date<=:t
    """), {"c": company_id, "t": today}).scalar() or 0)
    if payables > 0:
        cover = cash / payables
        add("liquidez", "Cobertura de caja sobre pasivos",
            f"Caja y bancos {cash:,.2f} PEN frente a pasivos por pagar {payables:,.2f} PEN (cobertura {cover:.2f}x).",
            "positive" if cover >= 1 else "negative", round(cover, 2),
            "Priorice cobranza o negocie plazos si la cobertura baja de 1.0x." if cover < 1 else "Posición de caja cómoda para obligaciones de corto plazo.")
    if any(rev):
        last3 = sum(rev[-3:]) / 3; prev3 = sum(rev[-6:-3]) / 3
        growth = (last3 - prev3) / prev3 * 100 if prev3 else 0.0
        add("rentabilidad", "Momentum de ingresos",
            f"Ingresos últimos 3 meses {last3:,.2f} vs 3 anteriores {prev3:,.2f} ({growth:+.1f}%).",
            "positive" if growth > 0 else "negative", round(growth, 1),
            "Refuerce las líneas en alza y revise la cartera de la baja." if growth < 0 else "Mantenga el ritmo comercial y vigile la capacidad de caja.")
    top = db.execute(text("""
        SELECT fa.name, SUM(l.credit_amount-l.debit_amount) amt FROM journal_entry_lines l
        JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id=l.auxiliary_id
        WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND a.account_type='revenue'
        GROUP BY fa.name ORDER BY amt DESC LIMIT 5
    """), {"c": company_id, "fy": fy_id}).mappings().all()
    tot_rev = sum(rev)
    if top and tot_rev > 0:
        share = float(top[0]["amt"]) / tot_rev * 100
        add("concentración", f"Cliente principal: {top[0]['name']}",
            f"Aporta {share:.1f}% de los ingresos del ejercicio ({float(top[0]['amt']):,.2f} PEN).",
            "negative" if share > 40 else "neutral", round(share, 1),
            "Diversifique la cartera si supera 40% del ingreso." if share > 40 else "Concentración dentro de rango saludable.")
    ar = [i for i in _open_ar_ap(db, company_id) if i["document_type"] in ("sales_invoice", "sales_credit_note")]
    buckets = {"current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "over_90": 0.0}
    for i in ar:
        days = (today - (i["due_date"] or i["issue_date"])).days
        amt = float(i["open_amount"])
        k = "current" if days <= 0 else ("1-30" if days <= 30 else ("31-60" if days <= 60 else ("61-90" if days <= 90 else "over_90")))
        buckets[k] += amt
    overdue = buckets["31-60"] + buckets["61-90"] + buckets["over_90"]
    total_ar = sum(buckets.values())
    if total_ar > 0:
        add("cartera", "Vencimientos de cartera",
            f"Cartera abierta {total_ar:,.2f} PEN; vencida >30 días {overdue:,.2f} ({overdue/total_ar*100:.1f}%).",
            "negative" if overdue / total_ar > 0.25 else "neutral", round(overdue, 2),
            "Active cobranza preventiva y revise crédito a clientes morosos." if overdue / total_ar > 0.25 else "Cartera dentro de parámetros normales.")
    budgets = db.execute(text("SELECT id,name FROM budgets WHERE company_id=:c AND fiscal_year_id=:fy AND status='active'"), {"c": company_id, "fy": fy_id}).mappings().all()
    for b in budgets:
        lines = db.execute(text("SELECT bl.account_id, bl.planned_amount, a.account_type FROM budget_lines bl JOIN accounts a ON a.id=bl.account_id WHERE bl.budget_id=:id"), {"id": b["id"]}).mappings().all()
        ids = [l["account_id"] for l in lines]
        ex: dict = {}
        if ids:
            for r in db.execute(text("""
                SELECT l.account_id, SUM(CASE WHEN a.account_type IN ('revenue','liability','equity') THEN l.credit_amount-l.debit_amount ELSE l.debit_amount-l.credit_amount END) v
                FROM journal_entry_lines l JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
                WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND l.account_id=ANY(CAST(:ids AS uuid[])) GROUP BY l.account_id
            """), {"c": company_id, "fy": fy_id, "ids": ids}).all():
                ex[str(r[0])] = float(r[1] or 0)
        over = sum(1 for l in lines if l["account_type"] == "expense" and ex.get(str(l["account_id"]), 0) > float(l["planned_amount"]) * 1.1)
        if over:
            add("presupuesto", f"Desviaciones en '{b['name']}'",
                f"{over} líneas de gasto superan 110% de lo planificado.", "negative", over,
                "Revise las partidas con sobreejecución y ajuste compromisos.")
    tax = db.execute(text("""
        SELECT COALESCE(SUM(CASE WHEN d.document_type='sales_invoice' THEN d.tax_total ELSE 0 END),0) s,
               COALESCE(SUM(CASE WHEN d.document_type='purchase_bill' THEN d.tax_total ELSE 0 END),0) p
        FROM finance_documents d WHERE d.company_id=:c AND d.status='posted' AND d.issue_date BETWEEN :s AND :e
    """), {"c": company_id, "s": db.execute(text("SELECT start_date FROM fiscal_years WHERE id=:id"), {"id": fy_id}).scalar(), "e": db.execute(text("SELECT end_date FROM fiscal_years WHERE id=:id"), {"id": fy_id}).scalar()}).mappings().first()
    if tax and (tax["s"] or tax["p"]):
        net_tax = float(tax["s"] - tax["p"])
        add("tributario", "Saldo de IGV del periodo",
            f"IGV ventas {float(tax['s']):,.2f} menos IGV compras {float(tax['p']):,.2f} = {net_tax:,.2f} PEN a favor/ en contra.",
            "neutral", round(net_tax, 2),
            "Provisione el pago si el saldo es a favor del fisco.")
    return {"company_id": company_id, "fiscal_year_id": fy_id, "generated_at": datetime.now(UTC), "currency": "PEN",
            "insights": insights, "aging": {k: str(round(v, 2)) for k, v in buckets.items()},
            "has_data": bool(any(rev) or any(exp) or ar or budgets)}


class NLQueryRequest(BaseModel):
    question: str
    company_id: UUID
    fiscal_year_id: Optional[UUID] = None


MONTHS_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _resolve_fy(db, company_id: UUID, fiscal_year_id: Optional[UUID]):
    if fiscal_year_id:
        return fiscal_year_id
    fy = db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c AND start_date<=:t AND end_date>=:t ORDER BY start_date DESC LIMIT 1"), {"c": company_id, "t": date.today()}).scalar()
    return fy or db.execute(text("SELECT id FROM fiscal_years WHERE company_id=:c ORDER BY start_date DESC LIMIT 1"), {"c": company_id}).scalar()


def _unaccent(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


@app.post("/api/v1/finance/ai/natural-query", tags=["ai"])
def ai_natural_query(payload: NLQueryRequest, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Responde preguntas financieras en lenguaje natural usando datos reales contabilizados."""
    require_company(claims, payload.company_id)
    q = _unaccent(payload.question or "")
    fy_id = _resolve_fy(db, payload.company_id, payload.fiscal_year_id)
    rev = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "revenue")]
    exp = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "expense")]
    rec = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "receipts")]
    pay = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "payments")]
    t_rev, t_exp = sum(rev), sum(exp)
    intent, data, suggestions = "general", {}, ["¿Cual es mi caja proyectada a 6 meses?", "¿Que clientes concentran mis ventas?", "¿Hay anomalias en mis asientos?"]
    if any(k in q for k in ("caja", "flujo", "liquidez", "efectivo", "tesoreria", "entrada", "salida")):
        intent = "cashflow"
        opening = float(_cash_balance(db, payload.company_id, date.today()))
        data = {"opening_cash": round(opening, 2), "receipts": [round(v, 2) for v in rec], "payments": [round(v, 2) for v in pay], "net": [round(rec[i] - pay[i], 2) for i in range(12)]}
        best = max(range(12), key=lambda i: rec[i] - pay[i])
        answer = f"Caja actual {opening:,.2f} PEN. En los ultimos 12 meses entro {sum(rec):,.2f} y salio {sum(pay):,.2f} (neto {sum(rec)-sum(pay):,.2f}); el mejor mes fue {MONTHS_ES[best]} (+{rec[best]-pay[best]:,.2f})."
        suggestions = ["¿Como sera mi caja los proximos 6 meses?", "¿Cuanto espero cobrar las proximas 8 semanas?", "¿Cuantos pasivos tengo por pagar?"]
    elif any(k in q for k in ("ingreso", "venta", "recaudo", "factur", "client", "ingresos")):
        intent = "revenue"
        data = {"total_revenue": round(t_rev, 2), "monthly": [round(v, 2) for v in rev]}
        growth = (sum(rev[-3:]) / 3 - sum(rev[-6:-3]) / 3) / (sum(rev[-6:-3]) / 3) * 100 if sum(rev[-6:-3]) else 0.0
        answer = f"Ingresos del ejercicio {t_rev:,.2f} PEN; promedio mensual {t_rev/12:,.2f}; momentum ultimos 3 meses {growth:+.1f}%."
        suggestions = ["¿Que cliente aporta mas?", "¿Cual es el margen neto proyectado?", "¿Como cierran los impuestos del año?"]
    elif any(k in q for k in ("gasto", "costo", "egreso", "pago", "gastos")):
        intent = "expense"
        data = {"total_expenses": round(t_exp, 2), "monthly": [round(v, 2) for v in exp]}
        top = db.execute(text("""
            SELECT a.code, a.name, SUM(l.debit_amount-l.credit_amount) v FROM journal_entry_lines l
            JOIN journal_entries j ON j.id=l.journal_entry_id JOIN accounts a ON a.id=l.account_id
            WHERE j.company_id=:c AND j.fiscal_year_id=:fy AND j.status='posted' AND a.account_type='expense'
            GROUP BY a.code, a.name ORDER BY v DESC LIMIT 1
        """), {"c": payload.company_id, "fy": fy_id}).mappings().first()
        extra = f" La partida mayor es {top['code']} {top['name']} ({float(top['v']):,.2f} PEN)." if top else ""
        answer = f"Gastos del ejercicio {t_exp:,.2f} PEN (promedio mensual {t_exp/12:,.2f}).{extra}"
        suggestions = ["¿Que partida crece mas rapido?", "¿Donde hay anomalias de monto?", "¿Como voy contra presupuesto?"]
    elif any(k in q for k in ("utilidad", "resultado", "ganancia", "perdida", "margen", "beneficio")):
        intent = "result"
        net = t_rev - t_exp
        data = {"revenue": round(t_rev, 2), "expenses": round(t_exp, 2), "net": round(net, 2), "margin_pct": round(net / t_rev * 100, 1) if t_rev else 0.0}
        answer = f"Resultado del ejercicio: {net:,.2f} PEN ({data['margin_pct']:.1f}% de margen sobre ventas de {t_rev:,.2f})."
        suggestions = ["¿Como se proyecta el resultado a fin de año?", "¿Que tan liquida estoy?", "¿Cuanto impuesto me queda?"]
    elif any(k in q for k in ("presupuesto", "presupuestar", "avance", "desviacion")):
        intent = "budget"
        bs = db.execute(text("SELECT id,name,status FROM budgets WHERE company_id=:c AND fiscal_year_id=:fy ORDER BY name"), {"c": payload.company_id, "fy": fy_id}).mappings().all()
        data = {"budgets": [{"id": b["id"], "name": b["name"], "status": b["status"]} for b in bs]}
        answer = f"Tiene {len(bs)} presupuesto(s) activo(s) en el ejercicio." + (f" El primero es '{bs[0]['name']}'." if bs else "")
        suggestions = ["¿Cual es la proyeccion de cierre de mi presupuesto?", "¿Que partidas se desvian?", "¿Cual es el gasto total del año?"]
    elif any(k in q for k in ("impuesto", "igv", "tribut", "iva", "sunat")):
        intent = "tax"
        row = db.execute(text("""
            SELECT COALESCE(SUM(CASE WHEN d.document_type='sales_invoice' THEN d.tax_total ELSE 0 END),0) s,
                   COALESCE(SUM(CASE WHEN d.document_type='purchase_bill' THEN d.tax_total ELSE 0 END),0) p
            FROM finance_documents d WHERE d.company_id=:c AND d.status='posted'
        """), {"c": payload.company_id}).mappings().first()
        net_tax = float(row["s"] - row["p"])
        data = {"sales_tax": round(float(row["s"]), 2), "purchase_tax": round(float(row["p"]), 2), "net_tax": round(net_tax, 2)}
        answer = f"IGV ventas {float(row['s']):,.2f} menos IGV compras {float(row['p']):,.2f}: saldo a favor/ en contra del fisco {net_tax:,.2f} PEN."
        suggestions = ["¿Que documentos tengo pendientes de pago?", "¿Hay duplicados en mis comprobantes?"]
    elif any(k in q for k in ("cartera", "vencido", "moros", "pendiente", "cobrar", "cobro", "deuda")):
        intent = "collections"
        ar = [i for i in _open_ar_ap(db, payload.company_id) if i["document_type"] in ("sales_invoice", "sales_credit_note")]
        total = sum(float(i["open_amount"]) for i in ar)
        overdue = sum(float(i["open_amount"]) for i in ar if (date.today() - (i["due_date"] or i["issue_date"])).days > 0)
        data = {"open_ar": round(total, 2), "overdue": round(overdue, 2), "clients": len(ar)}
        answer = f"Cartera pendiente {total:,.2f} PEN en {len(ar)} documento(s); vencida {overdue:,.2f} PEN ({overdue/total*100:.0f}%)." if total else "No hay cartera pendiente de cobro."
        suggestions = ["¿Cuando espero cobrar la proximas 8 semanas?", "¿Que cliente concentra mas ventas?", "¿Hay asientos de fin de semana?"]
    elif any(k in q for k in ("anomal", "raro", "atipico", "fraude", "duplicad", "fin de semana", "sabado", "domingo")):
        intent = "anomalies"
        weekend = db.execute(text("SELECT count(*) n FROM journal_entries WHERE company_id=:c AND status='posted' AND EXTRACT(DOW FROM entry_date) IN (0,6)"), {"c": payload.company_id}).scalar()
        dups = db.execute(text("""
            SELECT count(*) n FROM (
              SELECT d.party_tax_id, d.total, d.issue_date FROM finance_documents d
              WHERE d.company_id=:c AND d.status='posted' AND d.party_tax_id IS NOT NULL
              GROUP BY d.party_tax_id, d.total, d.issue_date HAVING count(*)>1
            ) x
        """), {"c": payload.company_id}).scalar()
        data = {"weekend_entries": int(weekend or 0), "duplicate_groups": int(dups or 0)}
        answer = f"Detecto {int(weekend or 0)} asiento(s) publicado(s) en fin de semana y {int(dups or 0)} grupo(s) de comprobantes duplicados; use el panel de anomalias para montos atipicos."
        suggestions = ["¿Que asientos tienen montos atipicos?", "¿Como esta mi caja proyectada?", "¿Que clientes concentran mis ventas?"]
    else:
        intent = "kpis"
        answer = f"Ejercicio: ingresos {t_rev:,.2f}, gastos {t_exp:,.2f}, resultado {t_rev-t_exp:,.2f} PEN; caja actual {float(_cash_balance(db, payload.company_id, date.today())):,.2f}."
        data = {"revenue": round(t_rev, 2), "expenses": round(t_exp, 2), "net": round(t_rev - t_exp, 2)}
    return {"question": payload.question, "intent": intent, "answer": answer, "data": data, "suggestions": suggestions, "currency": "PEN", "has_data": bool(any(rev) or any(exp))}


class ScenarioRequest(BaseModel):
    company_id: UUID
    fiscal_year_id: Optional[UUID] = None
    revenue_change_pct: float = 0.0
    expense_change_pct: float = 0.0
    collection_delay_days: int = 0
    extra_fixed_cost: float = 0.0


@app.post("/api/v1/finance/ai/scenario", tags=["ai"])
def ai_scenario(payload: ScenarioRequest, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Simula escenarios sobre la caja: variación de ingresos/gastos, rezago de cobro y costo fijo extra."""
    require_company(claims, payload.company_id)
    fy_id = _resolve_fy(db, payload.company_id, payload.fiscal_year_id)
    rec = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "receipts")]
    pay = [float(x) for x in _monthly_series(db, payload.company_id, fy_id, "payments")]
    b_r, a_r, _ = _regress(rec); b_p, a_p, _ = _regress(pay)
    s_r = _seasonal_index(rec); s_p = _seasonal_index(pay)
    horizon = 6
    months = _next_months(horizon)
    base_rec, base_pay = [], []
    for i, m in enumerate(months):
        x = 13 + i; mn = int(m[5:])
        base_rec.append(max(a_r + b_r * x, 0.0) * s_r[mn - 1])
        base_pay.append(max(a_p + b_p * x, 0.0) * s_p[mn - 1])
    p = min(max(payload.collection_delay_days / 30.0, 0.0), 0.5)
    sc_rec = [base_rec[i] * (1 - p) + (base_rec[i - 1] * p if i > 0 else 0.0) for i in range(horizon)]
    sc_rec = [v * (1 + payload.revenue_change_pct / 100) for v in sc_rec]
    sc_pay = [v * (1 + payload.expense_change_pct / 100) + payload.extra_fixed_cost for v in base_pay]
    def cumulate(recs, pays):
        out = []; run = 0.0
        for i in range(horizon):
            run += recs[i] - pays[i]; out.append(run)
        return out
    b_net = [base_rec[i] - base_pay[i] for i in range(horizon)]
    s_net = [sc_rec[i] - sc_pay[i] for i in range(horizon)]
    b_cum, s_cum = cumulate(base_rec, base_pay), cumulate(sc_rec, sc_pay)
    opening = float(_cash_balance(db, payload.company_id, date.today()))
    narrative = []
    if payload.revenue_change_pct:
        narrative.append(f"Ingresos {payload.revenue_change_pct:+.1f}%: recaudo esperado pasa de {sum(base_rec):,.2f} a {sum(sc_rec):,.2f} PEN.")
    if payload.expense_change_pct:
        narrative.append(f"Gastos {payload.expense_change_pct:+.1f}%: pagos pasan de {sum(base_pay):,.2f} a {sum(sc_pay):,.2f} PEN.")
    if payload.collection_delay_days:
        narrative.append(f"Rezago de cobro +{payload.collection_delay_days} días desplaza {p*100:.0f}% del recaudo al mes siguiente.")
    if payload.extra_fixed_cost:
        narrative.append(f"Costo fijo extra de {payload.extra_fixed_cost:,.2f} PEN/mes suma {payload.extra_fixed_cost*horizon:,.2f} PEN en {horizon} meses.")
    if not narrative:
        narrative.append("Sin cambios: escenario base (= tendencia histórica).")
    if s_cum[-1] < b_cum[-1]:
        narrative.append(f"El escenario empeora el flujo neto acumulado en {s_cum[-1]-b_cum[-1]:,.2f} PEN.")
    elif s_cum[-1] > b_cum[-1]:
        narrative.append(f"El escenario mejora el flujo neto acumulado en {s_cum[-1]-b_cum[-1]:,.2f} PEN.")
    if opening + min(s_cum) < 0:
        narrative.append(f"ALERTA: con este escenario la caja llega a {opening+min(s_cum):,.2f} PEN (negativa).")
    return {
        "company_id": payload.company_id, "fiscal_year_id": fy_id, "currency": "PEN", "horizon_months": horizon, "months": months,
        "opening_cash": str(round(opening, 2)),
        "baseline": {"receipts": [str(round(v, 2)) for v in base_rec], "payments": [str(round(v, 2)) for v in base_pay], "net": [str(round(v, 2)) for v in b_net], "cumulative": [str(round(v, 2)) for v in b_cum]},
        "scenario": {"receipts": [str(round(v, 2)) for v in sc_rec], "payments": [str(round(v, 2)) for v in sc_pay], "net": [str(round(v, 2)) for v in s_net], "cumulative": [str(round(v, 2)) for v in s_cum]},
        "delta": {"net": [str(round(s_net[i] - b_net[i], 2)) for i in range(horizon)],
                  "ending_cash_baseline": str(round(opening + b_cum[-1], 2)), "ending_cash_scenario": str(round(opening + s_cum[-1], 2)),
                  "ending_cash_delta": str(round(s_cum[-1] - b_cum[-1], 2)),
                  "min_cash_baseline": str(round(opening + min(b_cum), 2)), "min_cash_scenario": str(round(opening + min(s_cum), 2))},
        "inputs": {"revenue_change_pct": payload.revenue_change_pct, "expense_change_pct": payload.expense_change_pct, "collection_delay_days": payload.collection_delay_days, "extra_fixed_cost": payload.extra_fixed_cost},
        "narrative": narrative, "has_data": bool(any(rec) or any(pay)),
    }



# ===========================================================================
# COST CENTERS & PROJECTS
# ===========================================================================

@app.get("/api/v1/finance/cost-centers", response_model=list[CostCenterResponse], tags=["cost-centers"])
def list_cost_centers(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT id, company_id, code, name, parent_id, is_active, created_at, updated_at FROM cost_centers WHERE company_id = :cid ORDER BY code ASC"),
        {"cid": company_id}
    ).mappings().all()
    return [CostCenterResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/cost-centers", response_model=CostCenterResponse, status_code=201, tags=["cost-centers"])
def create_cost_center(payload: CostCenterCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO cost_centers (company_id, code, name, parent_id, is_active)
                VALUES (:company_id, :code, :name, :parent_id, :is_active)
                RETURNING id, company_id, code, name, parent_id, is_active, created_at, updated_at
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.cost_center.created", payload.company_id, "cost_center", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de centro de costo ya registrado o error de integridad.") from exc
    return CostCenterResponse(**dict(row))

@app.patch("/api/v1/finance/cost-centers/{cost_center_id}", response_model=CostCenterResponse, tags=["cost-centers"])
def update_cost_center(cost_center_id: UUID, payload: CostCenterUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT id, company_id FROM cost_centers WHERE id = :id"), {"id": cost_center_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Centro de costo no encontrado.")
    require_company(claims, current["company_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios.")
    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    changes["id"] = cost_center_id
    row = db.execute(
        text(f"UPDATE cost_centers SET {assignments}, updated_at = now() WHERE id = :id RETURNING id, company_id, code, name, parent_id, is_active, created_at, updated_at"),
        changes
    ).mappings().first()
    _audit(db, claims, "finance.cost_center.updated", current["company_id"], "cost_center", str(cost_center_id))
    db.commit()
    return CostCenterResponse(**dict(row))

@app.delete("/api/v1/finance/cost-centers/{cost_center_id}", status_code=204, tags=["cost-centers"])
def delete_cost_center(cost_center_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT id, company_id FROM cost_centers WHERE id = :id"), {"id": cost_center_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Centro de costo no encontrado.")
    require_company(claims, current["company_id"])
    db.execute(text("UPDATE cost_centers SET is_active = FALSE, updated_at = now() WHERE id = :id"), {"id": cost_center_id})
    _audit(db, claims, "finance.cost_center.deactivated", current["company_id"], "cost_center", str(cost_center_id))
    db.commit()
    return None

@app.get("/api/v1/finance/projects", response_model=list[ProjectResponse], tags=["projects"])
def list_projects(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT id, company_id, code, name, start_date, end_date, budget_amount, status, manager_name, created_at, updated_at FROM projects WHERE company_id = :cid ORDER BY code ASC"),
        {"cid": company_id}
    ).mappings().all()
    return [ProjectResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/projects", response_model=ProjectResponse, status_code=201, tags=["projects"])
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO projects (company_id, code, name, start_date, end_date, budget_amount, status, manager_name)
                VALUES (:company_id, :code, :name, :start_date, :end_date, :budget_amount, :status, :manager_name)
                RETURNING id, company_id, code, name, start_date, end_date, budget_amount, status, manager_name, created_at, updated_at
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.project.created", payload.company_id, "project", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de proyecto ya existe o error en campos.") from exc
    return ProjectResponse(**dict(row))

@app.patch("/api/v1/finance/projects/{project_id}", response_model=ProjectResponse, tags=["projects"])
def update_project(project_id: UUID, payload: ProjectUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT id, company_id FROM projects WHERE id = :id"), {"id": project_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    require_company(claims, current["company_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios.")
    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    changes["id"] = project_id
    row = db.execute(
        text(f"UPDATE projects SET {assignments}, updated_at = now() WHERE id = :id RETURNING id, company_id, code, name, start_date, end_date, budget_amount, status, manager_name, created_at, updated_at"),
        changes
    ).mappings().first()
    _audit(db, claims, "finance.project.updated", current["company_id"], "project", str(project_id))
    db.commit()
    return ProjectResponse(**dict(row))


# ===========================================================================
# FIXED ASSETS & DEPRECIATION
# ===========================================================================

@app.get("/api/v1/finance/asset-categories", response_model=list[AssetCategoryResponse], tags=["fixed-assets"])
def list_asset_categories(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT * FROM asset_categories WHERE company_id = :cid ORDER BY code ASC"),
        {"cid": company_id}
    ).mappings().all()
    return [AssetCategoryResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/asset-categories", response_model=AssetCategoryResponse, status_code=201, tags=["fixed-assets"])
def create_asset_category(payload: AssetCategoryCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO asset_categories (company_id, code, name, depreciation_method, useful_life_years, salvage_rate, asset_account_id, accumulated_depreciation_account_id, depreciation_expense_account_id, is_active)
                VALUES (:company_id, :code, :name, :depreciation_method, :useful_life_years, :salvage_rate, :asset_account_id, :accumulated_depreciation_account_id, :depreciation_expense_account_id, :is_active)
                RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.asset_category.created", payload.company_id, "asset_category", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al crear categoría de activos.") from exc
    return AssetCategoryResponse(**dict(row))

@app.get("/api/v1/finance/fixed-assets", response_model=list[FixedAssetResponse], tags=["fixed-assets"])
def list_fixed_assets(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(
        text("SELECT * FROM fixed_assets WHERE company_id = :cid ORDER BY code ASC"),
        {"cid": company_id}
    ).mappings().all()
    return [FixedAssetResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/fixed-assets", response_model=FixedAssetResponse, status_code=201, tags=["fixed-assets"])
def create_fixed_asset(payload: FixedAssetCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    data = payload.model_dump()
    data["current_book_value"] = data["acquisition_cost"]
    data["accumulated_depreciation"] = Decimal("0")
    data["status"] = "active"
    try:
        row = db.execute(
            text("""
                INSERT INTO fixed_assets (
                    company_id, category_id, code, name, description, serial_number, location,
                    acquisition_date, start_depreciation_date, acquisition_cost, salvage_value,
                    useful_life_months, current_book_value, accumulated_depreciation, status, cost_center_id
                ) VALUES (
                    :company_id, :category_id, :code, :name, :description, :serial_number, :location,
                    :acquisition_date, :start_depreciation_date, :acquisition_cost, :salvage_value,
                    :useful_life_months, :current_book_value, :accumulated_depreciation, :status, :cost_center_id
                ) RETURNING *
            """),
            data
        ).mappings().first()
        _audit(db, claims, "finance.fixed_asset.created", payload.company_id, "fixed_asset", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de activo fijo ya existe o error en campos.") from exc
    return FixedAssetResponse(**dict(row))

@app.patch("/api/v1/finance/fixed-assets/{asset_id}", response_model=FixedAssetResponse, tags=["fixed-assets"])
def update_fixed_asset(asset_id: UUID, payload: FixedAssetUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT id, company_id FROM fixed_assets WHERE id = :id"), {"id": asset_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Activo fijo no encontrado.")
    require_company(claims, current["company_id"])
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="Sin cambios.")
    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    changes["id"] = asset_id
    row = db.execute(
        text(f"UPDATE fixed_assets SET {assignments}, updated_at = now() WHERE id = :id RETURNING *"),
        changes
    ).mappings().first()
    _audit(db, claims, "finance.fixed_asset.updated", current["company_id"], "fixed_asset", str(asset_id))
    db.commit()
    return FixedAssetResponse(**dict(row))

@app.post("/api/v1/finance/fixed-assets/{asset_id}/depreciate", tags=["fixed-assets"])
def run_asset_depreciation(asset_id: UUID, period_date: date = Query(...), fiscal_period_id: Optional[UUID] = Query(None), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    asset = db.execute(text("SELECT * FROM fixed_assets WHERE id = :id"), {"id": asset_id}).mappings().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo fijo no encontrado.")
    require_company(claims, asset["company_id"])
    if asset["status"] != "active":
        raise HTTPException(status_code=400, detail=f"El activo no está activo para depreciar (estado: {asset['status']}).")
    
    cost = Decimal(str(asset["acquisition_cost"]))
    salvage = Decimal(str(asset["salvage_value"]))
    depreciable_base = max(Decimal("0"), cost - salvage)
    months = Decimal(str(asset["useful_life_months"]))
    monthly_depr = round(depreciable_base / months, 4)
    
    accum_before = Decimal(str(asset["accumulated_depreciation"]))
    remaining = max(Decimal("0"), depreciable_base - accum_before)
    if remaining <= Decimal("0"):
        db.execute(text("UPDATE fixed_assets SET status = 'fully_depreciated' WHERE id = :id"), {"id": asset_id})
        db.commit()
        return {"message": "El activo ya se encuentra totalmente depreciado."}
    
    amount = min(monthly_depr, remaining)
    accum_after = accum_before + amount
    book_value_after = cost - accum_after
    
    db.execute(
        text("""
            INSERT INTO asset_depreciation_lines (asset_id, fiscal_period_id, period_date, depreciation_amount, accumulated_before, accumulated_after, book_value_after)
            VALUES (:aid, :fpid, :pdate, :amount, :before, :after, :bv)
        """),
        {"aid": asset_id, "fpid": fiscal_period_id, "pdate": period_date, "amount": amount, "before": accum_before, "after": accum_after, "bv": book_value_after}
    )
    
    new_status = "fully_depreciated" if book_value_after <= salvage else "active"
    db.execute(
        text("UPDATE fixed_assets SET accumulated_depreciation = :accum, current_book_value = :bv, status = :st, updated_at = now() WHERE id = :id"),
        {"accum": accum_after, "bv": book_value_after, "st": new_status, "id": asset_id}
    )
    _audit(db, claims, "finance.fixed_asset.depreciated", asset["company_id"], "fixed_asset", str(asset_id))
    db.commit()
    return {"message": "Depreciación calculada exitosamente.", "depreciation_amount": str(amount), "new_book_value": str(book_value_after), "status": new_status}

@app.get("/api/v1/finance/fixed-assets/{asset_id}/depreciation-schedule", response_model=list[AssetDepreciationLineResponse], tags=["fixed-assets"])
def get_depreciation_schedule(asset_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    asset = db.execute(text("SELECT id, company_id FROM fixed_assets WHERE id = :id"), {"id": asset_id}).mappings().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Activo no encontrado.")
    require_company(claims, asset["company_id"])
    rows = db.execute(
        text("SELECT * FROM asset_depreciation_lines WHERE asset_id = :id ORDER BY period_date ASC"),
        {"id": asset_id}
    ).mappings().all()
    return [AssetDepreciationLineResponse(**dict(r)) for r in rows]


# ===========================================================================
# PAYMENT TERMS & WITHHOLDING TAXES
# ===========================================================================

@app.get("/api/v1/finance/payment-terms", response_model=list[PaymentTermResponse], tags=["payment-terms"])
def list_payment_terms(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT * FROM payment_terms WHERE company_id = :cid ORDER BY code ASC"), {"cid": company_id}).mappings().all()
    return [PaymentTermResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/payment-terms", response_model=PaymentTermResponse, status_code=201, tags=["payment-terms"])
def create_payment_term(payload: PaymentTermCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO payment_terms (company_id, code, name, days_net, days_discount, discount_rate, is_active)
                VALUES (:company_id, :code, :name, :days_net, :days_discount, :discount_rate, :is_active)
                RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.payment_term.created", payload.company_id, "payment_term", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Condición de pago duplicada o inválida.") from exc
    return PaymentTermResponse(**dict(row))

@app.get("/api/v1/finance/withholding-types", response_model=list[WithholdingTypeResponse], tags=["withholdings"])
def list_withholding_types(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT * FROM withholding_types WHERE company_id = :cid ORDER BY code ASC"), {"cid": company_id}).mappings().all()
    return [WithholdingTypeResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/withholding-types", response_model=WithholdingTypeResponse, status_code=201, tags=["withholdings"])
def create_withholding_type(payload: WithholdingTypeCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO withholding_types (company_id, code, name, rate, applies_to, withholding_account_id, is_active)
                VALUES (:company_id, :code, :name, :rate, :applies_to, :withholding_account_id, :is_active)
                RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.withholding_type.created", payload.company_id, "withholding_type", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tipo de retención duplicado o inválido.") from exc
    return WithholdingTypeResponse(**dict(row))


# ===========================================================================
# INVOICE SERIES
# ===========================================================================

@app.get("/api/v1/finance/invoice-series", response_model=list[InvoiceSeriesResponse], tags=["invoice-series"])
def list_invoice_series(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT * FROM invoice_series WHERE company_id = :cid ORDER BY document_type_code, series ASC"), {"cid": company_id}).mappings().all()
    return [InvoiceSeriesResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/invoice-series", response_model=InvoiceSeriesResponse, status_code=201, tags=["invoice-series"])
def create_invoice_series(payload: InvoiceSeriesCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO invoice_series (company_id, document_type_code, series, description, is_electronic, is_default, is_active)
                VALUES (:company_id, :document_type_code, :series, :description, :is_electronic, :is_default, :is_active)
                RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.invoice_series.created", payload.company_id, "invoice_series", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Serie de comprobante ya registrada.") from exc
    return InvoiceSeriesResponse(**dict(row))


# ===========================================================================
# LIBROS CONTABLES & REGISTROS SUNAT (PLE)
# ===========================================================================

@app.get("/api/v1/finance/registers/purchases", response_model=list[PurchaseRegisterEntryResponse], tags=["accounting-books"])
def list_purchase_register(company_id: UUID = Query(...), fiscal_period_id: Optional[UUID] = Query(None), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    q = "SELECT * FROM purchase_register_entries WHERE company_id = :cid"
    params = {"cid": company_id}
    if fiscal_period_id:
        q += " AND fiscal_period_id = :fpid"
        params["fpid"] = fiscal_period_id
    q += " ORDER BY issue_date ASC, series ASC, voucher_number ASC"
    rows = db.execute(text(q), params).mappings().all()
    return [PurchaseRegisterEntryResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/registers/purchases", response_model=PurchaseRegisterEntryResponse, status_code=201, tags=["accounting-books"])
def create_purchase_register_entry(payload: PurchaseRegisterEntryCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO purchase_register_entries (
                    company_id, fiscal_period_id, document_id, journal_entry_id, cuo, issue_date, due_date,
                    voucher_type, series, voucher_number, supplier_id_type, supplier_tax_id, supplier_name,
                    taxable_base, igv_amount, exempt_amount, unaffected_amount, isc_amount, icbper_amount,
                    other_taxes, total_amount, currency, exchange_rate, detraction_date, detraction_constancy,
                    retention_amount, operation_status
                ) VALUES (
                    :company_id, :fiscal_period_id, :document_id, :journal_entry_id, :cuo, :issue_date, :due_date,
                    :voucher_type, :series, :voucher_number, :supplier_id_type, :supplier_tax_id, :supplier_name,
                    :taxable_base, :igv_amount, :exempt_amount, :unaffected_amount, :isc_amount, :icbper_amount,
                    :other_taxes, :total_amount, :currency, :exchange_rate, :detraction_date, :detraction_constancy,
                    :retention_amount, :operation_status
                ) RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.purchase_register.created", payload.company_id, "purchase_register", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al registrar en Libro de Compras.") from exc
    return PurchaseRegisterEntryResponse(**dict(row))

@app.get("/api/v1/finance/registers/purchases/ple", tags=["accounting-books"])
def export_purchases_ple(company_id: UUID = Query(...), fiscal_period_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Genera archivo de texto estructurado según formato oficial PLE 8.1 / 8.2 SUNAT."""
    require_company(claims, company_id)
    company = db.execute(text("SELECT tax_id FROM companies WHERE id = :id"), {"id": company_id}).mappings().first()
    rows = db.execute(
        text("SELECT * FROM purchase_register_entries WHERE company_id = :cid AND fiscal_period_id = :fpid ORDER BY issue_date ASC"),
        {"cid": company_id, "fpid": fiscal_period_id}
    ).mappings().all()
    lines = []
    for r in rows:
        fields = [
            str(r["fiscal_period_id"] or ""),
            str(r["cuo"] or ""),
            f"M{r['cuo']}",
            str(r["issue_date"].strftime("%d/%m/%Y")),
            str(r["due_date"].strftime("%d/%m/%Y")) if r["due_date"] else "",
            str(r["voucher_type"] or "01"),
            str(r["series"] or ""),
            str(r["voucher_number"] or ""),
            "",
            str(r["supplier_id_type"] or "6"),
            str(r["supplier_tax_id"] or ""),
            str(r["supplier_name"] or ""),
            f"{r['taxable_base']:.2f}",
            f"{r['igv_amount']:.2f}",
            "0.00", "0.00", "0.00", "0.00",
            f"{r['exempt_amount']:.2f}",
            f"{r['unaffected_amount']:.2f}",
            f"{r['isc_amount']:.2f}",
            f"{r['icbper_amount']:.2f}",
            f"{r['other_taxes']:.2f}",
            f"{r['total_amount']:.2f}",
            str(r["currency"] or "PEN"),
            f"{r['exchange_rate']:.3f}",
            "", "", "", "",
            str(r["detraction_date"].strftime("%d/%m/%Y")) if r["detraction_date"] else "",
            str(r["detraction_constancy"] or ""),
            f"{r['retention_amount']:.2f}",
            str(r["operation_status"] or "1"),
        ]
        lines.append("|".join(fields) + "|")
    content = "\r\n".join(lines)
    filename = f"LE{company['tax_id'] or '20000000001'}080100001111.txt"
    return {"filename": filename, "content": content, "total_records": len(rows)}

@app.get("/api/v1/finance/registers/sales", response_model=list[SalesRegisterEntryResponse], tags=["accounting-books"])
def list_sales_register(company_id: UUID = Query(...), fiscal_period_id: Optional[UUID] = Query(None), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    q = "SELECT * FROM sales_register_entries WHERE company_id = :cid"
    params = {"cid": company_id}
    if fiscal_period_id:
        q += " AND fiscal_period_id = :fpid"
        params["fpid"] = fiscal_period_id
    q += " ORDER BY issue_date ASC, series ASC, voucher_number ASC"
    rows = db.execute(text(q), params).mappings().all()
    return [SalesRegisterEntryResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/registers/sales", response_model=SalesRegisterEntryResponse, status_code=201, tags=["accounting-books"])
def create_sales_register_entry(payload: SalesRegisterEntryCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(
            text("""
                INSERT INTO sales_register_entries (
                    company_id, fiscal_period_id, document_id, journal_entry_id, cuo, issue_date, due_date,
                    voucher_type, series, voucher_number, customer_id_type, customer_tax_id, customer_name,
                    export_amount, taxable_base, discount_base, igv_amount, discount_igv, exempt_amount,
                    unaffected_amount, isc_amount, icbper_amount, other_taxes, total_amount, currency,
                    exchange_rate, operation_status
                ) VALUES (
                    :company_id, :fiscal_period_id, :document_id, :journal_entry_id, :cuo, :issue_date, :due_date,
                    :voucher_type, :series, :voucher_number, :customer_id_type, :customer_tax_id, :customer_name,
                    :export_amount, :taxable_base, :discount_base, :igv_amount, :discount_igv, :exempt_amount,
                    :unaffected_amount, :isc_amount, :icbper_amount, :other_taxes, :total_amount, :currency,
                    :exchange_rate, :operation_status
                ) RETURNING *
            """),
            payload.model_dump()
        ).mappings().first()
        _audit(db, claims, "finance.sales_register.created", payload.company_id, "sales_register", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al registrar en Libro de Ventas.") from exc
    return SalesRegisterEntryResponse(**dict(row))

@app.get("/api/v1/finance/registers/sales/ple", tags=["accounting-books"])
def export_sales_ple(company_id: UUID = Query(...), fiscal_period_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Genera archivo de texto estructurado según formato oficial PLE 14.1 SUNAT."""
    require_company(claims, company_id)
    company = db.execute(text("SELECT tax_id FROM companies WHERE id = :id"), {"id": company_id}).mappings().first()
    rows = db.execute(
        text("SELECT * FROM sales_register_entries WHERE company_id = :cid AND fiscal_period_id = :fpid ORDER BY issue_date ASC"),
        {"cid": company_id, "fpid": fiscal_period_id}
    ).mappings().all()
    lines = []
    for r in rows:
        fields = [
            str(r["fiscal_period_id"] or ""),
            str(r["cuo"] or ""),
            f"M{r['cuo']}",
            str(r["issue_date"].strftime("%d/%m/%Y")),
            str(r["due_date"].strftime("%d/%m/%Y")) if r["due_date"] else "",
            str(r["voucher_type"] or "01"),
            str(r["series"] or ""),
            str(r["voucher_number"] or ""),
            "",
            str(r["customer_id_type"] or "6"),
            str(r["customer_tax_id"] or ""),
            str(r["customer_name"] or ""),
            f"{r['export_amount']:.2f}",
            f"{r['taxable_base']:.2f}",
            f"{r['discount_base']:.2f}",
            f"{r['igv_amount']:.2f}",
            f"{r['discount_igv']:.2f}",
            f"{r['exempt_amount']:.2f}",
            f"{r['unaffected_amount']:.2f}",
            f"{r['isc_amount']:.2f}",
            f"{r['icbper_amount']:.2f}",
            f"{r['other_taxes']:.2f}",
            f"{r['total_amount']:.2f}",
            str(r["currency"] or "PEN"),
            f"{r['exchange_rate']:.3f}",
            "", "", "", "", "",
            str(r["operation_status"] or "1"),
        ]
        lines.append("|".join(fields) + "|")
    content = "\r\n".join(lines)
    filename = f"LE{company['tax_id'] or '20000000001'}140100001111.txt"
    return {"filename": filename, "content": content, "total_records": len(rows)}

class WmsIntegrationInput(BaseModel):
    company_id: UUID
    integration_code: str = "WMS"
    external_base_url: str | None = None
    is_active: bool = True
    inventory_account_id: UUID | None = None
    offset_account_id: UUID | None = None
    expense_account_id: UUID | None = None
    valuation_method: str | None = None
    currency: str | None = None


class WmsSyncEventInput(BaseModel):
    external_event_id: str
    external_event_type: str
    external_document_id: str | None = None
    external_document_number: str | None = None
    occurred_at: datetime | None = None
    payload: dict = {}
    lines: list[dict] = []


@app.get("/api/v1/finance/wms/integration", tags=["wms-integration"])
def get_wms_integration(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    row = db.execute(text("""
        SELECT wi.id,wi.company_id,wi.integration_code,wi.external_base_url,wi.is_active,
          wi.inventory_account_id,ia.code AS inventory_account_code,ia.name AS inventory_account_name,
          wi.offset_account_id,oa.code AS offset_account_code,oa.name AS offset_account_name,
          wi.expense_account_id,ea.code AS expense_account_code,ea.name AS expense_account_name,
          wi.valuation_method,wi.currency,wi.created_at,wi.updated_at
        FROM wms_integrations wi
        LEFT JOIN accounts ia ON ia.id=wi.inventory_account_id
        LEFT JOIN accounts oa ON oa.id=wi.offset_account_id
        LEFT JOIN accounts ea ON ea.id=wi.expense_account_id
        WHERE wi.company_id=:company_id AND wi.integration_code='WMS'
    """), {"company_id": company_id}).mappings().first()
    events = db.execute(text("""
        SELECT status,COUNT(*) AS count FROM wms_sync_events
        WHERE company_id=:company_id GROUP BY status ORDER BY status
    """), {"company_id": company_id}).mappings().all()
    return {"integration": dict(row) if row else None, "event_counts": [dict(x) for x in events]}


@app.put("/api/v1/finance/wms/integration", tags=["wms-integration"])
def save_wms_integration(payload: WmsIntegrationInput, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    if payload.valuation_method and payload.valuation_method not in {"fifo", "weighted_average", "specific"}:
        raise HTTPException(status_code=422, detail="Método de valoración inválido.")
    if payload.currency and len(payload.currency) != 3:
        raise HTTPException(status_code=422, detail="La moneda debe tener tres caracteres ISO.")
    account_ids = {x for x in (payload.inventory_account_id, payload.offset_account_id, payload.expense_account_id) if x}
    if account_ids:
        rows = db.execute(text("SELECT id,account_type,account_subtype,is_active,allow_posting,is_group FROM accounts WHERE company_id=:c AND id=ANY(CAST(:ids AS uuid[]))"), {"c": payload.company_id, "ids": list(account_ids)}).mappings().all()
        by_id = {r["id"]: r for r in rows}
        if len(by_id) != len(account_ids) or any(not r["is_active"] or not r["allow_posting"] or r["is_group"] for r in by_id.values()):
            raise HTTPException(status_code=422, detail="Todas las cuentas de integración deben ser cuentas imputables activas de esta empresa.")
        if payload.inventory_account_id and by_id[payload.inventory_account_id]["account_type"] != "asset":
            raise HTTPException(status_code=422, detail="La cuenta de inventario debe ser de activo.")
        if payload.expense_account_id and by_id[payload.expense_account_id]["account_type"] != "expense":
            raise HTTPException(status_code=422, detail="La cuenta de variación/costo debe ser de gasto.")
    existing = db.execute(text("SELECT id FROM wms_integrations WHERE company_id=:c AND integration_code='WMS'"), {"c": payload.company_id}).scalar_one_or_none()
    params = payload.model_dump()
    if existing:
        row = db.execute(text("""
            UPDATE wms_integrations SET external_base_url=:external_base_url,is_active=:is_active,
              inventory_account_id=:inventory_account_id,offset_account_id=:offset_account_id,
              expense_account_id=:expense_account_id,valuation_method=:valuation_method,currency=:currency,updated_at=now()
            WHERE id=:id RETURNING id,company_id,integration_code,external_base_url,is_active,
              inventory_account_id,offset_account_id,expense_account_id,valuation_method,currency,created_at,updated_at
        """), {**params, "id": existing}).mappings().first()
        event = "finance.wms.integration.updated"
    else:
        row = db.execute(text("""
            INSERT INTO wms_integrations(company_id,integration_code,external_base_url,is_active,
              inventory_account_id,offset_account_id,expense_account_id,valuation_method,currency)
            VALUES(:company_id,'WMS',:external_base_url,:is_active,:inventory_account_id,
              :offset_account_id,:expense_account_id,:valuation_method,:currency)
            RETURNING id,company_id,integration_code,external_base_url,is_active,
              inventory_account_id,offset_account_id,expense_account_id,valuation_method,currency,created_at,updated_at
        """), params).mappings().first()
        event = "finance.wms.integration.created"
    _audit(db, claims, event, payload.company_id, "wms_integration", str(row["id"]))
    db.commit()
    return dict(row)


@app.get("/api/v1/finance/wms/events", tags=["wms-integration"])
def list_wms_sync_events(company_id: UUID, status_filter: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    sql = """SELECT e.id,e.external_event_id,e.external_event_type,e.external_document_id,e.external_document_number,
      e.occurred_at,e.status,e.block_reason,e.journal_entry_id,e.received_at,e.processed_at,
      (SELECT COUNT(*) FROM wms_sync_event_lines l WHERE l.event_id=e.id) AS line_count
      FROM wms_sync_events e WHERE e.company_id=:company_id"""
    params: dict = {"company_id": company_id, "limit": limit}
    if status_filter:
        sql += " AND e.status=:status_filter"
        params["status_filter"] = status_filter
    sql += " ORDER BY e.received_at DESC LIMIT :limit"
    return [dict(row) for row in db.execute(text(sql), params).mappings().all()]


@app.post("/api/v1/finance/wms/integration/{integration_id}/events", status_code=202, tags=["wms-integration"])
def receive_wms_event(integration_id: UUID, payload: WmsSyncEventInput, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Store WMS events idempotently. This endpoint deliberately never posts accounting entries."""
    integration = db.execute(text("SELECT * FROM wms_integrations WHERE id=:id"), {"id": integration_id}).mappings().first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integración WMS no encontrada.")
    require_company(claims, integration["company_id"])
    if not integration["is_active"]:
        raise HTTPException(status_code=409, detail="La integración WMS está desactivada.")
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    existing = db.execute(text("SELECT id,payload_hash,status,journal_entry_id FROM wms_sync_events WHERE integration_id=:integration_id AND external_event_id=:external_event_id"), {"integration_id": integration_id, "external_event_id": payload.external_event_id}).mappings().first()
    if existing:
        if existing["payload_hash"] != digest:
            raise HTTPException(status_code=409, detail="El ID externo ya existe con un payload diferente; no se sobrescribió el evento.")
        return {"id": existing["id"], "status": existing["status"], "journal_entry_id": existing["journal_entry_id"], "duplicate": True}
    ready = bool(integration["inventory_account_id"] and integration["offset_account_id"] and integration["valuation_method"] and integration["currency"])
    block_reason = None if ready else "Falta configurar cuentas de inventario/contrapartida, método de valoración o moneda; requiere revisión antes de contabilizar."
    try:
        row = db.execute(text("""
            INSERT INTO wms_sync_events(integration_id,company_id,external_event_id,external_event_type,
              external_document_id,external_document_number,occurred_at,payload,payload_hash,status,block_reason)
            VALUES(:integration_id,:company_id,:external_event_id,:external_event_type,
              :external_document_id,:external_document_number,:occurred_at,CAST(:payload AS jsonb),:payload_hash,:status,:block_reason)
            RETURNING id,status,block_reason
        """), {"integration_id": integration_id, "company_id": integration["company_id"], "external_event_id": payload.external_event_id, "external_event_type": payload.external_event_type, "external_document_id": payload.external_document_id, "external_document_number": payload.external_document_number, "occurred_at": payload.occurred_at, "payload": serialized, "payload_hash": digest, "status": "preview" if ready else "blocked", "block_reason": block_reason}).mappings().first()
        for line in payload.lines:
            db.execute(text("""
                INSERT INTO wms_sync_event_lines(event_id,external_line_id,external_material_id,material_code,material_description,quantity,unit_of_measure,unit_cost,currency,external_warehouse_id,external_location_id,external_lot_id,metadata)
                VALUES(:event_id,:external_line_id,:external_material_id,:material_code,:material_description,:quantity,:unit_of_measure,:unit_cost,:currency,:external_warehouse_id,:external_location_id,:external_lot_id,CAST(:metadata AS jsonb))
            """), {"event_id": row["id"], "external_line_id": line.get("external_line_id"), "external_material_id": line.get("external_material_id"), "material_code": line.get("material_code"), "material_description": line.get("material_description"), "quantity": line.get("quantity"), "unit_of_measure": line.get("unit_of_measure"), "unit_cost": line.get("unit_cost"), "currency": line.get("currency"), "external_warehouse_id": line.get("external_warehouse_id"), "external_location_id": line.get("external_location_id"), "external_lot_id": line.get("external_lot_id"), "metadata": json.dumps(line.get("metadata") or {}, ensure_ascii=False)} )
        _audit(db, claims, "finance.wms.event.received", integration["company_id"], "wms_sync_event", str(row["id"]), {"external_event_id": payload.external_event_id, "status": row["status"], "payload_hash": digest})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo guardar el evento WMS; no se contabilizó ningún asiento.") from exc
    return {"id": row["id"], "status": row["status"], "block_reason": row["block_reason"], "duplicate": False, "accounting_posted": False}


@app.get("/api/v1/finance/reports/journal-book", tags=["accounting-books"])
def get_journal_book(company_id: UUID = Query(...), start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Libro Diario en formato oficial 5.1 PCGE con desglose de asientos y cuentas."""
    require_company(claims, company_id)
    rows = db.execute(
        text("""
            SELECT 
                je.id AS entry_id, je.entry_number, je.entry_date, je.description AS entry_description, je.status,
                jl.id AS line_id, jl.line_number, jl.account_id, a.code AS account_code, a.name AS account_name,
                jl.debit_amount AS debit, jl.credit_amount AS credit, jl.description AS line_description,
                cc.code AS cost_center_code, cc.name AS cost_center_name,
                p.code AS project_code,
                aux.tax_id AS auxiliary_tax_id, aux.name AS auxiliary_name
            FROM journal_entries je
            JOIN journal_entry_lines jl ON jl.journal_entry_id = je.id
            JOIN accounts a ON a.id = jl.account_id
            LEFT JOIN cost_centers cc ON cc.id = jl.cost_center_id
            LEFT JOIN projects p ON p.id = jl.project_id
            LEFT JOIN finance_auxiliaries aux ON aux.id = jl.auxiliary_id
            WHERE je.company_id = :cid AND je.entry_date BETWEEN :sdate AND :edate AND je.status = 'posted'
            ORDER BY je.entry_date ASC, je.entry_number ASC, jl.line_number ASC
        """),
        {"cid": company_id, "sdate": start_date, "edate": end_date}
    ).mappings().all()
    
    total_debit = sum(Decimal(str(r["debit"])) for r in rows)
    total_credit = sum(Decimal(str(r["credit"])) for r in rows)
    
    return {
        "company_id": company_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "is_balanced": abs(total_debit - total_credit) < Decimal("0.01"),
        "lines": [dict(r) for r in rows]
    }

@app.get("/api/v1/finance/registers/cash-book", tags=["accounting-books"])
def get_cash_book(company_id: UUID = Query(...), start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Libro Caja y Bancos (Libro 1.1 y 1.2 SUNAT) con movimientos de efectivo y cuentas corrientes."""
    require_company(claims, company_id)
    rows = db.execute(
        text("""
            SELECT 
                je.entry_date, je.entry_number, a.code AS account_code, a.name AS account_name,
                jl.debit_amount AS debit, jl.credit_amount AS credit, jl.description,
                fba.bank_name, fba.account_number,
                aux.tax_id AS auxiliary_tax_id, aux.name AS auxiliary_name
            FROM journal_entry_lines jl
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            JOIN accounts a ON a.id = jl.account_id
            LEFT JOIN finance_bank_accounts fba ON fba.account_id = a.id
            LEFT JOIN finance_auxiliaries aux ON aux.id = jl.auxiliary_id
            WHERE je.company_id = :cid AND je.entry_date BETWEEN :sdate AND :edate AND je.status = 'posted'
              AND (a.account_subtype IN ('cash', 'bank') OR a.code LIKE '10%')
            ORDER BY je.entry_date ASC, je.entry_number ASC
        """),
        {"cid": company_id, "sdate": start_date, "edate": end_date}
    ).mappings().all()
    
    inflows = sum(Decimal(str(r["debit"])) for r in rows)
    outflows = sum(Decimal(str(r["credit"])) for r in rows)
    net_flow = inflows - outflows
    
    return {
        "company_id": company_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_inflows": str(inflows),
        "total_outflows": str(outflows),
        "net_flow": str(net_flow),
        "movements": [dict(r) for r in rows]
    }

@app.get("/api/v1/finance/registers/purchase-journal", tags=["accounting-books"])
def get_purchase_journal(company_id: UUID = Query(...), start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Registro de Compras (Libro 2.1 SUNAT) con detalle de proveedores, impuestos y saldo."""
    require_company(claims, company_id)
    rows = db.execute(text("""
        SELECT acj.journal_date, je.entry_number, a.code AS account_code, a.name AS account_name,
               acj.debit_amount, acj.credit_amount, acj.description,
               fa.code AS auxiliary_code, fa.name AS auxiliary_name, fa.tax_id AS auxiliary_tax_id
        FROM accounting_purchase_journal acj
        JOIN journal_entries je ON je.id = acj.journal_entry_id
        JOIN accounts a ON a.id = acj.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id = acj.auxiliary_id
        WHERE acj.company_id = :cid AND acj.journal_date BETWEEN :sdate AND :edate
        ORDER BY acj.journal_date ASC, je.entry_number ASC
    """), {"cid": company_id, "sdate": start_date, "edate": end_date}).mappings().all()
    total_debit = sum(Decimal(str(r["debit_amount"])) for r in rows)
    total_credit = sum(Decimal(str(r["credit_amount"])) for r in rows)
    net = total_debit - total_credit
    return {
        "company_id": company_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "net": str(net),
        "movements": [dict(r) for r in rows]
    }

@app.get("/api/v1/finance/registers/sales-journal", tags=["accounting-books"])
def get_sales_journal(company_id: UUID = Query(...), start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Registro de Ventas (Libro 3.1 SUNAT) con detalle de clientes, impuestos y saldo."""
    require_company(claims, company_id)
    rows = db.execute(text("""
        SELECT asj.journal_date, je.entry_number, a.code AS account_code, a.name AS account_name,
               asj.debit_amount, asj.credit_amount, asj.description,
               fa.code AS auxiliary_code, fa.name AS auxiliary_name, fa.tax_id AS auxiliary_tax_id
        FROM accounting_sales_journal asj
        JOIN journal_entries je ON je.id = asj.journal_entry_id
        JOIN accounts a ON a.id = asj.account_id
        LEFT JOIN finance_auxiliaries fa ON fa.id = asj.auxiliary_id
        WHERE asj.company_id = :cid AND asj.journal_date BETWEEN :sdate AND :edate
        ORDER BY asj.journal_date ASC, je.entry_number ASC
    """), {"cid": company_id, "sdate": start_date, "edate": end_date}).mappings().all()
    total_debit = sum(Decimal(str(r["debit_amount"])) for r in rows)
    total_credit = sum(Decimal(str(r["credit_amount"])) for r in rows)
    net = total_credit - total_debit  # Sales are credit-oriented
    return {
        "company_id": company_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_debit": str(total_debit),
        "total_credit": str(total_credit),
        "net": str(net),
        "movements": [dict(r) for r in rows]
    }

@app.get("/api/v1/finance/registers/bank-reconciliation", tags=["accounting-books"])
def get_bank_reconciliation(company_id: UUID = Query(...), bank_account_id: UUID | None = Query(None), start_date: date = Query(...), end_date: date = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Conciliación Bancaria con movimientos del libro de bancos vs extractos bancarios."""
    require_company(claims, company_id)
    conditions = ["acj.company_id = :cid", "acj.journal_date BETWEEN :sdate AND :edate"]
    params = {"cid": company_id, "sdate": start_date, "edate": end_date}
    if bank_account_id:
        conditions.append("fba.id = :bacc")
        params["bacc"] = bank_account_id
    rows = db.execute(text(f"""
        SELECT acj.journal_date, je.entry_number, fba.bank_name, fba.account_number,
               acj.amount AS ledger_amount, acj.direction AS ledger_direction, acj.description AS ledger_desc,
               fbsl.transaction_date AS statement_date, fbsl.amount AS statement_amount, fbsl.description AS statement_desc,
               CASE WHEN fbsl.id IS NOT NULL THEN TRUE ELSE FALSE END AS has_statement
        FROM accounting_cash_book acj
        JOIN journal_entries je ON je.id = acj.journal_entry_id
        LEFT JOIN finance_bank_accounts fba ON fba.account_id = acj.account_id
        LEFT JOIN finance_bank_statement_lines fbsl ON fbsl.journal_entry_id = acj.journal_entry_id
        WHERE {' AND '.join(conditions)}
        ORDER BY acj.journal_date ASC, je.entry_number ASC
    """), params).mappings().all()
    return {
        "company_id": company_id,
        "bank_account_id": bank_account_id,
        "start_date": start_date,
        "end_date": end_date,
        "reconciliation_items": [dict(r) for r in rows]
    }

@app.post("/api/v1/finance/fiscal-years/{fiscal_year_id}/close", tags=["accounting-books"])
def execute_fiscal_year_closing(fiscal_year_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    """Genera asientos de cierre anual del ejercicio contable (cancelación de resultados y cierre de balance)."""
    fy = db.execute(text("SELECT id, company_id, name, start_date, end_date, is_closed FROM fiscal_years WHERE id = :id"), {"id": fiscal_year_id}).mappings().first()
    if not fy:
        raise HTTPException(status_code=404, detail="Ejercicio fiscal no encontrado.")
    require_company(claims, fy["company_id"])
    if fy["is_closed"]:
        raise HTTPException(status_code=400, detail="El ejercicio fiscal ya está cerrado.")
    
    res_rows = db.execute(
        text("""
            SELECT a.id, a.code, a.name, a.account_type,
                   COALESCE(SUM(jl.debit), 0) AS total_debit,
                   COALESCE(SUM(jl.credit), 0) AS total_credit
            FROM accounts a
            JOIN journal_entry_lines jl ON jl.account_id = a.id
            JOIN journal_entries je ON je.id = jl.journal_entry_id
            WHERE je.company_id = :cid AND je.fiscal_year_id = :fyid AND je.status = 'posted'
              AND a.account_type IN ('revenue', 'expense')
            GROUP BY a.id, a.code, a.name, a.account_type
        """),
        {"cid": fy["company_id"], "fyid": fiscal_year_id}
    ).mappings().all()
    
    close_log = db.execute(
        text("""
            INSERT INTO closing_entries (company_id, fiscal_year_id, step_number, step_name, notes)
            VALUES (:cid, :fyid, 1, 'Cancelación de Cuentas de Resultados y Determinación de Ejercicio', :notes)
            RETURNING *
        """),
        {"cid": fy["company_id"], "fyid": fiscal_year_id, "notes": f"Proceso ejecutado con {len(res_rows)} cuentas de gestión analizadas."}
    ).mappings().first()
    
    db.execute(text("UPDATE fiscal_years SET is_closed = TRUE, closed_at = now(), updated_at = now() WHERE id = :id"), {"id": fiscal_year_id})
    _audit(db, claims, "finance.fiscal_year.closed", fy["company_id"], "fiscal_year", str(fiscal_year_id))
    db.commit()
    
    return {"message": "Cierre de ejercicio fiscal ejecutado con éxito.", "closing_entry_id": str(close_log["id"]), "fiscal_year": fy["name"]}
# ---------------------------------------------------------------------------
# Budget control: CDP, Commitments, Payment Orders
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/budget-cdp", response_model=list[BudgetCDPResponse], tags=["budgets"])
def list_budget_cdp(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT id, company_id, number, cdp_date, line_text, requester_area, amount, status, created_at, updated_at FROM budget_cdp WHERE company_id=:c ORDER BY cdp_date DESC, created_at DESC"), {"c": company_id}).mappings().all()
    return [BudgetCDPResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/budget-cdp", response_model=BudgetCDPResponse, status_code=201, tags=["budgets"])
def create_budget_cdp(payload: BudgetCDPCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    bud_count = db.execute(text("SELECT COUNT(*) FROM budgets WHERE company_id = :cid"), {"cid": payload.company_id}).scalar_one()
    if bud_count == 0:
        raise HTTPException(status_code=409, detail="No se puede crear CDP: debe crear primero un Presupuesto/Apropiación inicial.")
    try:
        row = db.execute(text("""
            INSERT INTO budget_cdp (company_id, number, cdp_date, line_text, requester_area, amount, status)
            VALUES (:company_id, :number, :cdp_date, :line_text, :requester_area, :amount, :status)
            RETURNING id, company_id, number, cdp_date, line_text, requester_area, amount, status, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        _audit(db, claims, "finance.budget_cdp.created", payload.company_id, "budget_cdp", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al crear CDP.") from exc
    return BudgetCDPResponse(**dict(row))


@app.patch("/api/v1/finance/budget-cdp/{cdp_id}", response_model=BudgetCDPResponse, tags=["budgets"])
def patch_budget_cdp(cdp_id: UUID, payload: dict, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT * FROM budget_cdp WHERE id=:id"), {"id": cdp_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="CDP no encontrado.")
    require_company(claims, row["company_id"])
    allowed = {"number", "cdp_date", "line_text", "requester_area", "amount", "status"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="Sin cambios válidos.")
    set_parts = ", ".join([f"{k}=:{k}" for k in updates.keys()])
    updates["id"] = cdp_id
    try:
        row2 = db.execute(text(f"UPDATE budget_cdp SET {set_parts}, updated_at=now() WHERE id=:id RETURNING id, company_id, number, cdp_date, line_text, requester_area, amount, status, created_at, updated_at"), updates).mappings().first()
        _audit(db, claims, "finance.budget_cdp.updated", row["company_id"], "budget_cdp", str(cdp_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el CDP.") from exc
    return BudgetCDPResponse(**dict(row2))


@app.delete("/api/v1/finance/budget-cdp/{cdp_id}", status_code=204, tags=["budgets"])
def delete_budget_cdp(cdp_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM budget_cdp WHERE id=:id"), {"id": cdp_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="CDP no encontrado.")
    require_company(claims, row["company_id"])
    has = db.execute(text("SELECT 1 FROM budget_commitments WHERE cdp_id=:id LIMIT 1"), {"id": cdp_id}).first()
    if has:
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene compromisos asociados.")
    try:
        db.execute(text("DELETE FROM budget_cdp WHERE id=:id"), {"id": cdp_id})
        _audit(db, claims, "finance.budget_cdp.deleted", row["company_id"], "budget_cdp", str(cdp_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el CDP.") from exc
    return None

@app.get("/api/v1/finance/budget-commitments", response_model=list[BudgetCommitmentResponse], tags=["budgets"])
def list_budget_commitments(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT id, company_id, number, commitment_date, reference, amount, status, cdp_id, supplier_id, created_at, updated_at FROM budget_commitments WHERE company_id=:c ORDER BY commitment_date DESC"), {"c": company_id}).mappings().all()
    return [BudgetCommitmentResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/budget-commitments", response_model=BudgetCommitmentResponse, status_code=201, tags=["budgets"])
def create_budget_commitment(payload: BudgetCommitmentCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    bud_count = db.execute(text("SELECT COUNT(*) FROM budgets WHERE company_id = :cid"), {"cid": payload.company_id}).scalar_one()
    if bud_count == 0:
        raise HTTPException(status_code=409, detail="No se puede crear compromisos: debe crear primero un Presupuesto/Apropiación inicial.")
    if payload.cdp_id:
        cdp = db.execute(text("SELECT id, amount FROM budget_cdp WHERE id = :id AND company_id = :cid"), {"id": payload.cdp_id, "cid": payload.company_id}).mappings().first()
        if not cdp:
            raise HTTPException(status_code=404, detail="CDP no encontrado para esta empresa.")
        committed = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM budget_commitments WHERE cdp_id = :id AND status != 'anulado'"), {"id": payload.cdp_id}).scalar_one()
        if Decimal(str(committed)) + Decimal(str(payload.amount)) > Decimal(str(cdp["amount"])):
            raise HTTPException(status_code=409, detail=f"Saldo insuficiente en CDP: comprometido {committed}, disponible {Decimal(str(cdp['amount'])) - Decimal(str(committed))}.")
    try:
        row = db.execute(text("""
            INSERT INTO budget_commitments (company_id, number, commitment_date, reference, amount, status, cdp_id, supplier_id)
            VALUES (:company_id, :number, :commitment_date, :reference, :amount, :status, :cdp_id, :supplier_id)
            RETURNING id, company_id, number, commitment_date, reference, amount, status, cdp_id, supplier_id, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        _audit(db, claims, "finance.budget_commitment.created", payload.company_id, "budget_commitment", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al crear compromiso.") from exc
    return BudgetCommitmentResponse(**dict(row))


@app.patch("/api/v1/finance/budget-commitments/{commitment_id}", response_model=BudgetCommitmentResponse, tags=["budgets"])
def patch_budget_commitment(commitment_id: UUID, payload: dict, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT * FROM budget_commitments WHERE id=:id"), {"id": commitment_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado.")
    require_company(claims, row["company_id"])
    allowed = {"status", "reference", "amount", "supplier_id", "commitment_date"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="Sin cambios válidos.")
    old_status = row["status"]
    new_status = updates.get("status", old_status)
    if "amount" in updates or "status" in updates:
        cdp_id = row["cdp_id"]
        new_amount = Decimal(str(updates.get("amount", row["amount"])))
        if cdp_id and new_status != "anulado":
            cdp = db.execute(text("SELECT amount FROM budget_cdp WHERE id=:id"), {"id": cdp_id}).mappings().first()
            if cdp:
                committed = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM budget_commitments WHERE cdp_id=:id AND status!='anulado' AND id!=:cid"), {"id": cdp_id, "cid": commitment_id}).scalar_one()
                if Decimal(str(committed)) + new_amount > Decimal(str(cdp["amount"])):
                    raise HTTPException(status_code=409, detail="Saldo insuficiente en CDP para este monto.")
    set_parts = ", ".join([f"{k}=:{k}" for k in updates.keys()])
    updates["id"] = commitment_id
    try:
        row2 = db.execute(text(f"UPDATE budget_commitments SET {set_parts}, updated_at=now() WHERE id=:id RETURNING id, company_id, number, commitment_date, reference, amount, status, cdp_id, supplier_id, created_at, updated_at"), updates).mappings().first()
        _audit(db, claims, "finance.budget_commitment.updated", row["company_id"], "budget_commitment", str(commitment_id))
        # Auto journal entry on accrual: devengado
        if old_status != "devengado" and new_status == "devengado":
            # find open fiscal year/period for commitment date
            cdate = row2["commitment_date"]
            fy = db.execute(text("SELECT id, is_closed FROM fiscal_years WHERE company_id=:cid AND start_date<=:d AND end_date>=:d LIMIT 1"), {"cid": row["company_id"], "d": cdate}).mappings().first()
            if fy and not fy["is_closed"]:
                period = db.execute(text("SELECT id, is_closed FROM fiscal_periods WHERE fiscal_year_id=:fy AND start_date<=:d AND end_date>=:d LIMIT 1"), {"fy": fy["id"], "d": cdate}).mappings().first()
                if period and not period["is_closed"]:
                    # find expense account from config (env) or default '63'
                    expense_code = os.getenv("BUDGET_DEVENGO_EXPENSE_ACCOUNT_CODE", "63")
                    payable_code = os.getenv("BUDGET_DEVENGO_PAYABLE_ACCOUNT_CODE", "4212")
                    exp = db.execute(text("SELECT id FROM accounts WHERE company_id=:cid AND code LIKE :code AND is_active AND allow_posting AND NOT is_group ORDER BY code LIMIT 1"), {"cid": row["company_id"], "code": f"{expense_code}%"}).mappings().first()
                    pay = db.execute(text("SELECT id FROM accounts WHERE company_id=:cid AND code LIKE :code AND is_active AND allow_posting AND NOT is_group ORDER BY code LIMIT 1"), {"cid": row["company_id"], "code": f"{payable_code}%"}).mappings().first()
                    if exp and pay:
                        entry_no = f"DEV-{cdate:%Y%m%d}-{str(uuid4())[:6].upper()}"
                        amt = Decimal(str(row2["amount"]))
                        entry = db.execute(text("""
                            INSERT INTO journal_entries (company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description, currency, exchange_rate, total_debit, total_credit, created_by, status)
                            VALUES (:cid, :fy, :period, :eno, :edate, :ref, :desc, 'PEN', 1, :amt, :amt, :actor, 'draft')
                            RETURNING id
                        """), {"cid": row["company_id"], "fy": fy["id"], "period": period["id"], "eno": entry_no, "edate": cdate, "ref": row2["number"], "desc": f"Devengo compromiso {row2['number']}", "amt": amt, "actor": claims.get("sub")}).scalar_one()
                        db.execute(text("INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount) VALUES (:jid,:acc,:aux,1,:d,:debit,0)"), {"jid": entry, "acc": exp["id"], "aux": row2["supplier_id"], "d": "Devengo gasto/servicio", "debit": amt})
                        db.execute(text("INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount) VALUES (:jid,:acc,:aux,2,:d,0,:credit)"), {"jid": entry, "acc": pay["id"], "aux": row2["supplier_id"], "d": "Cuenta por pagar", "credit": amt})
                        _audit(db, claims, "finance.journal_entry.auto_created_from_commitment", row["company_id"], "journal_entry", str(entry))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el compromiso.") from exc
    return BudgetCommitmentResponse(**dict(row2))


@app.delete("/api/v1/finance/budget-commitments/{commitment_id}", status_code=204, tags=["budgets"])
def delete_budget_commitment(commitment_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM budget_commitments WHERE id=:id"), {"id": commitment_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Compromiso no encontrado.")
    require_company(claims, row["company_id"])
    has_po = db.execute(text("SELECT 1 FROM payment_orders WHERE commitment_id=:id LIMIT 1"), {"id": commitment_id}).first()
    if has_po:
        raise HTTPException(status_code=409, detail="No se puede eliminar: tiene órdenes de pago asociadas.")
    try:
        db.execute(text("DELETE FROM budget_commitments WHERE id=:id"), {"id": commitment_id})
        _audit(db, claims, "finance.budget_commitment.deleted", row["company_id"], "budget_commitment", str(commitment_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el compromiso.") from exc
    return None

@app.get("/api/v1/finance/payment-orders", response_model=list[PaymentOrderResponse], tags=["budgets"])
def list_payment_orders(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT id, company_id, number, order_date, payee, amount, status, commitment_id, supplier_id, bank_account_id, created_at, updated_at FROM payment_orders WHERE company_id=:c ORDER BY order_date DESC"), {"c": company_id}).mappings().all()
    return [PaymentOrderResponse(**dict(r)) for r in rows]

@app.post("/api/v1/finance/payment-orders", response_model=PaymentOrderResponse, status_code=201, tags=["budgets"])
def create_payment_order(payload: PaymentOrderCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(text("""
            INSERT INTO payment_orders (company_id, number, order_date, payee, amount, status, commitment_id, supplier_id, bank_account_id)
            VALUES (:company_id, :number, :order_date, :payee, :amount, :status, :commitment_id, :supplier_id, :bank_account_id)
            RETURNING id, company_id, number, order_date, payee, amount, status, commitment_id, supplier_id, bank_account_id, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        _audit(db, claims, "finance.payment_order.created", payload.company_id, "payment_order", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Error al crear orden de pago.") from exc
    return PaymentOrderResponse(**dict(row))


@app.patch("/api/v1/finance/payment-orders/{order_id}", response_model=PaymentOrderResponse, tags=["budgets"])
def patch_payment_order(order_id: UUID, payload: dict, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT * FROM payment_orders WHERE id=:id"), {"id": order_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
    require_company(claims, row["company_id"])
    allowed = {"number", "order_date", "payee", "amount", "status", "commitment_id", "supplier_id", "bank_account_id"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="Sin cambios válidos.")
    old_status = row["status"]
    new_status = updates.get("status", old_status)
    if old_status not in ("pagado", "paid") and new_status in ("pagado", "paid"):
        final_bank = updates.get("bank_account_id")
        if final_bank is None:
            final_bank = row.get("bank_account_id")
        final_commit = updates.get("commitment_id")
        if final_commit is None:
            final_commit = row.get("commitment_id")
        if not final_bank or not final_commit:
            raise HTTPException(status_code=409, detail="Para marcar como pagada la orden debe tener cuenta bancaria y compromiso vinculados.")
    set_parts = ", ".join([f"{k}=:{k}" for k in updates.keys()])
    updates["id"] = order_id
    try:
        row2 = db.execute(text(f"UPDATE payment_orders SET {set_parts}, updated_at=now() WHERE id=:id RETURNING id, company_id, number, order_date, payee, amount, status, commitment_id, supplier_id, bank_account_id, created_at, updated_at"), updates).mappings().first()
        _audit(db, claims, "finance.payment_order.updated", row["company_id"], "payment_order", str(order_id))
        # Auto journal entry on payment: status -> pagado/paid
        if old_status not in ("pagado", "paid") and new_status in ("pagado", "paid"):
            bank_account_id = row2["bank_account_id"]
            commitment_id = row2["commitment_id"]
            if bank_account_id and commitment_id:
                cdate = row2["order_date"]
                fy = db.execute(text("SELECT id, is_closed FROM fiscal_years WHERE company_id=:cid AND start_date<=:d AND end_date>=:d LIMIT 1"), {"cid": row["company_id"], "d": cdate}).mappings().first()
                if fy and not fy["is_closed"]:
                    period = db.execute(text("SELECT id, is_closed FROM fiscal_periods WHERE fiscal_year_id=:fy AND start_date<=:d AND end_date>=:d LIMIT 1"), {"fy": fy["id"], "d": cdate}).mappings().first()
                    if period and not period["is_closed"]:
                        # bank account -> cash/bank account
                        ba = db.execute(text("SELECT account_id FROM finance_bank_accounts WHERE id=:id AND company_id=:cid"), {"id": bank_account_id, "cid": row["company_id"]}).mappings().first()
                        # payable 4212
                        payable_code = os.getenv("BUDGET_DEVENGO_PAYABLE_ACCOUNT_CODE", "4212")
                        pay_acc = db.execute(text("SELECT id FROM accounts WHERE company_id=:cid AND code LIKE :code AND is_active AND allow_posting AND NOT is_group ORDER BY code LIMIT 1"), {"cid": row["company_id"], "code": f"{payable_code}%"}).mappings().first()
                        # get commitment supplier
                        com = db.execute(text("SELECT supplier_id FROM budget_commitments WHERE id=:id"), {"id": commitment_id}).mappings().first()
                        supplier_id = com["supplier_id"] if com else row2.get("supplier_id")
                        if ba and pay_acc:
                            entry_no = f"PAGO-{cdate:%Y%m%d}-{str(uuid4())[:6].upper()}"
                            amt = Decimal(str(row2["amount"]))
                            entry = db.execute(text("""
                                INSERT INTO journal_entries (company_id, fiscal_year_id, fiscal_period_id, entry_number, entry_date, reference, description, currency, exchange_rate, total_debit, total_credit, created_by, status)
                                VALUES (:cid, :fy, :period, :eno, :edate, :ref, :desc, 'PEN', 1, :amt, :amt, :actor, 'draft')
                                RETURNING id
                            """), {"cid": row["company_id"], "fy": fy["id"], "period": period["id"], "eno": entry_no, "edate": cdate, "ref": row2["number"], "desc": f"Pago orden {row2['number']}", "amt": amt, "actor": claims.get("sub")}).scalar_one()
                            db.execute(text("INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount) VALUES (:jid,:acc,:aux,1,:d,:debit,0)"), {"jid": entry, "acc": pay_acc["id"], "aux": supplier_id, "d": "Pago a proveedor", "debit": amt})
                            db.execute(text("INSERT INTO journal_entry_lines (journal_entry_id, account_id, auxiliary_id, line_number, description, debit_amount, credit_amount) VALUES (:jid,:acc,:aux,2,:d,0,:credit)"), {"jid": entry, "acc": ba["account_id"], "aux": None, "d": "Salida caja/banco", "credit": amt})
                            _audit(db, claims, "finance.journal_entry.auto_created_from_payment_order", row["company_id"], "journal_entry", str(entry))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar la orden de pago.") from exc
    return PaymentOrderResponse(**dict(row2))


@app.delete("/api/v1/finance/payment-orders/{order_id}", status_code=204, tags=["budgets"])
def delete_payment_order(order_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    row = db.execute(text("SELECT company_id FROM payment_orders WHERE id=:id"), {"id": order_id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Orden de pago no encontrada.")
    require_company(claims, row["company_id"])
    try:
        db.execute(text("DELETE FROM payment_orders WHERE id=:id"), {"id": order_id})
        _audit(db, claims, "finance.payment_order.deleted", row["company_id"], "payment_order", str(order_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar la orden de pago.") from exc
    return None


# ---------------------------------------------------------------------------
# Budget transfers (traslados entre áreas)
# ---------------------------------------------------------------------------
@app.get("/api/v1/finance/budget-transfers", response_model=list[BudgetTransferResponse], tags=["budgets"])
def list_budget_transfers(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT id, company_id, original_cdp_id, original_cdp_number, from_area, to_area, amount, new_partida, new_account_code, notes, created_at, updated_at FROM budget_transfers WHERE company_id=:c ORDER BY created_at DESC"), {"c": company_id}).mappings().all()
    return [BudgetTransferResponse(**dict(r)) for r in rows]


@app.post("/api/v1/finance/budget-transfers", response_model=BudgetTransferResponse, status_code=201, tags=["budgets"])
def create_budget_transfer(payload: BudgetTransferCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    if payload.original_cdp_id:
        cdp = db.execute(text("SELECT id, amount FROM budget_cdp WHERE id=:id AND company_id=:cid"), {"id": payload.original_cdp_id, "cid": payload.company_id}).mappings().first()
        if not cdp:
            raise HTTPException(status_code=404, detail="CDP origen no encontrado.")
        committed = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM budget_commitments WHERE cdp_id=:id AND status!='anulado'"), {"id": payload.original_cdp_id}).scalar_one()
        transferred = db.execute(text("SELECT COALESCE(SUM(amount),0) FROM budget_transfers WHERE original_cdp_id=:id"), {"id": payload.original_cdp_id}).scalar_one()
        available = Decimal(str(cdp["amount"])) - Decimal(str(committed)) - Decimal(str(transferred))
        if Decimal(str(payload.amount)) > available:
            raise HTTPException(status_code=409, detail=f"Saldo insuficiente en CDP para traslado. Disponible: {available}")
    try:
        row = db.execute(text("""
            INSERT INTO budget_transfers (company_id, original_cdp_id, original_cdp_number, from_area, to_area, amount, new_partida, new_account_code, notes)
            VALUES (:company_id, :original_cdp_id, :original_cdp_number, :from_area, :to_area, :amount, :new_partida, :new_account_code, :notes)
            RETURNING id, company_id, original_cdp_id, original_cdp_number, from_area, to_area, amount, new_partida, new_account_code, notes, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        _audit(db, claims, "finance.budget_transfer.created", payload.company_id, "budget_transfer", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el traslado.") from exc
    return BudgetTransferResponse(**dict(row))


# ---------------------------------------------------------------------------
# Finance banks (catalog)
# ---------------------------------------------------------------------------

@app.get("/api/v1/finance/banks", response_model=list[FinanceBankResponse], tags=["treasury"])
def list_finance_banks(company_id: UUID = Query(...), db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, company_id)
    rows = db.execute(text("SELECT id, company_id, code, name, is_active, created_at, updated_at FROM finance_banks WHERE company_id=:c ORDER BY name"), {"c": company_id}).mappings().all()
    return [FinanceBankResponse(**dict(r)) for r in rows]


@app.post("/api/v1/finance/banks", response_model=FinanceBankResponse, status_code=201, tags=["treasury"])
def create_finance_bank(payload: FinanceBankCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company(claims, payload.company_id)
    try:
        row = db.execute(text("""
            INSERT INTO finance_banks (company_id, code, name, is_active)
            VALUES (:company_id, :code, :name, :is_active)
            RETURNING id, company_id, code, name, is_active, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        _audit(db, claims, "finance.bank.created", payload.company_id, "finance_bank", str(row["id"]))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear el banco.") from exc
    return FinanceBankResponse(**dict(row))


@app.patch("/api/v1/finance/banks/{bank_id}", response_model=FinanceBankResponse, tags=["treasury"])
def update_finance_bank(bank_id: UUID, payload: FinanceBankCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM finance_banks WHERE id=:id"), {"id": bank_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Banco no encontrado.")
    require_company(claims, current["company_id"])
    try:
        row = db.execute(text("""
            UPDATE finance_banks SET code=:code, name=:name, is_active=:is_active, updated_at=now()
            WHERE id=:id
            RETURNING id, company_id, code, name, is_active, created_at, updated_at
        """), {**payload.model_dump(), "id": bank_id}).mappings().first()
        _audit(db, claims, "finance.bank.updated", current["company_id"], "finance_bank", str(bank_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo actualizar el banco.") from exc
    return FinanceBankResponse(**dict(row))


@app.delete("/api/v1/finance/banks/{bank_id}", status_code=204, tags=["treasury"])
def delete_finance_bank(bank_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM finance_banks WHERE id=:id"), {"id": bank_id}).mappings().first()
    if not current:
        raise HTTPException(status_code=404, detail="Banco no encontrado.")
    require_company(claims, current["company_id"])
    try:
        db.execute(text("DELETE FROM finance_banks WHERE id=:id"), {"id": bank_id})
        _audit(db, claims, "finance.bank.deleted", current["company_id"], "finance_bank", str(bank_id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo eliminar el banco (puede estar en uso).") from exc
    return None
