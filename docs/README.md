> **v0.2:** El arranque por defecto `RUN_DESKTOP.bat` abre una base local SIN movimientos ni proyectos ficticios. Usa `RUN_CON_DATOS_DEMO.bat` para la anterior demo con datos falsos. Abre **Reglas y políticas** para distinguir validaciones de sistema y propuestas pendientes. Las cuentas temporales de prueba se crean en ambos modos.

> **Actualización v0.1.1 / carpeta compartida:** los archivos .bat usan `pushd` en vez de `cd /d`, por lo que pueden ejecutarse desde `\\VLUX\vlux\...`. Mientras la demo está abierta, manten la consola negra activa. En Windows los datos se guardan en `%LOCALAPPDATA%\VLUX\FinanceOS\vlux_local.sqlite3` para que ninguna instalación escriba SQLite en una carpeta de red. El hecho de compartir el ZIP **no** significa compartir datos; para eso se necesita la instalación posterior del backend en SQL Server.

# VLUX Finance OS — Desktop MVP 0.2

**Entregado para prueba LOCAL, no para producción financiera.** Paquete de aplicación en ventana de escritorio de Microsoft Edge (modo `--app`) + servidor Python HTTP local + SQLite. El front-end no requiere Node, npm ni conexión a Internet.

## 1. Arranque en Windows

1. Descomprime el ZIP en una carpeta propia (ej. `C:\VLUX-FinanceOS`).
2. Instala **Python 3.11+** en caso de no tenerlo (activa `Add Python to PATH`). No usa paquetes extra para la demo.
3. Da doble clic a **`RUN_DESKTOP.bat`** (sin precarga financiera). Abrirá una ventana propia de Edge sin barras del navegador, y una consola del servidor local (debe permanecer abierta).
4. Si falla la apertura automática, ejecuta `START_LOCAL_API.bat` y visita `http://127.0.0.1:8765`.
5. Usuarios iniciales ficticios: `ludwing@vlux.local` y `rodrigo@vlux.local`; contraseña **`DemoVlux2026!`**. Perfil de solo lectura: `consulta@vlux.local` con misma contraseña. Esa contraseña pública solo abre sesión en modo demo; en modo local se exige sustituirla en el primer acceso y producción la rechaza. **Nunca uses estas credenciales en producción.**

### Nota sobre compartirlo con compañeros

- Si mandas el ZIP a 3 personas, cada PC tendrá su **propia base de prueba SQLite**, por lo que NO comparten todavía transacciones.
- Para uso compartido: instalar el backend en un servidor, SQL Server y HTTPS; entonces todos abren la MISMA URL HTTPS en modo escritorio usando `INSTALAR_ACCESO_REMOTO.bat` o un acceso directo distribuido por TI.
- **No es un instalador `.exe` ni un Electron empaquetado**: esta primera versión es una aplicación de escritorio tipo Edge App, diseñada para probar rápidamente y validar requisitos sin dependencias de npm. Para distribución empresarial posterior se puede empaquetar con WebView2/Electron.

## 2. Funcionalidad implementada

| Módulo | Funciones |
|---|---|
| Acceso | Sesión segura con cookie HttpOnly, PBKDF2-SHA256, cierre de sesión, cambio de contraseña, solo lectura para invitados |
| Resumen | Saldos operativos, utilidad simple, tendencia mensual, reserva, punto de equilibrio ilustrativo |
| Movimientos | Ingreso, gasto y aportación de capital, concepto, categoría, referencia, proyecto, anulación auditada; autorización del segundo socio en gastos mayores a $1,000 y capital |
| Proyectos | Cartera, presupuesto y margen por movimientos atribuidos, estados |
| Planeación | Proyección de ingresos editables por 12 meses, tres escenarios (70%, 100%, 130%), punto de equilibrio estimado y presupuestos de remuneraciones |
| Pagos a socios | Solicitud propia, aprobación por el otro socio, registro de pago integrado a egresos |
| Dividendos | Propuesta trimestral, aprobación de ambos, reserva mínima, tope interno del 30% del resultado después de provisión hipotética, registro 50/50 y referencia contable |
| Reportes | CSV: movimientos, proyectos y auditoría; bitácora hasta 300 entradas |
| Configuración | Reserva, costos, planificación, remuneraciones, umbrales y usuarios lectores |

## 3. Reglas y límites financieros

- Participación **50/50** de Ludwing y Rodrigo, condicionada al acuerdo societario y vesting aplicable; no se edita desde la interfaz.
- La plantilla financiera arranca con $8,000 MXN de gastos fijos, 40% costos variables, 20% provisión fiscal **solo como hipótesis de planificación**, y $96,000 MXN como objetivo de reserva. No representan las finanzas reales.
- Todos los importes están almacenados como **centavos enteros** para no perder precisión.
- La app separa aportación de capital e ingreso, y el reparto de dividendos no se contabiliza como gasto del resultado operativo.
- Los saldos reflejan **movimientos registrados**, no bancos sincronizados ni contabilidad oficial. IVA por pagar, impuestos, pasivos, nómina, obligaciones de contratos pendientes y reservas restringidas **no se concilian automáticamente**.
- No usar propuesta/dividendo como prueba de que existen utilidades contables distribuibles. Requiere aprobación de estados, acta, conciliaciones y determinación fiscal del contador.
- El modelo de remuneración es un **flujo de control administrativo**, no genera CFDI, timbra nóminas ni realiza transferencias bancarias.
- Los umbrales de facturación y remuneración en Planeación son **alertas/modelos de decisión**: la validación estricta de dos o tres meses consecutivos de ingresos y reservas aún no está automatizada en la autorización de pagos.
- El punto de equilibrio es una **estimación**, calculada a partir de los costos fijos y variables configurados, no de costos totales tomados automáticamente de la base.
- Las comisiones a colaboradores se registran como gastos de proyecto; este MVP no calcula todavía las complejas reglas de contratos de terceros.

