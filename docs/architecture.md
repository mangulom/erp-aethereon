# Arquitectura y límites de dominio

## Shell y microfrontends

El shell en `localhost:4200` posee navegación, sesión del navegador, permisos de presentación y el contrato común de UI. El registro en `frontend/public/assets/microfrontends.json` expone rutas, etiqueta, puerto de desarrollo y estado de cada módulo. Primera implementación: módulos lazy del shell. Al evolucionar a despliegues independientes, publicar los módulos como remotes Angular y cargarlos de forma lazy, manteniendo el catálogo/contrato y la autenticación por OIDC/token. No simular remotes antes de que tengan artefactos reales.

Una futura topología Module Federation requiere incorporar un builder compatible y fijar la versión mayor Angular de host/remotes conjuntamente. El punto de extensión y puertos ya están reservados; no se agrega un plugin que comprometa Angular 19 antes de validar compatibilidad.

## Microservicios Python

Cada servicio expone `/api/v1/...`, `/health/live` y `/health/ready`, empaqueta sus dependencias y conserva la propiedad de sus tablas. La identidad firma JWT de acceso (no persiste credenciales sensibles en el shell). Ningún módulo puede ejecutar SQL directo sobre las tablas de otro dominio. Las operaciones interdominio se coordinan mediante APIs versionadas o eventos idempotentes; el bus (RabbitMQ/Kafka) se elegirá al justificarlo.

| Puerto | Servicio | Dominio | Madurez |
|---:|---|---|---|
| 18001 | identity | usuarios, roles, empresas, membresías, login | base implementable |
| 18002 | platform | configuración, registro de módulos, health agregado | reservado; contrato en `backend/services/platform/README.md` |
| 18003 | finance | finanzas y tesorería | reservado |
| 18004 | accounting | contabilidad y tributación Perú | reservado |
| 18005 | sales | ventas y CRM | reservado |
| 18006 | procurement | compras y proveedores | reservado |
| 18007 | inventory | inventarios y almacenes | reservado |
| 18008 | logistics | logística y distribución | reservado |
| 18009 | people | RR. HH. y talento | reservado |
| 18010 | payroll | nómina Perú | reservado |
| 18011 | manufacturing | producción y MRP | reservado |
| 18012 | projects | proyectos | reservado |
| 18013 | maintenance | mantenimiento y activos | reservado |
| 18014 | quality | calidad y CAPA | reservado |
| 18015 | safety | seguridad y salud ocupacional | reservado |
| 18016 | legal | legal y cumplimiento | reservado |
| 18017 | documents | gestión documental | reservado |
| 18018 | support | atención posventa | reservado |
| 18019 | analytics | BI y analítica | reservado |
| 18020 | commerce | comercio electrónico y POS | reservado |
| 18021 | innovation | I+D+i | reservado |
| 18022 | ai-command | IA, agentes y automatización | reservado; con auditoría y aprobaciones |

El número de puerto asignado a un servicio es estable en desarrollo. Un módulo que necesite varios servicios usa puertos adicionales a partir de 18023; nunca comparte puerto ni esquema de propiedad con el shell.

## Seguridad y datos

- PostgreSQL aloja esquemas por dominio al inicio; dominios desacoplados pueden separarse a bases independientes sin cambiar el contrato HTTP/eventos.
- Aislamiento multiempresa validado en backend en todas las consultas y operaciones; `empresa_id` nunca se considera confiable si viene solo del cliente.
- Contraseñas Argon2id; tokens JWT firmados y corta duración; secreto por entorno, cookies/tokens protegidos según el flujo OIDC final.
- Roles y permisos por acción, entidad y empresa; mínimo privilegio.
- Auditoría inmutable lógica: actor, empresa, acción, entidad, fecha y request id; no registrar secretos ni datos sensibles completos.
- Facturas, asientos, pagos, nómina y órdenes relevantes requieren una autorización explícita. Las propuestas de IA no son transacciones aprobadas.
- Configuración/secretos solo mediante entorno; secretos reales nunca se guardan en Git.

## Etapas

1. **Fundación:** shell, identidad, administración, auditoría, PostgreSQL y CI.
2. **Núcleo transaccional:** ventas, compras, inventario, finanzas y contabilidad Perú.
3. **Operación:** personas/nómina, proyectos, logística, producción, activos y calidad.
4. **Inteligencia:** BI, AI Command Center, documentos, previsión y agentes con controles humanos.
5. **Ecosistema:** comercio electrónico, conectores, innovación y despliegue distribuido.
