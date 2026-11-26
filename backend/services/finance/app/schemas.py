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
    origin_area: Optional[str] = Field(default=None, max_length=60)


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
    origin_area: Optional[str] = Field(default=None, max_length=60)


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


# --- Cost Centers & Projects ---
class CostCenterBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    parent_id: Optional[UUID] = None
    is_active: bool = True

class CostCenterCreate(CostCenterBase):
    company_id: UUID

class CostCenterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    parent_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class CostCenterResponse(CostCenterBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_amount: Decimal = Field(default=Decimal("0"), ge=0)
    status: str = Field(default="active", pattern="^(active|completed|suspended|cancelled)$")
    manager_name: Optional[str] = None

class ProjectCreate(ProjectBase):
    company_id: UUID

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget_amount: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, pattern="^(active|completed|suspended|cancelled)$")
    manager_name: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Fixed Assets ---
class AssetCategoryBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    depreciation_method: str = Field(default="straight_line", pattern="^(straight_line|declining_balance|units_of_production)$")
    useful_life_years: int = Field(default=5, ge=1)
    salvage_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    asset_account_id: Optional[UUID] = None
    accumulated_depreciation_account_id: Optional[UUID] = None
    depreciation_expense_account_id: Optional[UUID] = None
    is_active: bool = True

class AssetCategoryCreate(AssetCategoryBase):
    company_id: UUID

class AssetCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    depreciation_method: Optional[str] = Field(default=None, pattern="^(straight_line|declining_balance|units_of_production)$")
    useful_life_years: Optional[int] = Field(default=None, ge=1)
    salvage_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    asset_account_id: Optional[UUID] = None
    accumulated_depreciation_account_id: Optional[UUID] = None
    depreciation_expense_account_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class AssetCategoryResponse(AssetCategoryBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FixedAssetBase(BaseModel):
    category_id: UUID
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    acquisition_date: date
    start_depreciation_date: date
    acquisition_cost: Decimal = Field(gt=0)
    salvage_value: Decimal = Field(default=Decimal("0"), ge=0)
    useful_life_months: int = Field(default=60, ge=1)
    cost_center_id: Optional[UUID] = None

class FixedAssetCreate(FixedAssetBase):
    company_id: UUID

class FixedAssetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    serial_number: Optional[str] = None
    location: Optional[str] = None
    cost_center_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, pattern="^(active|fully_depreciated|disposed|under_maintenance)$")
    disposal_date: Optional[date] = None
    disposal_reason: Optional[str] = None

class FixedAssetResponse(FixedAssetBase):
    id: UUID
    company_id: UUID
    current_book_value: Decimal
    accumulated_depreciation: Decimal
    status: str
    disposal_date: Optional[date] = None
    disposal_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssetDepreciationLineResponse(BaseModel):
    id: UUID
    asset_id: UUID
    fiscal_period_id: Optional[UUID] = None
    period_date: date
    depreciation_amount: Decimal
    accumulated_before: Decimal
    accumulated_after: Decimal
    book_value_after: Decimal
    journal_entry_id: Optional[UUID] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Payment Terms & Withholding ---
class PaymentTermBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    days_net: int = Field(default=0, ge=0)
    days_discount: int = Field(default=0, ge=0)
    discount_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    is_active: bool = True

class PaymentTermCreate(PaymentTermBase):
    company_id: UUID

class PaymentTermUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    days_net: Optional[int] = Field(default=None, ge=0)
    days_discount: Optional[int] = Field(default=None, ge=0)
    discount_rate: Optional[Decimal] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None

