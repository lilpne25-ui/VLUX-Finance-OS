"""Run only in SQL Server host under DBA supervision, once approved by shareholders.
Usage (after setting VLUX_DB=sqlserver and connection in environment):
python backend/provision_second_partner.py
"""
import getpass,os,sys
from db import DB
from app import encode_pwd,now,audit

def main():
    if os.environ.get('VLUX_DB','').lower()!='sqlserver':sys.exit('Esta herramienta sólo se usa en servidor SQL Server')
    db=DB()
    try:
        existing=db.rows("SELECT id,name,email FROM {users} WHERE role='socio' AND active=1 ORDER BY id")
        print('Socios existentes:',[(r['name'],r['email']) for r in existing])
        if len(existing)!=1:sys.exit('Se requiere exactamente un socio inicial activo; no se modificarán datos')
        print('Alta del SEGUNDO socio: requiere documento de aprobación societaria previo.')
        if input('Escriba AUTORIZADO para continuar: ').strip()!='AUTORIZADO':sys.exit('Sin modificaciones')
        name=input('Nombre completo del segundo socio: ').strip()
        email=input('Correo corporativo del segundo socio: ').strip().lower()
        if not name or '@' not in email or len(name)>200 or len(email)>200:sys.exit('Datos inválidos')
        if db.one('SELECT id FROM {users} WHERE email=?',(email,)):sys.exit('Correo existente')
        pw=getpass.getpass('Contraseña inicial 14+ caracteres: ')
        again=getpass.getpass('Repetir contraseña: ')
        if pw!=again or len(pw)<14:sys.exit('Contraseñas distintas o demasiado cortas')
        id_=db.insert('users',['name','email','password_hash','role','active','created_at'],[name,email,encode_pwd(pw),'socio',1,now()])
        audit(db,None,'PROVISION_SECOND_PARTNER','users',id_,'Segundo socio habilitado desde consola supervisada')
        db.commit();print('Segundo socio agregado correctamente con ID',id_)
    finally:db.close()

if __name__=='__main__':main()
