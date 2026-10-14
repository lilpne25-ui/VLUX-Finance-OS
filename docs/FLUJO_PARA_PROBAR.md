# Prueba guiada (sin dinero real)

## Recomendación

Primero ejecutar `PROBAR_SISTEMA.bat`; ejecuta pruebas que crean bases temporales aisladas y no tocan tus datos de prueba.

1. `RUN_DESKTOP.bat` inicia la base local SIN proyectos, ingresos ni gastos precargados. **Precarga tres perfiles demostrativos sin modalidades ni contratos.**
2. Inicio: `ludwing@vlux.local` / `DemoVlux2026!`. Cambia credenciales y no introduzcas datos sensibles.
3. `Proyectos` → crear proyecto de ejemplo, p. ej. `POS TEST / CLIENTE FICTICIO`.
4. `Ventas y cobros` → registrar una venta neta ficticia por MXN 20,000; registrar un cobro parcial de MXN 10,000. Evitar duplicar ingreso si ya estaba en Movimientos.
5. `Costos periódicos` → costo de hosting MXN 2,000 pagado: el otro socio debe aprobar en Movimientos antes de que se aplique a la base.
6. `Ganancias por trabajo` → crear una modalidad comercial ficticia sin activarla y asignarle una venta; el sistema debe bloquear el pago hasta cumplir las condiciones.
7. `Colaboradores` → crear y revisar modalidades de colaboradores de prueba. **No indicar falsamente que un contrato está firmado para generar pagos.** Las pruebas automáticas usan bases temporales independientes sin contratos reales.
8. `Costos periódicos` → programar hosting mensual/anual; al vencer, generar el costo, registrar su pago, aprobarlo en Movimientos si supera MXN 1,000.
9. `Ganancias por trabajo` → una vez exista contrato real firmado, asignación válida, cobranza aplicable, revisión dual de costos y autorización dual, crear corte de colaboración. Para colaborador de producto capturar CFDI recibido y fecha.
10. `Ganancias por trabajo` → abrir **Ver ticket**, usar **Imprimir / Guardar como PDF** y enviárselo al colaborador por el medio que prefieran. No equivale a CFDI ni transferencia real.

## Compatibilidad

- Funciona desde carpetas UNC gracias a `pushd` en los `.bat` (la base local se guarda en `%LOCALAPPDATA%\VLUX\FinanceOS`).
- **La aplicación es una ventana Edge conectada con backend Python**, no ejecutable Electron nativo. Compatible con Python 3.11+.
- Esta versión agrega tablas sin eliminar las de V0.2. Antes de actualizar, cerrar programa y ejecutar `RESPALDAR_BASE_LOCAL.bat`.
- Los modos `RUN_DESKTOP.bat` y `RUN_CON_DATOS_DEMO.bat` usan perfiles de SQLite distintos y nunca deben estar abiertos a la vez (ambos usan puerto 8765).
- La integración con SQL Server es futura; **los usuarios en varias computadoras no comparten datos aún**.
