"""Safe hot backup for local demo. Do not use as SQL Server backup strategy."""
import sqlite3,sys
from datetime import datetime
from pathlib import Path
from db import DB_PATH
out=Path(sys.argv[1]) if len(sys.argv)>1 else DB_PATH.parent/'backups'/('vlux_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.sqlite3')
out.parent.mkdir(parents=True,exist_ok=True)
if not DB_PATH.exists():raise SystemExit('Aún no existe la base de datos local')
with sqlite3.connect(DB_PATH) as source,sqlite3.connect(out) as target:source.backup(target)
print('Respaldo listo:',out)
