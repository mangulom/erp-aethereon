from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import logging
from uuid import UUID

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import engine, get_db
from .schemas import (CompanyCreate, CompanyUpdate, DocumentTypeCreate, DocumentTypeUpdate, HealthResponse, LoginRequest, LoginResponse, MembershipCreate, MembershipUpdate, RoleCreate, RoleUpdate, UserCompanyAssignment, UserCreate, UserMembershipsUpdate, UserUpdate, UserResponse)
from .security import create_access_token, hash_password, verify_password

settings = get_settings()
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("aethereon.identity.health")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title=settings.service_name,
    description="Servicio independiente de autenticaciÃ³n, usuarios y membresÃ­as empresariales.",
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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Service-Name"] = "identity"
    return response


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
def health_live() -> HealthResponse:
    return HealthResponse(status="ok", service="identity", version=settings.service_version)


@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
def health_ready(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        original = getattr(exc, "orig", None)
        sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        logger.error("Database readiness check failed: error_type=%s sqlstate=%s", type(original).__name__ if original else type(exc).__name__, sqlstate)
        raise HTTPException(status_code=503, detail="PostgreSQL no disponible.") from exc
    return HealthResponse(status="ready", service="identity", version=settings.service_version)


@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["authentication"])
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        result = db.execute(
            text("""
                SELECT id, email, display_name, avatar_data_url, password_hash, is_active, is_platform_admin, locked_until
                FROM users WHERE lower(email) = lower(:email)
            """),
            {"email": payload.email},
        ).mappings().first()
    except SQLAlchemyError:
        # Keep authentication available until the avatar-column migration is applied.
        db.rollback()
        try:
            result = db.execute(text("SELECT id,email,display_name,password_hash,is_active,is_platform_admin,locked_until FROM users WHERE lower(email)=lower(:email)"), {"email":payload.email}).mappings().first()
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="Base de datos no disponible o esquema inicial no aplicado.") from exc
    # Perform the same cost Argon2 verification for an unknown address to reduce timing disclosure.
    if result is None:
        from .security import _hasher

        _hasher.hash(payload.password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseÃ±a incorrectos.")
    now = datetime.now(UTC)
    locked_until = result["locked_until"]
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    if locked_until and locked_until > now:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="La cuenta estÃ¡ temporalmente bloqueada. IntÃ©ntalo mÃ¡s tarde.")
    password_ok = verify_password(payload.password, result["password_hash"])
    if not result["is_active"] or not password_ok:
        db.execute(
            text("""
                UPDATE users SET failed_login_attempts = failed_login_attempts + 1,
                    locked_until = CASE WHEN failed_login_attempts + 1 >= 8 THEN :until ELSE locked_until END,
                    updated_at = now() WHERE id = :id
            """),
            {"id": result["id"], "until": now + timedelta(minutes=15)},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o contraseÃ±a incorrectos.")
    db.execute(
        text("DELETE FROM memberships WHERE user_id = :user_id AND NOT EXISTS (SELECT 1 FROM roles WHERE roles.id = memberships.role_id AND roles.company_id = memberships.company_id)"),
        {"user_id": result["id"]},
    )

    db.execute(
        text("UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login_at = now(), updated_at = now() WHERE id = :id"),
        {"id": result["id"]},
    )
    company_ids = [row[0] for row in db.execute(
        text("""
            SELECT m.company_id FROM memberships m
            JOIN roles r ON r.id = m.role_id AND r.company_id = m.company_id
            WHERE m.user_id = :user_id AND m.is_active = TRUE
              AND EXISTS (SELECT 1 FROM companies c WHERE c.id = m.company_id AND c.is_active = TRUE)
            ORDER BY m.company_id
        """),
        {"user_id": result["id"]},
    ).all()]
    permission_codes = [row[0] for row in db.execute(text("""
        SELECT DISTINCT p.code FROM memberships m
        JOIN roles r ON r.id=m.role_id AND r.company_id=m.company_id
        JOIN role_permissions rp ON rp.role_id=r.id
        JOIN permissions p ON p.id=rp.permission_id
        WHERE m.user_id=:user_id AND m.is_active
    """), {"user_id": result["id"]}).all()]
    db.execute(
        text("""
            INSERT INTO audit_events (actor_user_id, actor_type, action, entity_type, entity_id)
            VALUES (:user_id, 'user', 'identity.login.succeeded', 'user', :entity_id)
        """),
        {"user_id": result["id"], "entity_id": str(result["id"])},
    )
    db.commit()
    access_token, expiry = create_access_token(result["id"], company_ids, result["is_platform_admin"], permission_codes)
    user = UserResponse(
        id=result["id"], email=result["email"], display_name=result["display_name"], avatar_data_url=result.get("avatar_data_url"),
        is_platform_admin=result["is_platform_admin"],
    )
    return LoginResponse(access_token=access_token, expires_at=expiry, user=user)


@app.get("/api/v1/auth/me", response_model=UserResponse, tags=["authentication"])
def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserResponse:
    if not credentials:
        raise HTTPException(status_code=401, detail="AutenticaciÃ³n requerida.")
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer="aethereon-identity",
            audience="aethereon-erp",
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        user_id = UUID(claims["sub"])
        authorized_company_ids = [UUID(company_id) for company_id in claims.get("companies", [])]
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="La sesiÃ³n no es vÃ¡lida o ha vencido.") from exc
    try:
        result = db.execute(
            text("""
                SELECT u.id, u.email, u.display_name, u.avatar_data_url, u.is_platform_admin, u.is_active
                FROM users AS u
                WHERE u.id = :id
                  AND (:is_platform_admin OR EXISTS (
                    SELECT 1 FROM memberships AS m
                    WHERE m.user_id = u.id AND m.company_id = ANY(:company_ids) AND m.is_active = TRUE
                  ))
            """),
            {"id": user_id, "is_platform_admin": claims.get("platform_admin") is True, "company_ids": authorized_company_ids},
        ).mappings().first()
    except SQLAlchemyError:
        db.rollback()
        result = db.execute(text("""
            SELECT u.id,u.email,u.display_name,u.is_platform_admin,u.is_active
            FROM users u WHERE u.id=:id AND (:is_platform_admin OR EXISTS (
                SELECT 1 FROM memberships m WHERE m.user_id=u.id AND m.company_id=ANY(:company_ids) AND m.is_active=TRUE
            ))
        """), {"id":user_id,"is_platform_admin":claims.get("platform_admin") is True,"company_ids":authorized_company_ids}).mappings().first()
    if not result or not result["is_active"]:
        raise HTTPException(status_code=401, detail="La cuenta no estÃ¡ activa.")
    return UserResponse(id=result["id"], email=result["email"], display_name=result["display_name"], is_platform_admin=result["is_platform_admin"], avatar_data_url=result["avatar_data_url"])


