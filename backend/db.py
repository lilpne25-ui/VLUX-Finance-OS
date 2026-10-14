"""Minimal parameterized DB adapter: SQLite demo or ODBC SQL Server.
All SQL uses ? parameters. No database credentials are ever sent to clients.
"""
import os, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODE = os.environ.get('VLUX_DB', 'sqlite').lower()
# Windows clients must not run their SQLite db from a shared SMB/UNC folder.
# This default also protects launches that bypass the .bat scripts.
if os.name == 'nt':
    _local_profile = os.getenv('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
    _sqlite_default = str(Path(_local_profile) / 'VLUX' / 'FinanceOS' / 'vlux_local.sqlite3')
else:
    _sqlite_default = str(ROOT / 'storage' / 'vlux_local.sqlite3')
DB_PATH = Path(os.environ.get('VLUX_SQLITE_PATH', _sqlite_default))

SCHEMA_SQLITE = [
'''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token_hash TEXT NOT NULL UNIQUE, expires_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, client TEXT NOT NULL, budget_cents INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'activo', created_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, txn_date TEXT NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL, project_id INTEGER, recipient_user_id INTEGER, reference TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'vigente', created_by INTEGER NOT NULL, created_at TEXT NOT NULL, void_reason TEXT)''',
'''CREATE TABLE IF NOT EXISTS compensations (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT NOT NULL, user_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL, notes TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT 'solicitado', created_by INTEGER NOT NULL, approved_by INTEGER, paid_by INTEGER, transaction_id INTEGER, created_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS dividends (id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT NOT NULL, amount_cents INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'propuesto', accounting_reference TEXT NOT NULL DEFAULT '', created_by INTEGER NOT NULL, paid_by INTEGER, created_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS dividend_approvals (id INTEGER PRIMARY KEY AUTOINCREMENT, dividend_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL, UNIQUE(dividend_id,user_id))''',
'''CREATE TABLE IF NOT EXISTS forecasts (period TEXT PRIMARY KEY, revenue_cents INTEGER NOT NULL, notes TEXT NOT NULL DEFAULT '', updated_by INTEGER, updated_at TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, actor_id INTEGER, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER, detail TEXT NOT NULL)'''
]

SCHEMA_SQLSERVER = [
"IF OBJECT_ID('dbo.vlux_users','U') IS NULL CREATE TABLE dbo.vlux_users (id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(200) NOT NULL, email NVARCHAR(200) NOT NULL UNIQUE, password_hash NVARCHAR(300) NOT NULL, role NVARCHAR(30) NOT NULL, active INT NOT NULL DEFAULT 1, created_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_sessions','U') IS NULL CREATE TABLE dbo.vlux_sessions (id INT IDENTITY(1,1) PRIMARY KEY, user_id INT NOT NULL, token_hash NVARCHAR(100) NOT NULL UNIQUE, expires_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_projects','U') IS NULL CREATE TABLE dbo.vlux_projects (id INT IDENTITY(1,1) PRIMARY KEY, name NVARCHAR(200) NOT NULL, client NVARCHAR(200) NOT NULL, budget_cents BIGINT NOT NULL DEFAULT 0, status NVARCHAR(30) NOT NULL DEFAULT 'activo', created_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_transactions','U') IS NULL CREATE TABLE dbo.vlux_transactions (id INT IDENTITY(1,1) PRIMARY KEY, txn_date NVARCHAR(10) NOT NULL, kind NVARCHAR(30) NOT NULL, amount_cents BIGINT NOT NULL, category NVARCHAR(100) NOT NULL, description NVARCHAR(600) NOT NULL, project_id INT NULL, recipient_user_id INT NULL, reference NVARCHAR(200) NOT NULL DEFAULT '', status NVARCHAR(30) NOT NULL DEFAULT 'vigente', created_by INT NOT NULL, created_at NVARCHAR(40) NOT NULL, void_reason NVARCHAR(600) NULL)",
"IF OBJECT_ID('dbo.vlux_compensations','U') IS NULL CREATE TABLE dbo.vlux_compensations (id INT IDENTITY(1,1) PRIMARY KEY, period NVARCHAR(7) NOT NULL, user_id INT NOT NULL, amount_cents BIGINT NOT NULL, notes NVARCHAR(600) NOT NULL DEFAULT '', state NVARCHAR(30) NOT NULL DEFAULT 'solicitado', created_by INT NOT NULL, approved_by INT NULL, paid_by INT NULL, transaction_id INT NULL, created_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_dividends','U') IS NULL CREATE TABLE dbo.vlux_dividends (id INT IDENTITY(1,1) PRIMARY KEY, period NVARCHAR(20) NOT NULL, amount_cents BIGINT NOT NULL, state NVARCHAR(30) NOT NULL DEFAULT 'propuesto', accounting_reference NVARCHAR(300) NOT NULL DEFAULT '', created_by INT NOT NULL, paid_by INT NULL, created_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_dividend_approvals','U') IS NULL CREATE TABLE dbo.vlux_dividend_approvals (id INT IDENTITY(1,1) PRIMARY KEY, dividend_id INT NOT NULL, user_id INT NOT NULL, created_at NVARCHAR(40) NOT NULL, CONSTRAINT UQ_vlux_div_approval UNIQUE(dividend_id,user_id))",
"IF OBJECT_ID('dbo.vlux_forecasts','U') IS NULL CREATE TABLE dbo.vlux_forecasts (period NVARCHAR(7) NOT NULL PRIMARY KEY, revenue_cents BIGINT NOT NULL, notes NVARCHAR(300) NOT NULL DEFAULT '', updated_by INT NULL, updated_at NVARCHAR(40) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_settings','U') IS NULL CREATE TABLE dbo.vlux_settings ([key] NVARCHAR(100) NOT NULL PRIMARY KEY, [value] NVARCHAR(500) NOT NULL)",
"IF OBJECT_ID('dbo.vlux_audit','U') IS NULL CREATE TABLE dbo.vlux_audit (id INT IDENTITY(1,1) PRIMARY KEY, created_at NVARCHAR(40) NOT NULL, actor_id INT NULL, action NVARCHAR(80) NOT NULL, entity NVARCHAR(80) NOT NULL, entity_id INT NULL, detail NVARCHAR(1200) NOT NULL)"
]
TABLES = ('users','sessions','projects','transactions','compensations','dividends','dividend_approvals','forecasts','settings','audit')


from collab_storage import EXTRA_TABLES, SCHEMA_SQLITE_EXTRA, SCHEMA_SQLSERVER_EXTRA
SCHEMA_SQLITE.extend(SCHEMA_SQLITE_EXTRA)
SCHEMA_SQLSERVER.extend(SCHEMA_SQLSERVER_EXTRA)
TABLES += EXTRA_TABLES

class DB:
    def __init__(self):
        self.sqlserver = MODE == 'sqlserver'
        if self.sqlserver:
            try: import pyodbc
            except ImportError as e: raise RuntimeError('SQL Server requiere pip install pyodbc y ODBC Driver 18') from e
            cs = os.environ.get('VLUX_SQLSERVER_CONNECTION','')
            if not cs: raise RuntimeError('Falta VLUX_SQLSERVER_CONNECTION en el servidor')
            self.conn = pyodbc.connect(cs, autocommit=False, timeout=10)
        else:
            DB_PATH.parent.mkdir(exist_ok=True, parents=True)
            self.conn = sqlite3.connect(str(DB_PATH),timeout=15)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA busy_timeout=15000')
    def name(self, table):
        if table not in TABLES: raise ValueError('Tabla no reconocida')
        return ('dbo.vlux_' if self.sqlserver else '') + table
    def sql(self, text):
        # Code-generated identifiers only; SQL parameters are used for all values.
        for table in sorted(TABLES, key=len, reverse=True):
            text = text.replace('{'+table+'}', self.name(table))
        if self.sqlserver:
            text=text.replace('{key}','[key]').replace('{value}','[value]')
        else:
            text=text.replace('{key}','key').replace('{value}','value')
        return text
    def execute(self, text, params=()):
        cur=self.conn.cursor()
        cur.execute(self.sql(text), tuple(params))
        return cur
    def rows(self,text,params=()):
        cur=self.execute(text,params)
        names=[x[0] for x in cur.description] if cur.description else []
        return [dict(zip(names,r)) for r in cur.fetchall()]
    def one(self,text,params=()):
        a=self.rows(text,params)
        return a[0] if a else None
    def insert(self,table,cols,vals):
        assert table in TABLES and all(c.isidentifier() for c in cols)
        placeholders=','.join('?' for _ in vals)
        statement=f"INSERT INTO {{{table}}} ({','.join('['+c+']' if self.sqlserver and c in ('key','value') else c for c in cols)})"
        if self.sqlserver:
            statement += f" OUTPUT INSERTED.id VALUES ({placeholders})"
            return int(self.execute(statement, vals).fetchone()[0])
        statement += f" VALUES ({placeholders})"
        return int(self.execute(statement, vals).lastrowid)
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

def initialize():
    db=DB()
    try:
        for stmt in (SCHEMA_SQLSERVER if db.sqlserver else SCHEMA_SQLITE):db.execute(stmt)
        if not db.sqlserver:
            for k, v in DEFAULT_SETTINGS.items():
                db.execute('INSERT OR IGNORE INTO {settings} ({key}, {value}) VALUES (?,?)',(k,str(v)))
        else:
            for k,v in DEFAULT_SETTINGS.items():
                if not db.one('SELECT {value} AS val FROM {settings} WHERE {key}=?',(k,)):
                    db.insert('settings',['key','value'],[k,str(v)])
        db.commit()
    finally:db.close()

DEFAULT_SETTINGS={
 'monthly_fixed_cents':800000,'variable_cost_pct':40,'planning_tax_pct':20,
 'reserve_target_cents':9600000,'salary_stage1_cents':600000,'salary_stage2_cents':1200000,
 'salary_stage1_revenue_cents':3500000,'salary_stage2_revenue_cents':6000000,
 'salary_stage1_reserve_cents':2000000,'salary_stage2_reserve_cents':6400000,
 'share_ludwing_pct':50,'share_rodrigo_pct':50,'min_gross_margin_pct':50,
 'company_name':'VLUX','currency':'MXN'
}
