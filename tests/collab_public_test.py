"""Public distribution check: collaborators exist only as empty profiles, not real contract terms."""
import os,subprocess,sys,tempfile,urllib.request,urllib.error,json,socket,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
 with socket.socket() as sk:sk.bind(('127.0.0.1',0));port=sk.getsockname()[1]
 env=os.environ.copy();env.update(VLUX_MODE='local',VLUX_DB='sqlite',VLUX_HOST='127.0.0.1',VLUX_PORT=str(port),VLUX_SQLITE_PATH=str(Path(tmp)/'check.sqlite3'))
 proc=subprocess.Popen([sys.executable,str(root/'backend/app.py')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
 try:
  url=f'http://127.0.0.1:{port}'
  for _ in range(70):
   try:urllib.request.urlopen(url+'/health',timeout=1);break
   except Exception:time.sleep(.1)
  hdr={'Content-Type':'application/json','X-Requested-With':'VLUX-Desktop','Origin':url}
  first=urllib.request.Request(url+'/api/first-password',method='POST',headers=hdr,data=json.dumps({'email':'ludwing@vlux.local','current_password':'DemoVlux2026!','new_password':'Prueba-Publica-2026!'}).encode())
  urllib.request.urlopen(first,timeout=4).read()
  login=urllib.request.Request(url+'/api/login',method='POST',headers=hdr,data=json.dumps({'email':'ludwing@vlux.local','password':'Prueba-Publica-2026!'}).encode())
  with urllib.request.urlopen(login,timeout=4) as r:cookie=r.headers['Set-Cookie'].split(';')[0]
  req=urllib.request.Request(url+'/api/collab/people',headers={'Cookie':cookie,'X-Requested-With':'VLUX-Desktop'})
  with urllib.request.urlopen(req,timeout=4) as r:res=json.loads(r.read())
  assert len(res['collaborators'])==3 and not res['terms'],res
  for c in res['collaborators']:assert not any(s in c['name'] for s in ['Levet','Enrique','Mariano'])
  print('PASS: perfiles demostrativos neutrales sin contratos privados cargados')
 finally:proc.terminate();proc.wait(timeout=10)
