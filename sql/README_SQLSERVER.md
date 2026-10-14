# Compatibilidad SQL Server — instrucciones para DBA

El backend tiene DDL `SCHEMA_SQLSERVER` en `backend/db.py`; usa tablas `dbo.vlux_*` creadas si no existen. No usa ORM ni procedimientos externos. Las consultas CRUD usan placeholders `?` desde `pyodbc`, por lo que no hay concatenación directa de valores recibidos de usuario.

En la primera fase, DBA debe:
- Crear BD dedicada `VLUX_Finanzas` con collation Unicode compatible e historial de copias de seguridad.
- Crear cuenta dedicada con SELECT/INSERT/UPDATE/DELETE en tablas `dbo.vlux_*`. Para primer bootstrap se requiere permiso CREATE TABLE y CREATE/ALTER schema (el DBA puede precrear tablas primero y después revocar DDL).
- Preferir conexión cifrada `Encrypt=yes;TrustServerCertificate=no` con CA confiable.
- Probar localmente adaptador con SQL Server Developer/Express en un ambiente de prueba antes de producción.
- Ejecutar pruebas de concurrencia para pagos/retenciones y validar atomicidad. La compatibilidad ODBC no fue probada con servidor real en esta entrega.

**Datos e identidades**: la base SQLite DEMO no se migra por defecto. Nunca copiar datos ficticios a la base corporativa.
