# VLUX Finance OS — Desktop MVP v0.3 (versión pública)

Plataforma financiera interna para proyectos, ingresos, gastos, colaboradores, aprobaciones y propuestas de liquidación. **Versión de evaluación; no apta aún para producción.**

## Inicio en Windows

1. Requisitos: Python 3.11+ y Microsoft Edge.
2. Ejecuta `RUN_DESKTOP.bat` para iniciar con movimientos vacíos; `RUN_CON_DATOS_DEMO.bat` para un entorno ficticio independiente.
3. Para comprobar el backend usa `PROBAR_SISTEMA.bat` (los tests de políticas privadas requieren configurar previamente un entorno aislado).
4. La aplicación es un servidor local que Edge muestra en modo aplicación; no es un EXE nativo firmado.

## Confidencialidad

Esta es una versión pública: **no** incluye las condiciones económicas, identidades ni anexos privados de colaboradores. Sus perfiles y términos deben registrarse a partir de contratos aprobados; no inventes porcentajes ni marques documentos como firmados cuando no lo estén. No subas bases SQLite, `storage/`, `.env`, credenciales, tickets reales o documentos fiscales.

## Limitaciones

- Para cada PC hay una base SQLite local separada; no existe sincronización multiusuario a través de una carpeta UNC.
- SQL Server exige la configuración de un backend seguro en servidor y las pruebas de su despliegue.
- No mueve fondos bancarios, no emite CFDI ni sustituye la contabilidad o aprobación de pagos externos.
- Los pagos requieren revisión de sus obligaciones fiscales, legales y de documentación.

Más detalles en [`docs/README.md`](docs/README.md) y [`docs/PREGUNTAS_PARA_KLAUS_SERVIDOR.md`](docs/PREGUNTAS_PARA_KLAUS_SERVIDOR.md).