## 4. Conexión a SQL Server

El navegador en modo escritorio NUNCA debe conectarse directamente a SQL Server; la arquitectura es:

```
PC Ludwing  ─┐
PC Rodrigo  ─┼── HTTPS (Edge app) ── Proxy TLS ── API VLUX en servidor ── ODBC 18 ── SQL Server
PC Equipo    ┘                            (127.0.0.1:8765)
```

1. Crear o seleccionar base `VLUX_Finanzas` **dedicada**, no reutilizar la BD ERP/CRM ni tablas `InnovaxAutocontrol`.
2. Instalar Python 3.11+ y `pyodbc` en servidor, junto con **Microsoft ODBC Driver 18 for SQL Server**.
3. La cuenta de servicio debe tener acceso mínimo necesario a las tablas `dbo.vlux_*` de la BD dedicada. Es preferible autenticación integrada de Windows si resulta viable.
4. Configurar variables de entorno de **`.env.production.example`** en el servicio del servidor, reemplazando valores de ejemplo. El programa lee variables **del proceso** y no carga automáticamente `.env`.
5. El backend crea sus tablas al iniciar; hacer primero backup/snapshot y revisar permisos. **Nunca correr migraciones a ciegas sobre una BD ya existente.**
6. Con proxy IIS/ARR, Caddy o Nginx, publicar HTTPS válido que reenvíe a `127.0.0.1:8765`; preservar cabeceras `Host`, `Origin`, `Cookie`, `Set-Cookie`, y evitar caché de API.
7. `VLUX_PUBLIC_ORIGIN` debe coincidir con la URL HTTPS visible al usuario; cookies seguras y `SameSite=Strict` en producción.
8. Crear primera cuenta con `VLUX_BOOTSTRAP_ADMIN_EMAIL` / `VLUX_BOOTSTRAP_ADMIN_PASSWORD` (14+ caracteres). **Retirar la contraseña de arranque de la configuración una vez creada la cuenta**, reiniciar y cambiarla en aplicación. Esta primera cuenta será socio. Para incorporar al segundo socio bajo supervisión, el DBA ejecutará `python backend/provision_second_partner.py` en la consola del servidor, con aprobación societaria previa.
9. Configurar backups SQL Server (full/diff/log según recovery model), monitoreo, rotación de logs y pruebas de recuperación con su DBA. Nunca copiar archivos .mdf en caliente.
10. No abrir puerto 1433 de SQL Server a las estaciones. No publicar el 8765 a Internet: solo proxy HTTPS.

**Situación del soporte SQL Server:** el adaptador, el DDL y las consultas parametrizadas están implementadas, **pero no se ha probado contra un SQL Server real**. Es obligatorio realizar pruebas de integración y validación de esquema, migración, usuarios concurrentes y restauración antes de implantarlo.

## 5. Seguridad y pendientes ANTES de producción

- Solicitar al DBA cuenta de servicio de menor privilegio, backups y validación de DDL.
- Formalizar alta de segundo socio con acuerdo y consola supervisada; implementar recuperación MFA, restablecimiento de contraseñas y bloqueo de cuentas.
- Agregar control de concurrencia y transacciones idempotentes con pruebas SQL Server reales para operaciones financieras críticas.
- Añadir conciliación bancaria, cuentas por cobrar/pagar, IVA, CFDI y provisiones fiscales calculadas por el contador.
- Adjuntos y comprobantes de pagos con almacenamiento seguro, antivirus, retención y permisos.
- Bitácora inalterable/apéndice protegido y sistema de permisos de granularidad por usuario.
- Pruebas de seguridad, controles de ingreso de red, parches y monitoreo, y homologación con política de datos personales.
- Reconciliar pagado vs comprometido y calcular utilidades acumuladas de ejercicios contables cerrados.

## 6. Prueba automatizada y respaldo

En Windows: doble clic en `PROBAR_SISTEMA.bat`. Alternativa multiplataforma: `python tests/smoke_test.py`. La prueba usa su propia base temporal y no altera tus movimientos.

### Copia de seguridad local

```bat
py -3 backend\backup_sqlite.py
```

Por defecto guarda copia consistente en `storage/backups`. La demo funciona sin conectividad. Puedes borrar `storage/vlux_local.sqlite3` (con el servidor apagado) para reiniciar **datos de prueba**, pero se borrarán registros locales propios que hayas creado.

## 7. Autoría, alcance y notas técnicas

- Back-end: Python 3.11+ stdlib `http.server`, SQLite (demo) y adaptador opcional `pyodbc` (SQL Server).
- Front-end: HTML/CSS/JavaScript local con sesiones basadas en cookies.
- Escritorio: Microsoft Edge modo aplicación, una ventana dedicada sin interfaz de navegación. Windows 10/11.
- Entradas sensibles no se registran en los logs HTTP; la base demo queda en el equipo local.
- Estado: **MVP para evaluación funcional**. No debe usarse como ERP ni como sistema contable oficial sin mejoras y revisión legal/fiscal.