@app.get("/api/v1/auth/companies", tags=["authentication"])
def current_user_companies(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if not credentials: raise HTTPException(status_code=401,detail="Autenticación requerida.")
    try:
        claims=jwt.decode(credentials.credentials,settings.jwt_secret_key,algorithms=[settings.jwt_algorithm],issuer="aethereon-identity",audience="aethereon-erp")
        user_id=UUID(claims["sub"])
    except (jwt.InvalidTokenError,KeyError,ValueError) as exc:
        raise HTTPException(status_code=401,detail="La sesión no es válida o ha vencido.") from exc
    if claims.get("platform_admin") is True:
        rows=db.execute(text("SELECT id,legal_name,trade_name,default_currency FROM companies WHERE is_active ORDER BY legal_name")).mappings().all()
    else:
        rows=db.execute(text("""
            SELECT c.id,c.legal_name,c.trade_name,c.default_currency FROM memberships m
            JOIN companies c ON c.id=m.company_id AND c.is_active
            JOIN roles r ON r.id=m.role_id AND r.company_id=m.company_id
            WHERE m.user_id=:user_id AND m.is_active GROUP BY c.id ORDER BY c.legal_name
        """),{"user_id":user_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/auth/select-company", tags=["authentication"])
def select_current_company(company_id: UUID,credentials: HTTPAuthorizationCredentials | None = Depends(bearer),db: Session=Depends(get_db)):
    if not credentials:raise HTTPException(status_code=401,detail="Autenticación requerida.")
    try:
        claims=jwt.decode(credentials.credentials,settings.jwt_secret_key,algorithms=[settings.jwt_algorithm],issuer="aethereon-identity",audience="aethereon-erp")
        user_id=UUID(claims["sub"])
    except (jwt.InvalidTokenError,KeyError,ValueError) as exc:
        raise HTTPException(status_code=401,detail="La sesión no es válida o ha vencido.") from exc
    if claims.get("platform_admin") is not True and not db.execute(text("""
        SELECT 1 FROM memberships m JOIN companies c ON c.id=m.company_id AND c.is_active
        JOIN roles r ON r.id=m.role_id AND r.company_id=m.company_id
        WHERE m.user_id=:user_id AND m.company_id=:company_id AND m.is_active
    """),{"user_id":user_id,"company_id":company_id}).first():
        raise HTTPException(status_code=403,detail="No tienes acceso a esta empresa.")
    user=db.execute(text("SELECT is_platform_admin FROM users WHERE id=:id AND is_active"),{"id":user_id}).mappings().first()
    if not user:raise HTTPException(status_code=401,detail="La cuenta no está activa.")
    permission_codes=[row[0] for row in db.execute(text("""
        SELECT DISTINCT p.code FROM memberships m JOIN roles r ON r.id=m.role_id AND r.company_id=m.company_id
        JOIN role_permissions rp ON rp.role_id=r.id JOIN permissions p ON p.id=rp.permission_id
        WHERE m.user_id=:user_id AND m.company_id=:company_id AND m.is_active
    """),{"user_id":user_id,"company_id":company_id}).all()]
    token,expiry=create_access_token(str(user_id),[str(company_id)],user["is_platform_admin"],permission_codes)
    return {"access_token":token,"token_type":"bearer","expires_at":expiry,"selected_company_id":company_id}


@app.post("/api/v1/auth/verify", tags=["authentication"])
def verify_session(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, bool]:
    if not credentials:
        raise HTTPException(status_code=401, detail="AutenticaciÃ³n requerida.")
    try:
        jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], issuer="aethereon-identity", audience="aethereon-erp")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="La sesiÃ³n no es vÃ¡lida o ha vencido.") from exc
    return {"valid": True}


