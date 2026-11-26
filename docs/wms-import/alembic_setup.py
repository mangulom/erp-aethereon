"""
============================================================
WMS REPSOL - ALEMBIC CONFIGURATION
Setup de migraciones de base de datos
============================================================
Comandos:
  alembic init migrations        # Inicializar (ya hecho)
  alembic revision --autogenerate -m "descripcion"  # Generar migración
  alembic upgrade head           # Aplicar todas las migraciones
  alembic downgrade -1           # Revertir última migración
  alembic history                # Ver historial
============================================================
"""

# ── alembic.ini ──────────────────────────────────────────
ALEMBIC_INI = """
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = postgresql://postgres:3mlx440*@localhost:15432/wms_repsol

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

# ── migrations/env.py ────────────────────────────────────
ENV_PY = '''
"""Alembic Environment Configuration"""
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.all_models import Base
from database import DATABASE_URL

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in offline mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in online mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True, compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

# ── migrations/versions/001_initial.py ───────────────────
INITIAL_MIGRATION = '''
"""Initial migration - Create all WMS tables

Revision ID: 001_initial
Revises:
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ── Plantas ──
    op.create_table('plantas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo', sa.String(20), unique=True, nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('direccion', sa.Text()),
        sa.Column('activa', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Usuarios ──
    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('email', sa.String(100), unique=True),
        sa.Column('rol', sa.String(20), nullable=False, default='operador'),
        sa.Column('activo', sa.Boolean(), default=True),
        sa.Column('ultimo_login', sa.DateTime(timezone=True)),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_usuarios_username', 'usuarios', ['username'])

    # ── Categorías ──
    op.create_table('categorias',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('codigo', sa.String(20), unique=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('categorias.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Materiales ──
    op.create_table('materiales',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo_sap', sa.String(20), unique=True, nullable=False),
        sa.Column('nombre', sa.String(200), nullable=False),
        sa.Column('descripcion', sa.Text()),
        sa.Column('categoria_id', sa.Integer(), sa.ForeignKey('categorias.id')),
        sa.Column('unidad_medida', sa.String(10), default='UN'),
        sa.Column('barcode', sa.String(50)),
        sa.Column('es_peligroso', sa.Boolean(), default=False),
        sa.Column('stock_minimo', sa.Float()),
        sa.Column('stock_maximo', sa.Float()),
        sa.Column('punto_reorden', sa.Float()),
        sa.Column('costo_promedio', sa.Numeric(12, 2)),
        sa.Column('activo', sa.Boolean(), default=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_materiales_codigo_sap', 'materiales', ['codigo_sap'])
    op.create_index('idx_materiales_barcode', 'materiales', ['barcode'])

    # ── Almacenes ──
    op.create_table('almacenes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('planta_id', sa.Integer(), sa.ForeignKey('plantas.id'), nullable=False),
        sa.Column('codigo', sa.String(20), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('tipo', sa.String(50)),
        sa.Column('capacidad_total', sa.Float()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Ubicaciones ──
    op.create_table('ubicaciones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('almacen_id', sa.Integer(), sa.ForeignKey('almacenes.id'), nullable=False),
        sa.Column('codigo', sa.String(30), nullable=False),
        sa.Column('zona', sa.String(10)),
        sa.Column('pasillo', sa.String(10)),
        sa.Column('nivel', sa.String(10)),
        sa.Column('posicion', sa.String(10)),
        sa.Column('capacidad', sa.Float()),
        sa.Column('bloqueada', sa.Boolean(), default=False),
        sa.Column('tipo', sa.String(30)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_ubicaciones_codigo', 'ubicaciones', ['codigo'])

    # ── Lotes ──
    op.create_table('lotes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('numero', sa.String(50), unique=True, nullable=False),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materiales.id'), nullable=False),
        sa.Column('fecha_fabricacion', sa.Date()),
        sa.Column('fecha_vencimiento', sa.Date()),
        sa.Column('fecha_ingreso', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('proveedor', sa.String(200)),
        sa.Column('cantidad_inicial', sa.Float()),
        sa.Column('estado', sa.String(20), default='disponible'),
        sa.Column('motivo_estado', sa.String(200)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_lotes_numero', 'lotes', ['numero'])
    op.create_index('idx_lotes_vencimiento', 'lotes', ['fecha_vencimiento'])

    # ── Stock ──
    op.create_table('stock',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materiales.id'), nullable=False),
        sa.Column('ubicacion_id', sa.Integer(), sa.ForeignKey('ubicaciones.id'), nullable=False),
        sa.Column('lote_id', sa.Integer(), sa.ForeignKey('lotes.id')),
        sa.Column('cantidad', sa.Float(), nullable=False, default=0),
        sa.Column('cantidad_reservada', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_stock_material_ubicacion', 'stock', ['material_id', 'ubicacion_id'])

    # ── Movimientos ──
    op.create_table('movimientos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.String(30), nullable=False),
        sa.Column('material_id', sa.Integer(), sa.ForeignKey('materiales.id'), nullable=False),
        sa.Column('ubicacion_origen_id', sa.Integer(), sa.ForeignKey('ubicaciones.id')),
        sa.Column('ubicacion_destino_id', sa.Integer(), sa.ForeignKey('ubicaciones.id')),
        sa.Column('lote_id', sa.Integer(), sa.ForeignKey('lotes.id')),
        sa.Column('cantidad', sa.Float(), nullable=False),
        sa.Column('motivo', sa.String(200)),
        sa.Column('referencia', sa.String(50)),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id')),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_movimientos_fecha', 'movimientos', ['fecha'])

    print("\\n  Migration 001_initial: All core tables created successfully")


def downgrade():
    tables = ['movimientos', 'stock', 'lotes', 'ubicaciones', 'almacenes',
              'materiales', 'categorias', 'usuarios', 'plantas']
    for t in tables:
        op.drop_table(t)
'''


# ═══════════════════════════════════════════════════════════════
# Escribir archivos
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))

    # alembic.ini
    with open(os.path.join(base, "..", "alembic.ini"), "w") as f:
        f.write(ALEMBIC_INI.strip())

    # migrations/env.py
    os.makedirs(os.path.join(base, "versions"), exist_ok=True)
    with open(os.path.join(base, "env.py"), "w") as f:
        f.write(ENV_PY.strip())

    # Initial migration
    with open(os.path.join(base, "versions", "001_initial.py"), "w") as f:
        f.write(INITIAL_MIGRATION.strip())

    print("Alembic configuration generated successfully")
