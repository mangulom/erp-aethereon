# Aethereon ERP

ERP multisectorial, multiempresa y modular. El producto se construye de manera incremental: primero el shell, acceso, administración, identidad, auditoría y cimientos de datos; luego cada dominio se incorpora como microfrontend y microservicio independiente.

## Arquitectura acordada

- **Portal/shell:** Angular 19 + Tailwind CSS, puerto **4200**.
- **Microfrontends:** shell de carga e integra cada dominio de negocio como módulo frontend independiente. Configuración compartida en `frontend/public/assets/microfrontends.json`.
- **Microservicios:** servicios FastAPI/Python 3.11.8 independientes; puertos reservados desde **18001**.
- **Base de datos:** PostgreSQL. Esquema inicial relacional para identidad multiempresa, roles, usuarios, membresías y auditoría.
- **Comunicación:** HTTP/JSON versionado; no acoplar módulos mediante acceso directo a tablas de otro dominio. Cada servicio es propietario de sus datos.
- **IA:** transversal y gobernada. Un agente puede proponer/preparar operaciones, pero las acciones sensibles requieren permisos y aprobación humana.

### Puertos iniciales

| Aplicación | Puerto | Estado |
|---|---:|---|
| Angular shell | 4200 | base local, ejecución continua sujeta al proceso de la consola |
| Identidad y acceso (FastAPI) | 18001 | base local |
| Gobierno y configuración de plataforma (FastAPI) | 18002 | contrato reservado |
| Finanzas / contabilidad | 18003+ | reservado para fases siguientes |
| Ventas / CRM | 18004+ | reservado para fases siguientes |
| Compras / proveedores | 18005+ | reservado para fases siguientes |
| Inventario / almacenes | 18006+ | reservado para fases siguientes |

El mapa completo de servicios y puertos vive en `docs/architecture.md`. Los módulos aún no implementados se identifican como **planeados**, no como servicios ya operativos.

## Requisitos

- Node.js 20.19+ o 22.12+ y npm.
- Python 3.11.8.
- PostgreSQL 16+ (PostgreSQL 17 recomendado), escuchando en `localhost:15432` (puerto local de esta instalación; Docker publica `5432`).

## Estado del primer arranque

- El portal Angular sirve en `http://localhost:4200` y redirige al login después de la intro de 2 s.
- El login valida contra `/api/v1/auth/login`; requiere el microservicio de identidad activo.
- PostgreSQL de desarrollo está en `15432`; la app usa el rol dedicado `aethereon` mediante un `.env` privado.
- Acceso de evaluación (solo desarrollo): `admin@aethereon.pe`, con la contraseña temporal mostrada en la tarjeta del login; en PostgreSQL solo se guarda su hash Argon2id.
- Configura `backend/services/identity/.env` copiando `.env.example` y usando tu clave JWT privada para que el login llegue a PostgreSQL; nunca agregues ese `.env` al repositorio.
- El catálogo tiene 22 módulos planeados; el dashboard, identidad y configuración son las únicas partes funcionales iniciales. No hay aún remote microfrontends desplegables ni data empresarial falsa.
- Idioma predeterminado del shell: español. Usa el selector ES/EN del header; la preferencia queda guardada localmente.
- Footer global fijo: `Powered by Mauricio Antonio Angulo Martínez © 2026`.
- En dispositivos móviles, el menú lateral se despliega sobre el contenido; los grupos de navegación comienzan colapsados y se abren al tocarlos. La barra de desplazamiento del sidebar está oculta.

## Puesta en marcha

1. Crear PostgreSQL y una base vacía `aethereon_erp`.
2. Configura `.env` para tu PostgreSQL. La instalación local existente usa `localhost:15432`; Docker publica `localhost:15433` para evitar conflictos. Establece en `DATABASE_URL` el usuario de aplicación y en `POSTGRES_PASSWORD` una clave propia para el contenedor. Mantén la clave JWT aleatoria ya generada en `.env` y nunca la compartas.
3. Instalar dependencias con `npm run install:all` (`.npmrc` desactiva scripts ejecutables y acelera descargas en este entorno Windows). Si `frontend/node_modules` está incompleto, detén el servidor del shell y vuelve a ejecutar `npm install --prefix frontend --ignore-scripts --no-audit --no-fund --package-lock=false`.
4. Backend: `py -3.11 -m venv .venv`; activar `.venv`; `python -m pip install -r backend/services/identity/requirements.txt`.
5. Para PostgreSQL local en Windows (puerto `15432`), crea la base `aethereon_erp`, luego aplica `psql -h localhost -p 15432 -U postgres -d aethereon_erp -f database/migrations/001_identity.sql`. Conserva credenciales en `.env`; para otra instalación, no pongas la contraseña en la línea de comandos. Para Docker usa `docker compose up -d postgres`; su puerto es `15433` y aplica el esquema al inicializar un volumen nuevo. No reutilices la contraseña del clúster local.
6. `npm run dev:shell` inicia el shell en `http://localhost:4200` (no cerrar la consola mientras se desarrolla). Con PostgreSQL activo y `backend/services/identity/.env` configurado para `IDENTITY_PORT=18001`, inicia el API con `py -3.11 backend/run.py` o `npm run dev:identity`. La documentación está en `http://127.0.0.1:18001/docs`.

La cuenta temporal de demostración debe rotarse y eliminarse antes del despliegue en producción. No reutilices su contraseña ni la incluyas en el repositorio. Las empresas y membresías reales se crean después en el módulo de administración.