class PaymentTermResponse(PaymentTermBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WithholdingTypeBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    rate: Decimal = Field(gt=0, le=100)
    applies_to: str = Field(pattern="^(purchase|sale|both)$")
    withholding_account_id: Optional[UUID] = None
    is_active: bool = True

class WithholdingTypeCreate(WithholdingTypeBase):
    company_id: UUID

class WithholdingTypeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    rate: Optional[Decimal] = Field(default=None, gt=0, le=100)
    applies_to: Optional[str] = Field(default=None, pattern="^(purchase|sale|both)$")
    withholding_account_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class WithholdingTypeResponse(WithholdingTypeBase):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Invoice Series ---
class InvoiceSeriesBase(BaseModel):
    document_type_code: str = Field(min_length=1, max_length=10)
    series: str = Field(min_length=1, max_length=10)
    description: Optional[str] = None
    is_electronic: bool = True
    is_default: bool = False
    is_active: bool = True

class InvoiceSeriesCreate(InvoiceSeriesBase):
    company_id: UUID

class InvoiceSeriesUpdate(BaseModel):
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    current_correlative: Optional[int] = None
    next_correlative: Optional[int] = None

class InvoiceSeriesResponse(InvoiceSeriesBase):
    id: UUID
    company_id: UUID
    current_correlative: int
    next_correlative: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Registros Contables SUNAT (PLE) ---
class PurchaseRegisterEntryCreate(BaseModel):
    company_id: UUID
    fiscal_period_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    journal_entry_id: Optional[UUID] = None
    cuo: str = Field(min_length=1, max_length=40)
    issue_date: date
    due_date: Optional[date] = None
    voucher_type: str = Field(default="01", max_length=10)
    series: str = Field(max_length=20)
    voucher_number: str = Field(max_length=30)
    supplier_id_type: str = Field(default="6", max_length=10)
    supplier_tax_id: str = Field(max_length=24)
    supplier_name: str = Field(max_length=200)
    taxable_base: Decimal = Field(default=Decimal("0"))
    igv_amount: Decimal = Field(default=Decimal("0"))
    exempt_amount: Decimal = Field(default=Decimal("0"))
    unaffected_amount: Decimal = Field(default=Decimal("0"))
    isc_amount: Decimal = Field(default=Decimal("0"))
    icbper_amount: Decimal = Field(default=Decimal("0"))
    other_taxes: Decimal = Field(default=Decimal("0"))
    total_amount: Decimal = Field(default=Decimal("0"))
    currency: str = Field(default="PEN", max_length=10)
    exchange_rate: Decimal = Field(default=Decimal("1.0"))
    detraction_date: Optional[date] = None
    detraction_constancy: Optional[str] = None
    retention_amount: Decimal = Field(default=Decimal("0"))
    operation_status: str = Field(default="1", max_length=10)

class PurchaseRegisterEntryResponse(PurchaseRegisterEntryCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SalesRegisterEntryCreate(BaseModel):
    company_id: UUID
    fiscal_period_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    journal_entry_id: Optional[UUID] = None
    cuo: str = Field(min_length=1, max_length=40)
    issue_date: date
    due_date: Optional[date] = None
    voucher_type: str = Field(default="01", max_length=10)
    series: str = Field(max_length=20)
    voucher_number: str = Field(max_length=30)
    customer_id_type: str = Field(default="6", max_length=10)
    customer_tax_id: str = Field(max_length=24)
    customer_name: str = Field(max_length=200)
    export_amount: Decimal = Field(default=Decimal("0"))
    taxable_base: Decimal = Field(default=Decimal("0"))
    discount_base: Decimal = Field(default=Decimal("0"))
    igv_amount: Decimal = Field(default=Decimal("0"))
    discount_igv: Decimal = Field(default=Decimal("0"))
    exempt_amount: Decimal = Field(default=Decimal("0"))
    unaffected_amount: Decimal = Field(default=Decimal("0"))
    isc_amount: Decimal = Field(default=Decimal("0"))
    icbper_amount: Decimal = Field(default=Decimal("0"))
    other_taxes: Decimal = Field(default=Decimal("0"))
    total_amount: Decimal = Field(default=Decimal("0"))
    currency: str = Field(default="PEN", max_length=10)
    exchange_rate: Decimal = Field(default=Decimal("1.0"))
    operation_status: str = Field(default="1", max_length=10)

class SalesRegisterEntryResponse(SalesRegisterEntryCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClosingEntryCreate(BaseModel):
    company_id: UUID
    fiscal_year_id: UUID
    step_number: int
    step_name: str
    journal_entry_id: Optional[UUID] = None
    notes: Optional[str] = None

class ClosingEntryResponse(ClosingEntryCreate):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OpeningBalanceCreate(BaseModel):
    company_id: UUID
    fiscal_year_id: UUID
    account_id: UUID
    auxiliary_id: Optional[UUID] = None
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    journal_entry_id: Optional[UUID] = None

class OpeningBalanceResponse(OpeningBalanceCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BudgetCDPCreate(BaseModel):
    company_id: UUID
    number: str = Field(min_length=1, max_length=80)
    cdp_date: date
    line_text: Optional[str] = None
    requester_area: Optional[str] = None
    amount: Decimal = Field(default=Decimal("0"))
    status: str = Field(default="vigente", max_length=30)


class BudgetCDPResponse(BudgetCDPCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BudgetCommitmentCreate(BaseModel):
    company_id: UUID
    number: str = Field(min_length=1, max_length=80)
    commitment_date: date
    reference: Optional[str] = None
    amount: Decimal = Field(default=Decimal("0"))
    status: str = Field(default="comprometido", max_length=30)
    cdp_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None


class BudgetCommitmentResponse(BudgetCommitmentCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentOrderCreate(BaseModel):
    company_id: UUID
    number: str = Field(min_length=1, max_length=80)
    order_date: date
    payee: Optional[str] = None
    amount: Decimal = Field(default=Decimal("0"))
    status: str = Field(default="emitida", max_length=30)
    commitment_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    bank_account_id: Optional[UUID] = None


class PaymentOrderResponse(PaymentOrderCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FinanceBankCreate(BaseModel):
    company_id: UUID
    code: Optional[str] = None
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class FinanceBankResponse(FinanceBankCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BudgetTransferCreate(BaseModel):
    company_id: UUID
    original_cdp_id: Optional[UUID] = None
    original_cdp_number: str = Field(min_length=1, max_length=80)
    from_area: Optional[str] = None
    to_area: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(default=Decimal("0"), gt=0)
    new_partida: Optional[str] = None
    new_account_code: Optional[str] = None
    notes: Optional[str] = None


class BudgetTransferResponse(BudgetTransferCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