def require_claims(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Autenticación requerida.")
    try:
        return jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], issuer="aethereon-identity", audience="aethereon-erp")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="La sesión no es válida o ha vencido.") from exc


def require_platform_admin(claims: dict) -> None:
    if claims.get("platform_admin") is not True:
        raise HTTPException(status_code=403, detail="Se requiere administración de plataforma.")


def require_company_admin(db: Session, claims: dict, company_id: UUID) -> None:
    if claims.get("platform_admin") is True:
        return
    user_id = claims.get("sub")
    allowed = db.execute(text("""
        SELECT 1 FROM memberships m JOIN roles r ON r.id = m.role_id AND r.company_id = m.company_id
        WHERE m.user_id = :u AND m.company_id = :c AND m.is_active
          AND r.code IN ('COMPANY_ADMIN','ADMIN')
    """), {"u": user_id, "c": company_id}).first()
    if not allowed:
        raise HTTPException(status_code=403, detail="Se requiere administración de esta empresa.")


@app.get("/api/v1/admin/companies", tags=["administration"])
def admin_list_companies(db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    rows = db.execute(text("SELECT id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at FROM companies ORDER BY legal_name")).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/admin/companies", status_code=201, tags=["administration"])
def admin_create_company(payload: CompanyCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    try:
        row = db.execute(text("""
            INSERT INTO companies (legal_name, trade_name, tax_id, country_code, default_currency, timezone)
            VALUES (:legal_name, :trade_name, :tax_id, :country_code, :default_currency, :timezone)
            RETURNING id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at
        """), payload.model_dump()).mappings().first()
        db.execute(text("INSERT INTO audit_events (actor_user_id, actor_type, action, entity_type, entity_id) VALUES (:u,'user','identity.company.created','company',:id)"), {"u": claims.get("sub"), "id": str(row["id"])})
        db.commit()
        return dict(row)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo crear la empresa; verifica si el RUC ya está registrado.") from exc


@app.patch("/api/v1/admin/companies/{company_id}", tags=["administration"])
def admin_update_company(company_id: UUID, payload: CompanyUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not changes: raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    changes["id"] = company_id
    try:
        row = db.execute(text(f"UPDATE companies SET {assignments}, updated_at=now() WHERE id=:id RETURNING id, legal_name, trade_name, tax_id, country_code, default_currency, timezone, is_active, created_at, updated_at"), changes).mappings().first()
        if not row: raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        db.commit()
        return dict(row)
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudo actualizar la empresa.") from exc


@app.delete("/api/v1/admin/companies/{company_id}", status_code=204, tags=["administration"])
def admin_delete_company(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    try:
        result = db.execute(text("DELETE FROM companies WHERE id=:id"), {"id": company_id})
        if not result.rowcount: raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudo eliminar la empresa.") from exc


@app.get("/api/v1/admin/users", tags=["administration"])
def admin_list_users(db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    try:
        rows = db.execute(text("SELECT id, email, display_name, avatar_data_url, is_active, is_platform_admin, failed_login_attempts, locked_until, last_login_at, created_at, updated_at FROM users ORDER BY email")).mappings().all()
    except SQLAlchemyError:
        db.rollback()
        rows = db.execute(text("SELECT id, email, display_name, is_active, is_platform_admin, failed_login_attempts, locked_until, last_login_at, created_at, updated_at FROM users ORDER BY email")).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/admin/users", status_code=201, tags=["administration"])
def admin_create_user(payload: UserCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    if payload.avatar_data_url and not payload.avatar_data_url.startswith("data:image/jpeg;base64,"):
        raise HTTPException(status_code=422,detail="La foto debe ser una imagen JPEG optimizada en formato base64.")
    try:
        row = db.execute(text("INSERT INTO users (email, display_name, password_hash, avatar_data_url, is_active, is_platform_admin) VALUES (lower(:email),:display_name,:hash,:avatar,:active,:admin) RETURNING id,email,display_name,avatar_data_url,is_active,is_platform_admin,failed_login_attempts,locked_until,last_login_at,created_at,updated_at"), {"email": payload.email, "display_name": payload.display_name, "hash": hash_password(payload.password), "avatar":payload.avatar_data_url, "active": payload.is_active, "admin": payload.is_platform_admin}).mappings().first()
        db.commit(); return dict(row)
    except SQLAlchemyError as exc:
        db.rollback()
        if "avatar_data_url" in str(exc).lower():
            raise HTTPException(status_code=503,detail="Falta aplicar la migración 009_user_avatar_base64.sql como propietario de la tabla users.") from exc
        raise HTTPException(status_code=409, detail="No se pudo crear el usuario; el correo puede estar registrado.") from exc


@app.patch("/api/v1/admin/users/{user_id}", tags=["administration"])
def admin_update_user(user_id: UUID, payload: UserUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "avatar_data_url" in changes and changes["avatar_data_url"] and not changes["avatar_data_url"].startswith("data:image/jpeg;base64,"):
        raise HTTPException(status_code=422,detail="La foto debe ser una imagen JPEG optimizada en formato base64.")
    password = changes.pop("password", None)
    if password: changes["password_hash"] = hash_password(password)
    if not changes: raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if str(user_id) == str(claims.get("sub")) and changes.get("is_platform_admin") is False:
        raise HTTPException(status_code=409, detail="No puedes quitarte tu propio privilegio de administrador.")
    if "email" in changes: changes["email"] = str(changes["email"]).lower()
    assignments = ", ".join(f"{k} = :{k}" for k in changes); changes["id"] = user_id
    try:
        row = db.execute(text(f"UPDATE users SET {assignments}, updated_at=now() WHERE id=:id RETURNING id,email,display_name,avatar_data_url,is_active,is_platform_admin,failed_login_attempts,locked_until,last_login_at,created_at,updated_at"), changes).mappings().first()
        if not row: raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        db.commit(); return dict(row)
    except SQLAlchemyError as exc:
        db.rollback()
        if "avatar_data_url" in str(exc).lower():
            raise HTTPException(status_code=503,detail="Falta aplicar la migración 009_user_avatar_base64.sql como propietario de la tabla users.") from exc
        raise HTTPException(status_code=409, detail="No se pudo actualizar el usuario.") from exc


@app.delete("/api/v1/admin/users/{user_id}", status_code=204, tags=["administration"])
def admin_delete_user(user_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    if str(user_id) == str(claims.get("sub")): raise HTTPException(status_code=409, detail="No puedes eliminar tu propia cuenta.")
    result = db.execute(text("DELETE FROM users WHERE id=:id AND is_platform_admin=FALSE"), {"id": user_id})
    if not result.rowcount:
        db.rollback(); raise HTTPException(status_code=404, detail="Usuario no encontrado o es administrador de plataforma.")
    db.commit()


@app.get("/api/v1/admin/users/{user_id}/memberships", tags=["administration"])
def admin_get_user_memberships(user_id: UUID, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    require_platform_admin(claims)
    if not db.execute(text("SELECT 1 FROM users WHERE id=:id"),{"id":user_id}).first():
        raise HTTPException(status_code=404,detail="Usuario no encontrado.")
    rows=db.execute(text("""
        SELECT m.id AS membership_id,m.user_id,m.company_id,c.legal_name,c.trade_name,m.role_id,r.code AS role_code,r.name AS role_name,m.is_active
        FROM memberships m JOIN companies c ON c.id=m.company_id JOIN roles r ON r.id=m.role_id
        WHERE m.user_id=:user_id ORDER BY c.legal_name,r.name
    """),{"user_id":user_id}).mappings().all()
    return [dict(row) for row in rows]


@app.put("/api/v1/admin/users/{user_id}/memberships", tags=["administration"])
def admin_replace_user_memberships(user_id: UUID,payload: UserMembershipsUpdate,db: Session=Depends(get_db),claims: dict=Depends(require_claims)):
    require_platform_admin(claims)
    user=db.execute(text("SELECT is_platform_admin FROM users WHERE id=:id"),{"id":user_id}).mappings().first()
    if not user:raise HTTPException(status_code=404,detail="Usuario no encontrado.")
    if user["is_platform_admin"]:
        raise HTTPException(status_code=409,detail="Los administradores de plataforma no pueden tener membresías empresariales.")
    pairs={(item.company_id,item.role_id) for item in payload.assignments}
    if len(pairs)!=len(payload.assignments):raise HTTPException(status_code=422,detail="Hay asignaciones duplicadas.")
    for item in payload.assignments:
        valid=db.execute(text("""
            SELECT 1 FROM companies c JOIN roles r ON r.id=:role_id
            WHERE c.id=:company_id AND c.is_active AND (r.company_id=:company_id OR r.company_id IS NULL)
        """),{"company_id":item.company_id,"role_id":item.role_id}).first()
        if not valid:raise HTTPException(status_code=422,detail="Cada rol debe ser global o pertenecer a la empresa seleccionada.")
    try:
        db.execute(text("DELETE FROM memberships WHERE user_id=:user_id"),{"user_id":user_id})
        for item in payload.assignments:
            db.execute(text("INSERT INTO memberships(company_id,user_id,role_id,is_active) VALUES(:company_id,:user_id,:role_id,TRUE)"),{"company_id":item.company_id,"user_id":user_id,"role_id":item.role_id})
        db.execute(text("INSERT INTO audit_events(actor_user_id,actor_type,action,entity_type,entity_id,metadata) VALUES(:actor,'user','identity.user.memberships_replaced','user',:target,CAST(:metadata AS jsonb))"),{"actor":claims.get("sub"),"target":str(user_id),"metadata":json.dumps({"assignment_count":len(payload.assignments)})})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudieron actualizar las empresas asignadas.") from exc
    return admin_get_user_memberships(user_id,db,claims)


@app.get("/api/v1/admin/roles", tags=["administration"])
def admin_list_roles(company_id: UUID | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    if company_id is None:
        require_platform_admin(claims)
        rows = db.execute(text("SELECT id, company_id, code, name, description, is_system, created_at FROM roles WHERE company_id IS NULL ORDER BY name")).mappings().all()
    else:
        require_company_admin(db, claims, company_id)
        rows = db.execute(text("SELECT id, company_id, code, name, description, is_system, created_at FROM roles WHERE company_id=:c OR company_id IS NULL ORDER BY company_id NULLS FIRST, name"), {"c": company_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/admin/roles", status_code=201, tags=["administration"])
def admin_create_role(payload: RoleCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    if payload.company_id is None: require_platform_admin(claims)
    else: require_company_admin(db, claims, payload.company_id)
    try:
        row = db.execute(text("INSERT INTO roles (company_id, code, name, description, is_system) VALUES (:company_id,:code,:name,:description,FALSE) RETURNING id,company_id,code,name,description,is_system,created_at"), payload.model_dump()).mappings().first()
        db.commit(); return dict(row)
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudo crear el rol; verifica el código.") from exc


@app.patch("/api/v1/admin/roles/{role_id}", tags=["administration"])
def admin_update_role(role_id: UUID, payload: RoleUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    role = db.execute(text("SELECT company_id,is_system FROM roles WHERE id=:id"), {"id": role_id}).mappings().first()
    if not role: raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if role["company_id"] is None: require_platform_admin(claims)
    else: require_company_admin(db, claims, role["company_id"])
    if role["is_system"]: raise HTTPException(status_code=409, detail="Los roles del sistema no se pueden modificar.")
    changes = {k:v for k,v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not changes: raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    assignments = ",".join(f"{k}=:{k}" for k in changes); changes["id"] = role_id
    row = db.execute(text(f"UPDATE roles SET {assignments} WHERE id=:id RETURNING id,company_id,code,name,description,is_system,created_at"), changes).mappings().first()
    db.commit(); return dict(row)


@app.delete("/api/v1/admin/roles/{role_id}", status_code=204, tags=["administration"])
def admin_delete_role(role_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    role = db.execute(text("SELECT company_id,is_system FROM roles WHERE id=:id"), {"id": role_id}).mappings().first()
    if not role: raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if role["company_id"] is None: require_platform_admin(claims)
    else: require_company_admin(db, claims, role["company_id"])
    if role["is_system"]: raise HTTPException(status_code=409, detail="Los roles del sistema no se pueden eliminar.")
    try:
        db.execute(text("DELETE FROM roles WHERE id=:id"), {"id": role_id}); db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="El rol tiene usuarios asignados o no se puede eliminar.") from exc


@app.get("/api/v1/admin/permissions", tags=["administration"])
def admin_list_permissions(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company_admin(db, claims, company_id)
    rows = db.execute(text("SELECT id,code,module_code,action,description FROM permissions ORDER BY module_code,action,code")).mappings().all()
    return [dict(row) for row in rows]


@app.get("/api/v1/admin/roles/{role_id}/permissions", tags=["administration"])
def admin_get_role_permissions(role_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    role = db.execute(text("SELECT company_id FROM roles WHERE id=:id"), {"id":role_id}).mappings().first()
    if not role: raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if role["company_id"] is None: require_platform_admin(claims)
    else: require_company_admin(db, claims, role["company_id"])
    rows = db.execute(text("""
        SELECT p.id,p.code,p.module_code,p.action,p.description
        FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id
        WHERE rp.role_id=:r ORDER BY p.module_code,p.action,p.code
    """), {"r":role_id}).mappings().all()
    return [dict(row) for row in rows]


@app.put("/api/v1/admin/roles/{role_id}/permissions", tags=["administration"])
def admin_set_role_permissions(role_id: UUID, permission_ids: list[UUID], db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    role = db.execute(text("SELECT company_id,is_system FROM roles WHERE id=:id"), {"id":role_id}).mappings().first()
    if not role: raise HTTPException(status_code=404, detail="Rol no encontrado.")
    if role["company_id"] is None: require_platform_admin(claims)
    else: require_company_admin(db, claims, role["company_id"])
    if role["is_system"]: raise HTTPException(status_code=409, detail="Los permisos de un rol del sistema no se pueden modificar.")
    unique_ids = list(dict.fromkeys(permission_ids))
    if unique_ids:
        found = db.execute(text("SELECT id FROM permissions WHERE id=ANY(CAST(:ids AS uuid[]))"), {"ids":unique_ids}).all()
        if len(found) != len(unique_ids): raise HTTPException(status_code=422, detail="La lista contiene permisos inexistentes.")
    try:
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:id"), {"id":role_id})
        for permission_id in unique_ids:
            db.execute(text("INSERT INTO role_permissions(role_id,permission_id) VALUES(:r,:p)"), {"r":role_id,"p":permission_id})
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudieron guardar los permisos del rol.") from exc
    return admin_get_role_permissions(role_id, db, claims)


@app.get("/api/v1/admin/memberships", tags=["administration"])
def admin_list_memberships(company_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company_admin(db, claims, company_id)
    rows = db.execute(text("""
        SELECT m.id,m.company_id,m.user_id,u.email,u.display_name,m.role_id,r.code AS role_code,r.name AS role_name,m.is_active,m.created_at
        FROM memberships m JOIN users u ON u.id=m.user_id JOIN roles r ON r.id=m.role_id
        WHERE m.company_id=:c ORDER BY u.email,r.name
    """), {"c":company_id}).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/admin/memberships", status_code=201, tags=["administration"])
def admin_create_membership(payload: MembershipCreate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_company_admin(db, claims, payload.company_id)
    role = db.execute(text("SELECT id FROM roles WHERE id=:r AND (company_id=:c OR company_id IS NULL)"), {"r":payload.role_id,"c":payload.company_id}).first()
    if not role: raise HTTPException(status_code=422, detail="El rol no pertenece a esta empresa.")
    try:
        row = db.execute(text("INSERT INTO memberships(company_id,user_id,role_id,is_active) VALUES(:company_id,:user_id,:role_id,:is_active) RETURNING id,company_id,user_id,role_id,is_active,created_at"), payload.model_dump()).mappings().first()
        db.commit(); return dict(row)
    except SQLAlchemyError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="No se pudo asignar el rol (membresía duplicada o usuario inválido).") from exc


@app.patch("/api/v1/admin/memberships/{membership_id}", tags=["administration"])
def admin_update_membership(membership_id: UUID, payload: MembershipUpdate, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current = db.execute(text("SELECT company_id FROM memberships WHERE id=:id"), {"id":membership_id}).mappings().first()
    if not current: raise HTTPException(status_code=404, detail="Membresía no encontrada.")
    require_company_admin(db, claims, current["company_id"])
    changes = {k:v for k,v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not changes: raise HTTPException(status_code=400, detail="Sin cambios para aplicar.")
    if "role_id" in changes and not db.execute(text("SELECT 1 FROM roles WHERE id=:r AND (company_id=:c OR company_id IS NULL)"), {"r":changes["role_id"],"c":current["company_id"]}).first():
        raise HTTPException(status_code=422, detail="El rol no pertenece a esta empresa.")
    assignments=",".join(f"{k}=:{k}" for k in changes); changes["id"]=membership_id
    row=db.execute(text(f"UPDATE memberships SET {assignments} WHERE id=:id RETURNING id,company_id,user_id,role_id,is_active,created_at"),changes).mappings().first()
    db.commit(); return dict(row)


@app.delete("/api/v1/admin/memberships/{membership_id}", status_code=204, tags=["administration"])
def admin_delete_membership(membership_id: UUID, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    current=db.execute(text("SELECT company_id FROM memberships WHERE id=:id"),{"id":membership_id}).mappings().first()
    if not current: raise HTTPException(status_code=404, detail="Membresía no encontrada.")
    require_company_admin(db,claims,current["company_id"])
    db.execute(text("DELETE FROM memberships WHERE id=:id"),{"id":membership_id}); db.commit()


@app.get("/api/v1/admin/document-types", tags=["maintenance"])
def maintenance_list_document_types(company_id: UUID | None = None, db: Session = Depends(get_db), claims: dict = Depends(require_claims)):
    require_platform_admin(claims)
    if company_id:
        rows=db.execute(text("SELECT id,company_id,code,name,category,description,prefix,requires_tax_id,is_active,created_at,updated_at FROM document_types WHERE company_id IS NULL OR company_id=:company_id ORDER BY category,code"),{"company_id":company_id}).mappings().all()
    else:
        rows=db.execute(text("SELECT id,company_id,code,name,category,description,prefix,requires_tax_id,is_active,created_at,updated_at FROM document_types ORDER BY category,code")).mappings().all()
    return [dict(row) for row in rows]


@app.post("/api/v1/admin/document-types", status_code=201, tags=["maintenance"])
def maintenance_create_document_type(payload: DocumentTypeCreate, db: Session=Depends(get_db), claims: dict=Depends(require_claims)):
    require_platform_admin(claims)
    if payload.company_id and not db.execute(text("SELECT 1 FROM companies WHERE id=:id"),{"id":payload.company_id}).first():
        raise HTTPException(status_code=404,detail="Empresa no encontrada.")
    try:
        row=db.execute(text("""
            INSERT INTO document_types(company_id,code,name,category,description,prefix,requires_tax_id,is_active)
            VALUES(:company_id,:code,:name,:category,:description,:prefix,:requires_tax_id,:is_active)
            RETURNING id,company_id,code,name,category,description,prefix,requires_tax_id,is_active,created_at,updated_at
        """),payload.model_dump()).mappings().first()
        db.execute(text("INSERT INTO audit_events(actor_user_id,actor_type,action,entity_type,entity_id) VALUES(:u,'user','maintenance.document_type.created','document_type',:id)"),{"u":claims.get("sub"),"id":str(row["id"])})
        db.commit();return dict(row)
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo crear el tipo; verifica código duplicado.") from exc


@app.patch("/api/v1/admin/document-types/{document_type_id}", tags=["maintenance"])
def maintenance_update_document_type(document_type_id: UUID,payload: DocumentTypeUpdate,db: Session=Depends(get_db),claims: dict=Depends(require_claims)):
    require_platform_admin(claims)
    changes=payload.model_dump(exclude_unset=True)
    if not changes:raise HTTPException(status_code=400,detail="Sin cambios para aplicar.")
    assignments=", ".join(f"{key}=:{key}" for key in changes);changes["id"]=document_type_id
    try:
        row=db.execute(text(f"UPDATE document_types SET {assignments},updated_at=now() WHERE id=:id RETURNING id,company_id,code,name,category,description,prefix,requires_tax_id,is_active,created_at,updated_at"),changes).mappings().first()
        if not row:raise HTTPException(status_code=404,detail="Tipo de documento no encontrado.")
        db.commit();return dict(row)
    except SQLAlchemyError as exc:
        db.rollback();raise HTTPException(status_code=409,detail="No se pudo actualizar el tipo de documento.") from exc


@app.delete("/api/v1/admin/document-types/{document_type_id}",status_code=204,tags=["maintenance"])
def maintenance_delete_document_type(document_type_id: UUID,db: Session=Depends(get_db),claims: dict=Depends(require_claims)):
    require_platform_admin(claims)
    result=db.execute(text("UPDATE document_types SET is_active=FALSE,updated_at=now() WHERE id=:id AND is_active=TRUE"),{"id":document_type_id})
    if not result.rowcount:raise HTTPException(status_code=404,detail="Tipo de documento activo no encontrado.")
    db.commit()
