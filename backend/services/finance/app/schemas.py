"""JSON schemas for the Finance microservice."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AccountBase(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    account_type: str = Field(pattern="^(asset|liability|equity|revenue|expense)$")
    is_group: bool = False
    parent_id: Optional[UUID] = None
    account_subtype: Optional[str] = Field(default=None, pattern="^(cash|bank|receivable|payable|inventory|fixed_asset|tax|equity|income|expense)$")
    cash_flow_category: Optional[str] = Field(default=None, pattern="^(operating|investing|financing)$")
    currency: str = Field(default="PEN", min_length=3, max_length=3)
    allow_posting: bool = True
    is_active: bool = True
    description: Optional[str] = None


class AccountCreate(AccountBase):
    company_id: UUID


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    account_type: Optional[str] = Field(default=None, pattern="^(asset|liability|equity|revenue|expense)$")
    is_group: Optional[bool] = None
    parent_id: Optional[UUID] = None
    account_subtype: Optional[str] = Field(default=None, pattern="^(cash|bank|receivable|payable|inventory|fixed_asset|tax|equity|income|expense)$")
    cash_flow_category: Optional[str] = Field(default=None, pattern="^(operating|investing|financing)$")
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    allow_posting: Optional[bool] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


class AccountResponse(AccountBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


class AuxiliaryCreate(BaseModel):
    company_id: UUID
    code: str = Field(min_length=1,max_length=40)
    name: str = Field(min_length=1,max_length=200)
    auxiliary_type: str = Field(pattern="^(customer|supplier|employee|user|other)$")
    tax_id: Optional[str] = Field(default=None,max_length=24)
    user_id: Optional[UUID] = None
    email: Optional[str] = Field(default=None,max_length=320)
    phone: Optional[str] = Field(default=None,max_length=40)
    address: Optional[str] = None
    is_active: bool = True


class AuxiliaryUpdate(BaseModel):
    code: Optional[str] = Field(default=None,min_length=1,max_length=40)
    name: Optional[str] = Field(default=None,min_length=1,max_length=200)
    auxiliary_type: Optional[str] = Field(default=None,pattern="^(customer|supplier|employee|user|other)$")
    tax_id: Optional[str] = Field(default=None,max_length=24)
    user_id: Optional[UUID] = None
    email: Optional[str] = Field(default=None,max_length=320)
    phone: Optional[str] = Field(default=None,max_length=40)
    address: Optional[str] = None
    is_active: Optional[bool] = None


class AuxiliaryResponse(AuxiliaryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class FiscalYearBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start_date: date
    end_date: date


class FiscalYearCreate(FiscalYearBase):
    company_id: UUID


class FiscalYearResponse(FiscalYearBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    is_closed: bool
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FiscalPeriodBase(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=3, max_length=80)
    start_date: date
    end_date: date
    sort_order: int = Field(default=1, ge=1)


class FiscalPeriodCreate(FiscalPeriodBase):
    fiscal_year_id: UUID


class FiscalPeriodResponse(FiscalPeriodBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    fiscal_year_id: UUID
    is_closed: bool
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class JournalEntryLineBase(BaseModel):
    account_id: UUID
    auxiliary_id: Optional[UUID] = None
    line_number: int = Field(ge=1)
    description: Optional[str] = None
    debit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    currency_amount: Optional[Decimal] = None
    currency_code: Optional[str] = Field(default=None, min_length=3, max_length=3)
    analytical_dimension_1: Optional[str] = None
    analytical_dimension_2: Optional[str] = None


class JournalEntryLineCreate(JournalEntryLineBase):
    pass


class JournalEntryLineResponse(JournalEntryLineBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    journal_entry_id: UUID
    created_at: datetime
    updated_at: datetime


class JournalEntryBase(BaseModel):
    fiscal_year_id: UUID
    fiscal_period_id: Optional[UUID] = None
    entry_number: str = Field(min_length=1, max_length=40)
    entry_date: date
    reference: Optional[str] = None
    description: Optional[str] = None
    currency: str = Field(default="PEN", min_length=3, max_length=3)
    exchange_rate: Decimal = Field(default=Decimal("1.000000"), ge=0)


class JournalEntryCreate(JournalEntryBase):
    lines: list[JournalEntryLineCreate] = Field(min_length=1)


class JournalEntryResponse(JournalEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    status: str
    total_debit: Decimal
    total_credit: Decimal
    posted_by: Optional[UUID] = None
    posted_at: Optional[datetime] = None
    lines: list[JournalEntryLineResponse] = []
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class BudgetBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    fiscal_year_id: UUID
    description: Optional[str] = None
    currency: str = Field(default="PEN", min_length=3, max_length=3)


class BudgetCreate(BudgetBase):
    company_id: UUID


class BudgetResponse(BudgetBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    status: str
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class BudgetLineBase(BaseModel):
    account_id: UUID
    period_id: Optional[UUID] = None
    planned_amount: Decimal = Field(default=Decimal("0"), ge=0)


class BudgetLineCreate(BudgetLineBase):
    pass


class BudgetLineResponse(BudgetLineBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    budget_id: UUID
    created_at: datetime
    updated_at: datetime


class BudgetLineDetail(BudgetLineResponse):
    model_config = ConfigDict(from_attributes=True)
    account_code: str
    account_name: str
    account_type: str


class TaxRateBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    rate: Decimal = Field(ge=0)
    tax_type: str = Field(pattern="^(vat|withholding|excise|other)$")
    is_active: bool = True
    valid_from: date
    valid_until: Optional[date] = None


class TaxRateCreate(TaxRateBase):
    company_id: UUID


class TaxRateResponse(TaxRateBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime


class ExchangeRateBase(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(gt=0)
    source: Optional[str] = None


class ExchangeRateCreate(ExchangeRateBase):
    company_id: UUID


class ExchangeRateResponse(ExchangeRateBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    created_at: datetime


class CompanyBase(BaseModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    tax_id: Optional[str] = Field(default=None, max_length=24)
    country_code: str = Field(default="PE", min_length=2, max_length=2)
    default_currency: str = Field(default="PEN", min_length=3, max_length=3)
    timezone: str = Field(default="America/Lima", max_length=64)


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    tax_id: Optional[str] = Field(default=None, max_length=24)
    default_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    timezone: Optional[str] = Field(default=None, max_length=64)
    is_active: Optional[bool] = None


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FiscalYearUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_closed: Optional[bool] = None


class FiscalPeriodUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_closed: Optional[bool] = None
    sort_order: Optional[int] = None


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(draft|approved|active|closed)$")
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class BudgetLineUpdate(BaseModel):
    period_id: Optional[UUID] = None
    planned_amount: Optional[Decimal] = Field(default=None, ge=0)


class TaxRateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    rate: Optional[Decimal] = Field(default=None, ge=0)
    tax_type: Optional[str] = Field(default=None, pattern="^(vat|withholding|excise|other)$")
    is_active: Optional[bool] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


class ExchangeRateUpdate(BaseModel):
    rate: Optional[Decimal] = Field(default=None, gt=0)
    source: Optional[str] = None
