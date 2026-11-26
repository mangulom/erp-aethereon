"""
============================================================
WMS REPSOL - SQLALCHEMY MODELS
35+ tablas PostgreSQL para el sistema completo
============================================================
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    Date, ForeignKey, Enum, JSON, Numeric, Index, UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


# ═══════════════════════════════════════════════════════════════
# MIXINS
# ═══════════════════════════════════════════════════════════════
class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════
class RolEnum(enum.Enum):
    admin = "admin"
    supervisor = "supervisor"
    operador = "operador"
    inspector = "inspector"
    consulta = "consulta"

class EstadoLote(enum.Enum):
    disponible = "disponible"
    cuarentena = "cuarentena"
    bloqueado = "bloqueado"
    rechazado = "rechazado"
    vencido = "vencido"

class EstadoRecepcion(enum.Enum):
    borrador = "borrador"
    en_proceso = "en_proceso"
    inspeccion = "inspeccion"
    confirmada = "confirmada"
    gr_generada = "gr_generada"
    cancelada = "cancelada"

class EstadoDespacho(enum.Enum):
    pendiente = "pendiente"
    picking = "picking"
    packing = "packing"
    carga = "carga"
    despachado = "despachado"
    entregado = "entregado"
    cancelado = "cancelado"

class TipoMovimiento(enum.Enum):
    entrada = "entrada"
    salida = "salida"
    transferencia = "transferencia"
    ajuste_positivo = "ajuste_positivo"
    ajuste_negativo = "ajuste_negativo"
    devolucion = "devolucion"

class PrioridadDespacho(enum.Enum):
    urgente = "urgente"
    alta = "alta"
    normal = "normal"
    baja = "baja"


# ═══════════════════════════════════════════════════════════════
# 1. AUTH & USERS
# ═══════════════════════════════════════════════════════════════
class Planta(Base, TimestampMixin):
    __tablename__ = "plantas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    direccion = Column(Text)
    activa = Column(Boolean, default=True)
    almacenes = relationship("Almacen", back_populates="planta")

class Usuario(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    rol = Column(Enum(RolEnum), nullable=False, default=RolEnum.operador)
    activo = Column(Boolean, default=True)
    ultimo_login = Column(DateTime(timezone=True))
    plantas = relationship("UsuarioPlanta", back_populates="usuario")

class UsuarioPlanta(Base):
    __tablename__ = "usuario_plantas"
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    planta_id = Column(Integer, ForeignKey("plantas.id"), nullable=False)
    usuario = relationship("Usuario", back_populates="plantas")
    __table_args__ = (UniqueConstraint('usuario_id', 'planta_id'),)

class Permiso(Base):
    __tablename__ = "permisos"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(50), unique=True, nullable=False)
    descripcion = Column(String(200))
    modulo = Column(String(50))

class RolPermiso(Base):
    __tablename__ = "rol_permisos"
    id = Column(Integer, primary_key=True)
    rol = Column(Enum(RolEnum), nullable=False)
    permiso_id = Column(Integer, ForeignKey("permisos.id"), nullable=False)


# ═══════════════════════════════════════════════════════════════
# 2. MATERIALES
# ═══════════════════════════════════════════════════════════════
class Categoria(Base, TimestampMixin):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    codigo = Column(String(20), unique=True)
    parent_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    materiales = relationship("Material", back_populates="categoria_rel")

class Material(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "materiales"
    id = Column(Integer, primary_key=True)
    codigo_sap = Column(String(20), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    unidad_medida = Column(String(10), default="UN")
    peso_unitario = Column(Float)
    volumen_unitario = Column(Float)
    barcode = Column(String(50), index=True)
    es_peligroso = Column(Boolean, default=False)
    stock_minimo = Column(Float)
    stock_maximo = Column(Float)
    punto_reorden = Column(Float)
    costo_promedio = Column(Numeric(12, 2))
    activo = Column(Boolean, default=True)
    categoria_rel = relationship("Categoria", back_populates="materiales")
    lotes = relationship("Lote", back_populates="material")
    stocks = relationship("Stock", back_populates="material")
    __table_args__ = (
        Index('idx_material_nombre_trgm', 'nombre', postgresql_using='gin',
              postgresql_ops={'nombre': 'gin_trgm_ops'}),
    )


# ═══════════════════════════════════════════════════════════════
# 3. INVENTARIO
# ═══════════════════════════════════════════════════════════════
class Almacen(Base, TimestampMixin):
    __tablename__ = "almacenes"
    id = Column(Integer, primary_key=True)
    planta_id = Column(Integer, ForeignKey("plantas.id"), nullable=False)
    codigo = Column(String(20), nullable=False)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(50))  # general, matpel, refrigerado, cuarentena
    capacidad_total = Column(Float)
    planta = relationship("Planta", back_populates="almacenes")
    ubicaciones = relationship("Ubicacion", back_populates="almacen")

class Ubicacion(Base, TimestampMixin):
    __tablename__ = "ubicaciones"
    id = Column(Integer, primary_key=True)
    almacen_id = Column(Integer, ForeignKey("almacenes.id"), nullable=False)
    codigo = Column(String(30), nullable=False, index=True)
    zona = Column(String(10))
    pasillo = Column(String(10))
    estante = Column(String(10))
    nivel = Column(String(10))
    posicion = Column(String(10))
    capacidad = Column(Float)
    unidad_capacidad = Column(String(10), default="PAL")
    bloqueada = Column(Boolean, default=False)
    motivo_bloqueo = Column(String(200))
    tipo = Column(String(30))  # rack, piso, bulk, picking
    almacen = relationship("Almacen", back_populates="ubicaciones")
    __table_args__ = (UniqueConstraint('almacen_id', 'codigo'),)

class Stock(Base, TimestampMixin):
    __tablename__ = "stock"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=True)
    cantidad = Column(Float, nullable=False, default=0)
    cantidad_reservada = Column(Float, default=0)
    material = relationship("Material", back_populates="stocks")
    __table_args__ = (
        Index('idx_stock_material_ubicacion', 'material_id', 'ubicacion_id'),
        CheckConstraint('cantidad >= 0', name='chk_stock_positivo'),
    )

class Movimiento(Base, TimestampMixin):
    __tablename__ = "movimientos"
    id = Column(Integer, primary_key=True)
    tipo = Column(Enum(TipoMovimiento), nullable=False)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    ubicacion_origen_id = Column(Integer, ForeignKey("ubicaciones.id"))
    ubicacion_destino_id = Column(Integer, ForeignKey("ubicaciones.id"))
    lote_id = Column(Integer, ForeignKey("lotes.id"))
    cantidad = Column(Float, nullable=False)
    motivo = Column(String(200))
    referencia = Column(String(50))  # recepcion_id, despacho_id, etc.
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index('idx_movimiento_fecha', 'fecha'),)

class Ajuste(Base, TimestampMixin):
    __tablename__ = "ajustes"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"), nullable=False)
    cantidad_sistema = Column(Float, nullable=False)
    cantidad_real = Column(Float, nullable=False)
    diferencia = Column(Float, nullable=False)
    motivo = Column(String(200), nullable=False)
    estado = Column(String(20), default="pendiente")  # pendiente, aprobado, rechazado
    aprobado_por = Column(Integer, ForeignKey("usuarios.id"))
    fecha_aprobacion = Column(DateTime(timezone=True))
    creado_por = Column(Integer, ForeignKey("usuarios.id"))

class ConteoCiclico(Base, TimestampMixin):
    __tablename__ = "conteos_ciclicos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100))
    planta_id = Column(Integer, ForeignKey("plantas.id"))
    estado = Column(String(20), default="creado")
    asignado_a = Column(Integer, ForeignKey("usuarios.id"))
    fecha_inicio = Column(DateTime(timezone=True))
    fecha_cierre = Column(DateTime(timezone=True))
    lineas = relationship("ConteoLinea", back_populates="conteo")

class ConteoLinea(Base, TimestampMixin):
    __tablename__ = "conteo_lineas"
    id = Column(Integer, primary_key=True)
    conteo_id = Column(Integer, ForeignKey("conteos_ciclicos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materiales.id"))
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"))
    stock_sistema = Column(Float)
    stock_contado = Column(Float)
    diferencia = Column(Float)
    conteo = relationship("ConteoCiclico", back_populates="lineas")


# ═══════════════════════════════════════════════════════════════
# 4. LOTES
# ═══════════════════════════════════════════════════════════════
class Lote(Base, TimestampMixin):
    __tablename__ = "lotes"
    id = Column(Integer, primary_key=True)
    numero = Column(String(50), unique=True, nullable=False, index=True)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    fecha_fabricacion = Column(Date)
    fecha_vencimiento = Column(Date, index=True)
    fecha_ingreso = Column(DateTime(timezone=True), server_default=func.now())
    proveedor = Column(String(200))
    cantidad_inicial = Column(Float)
    estado = Column(Enum(EstadoLote), default=EstadoLote.disponible)
    motivo_estado = Column(String(200))
    material = relationship("Material", back_populates="lotes")
    inspecciones = relationship("InspeccionLote", back_populates="lote")
    __table_args__ = (Index('idx_lote_vencimiento', 'fecha_vencimiento'),)

class InspeccionLote(Base, TimestampMixin):
    __tablename__ = "inspecciones_lotes"
    id = Column(Integer, primary_key=True)
    lote_id = Column(Integer, ForeignKey("lotes.id"), nullable=False)
    resultado = Column(String(20))  # aprobado, rechazado, cuarentena
    criterios = Column(JSON)
    observaciones = Column(Text)
    inspector_id = Column(Integer, ForeignKey("usuarios.id"))
    lote = relationship("Lote", back_populates="inspecciones")


# ═══════════════════════════════════════════════════════════════
# 5. RECEPCIONES
# ═══════════════════════════════════════════════════════════════
class Recepcion(Base, TimestampMixin):
    __tablename__ = "recepciones"
    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, nullable=False, index=True)
    orden_compra = Column(String(30), index=True)
    proveedor_id = Column(Integer, ForeignKey("proveedores.id"))
    planta_id = Column(Integer, ForeignKey("plantas.id"), nullable=False)
    almacen_id = Column(Integer, ForeignKey("almacenes.id"))
    tipo = Column(String(20), default="orden_compra")
    estado = Column(Enum(EstadoRecepcion), default=EstadoRecepcion.borrador)
    fecha = Column(DateTime(timezone=True), server_default=func.now())
    documento_sap = Column(String(20))
    observaciones = Column(Text)
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    lineas = relationship("RecepcionLinea", back_populates="recepcion")

class RecepcionLinea(Base, TimestampMixin):
    __tablename__ = "recepcion_lineas"
    id = Column(Integer, primary_key=True)
    recepcion_id = Column(Integer, ForeignKey("recepciones.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    cantidad_esperada = Column(Float)
    cantidad_recibida = Column(Float)
    lote_id = Column(Integer, ForeignKey("lotes.id"))
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"))
    resultado_inspeccion = Column(String(20))
    observaciones = Column(Text)
    recepcion = relationship("Recepcion", back_populates="lineas")

class Proveedor(Base, TimestampMixin):
    __tablename__ = "proveedores"
    id = Column(Integer, primary_key=True)
    ruc = Column(String(11), unique=True, index=True)
    razon_social = Column(String(200), nullable=False)
    direccion = Column(Text)
    contacto = Column(String(100))
    telefono = Column(String(20))
    email = Column(String(100))
    activo = Column(Boolean, default=True)


# ═══════════════════════════════════════════════════════════════
# 6. DESPACHOS
# ═══════════════════════════════════════════════════════════════
class Despacho(Base, TimestampMixin):
    __tablename__ = "despachos"
    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, nullable=False, index=True)
    pedido_sap = Column(String(30), index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    planta_id = Column(Integer, ForeignKey("plantas.id"), nullable=False)
    almacen_id = Column(Integer, ForeignKey("almacenes.id"))
    prioridad = Column(Enum(PrioridadDespacho), default=PrioridadDespacho.normal)
    estado = Column(Enum(EstadoDespacho), default=EstadoDespacho.pendiente)
    fecha_requerida = Column(Date)
    fecha_despacho = Column(DateTime(timezone=True))
    destino = Column(String(200))
    documento_sap = Column(String(20))
    transportista = Column(String(200))
    conductor = Column(String(100))
    placa = Column(String(20))
    precintos = Column(String(100))
    creado_por = Column(Integer, ForeignKey("usuarios.id"))
    lineas = relationship("DespachoLinea", back_populates="despacho")

class DespachoLinea(Base, TimestampMixin):
    __tablename__ = "despacho_lineas"
    id = Column(Integer, primary_key=True)
    despacho_id = Column(Integer, ForeignKey("despachos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    cantidad_solicitada = Column(Float, nullable=False)
    cantidad_pickeada = Column(Float, default=0)
    lote_id = Column(Integer, ForeignKey("lotes.id"))
    ubicacion_id = Column(Integer, ForeignKey("ubicaciones.id"))
    estado = Column(String(20), default="pendiente")
    operador_id = Column(Integer, ForeignKey("usuarios.id"))
    despacho = relationship("Despacho", back_populates="lineas")

class Cliente(Base, TimestampMixin):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True)
    ruc = Column(String(11), unique=True, index=True)
    razon_social = Column(String(200), nullable=False)
    direccion = Column(Text)
    activo = Column(Boolean, default=True)


# ═══════════════════════════════════════════════════════════════
# 7. MATPEL / IQBF
# ═══════════════════════════════════════════════════════════════
class MaterialPeligroso(Base, TimestampMixin):
    __tablename__ = "materiales_peligrosos"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materiales.id"), unique=True, nullable=False)
    numero_onu = Column(String(10), nullable=False)
    clase_onu = Column(Integer, nullable=False)
    division = Column(String(10))
    grupo_embalaje = Column(String(5))
    nombre_tecnico = Column(String(200))
    es_iqbf = Column(Boolean, default=False)
    codigo_iqbf = Column(String(20))
    pictogramas_sga = Column(JSON)
    frases_h = Column(JSON)
    frases_p = Column(JSON)
    punto_inflamacion = Column(Float)
    epp_requerido = Column(JSON)
    condiciones_almacenamiento = Column(Text)

class MovimientoIQBF(Base, TimestampMixin):
    __tablename__ = "movimientos_iqbf"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    tipo_operacion = Column(String(20), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    unidad = Column(String(10), nullable=False)
    tercero_ruc = Column(String(11))
    tercero_nombre = Column(String(200))
    numero_guia = Column(String(30))
    autorizacion_sunat = Column(String(30))
    fecha = Column(DateTime(timezone=True), server_default=func.now())

class IncidenteMatpel(Base, TimestampMixin):
    __tablename__ = "incidentes_matpel"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materiales.id"))
    planta_id = Column(Integer, ForeignKey("plantas.id"))
    tipo = Column(String(50))
    descripcion = Column(Text, nullable=False)
    severidad = Column(String(20))
    acciones_tomadas = Column(Text)
    reportado_por = Column(Integer, ForeignKey("usuarios.id"))
    fecha = Column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════════
# 8. SAP INTEGRATION
# ═══════════════════════════════════════════════════════════════
class TransaccionSAP(Base, TimestampMixin):
    __tablename__ = "transacciones_sap"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(30), nullable=False)  # goods_receipt, goods_issue, transfer
    referencia_wms = Column(String(50))  # recepcion_id o despacho_id
    documento_sap = Column(String(20))
    estado = Column(String(20), default="pendiente")  # pendiente, procesado, error
    payload = Column(JSON)
    respuesta_sap = Column(JSON)
    error_message = Column(Text)
    intentos = Column(Integer, default=0)
    fecha_envio = Column(DateTime(timezone=True))
    fecha_respuesta = Column(DateTime(timezone=True))

class SyncLog(Base, TimestampMixin):
    __tablename__ = "sync_logs"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(30), nullable=False)
    direccion = Column(String(10))  # sap_to_wms, wms_to_sap
    registros_procesados = Column(Integer, default=0)
    registros_creados = Column(Integer, default=0)
    registros_actualizados = Column(Integer, default=0)
    errores = Column(Integer, default=0)
    detalle_errores = Column(JSON)
    duracion_ms = Column(Integer)


# ═══════════════════════════════════════════════════════════════
# 9. MOTOR IA
# ═══════════════════════════════════════════════════════════════
class ModeloIA(Base, TimestampMixin):
    __tablename__ = "modelos_ia"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    tipo = Column(String(50))  # time_series, anomaly_detection, optimization
    version = Column(String(20))
    precision = Column(Float)
    parametros = Column(JSON)
    estado = Column(String(20), default="activo")
    ultimo_entrenamiento = Column(DateTime(timezone=True))

class PrediccionDemanda(Base, TimestampMixin):
    __tablename__ = "predicciones_demanda"
    id = Column(Integer, primary_key=True)
    modelo_id = Column(Integer, ForeignKey("modelos_ia.id"))
    material_id = Column(Integer, ForeignKey("materiales.id"), nullable=False)
    planta_id = Column(Integer, ForeignKey("plantas.id"))
    fecha_prediccion = Column(Date, nullable=False)
    cantidad_predicha = Column(Float, nullable=False)
    limite_inferior = Column(Float)
    limite_superior = Column(Float)
    nivel_confianza = Column(Float, default=0.95)

class Anomalia(Base, TimestampMixin):
    __tablename__ = "anomalias"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(30))  # stock, movimiento, consumo
    material_id = Column(Integer, ForeignKey("materiales.id"))
    planta_id = Column(Integer, ForeignKey("plantas.id"))
    severidad = Column(String(20))  # baja, media, alta, critica
    descripcion = Column(Text)
    datos_anomalia = Column(JSON)
    resuelta = Column(Boolean, default=False)
    resuelta_por = Column(Integer, ForeignKey("usuarios.id"))
    fecha_resolucion = Column(DateTime(timezone=True))


# ═══════════════════════════════════════════════════════════════
# 10. CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════
class Configuracion(Base, TimestampMixin):
    __tablename__ = "configuraciones"
    id = Column(Integer, primary_key=True)
    clave = Column(String(100), unique=True, nullable=False)
    valor = Column(Text)
    tipo = Column(String(20))  # string, int, float, bool, json
    descripcion = Column(String(200))
    modulo = Column(String(50))
