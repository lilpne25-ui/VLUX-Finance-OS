/* VLUX Finance OS desktop front-end. No CDN, no trackers, no external dependencies. */
const $=id=>document.getElementById(id);
const mx=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN',maximumFractionDigits:2}).format((Number(n)||0)/100);
const peso=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN',maximumFractionDigits:0}).format((Number(n)||0)/100);
const esc=s=>String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmtDate=s=>{try{return new Date(String(s).slice(0,10)+'T12:00:00').toLocaleDateString('es-MX',{day:'2-digit',month:'short',year:'numeric'});}catch{return String(s)}};
const today=new Date().toLocaleDateString('en-CA');
const currentPeriod=today.slice(0,7);
const quarter=(()=>{let [y,m]=currentPeriod.split('-').map(Number);return `${y}-Q${Math.ceil(m/3)}`;})();
const num=s=>{let x=Number(String(s??'').replace(',','.'));if(!Number.isFinite(x)||x<=0)throw Error('Capture un importe positivo');return Math.round(x*100)};
let user=null,env='demo',dbMode='sqlite',page='dashboard',filterType='all',searchTerm='';
let cache={};
const menu=[['dashboard','◫','Resumen general'],['transactions','⇄','Movimientos'],['projects','▦','Proyectos'],['collaborators','♧','Colaboradores'],['salescollab','▤','Ventas y cobros'],['costscollab','☷','Costos periódicos'],['settlementscollab','◇','Ganancias por trabajo'],['planning','▤','Planeación'],['compensations','♙','Pagos a socios'],['dividends','◇','Utilidades'],['reports','▥','Reportes'],['policies','◈','Reglas y políticas'],['settings','⚙','Configuración']];
async function api(path,options={}){
  const r=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json','X-Requested-With':'VLUX-Desktop'},...options});
  let j;try{j=await r.json()}catch{throw Error('Respuesta del servidor no válida')}
  if(!r.ok){const err=Error(j.error||`Error ${r.status}`);err.code=j.code;throw err};
  return j;
}
function get(path){return api(path)}
function post(path,data){return api(path,{method:'POST',body:JSON.stringify(data)})}
function put(path,data){return api(path,{method:'PUT',body:JSON.stringify(data)})}
function showToast(message,error=false){const t=$('toast');t.textContent=message;t.className='toast'+(error?' error':'');clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>t.classList.add('hidden'),4800)}
function canWrite(){return user?.role==='socio'}
function warning(){return env==='local'?'<div class="notice info"><span>◇</span><div><strong>Base local vacía:</strong> los proyectos, ingresos, gastos, saldos y metas comienzan sin precarga. Los valores de Configuración son supuestos propuestos, no costos reales ni reglas societarias aprobadas. Los usuarios son temporales para pruebas. No ingrese información sensible.</div></div>':env==='demo'?'<div class="notice"><span>◇</span><div><strong>Modo demostración:</strong> los clientes, movimientos y saldos precargados son ficticios. No representan la contabilidad real de VLUX.</div></div>':'<div class="notice info">Datos de registro interno. Conciliar con banca y contabilidad antes de pagar impuestos o aprobar dividendos.</div>'}
function badge(v){const classes={ingreso:'income',gasto:'expense',capital:'capital',distribucion:'distribution',vigente:'activo',pendiente:'propuesto',anulado:'anulado',activo:'activo',cotizado:'cotizado',pausado:'pausado',cerrado:'cerrado',solicitado:'solicitado',aprobado:'aprobado',pagado:'pagado',propuesto:'propuesto'};const map={income:'Ingreso',expense:'Gasto',capital:'Capital',distribution:'Dividendo',vigente:'Vigente',pendiente:'Pendiente'};return `<span class="pill ${classes[v]||v}">${esc(map[v]||v)}</span>`}
const header=(label,title,subtitle,tools='')=>`<div class="page-header"><div><div class="eyebrow">${esc(label)}</div><h1>${esc(title)}</h1><p>${esc(subtitle)}</p></div><div class="toolbar">${tools}</div></div>`;
const metric=(title,value,icon,subtitle,type='')=>`<div class="stat-card"><div class="stat-top"><span>${title}</span><span class="stat-symbol">${icon}</span></div><strong class="${type}">${value}</strong><small>${subtitle}</small></div>`;
const btn=(text,action,kind='secondary')=>`<button class="btn ${kind}" data-action="${action}">${text}</button>`;
function moneyColor(kind){return kind==='income'||kind==='capital'?'plus':'minus'}
function tableMovements(rows,allowActions=true){
 if(!rows.length)return '<div class="empty"><b>Sin movimientos</b>Agrega el primer ingreso, gasto o aportación de capital.</div>';
 return `<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Tipo</th><th>Proyecto</th><th>Importe</th><th>Estado</th>${allowActions&&canWrite()?'<th>Acción</th>':''}</tr></thead><tbody>${rows.map(r=>`<tr><td>${fmtDate(r.txn_date)}</td><td><b>${esc(r.description)}</b><small>${esc(r.category)} ${r.reference?'· '+esc(r.reference):''}</small></td><td>${badge(r.kind)}</td><td>${esc(r.project_name||'—')}</td><td class="amount ${moneyColor(r.kind)}">${r.kind==='expense'||r.kind==='distribution'?'−':'+'}${mx(r.amount_cents)}</td><td>${badge(r.status)}</td>${allowActions&&canWrite()?`<td>${r.status==='pendiente'&&r.created_by!==user.id?`<button class="btn small" data-action="approve-txn:${r.id}">Aprobar</button>`:''}${(r.status==='vigente'||r.status==='pendiente')&&r.kind!=='distribution'&&r.category!=='Remuneración a socio'&&r.category!=='Liquidación colaborador'&&!String(r.reference||'').startsWith('VENTA-')&&!String(r.reference||'').startsWith('COSTO-')?`<button class="btn small danger" data-action="void:${r.id}">Anular</button>`:''}</td>`:''}</tr>`).join('')}</tbody></table></div>`
}
function svgChart(months){
 const W=760,H=220,left=38,top=15,usable=165,base=180;
 if(!months.length)return '<div class="empty">No hay datos para mostrar.</div>';
 const max=Math.max(1000000,...months.flatMap(m=>[m.income_cents,m.expense_cents]))*1.12;
 const step=(W-left-15)/months.length;
 let grid='';for(let i=0;i<4;i++){let y=top+i*usable/3;grid+=`<line class="chart-grid" x1="${left}" y1="${y}" x2="${W-12}" y2="${y}"/><text class="chart-text" x="${left-5}" y="${y+3}" text-anchor="end">${Math.round(max*(3-i)/3/100000)}k</text>`}
 let bars='';months.forEach((m,i)=>{let x=left+i*step+step*.22,w=Math.max(10,Math.min(19,step*.21)),h1=m.income_cents/max*usable,h2=m.expense_cents/max*usable;bars+=`<rect x="${x}" y="${base-h1}" width="${w}" height="${h1}" rx="4" fill="#67e4c9"/><rect x="${x+w+5}" y="${base-h2}" width="${w}" height="${h2}" rx="4" fill="#708bc5"/><text class="chart-text" x="${left+i*step+step*.52}" y="204" text-anchor="middle">${esc(m.month.slice(5))}/${esc(m.month.slice(2,4))}</text>`});
 return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Ingresos y gastos mensuales, escala en miles de pesos">${grid}${bars}</svg><div class="legend"><span><i class="dot"></i> Ingresos</span><span><i class="dot exp"></i> Gastos</span><span class="muted">MXN · miles de pesos</span></div>`
}
function showNav(){ $('nav').innerHTML=menu.map(([id,icon,title])=>`<button class="navbtn ${page===id?'active':''}" data-nav="${id}"><span class="navicon">${icon}</span><span class="label">${title}</span></button>`).join('');$('currentView').textContent=(menu.find(m=>m[0]===page)||menu[0])[2]}
async function navigate(to){page=to;showNav();$('content').innerHTML='<div class="muted">Cargando módulo...</div>';try{await render()}catch(e){$('content').innerHTML=`<div class="card"><h2>Error de carga</h2><p>${esc(e.message)}</p>${btn('Reintentar','refresh')}</div>`;showToast(e.message,true)}}
async function render(){
 if(page==='collaborators')return renderCollaborators();
 if(page==='salescollab')return renderSalesCollab();
 if(page==='costscollab')return renderCostCollab();
 if(page==='settlementscollab')return renderSettlementCollab();
 if(page==='dashboard')return renderDashboard();
 if(page==='transactions')return renderTransactions();
 if(page==='projects')return renderProjects();
 if(page==='planning')return renderPlanning();
 if(page==='compensations')return renderCompensations();
 if(page==='dividends')return renderDividends();
 if(page==='reports')return renderReports();
 if(page==='policies')return renderPolicies();
 if(page==='settings')return renderSettings();
}
async function renderDashboard(){
 const data=await get('/api/dashboard');cache.dashboard=data;const s=data.stats, pct=Math.max(0,Math.min(100,100*s.balance_cents/Math.max(1,s.reserve_target_cents)));
 const latest=s.monthly.at(-1)||{income_cents:0,expense_cents:0};
 $('content').innerHTML=warning()+header('PANEL EJECUTIVO','Visión financiera','Un panorama claro de lo que ingresa, se gasta y permanece en la empresa.',canWrite()?btn('＋ Nuevo movimiento','new-transaction','primary'):'')+
 `<section class="stat-grid">${metric('Saldo teórico',''+peso(s.balance_cents),'⌁','Ingresos + capital − pagos')}${metric('Ingresos registrados',peso(s.income_cents),'↗','Acumulado','positive')}${metric('Gastos registrados',peso(s.expense_cents),'↘','Acumulado','negative')}${metric('Resultado operativo',peso(s.operating_profit_cents),'◈','Antes de impuestos y ajustes',s.operating_profit_cents>=0?'positive':'negative')}</section>${s.pending_approvals?`<div class="notice" style="margin-top:18px">Atención: ${s.pending_approvals} movimientos por aprobar (${peso(s.pending_expenses_cents)} en egresos aún no incorporados al saldo). <button class="btn small" data-action="goto:transactions">Revisar</button></div>`:''}`+
 `<section class="grid-2"><div class="card"><div class="card-title-row"><div><div class="card-title">Ingresos vs. gastos</div><div class="card-meta">Evolución de los últimos 12 meses con movimientos</div></div>${badge('vigente')}</div>${svgChart(s.monthly)}</div><div class="card"><div class="card-title-row"><div><div class="card-title">Reserva de estabilidad</div><div class="card-meta">Objetivo mínimo aprobado</div></div><span class="kpi-badge">FONDO VLUX</span></div><div class="reserve-top"><div><span class="muted">Saldo disponible teórico</span><div><strong>${peso(s.balance_cents)}</strong></div></div><span class="muted">${Math.round(pct)}% / meta</span></div><div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div><div class="detail-line"><span>Objetivo de reserva</span><b>${peso(s.reserve_target_cents)}</b></div><div class="detail-line"><span>Excedente sobre reserva</span><b class="positive">${peso(s.free_cash_cents)}</b></div><hr class="separator"><div class="card-title">Punto de equilibrio teórico</div><div style="font-size:27px;font-weight:750;margin-top:14px">${s.break_even_no_salary_cents?peso(s.break_even_no_salary_cents):'—'} <span class="muted" style="font-size:12px">/ mes</span></div><p class="footnote">Basado en costos fijos y variables configurados; no sustituye una conciliación con datos reales.</p></div></section>`+
 `<div class="card" style="margin-top:18px"><div class="card-title-row"><div><div class="card-title">Actividad reciente</div><div class="card-meta">Últimos registros de la operación</div></div>${btn('Ver movimientos ↗','goto:transactions','ghost')}</div>${tableMovements(data.transactions,false)}</div>`;
}
async function renderTransactions(){
 const {transactions:t}=await get('/api/transactions');cache.transactions=t;
 let filtered=t.filter(r=>(filterType==='all'||r.kind===filterType)&&(!searchTerm||JSON.stringify([r.description,r.category,r.project_name,r.reference]).toLowerCase().includes(searchTerm.toLowerCase())));
 const action=canWrite()?btn('＋ Registrar movimiento','new-transaction','primary'):'';
 $('content').innerHTML=warning()+header('REGISTRO FINANCIERO','Movimientos','Ingresos, egresos y aportaciones con referencia, proyecto y autor.',action)+`<div class="card"><div class="card-title-row" style="flex-wrap:wrap"><div class="toolbar">${[['all','Todos'],['income','Ingresos'],['expense','Gastos'],['capital','Capital'],['distribution','Dividendos']].map(([id,title])=>`<button class="btn small ${filterType===id?'primary':'secondary'}" data-filter="${id}">${title}</button>`).join('')}</div><input id="searchTxn" style="width:235px;margin:0" placeholder="Buscar concepto o proyecto" value="${esc(searchTerm)}"></div><div id="transactionTable">${tableMovements(filtered)}</div></div>`;
 $('searchTxn').addEventListener('input',e=>{searchTerm=e.target.value;document.querySelector('#transactionTable').innerHTML=tableMovements(t.filter(r=>(filterType==='all'||r.kind===filterType)&&(!searchTerm||JSON.stringify([r.description,r.category,r.project_name,r.reference]).toLowerCase().includes(searchTerm.toLowerCase()))))})
}
async function renderProjects(){
 const {projects,project_stats}=await get('/api/projects');cache.projects=projects;
 $('content').innerHTML=warning()+header('CARTERA DE PROYECTOS','Proyectos y clientes','Presupuesto comercial, ingresos y gastos asociados a cada iniciativa.',canWrite()?btn('＋ Nuevo proyecto','new-project','primary'):'')+
 (projects.length?`<div class="grid-3">${projects.map(p=>{const stats=project_stats[String(p.id)]||{income_cents:0,expense_cents:0};return `<div class="project-card"><div class="project-bottom"><div class="p-icon">▣</div>${badge(p.status)}</div><div><h3>${esc(p.name)}</h3><p>${esc(p.client)}</p></div><div class="project-money">${peso(stats.income_cents)}</div><div class="muted" style="font-size:11px">Ingresos registrados</div><hr class="separator" style="margin:2px 0"><div class="detail-line"><span>Costos asociados</span><b>${peso(stats.expense_cents)}</b></div><div class="detail-line"><span>Resultado registrado</span><b>${peso(stats.income_cents-stats.expense_cents)}</b></div><div class="detail-line"><span>Presupuesto objetivo</span><b>${peso(p.budget_cents)}</b></div>${canWrite()?`<div class="project-bottom"><span class="muted">Estado</span><select aria-label="Estado del proyecto" data-projectstatus="${p.id}">${['activo','cotizado','pausado','cerrado'].map(st=>`<option value="${st}" ${p.status===st?'selected':''}>${st}</option>`).join('')}</select></div>`:''}</div>`}).join('')}</div>`:'<div class="card empty">No hay proyectos.</div>')+
 '<p class="footnote" style="margin-top:20px">La rentabilidad por proyecto contempla sólo los movimientos asignados explícitamente. Los costos generales y fiscales deben asignarse en una evaluación financiera final.</p>';
}
async function renderPlanning(){
 const {forecasts,settings:s,stats}=await get('/api/forecast');
 const byPeriod=Object.fromEntries(forecasts.map(f=>[f.period,f]));
 const current=new Date();let rows=[];
 for(let i=0;i<12;i++){
   let d=new Date(current.getFullYear(),current.getMonth()+i,1),period=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
   rows.push({period,revenue_cents:byPeriod[period]?.revenue_cents||0});
 }
 function simulate(factor){
   let cash=stats.balance_cents,result=[],sumRev=0,sumNet=0,sumPayroll=0;
   for(const r of rows){
     const rev=Math.round(r.revenue_cents*factor);
     let salary=0;
     if(rev>=s.salary_stage2_revenue_cents&&cash>=s.salary_stage2_reserve_cents)salary=s.salary_stage2_cents*2;
     else if(rev>=s.salary_stage1_revenue_cents&&cash>=s.salary_stage1_reserve_cents)salary=s.salary_stage1_cents*2;
     const cost=s.monthly_fixed_cents+Math.round(rev*s.variable_cost_pct/100)+salary;
     const beforeTax=rev-cost;
     const tax=Math.max(0,Math.round(beforeTax*s.planning_tax_pct/100));
     const net=beforeTax-tax;
     sumRev+=rev;sumNet+=net;sumPayroll+=salary;cash+=net;
     result.push({period:r.period,rev,salary,tax,net,cash});
   }
   return {sumRev,sumNet,sumPayroll,cash,result};
 }
 const base=simulate(1),low=simulate(.7),high=simulate(1.3);
 const scenarios=[['Conservador (−30%)',low],['Base',base],['Optimista (+30%)',high]];
 $('content').innerHTML=warning()+header('ESTRATEGIA FINANCIERA','Planeación 12 meses','Metas de ventas y escenarios proyectados a partir de supuestos editables.')+
 `<div class="notice info">Estas proyecciones son simulaciones, no facturas ni compromisos. Los umbrales de remuneración también requieren estabilidad de cobros, aprobación de ambos socios y validación fiscal.</div>`+
 `<div class="stat-grid">${metric('Meta acumulada de ingresos',peso(base.sumRev),'↗','Próximos 12 meses')}${metric('Resultado estimado',peso(base.sumNet),'◇','Después de provisión hipotética',base.sumNet>=0?'positive':'negative')}${metric('Bolsa remuneraciones',peso(base.sumPayroll),'♙','Ambos socios · costo total')}${metric('Saldo final proyectado',peso(base.cash),'▤','Sin reparto de dividendos')}</div>`+
 `<div class="grid-2"><div class="card"><div class="card-title-row"><div><div class="card-title">Proyección de ingresos</div><div class="card-meta">Actualiza la meta de facturación para cada mes</div></div></div>${svgChart(rows.map(r=>({month:r.period,income_cents:r.revenue_cents,expense_cents:Math.round(s.monthly_fixed_cents+r.revenue_cents*s.variable_cost_pct/100)})))}</div><div class="card"><div class="card-title">Política de crecimiento</div><div class="metric-line"><span>Gastos fijos mensuales</span><strong>${peso(s.monthly_fixed_cents)}</strong></div><div class="metric-line"><span>Costos variables planeados</span><strong>${s.variable_cost_pct}%</strong></div><div class="metric-line"><span>Umbral etapa 1</span><strong>${peso(s.salary_stage1_revenue_cents)}/mes</strong></div><div class="metric-line"><span>Umbral etapa 2</span><strong>${peso(s.salary_stage2_revenue_cents)}/mes</strong></div><div class="metric-line"><span>Reserva mínima</span><strong>${peso(s.reserve_target_cents)}</strong></div><div class="metric-line"><span>Propuesta después de reserva</span><strong>50% crecimiento · 20% reserva · 30% dividendos</strong></div><p class="footnote">Estos porcentajes no ejecutan retiros automáticos; se requiere propuesta de distribución y aprobación legal.</p></div></div>`+
 `<div class="card" style="margin-top:18px"><div class="card-title-row"><div class="card-title">Escenarios comparativos</div><div class="card-meta">Variación uniforme de metas de ingreso</div></div><div class="table-wrap"><table><thead><tr><th>Escenario</th><th>Ingresos proyectados</th><th>Resultado 12 meses</th><th>Bolsa remuneraciones</th><th>Saldo final estimado</th></tr></thead><tbody>${scenarios.map(([label,r])=>`<tr><td><b>${esc(label)}</b></td><td>${peso(r.sumRev)}</td><td class="amount ${r.sumNet>=0?'plus':'minus'}">${peso(r.sumNet)}</td><td>${peso(r.sumPayroll)}</td><td>${peso(r.cash)}</td></tr>`).join('')}</tbody></table></div></div>`+
 `<div class="card" style="margin-top:18px"><div class="card-title-row"><div class="card-title">Objetivos mensuales de facturación</div><span class="muted">Montos sin IVA · guardar por mes</span></div><div class="table-wrap"><table><thead><tr><th>Mes</th><th>Ingreso estimado</th><th>Remuneraciones simuladas</th><th>Resultado neto estimado</th><th>Saldo final estimado</th><th>Acción</th></tr></thead><tbody>${base.result.map(r=>`<tr><td><b>${esc(r.period)}</b></td><td><input style="margin:0;width:150px;min-height:34px;padding:7px" aria-label="Meta ${esc(r.period)}" data-forecast-value="${esc(r.period)}" type="number" min="0" step="100" value="${(r.rev/100).toFixed(0)}" ${canWrite()?'':'disabled'}></td><td>${peso(r.salary)}</td><td class="amount ${r.net>=0?'plus':'minus'}">${peso(r.net)}</td><td>${peso(r.cash)}</td><td>${canWrite()?`<button class="btn small" data-action="save-forecast:${r.period}">Guardar</button>`:''}</td></tr>`).join('')}</tbody></table></div></div><p class="footnote">La proyección no considera IVA, depreciaciones, adeudos, ingreso diferido, días de cobro, estructura real de nómina ni obligaciones contractuales no registradas. Use el resultado como referencia preliminar para decisiones, no como estado financiero auditado.</p>`;
}
async function renderCompensations(){
 const {compensations:c,users}=await get('/api/compensations');cache.users=users;
 const summary=users.filter(x=>x.role==='socio');
 $('content').innerHTML=warning()+header('REMUNERACIONES OPERATIVAS','Pagos a socios','Solicitudes, autorizaciones cruzadas y registros de pago.',canWrite()?btn('＋ Solicitar remuneración','new-comp','primary'):'')+
 `<div class="split">${summary.map(s=>`<div class="split-item"><span class="eyebrow">SOCIO ACTIVO</span><div style="font-size:20px;font-weight:750;margin-top:12px">${esc(s.name)}</div><p>Participación objetivo: 50% · Remuneración por trabajo separada del dividendo</p><div class="kpi-badge">${esc(s.email)}</div></div>`).join('')}</div>`+
 `<div class="card" style="margin-top:18px"><div class="card-title-row"><div class="card-title">Historial de solicitudes</div><span class="muted">El socio beneficiario no autoriza su pago</span></div><div class="table-wrap"><table><thead><tr><th>Periodo</th><th>Beneficiario</th><th>Monto</th><th>Solicitante</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>${c.map(r=>`<tr><td>${esc(r.period)}</td><td><b>${esc(r.person_name)}</b><small>${esc(r.notes)}</small></td><td class="amount">${mx(r.amount_cents)}</td><td>${esc(r.creator_name)}</td><td>${badge(r.state)}</td><td><div class="table-actions">${canWrite()&&r.state==='solicitado'&&r.created_by!==user.id&&r.user_id!==user.id?`<button class="btn small" data-action="approve-comp:${r.id}">Aprobar</button>`:''}${canWrite()&&r.state==='aprobado'?`<button class="btn small primary" data-action="pay-comp:${r.id}">Registrar pago</button>`:''}</div></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No hay solicitudes registradas.</td></tr>'}</tbody></table></div></div><p class="footnote">Las remuneraciones requieren acuerdo por escrito y tratamiento fiscal/laboral definido por el contador. El pago genera un gasto operativo dentro del sistema.</p>`;
}
async function renderDividends(){
 const {dividends:d,stats:s}=await get('/api/dividends');
 $('content').innerHTML=warning()+header('GOBIERNO CORPORATIVO','Utilidades y dividendos','Propón y controla distribuciones con aprobación de ambos socios.',canWrite()?btn('＋ Proponer dividendo','new-dividend','primary'):'')+
 `<div class="stat-grid">${metric('Resultado operativo',peso(s.operating_profit_cents),'↗','Ingresos menos gastos')}${metric('Reserva objetivo',peso(s.reserve_target_cents),'▤','Saldo mínimo protegido')}${metric('Caja libre estimada',peso(s.free_cash_cents),'◇','Excedente sobre reserva')}${metric('Bolsa potencial para repartir',peso(s.candidate_dividend_capacity_cents),'⇄','Máximo interno estimado, no aprobado')}</div>`+
 `<div class="notice info" style="margin-top:20px">El cálculo es operativo: la distribución real requiere estados financieros aprobados, utilidades legalmente distribuibles, acta societaria, CFDI/retenciones cuando correspondan y revisión contable. El sistema NO certifica estas condiciones.</div>`+
 `<div class="card"><div class="card-title-row"><div class="card-title">Propuestas trimestrales</div><span class="kpi-badge">50% / 50%</span></div><div class="table-wrap"><table><thead><tr><th>Periodo</th><th>Fondo propuesto</th><th>Ludwing / Rodrigo</th><th>Aprobaciones</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>${d.map(r=>`<tr><td><b>${esc(r.period)}</b><small>${esc(r.accounting_reference||'Sin documento contable adjunto')}</small></td><td class="amount">${mx(r.amount_cents)}</td><td>${mx(Math.floor(r.amount_cents/2))} / ${mx(r.amount_cents-Math.floor(r.amount_cents/2))}</td><td>${r.approvals.length}/2</td><td>${badge(r.state)}</td><td><div class="table-actions">${canWrite()&&r.state==='propuesto'&&!r.approvals.includes(user.id)?`<button class="btn small" data-action="approve-dividend:${r.id}">Aprobar</button>`:''}${canWrite()&&r.state==='aprobado'?`<button class="btn small primary" data-action="pay-dividend:${r.id}">Registrar distribución</button>`:''}</div></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No existen propuestas de dividendos.</td></tr>'}</tbody></table></div></div>`;
}
async function renderReports(){
 const {stats:s}=await get('/api/dashboard');const {events}=await get('/api/audit');
 $('content').innerHTML=warning()+header('TRAZABILIDAD','Reportes y auditoría','Histórico operativo, documentos CSV y control de cambios.')+
 `<div class="grid-3"><div class="card"><div class="card-title">Movimientos</div><p class="muted">Descargar registro de ingresos, gastos, capital y distribuciones.</p><a class="btn secondary" href="/api/export?type=transactions" download>↓ Exportar CSV</a></div><div class="card"><div class="card-title">Proyectos</div><p class="muted">Exportar cartera de clientes y presupuestos.</p><a class="btn secondary" href="/api/export?type=projects" download>↓ Exportar CSV</a></div><div class="card"><div class="card-title">Auditoría</div><p class="muted">Descargar eventos de alta, aprobación y anulación.</p><a class="btn secondary" href="/api/export?type=audit" download>↓ Exportar CSV</a></div></div>`+
 `<div class="card" style="margin-top:18px"><div class="card-title-row"><div><div class="card-title">Bitácora de cambios</div><div class="card-meta">Últimos 300 eventos registrados en el servidor</div></div><span class="kpi-badge">AUDIT TRAIL</span></div><div class="table-wrap"><table><thead><tr><th>Fecha UTC</th><th>Usuario</th><th>Evento</th><th>Entidad</th><th>Detalle</th></tr></thead><tbody>${events.map(r=>`<tr><td>${esc(r.created_at.replace('T',' ').slice(0,19))}</td><td>${esc(r.actor_name||'Sistema')}</td><td>${esc(r.action)}</td><td>${esc(r.entity)} #${esc(r.entity_id||'—')}</td><td>${esc(r.detail).slice(0,180)}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">No hay eventos de auditoría.</td></tr>'}</tbody></table></div></div>`;
}
async function renderPolicies(){
 const {settings:s}=await get('/api/settings');
 const check='<span class="rule-chip implemented">Aplicada en API</span>', draft='<span class="rule-chip proposed">Propuesta / parametrizable</span>', pending='<span class="rule-chip pending">Revisión manual</span>';
 const item=(n,title,status,description,source='')=>`<div class="rule-item"><div class="rule-number">${esc(n)}</div><div class="rule-detail"><div class="rule-heading"><strong>${esc(title)}</strong>${status}</div><div class="rule-description">${description}</div>${source?`<div class="rule-source">Fuente: ${esc(source)}</div>`:''}</div></div>`;
 const section=(title,subtitle,items)=>`<div class="card rule-section"><div class="card-title">${esc(title)}</div><div class="card-meta">${esc(subtitle)}</div>${items.join('')}</div>`;
 $('content').innerHTML=warning()+header('GOBIERNO FINANCIERO','Reglas y políticas','Reglamento visible: qué controla el sistema, qué es una propuesta y qué necesita validación.',btn('Modificar supuestos','goto:settings'))+
 `<div class="notice info"><strong>Estado documental:</strong> reglas provenientes del Acuerdo de Socios Fundadores V1.0 (18/05/2026) y del Plan Económico Interno V1.0 <b>propuesto</b>. Las etiquetas distinguen controles automáticos de condiciones que aún requieren contador, acta o revisión humana. No equivale a un reglamento final firmado ni a estados contables aprobados.</div>`+
 `<div class="rule-highlights"><div class="rule-hero"><span>PARTICIPACIÓN OBJETIVO</span><strong>${s.share_ludwing_pct}% <em>/</em> ${s.share_rodrigo_pct}%</strong><small>Ludwing / Rodrigo · confirmar con estatutos y vesting</small></div><div class="rule-hero"><span>AUTORIZACIÓN DUAL</span><strong>$1,000</strong><small>Gastos superiores al monto indicado</small></div><div class="rule-hero"><span>RESERVA OBJETIVO</span><strong>${peso(s.reserve_target_cents)}</strong><small>Supuesto editable · no cuenta bancaria separada</small></div></div>`+
 `<div class="rules-grid">`+
 section('01 · Gobierno de socios','Participación y decisiones de VLUX',[
 item('G01','Participación objetivo 50/50',check,'La distribución registrada de dividendos se divide en mitades entre dos usuarios socio activos. El registro societario y la condición de vesting no se verifican automáticamente.','Acuerdo de Socios Fundadores, cláusulas IV y V'),
 item('G02','Doble autorización para gastos',check,'Todo gasto superior a <b>$1,000 MXN</b> y toda aportación de capital quedan pendientes hasta la aprobación del otro socio. Los movimientos pendientes no se agregan a caja.','Acuerdo de Socios Fundadores, cláusulas XVII y XXI'),
 item('G03','Decisiones críticas y conflicto',pending,'Ingresos de socios, deuda, PI y cambios societarios requieren aprobación formal fuera de este MVP. Los cambios de parámetros tienen bitácora, pero todavía no exigen dos votos.','Acuerdo de Socios Fundadores, cláusula XVIII')])+
 section('02 · Modelo operativo','Parámetros de planeación; no son costos verificados',[
 item('F01','Costos y punto de equilibrio',draft,`Gasto fijo mensual: <b>${peso(s.monthly_fixed_cents)}</b>. Costo variable modelado: <b>${s.variable_cost_pct}%</b> de ingresos. Estos números NO se calculan automáticamente desde proveedores ni bancos.`),
 item('F02','Provisión fiscal hipotética',draft,`<b>${s.planning_tax_pct}%</b> del resultado positivo dentro del simulador y del tope interno. No sustituye el cálculo fiscal ni separa automáticamente IVA/ISR de la caja.`),
 item('F03','Fondo de estabilidad',draft,`Meta: <b>${peso(s.reserve_target_cents)}</b>. El sistema calcula la caja teórica excedente sobre ese monto, pero no inmoviliza el dinero ni verifica saldos bancarios.`)])+
 section('03 · Remuneraciones','Pago por trabajo independiente de los dividendos',[
 item('R01','Etapa 0 — sin remuneración fija',draft,'Hasta que exista liquidez y acuerdo entre socios, la remuneración propuesta es cero.'),
 item('R02','Etapa 1 / Etapa 2',draft,`Presupuestos por socio: <b>${peso(s.salary_stage1_cents)}</b> y <b>${peso(s.salary_stage2_cents)}</b> mensuales. Ingresos objetivo: <b>${peso(s.salary_stage1_revenue_cents)}</b> y <b>${peso(s.salary_stage2_revenue_cents)}</b>. Los meses consecutivos de cumplimiento aún no se validan automáticamente.`),
 item('R03','Autorización cruzada',check,'La solicitud operativa debe ser autorizada por el otro socio. Registrar el pago genera un egreso; no hace transferencia bancaria real ni CFDI de nómina.','Acuerdo de Socios Fundadores, cláusula XX')])+
 section('04 · Utilidades y dividendos','Potencial de reparto sujeto a capacidad y documentación',[
 item('U01','Reparto del flujo libre',draft,'Antes de cubrir la reserva objetivo: asignación sugerida de 70% a reserva y 30% a crecimiento; sin dividendos. Después: 50% reinversión, 20% fondo y 30% bolsa máxima candidata. Son políticas propuestas; la aplicación NO aparta físicamente esos montos.'),
 item('U02','Doble voto y límite del 30%',check,'Se requieren dos aprobaciones, caja teórica sobre la reserva y límite interno de 30% del resultado operativo estimado después de la provisión hipotética. No valida utilidades contables legalmente distribuibles.'),
 item('U03','Acta y validación fiscal',pending,'Antes de pagar: estados financieros aprobados, acta societaria, impuestos y validación contable. La aplicación solicita una referencia de acta, pero no autentica su contenido ni el pago bancario.')])+
 section('05 · Transparencia y límites','Evitar confundir el sistema con contabilidad certificada',[
 item('T01','Trazabilidad',check,'Las altas, autorizaciones, anulaciones y cambios de configuración quedan en auditoría; esta bitácora todavía NO es inmutable contra administradores de base de datos.'),
 item('T02','Terceros y comisiones',pending,'Las comisiones de colaboradores se capturan como costos reales del proyecto. El MVP aún no aplica automáticamente todos los contratos individuales.'),
 item('T03','Régimen fiscal y ley',pending,'Las remuneraciones y dividendos deberán revisarse con el contador y asesor jurídico antes de cualquier desembolso real.')])+
 `</div><div class="card" style="margin-top:18px"><div class="card-title">¿Dónde puedo cambiar cada regla?</div><p class="footnote">Los supuestos monetarios se modifican desde <strong>Configuración → Modelo económico</strong>; las metas mensuales, desde <strong>Planeación</strong>. Los controles contractuales de $1,000, participación 50/50 y aprobaciones permanecen fijos en esta versión y sólo deben cambiarse después de aprobar una nueva política.</p><button class="btn primary" data-action="goto:settings">Ir a configuración ↗</button></div>`;
}

async function renderSettings(){
 const [{settings:s},{users}]=await Promise.all([get('/api/settings'),get('/api/users')]);cache.settings=s;
 const settingsFields=[['monthly_fixed_cents','Gastos fijos mensuales (MXN)',true],['variable_cost_pct','Costos variables sobre ventas (%)',false],['planning_tax_pct','Provisión de planeación fiscal (%)',false],['reserve_target_cents','Reserva objetivo (MXN)',true],['salary_stage1_cents','Presupuesto remuneración etapa 1 / socio',true],['salary_stage2_cents','Presupuesto remuneración etapa 2 / socio',true],['salary_stage1_revenue_cents','Umbral facturación etapa 1 / mes',true],['salary_stage2_revenue_cents','Umbral facturación etapa 2 / mes',true]];
 $('content').innerHTML=warning()+header('ADMINISTRACIÓN','Configuración','Políticas financieras, usuarios y controles de acceso.')+
 `<div class="settings-sections"><div class="card"><div class="card-title-row"><div class="card-title">Modelo económico</div><span class="kpi-badge">2026–2027</span></div><p class="footnote">Los valores iniciales son supuestos editables, no datos reales.</p><form id="settingsForm" class="form-grid">${settingsFields.map(([key,title,isMoney])=>`<label class="${isMoney?'':'wide'}">${esc(title)}<input name="${key}" ${canWrite()?'':'disabled'} type="number" min="0" step="${isMoney?'.01':'1'}" value="${isMoney?(s[key]/100).toFixed(2):s[key]}"></label>`).join('')}<div class="wide">${canWrite()?'<button class="btn primary">Guardar parámetros ↗</button>':'<span class="muted">Solo consulta</span>'}</div></form></div>`+
 `<div class="card"><div class="card-title-row"><div class="card-title">Acceso al sistema</div>${canWrite()?btn('＋ Dar acceso de consulta','new-user','secondary'):''}</div><div class="table-wrap"><table><thead><tr><th>Usuario</th><th>Perfil</th><th>Acceso</th></tr></thead><tbody>${users.map(x=>`<tr><td><b>${esc(x.name)}</b><small>${esc(x.email)}</small></td><td>${badge(x.role==='socio'?'activo':'cotizado')}</td><td>${x.active?'Activo':'Bloqueado'}</td></tr>`).join('')}</tbody></table></div><hr class="separator"><div class="card-title">Seguridad personal</div><p class="footnote">Cambia tu contraseña. El sistema cerrará todas tus sesiones existentes.</p>${btn('Cambiar mi contraseña','change-password')}<hr class="separator"><div class="card-title">Estado de conexión</div><div class="metric-line"><span>Motor de datos</span><strong>${esc(dbMode==='sqlite'?'SQLite local (prueba)':'SQL Server central')}</strong></div><div class="metric-line"><span>Entorno</span><strong>${esc(env)}</strong></div><div class="metric-line"><span>Mi perfil</span><strong>${esc(user.role)}</strong></div><div class="metric-line"><span>Participación objetivo</span><strong>50% / 50%</strong></div></div></div>`;
 $('settingsForm').addEventListener('submit',async e=>{e.preventDefault();try{const o={};for(const [key,_,isMoney] of settingsFields){const v=Number(e.target.elements[key].value);if(!Number.isFinite(v)||v<0)throw Error('Importe inválido');o[key]=isMoney?Math.round(v*100):Math.round(v)}await put('/api/settings',o);showToast('Parámetros guardados');renderSettings()}catch(ex){showToast(ex.message,true)}});
}
function openModal(title,subtitle,fields,submitText,onSubmit){
 const inner=`<div class="eyebrow">VLUX · FINANCE OS</div><h2>${title}</h2><p>${subtitle}</p><form id="modalForm"><div class="form-grid">${fields}</div><div class="modal-actions"><button type="button" class="btn ghost" id="cancelModal">Cancelar</button><button class="btn primary">${submitText} ↗</button></div></form>`;
 $('modalBody').innerHTML=inner;$('modal').classList.remove('hidden');$('cancelModal').onclick=closeModal;
 $('modalForm').onsubmit=async ev=>{ev.preventDefault();const submit=ev.target.querySelector('button[type=submit],button:not([type])');if(submit)submit.disabled=true;try{await onSubmit(ev.target);closeModal();showToast('Registro guardado correctamente');await navigate(page)}catch(e){showToast(e.message,true)}finally{if(submit)submit.disabled=false}};
}
function closeModal(){$('modal').classList.add('hidden');$('modalBody').innerHTML=''}
function inp(name,title,type='text',val='',required=true,wide=false){return `<label class="${wide?'wide':''}">${esc(title)}<input name="${name}" type="${type}" value="${esc(val)}" ${required?'required':''} ${type==='number'?'min="0" step="0.01"':''}></label>`}
function select(name,title,options,wide=false){return `<label class="${wide?'wide':''}">${esc(title)}<select name="${name}">${options.map(([v,label])=>`<option value="${esc(v)}">${esc(label)}</option>`).join('')}</select></label>`}
async function newMovement(){if(!canWrite())return;const {projects}=await get('/api/projects');
 openModal('Nuevo movimiento','Registra un importe efectivamente cobrado o pagado. No incluyas IVA como ganancia.',
 select('kind','Tipo de movimiento',[['income','Ingreso'],['expense','Gasto operativo'],['capital','Aportación de capital']])+
 inp('amount','Importe en MXN (sin IVA)','number','',true)+inp('txn_date','Fecha','date',today)+
 select('project_id','Proyecto (opcional)',[['','Sin proyecto'],...projects.map(p=>[p.id,p.name])])+
 inp('category','Categoría','text','Servicios de software')+inp('reference','Referencia bancaria / folio','text','',false,true)+
 `<label class="wide">Concepto<textarea name="description" required placeholder="Qué se cobró, pagó o aportó"></textarea></label>`,
 'Registrar movimiento',async f=>post('/api/transactions',{kind:f.kind.value,amount_cents:num(f.amount.value),txn_date:f.txn_date.value,project_id:f.project_id.value?Number(f.project_id.value):null,category:f.category.value,reference:f.reference.value,description:f.description.value}));
}
function newProject(){openModal('Nuevo proyecto','Vincula los ingresos y gastos a un cliente o producto.',inp('name','Nombre del proyecto')+inp('client','Cliente / unidad de negocio')+inp('budget','Presupuesto objetivo (MXN)','number','0',true,true),'Crear proyecto',f=>post('/api/projects',{name:f.name.value,client:f.client.value,budget_cents:Math.round(Number(f.budget.value)*100),status:'activo'}))}
async function newComp(){const {users}=await get('/api/compensations');openModal('Solicitar remuneración','El otro socio debe autorizar antes de registrarla como pagada.',select('user_id','Beneficiario',users.filter(x=>x.role==='socio').map(x=>[x.id,x.name]))+inp('period','Mes de trabajo','month',currentPeriod)+inp('amount','Importe bruto / presupuesto MXN','number')+inp('notes','Concepto de remuneración','text','Trabajo operativo',false,true),'Enviar solicitud',f=>post('/api/compensations',{user_id:Number(f.user_id.value),period:f.period.value,amount_cents:num(f.amount.value),notes:f.notes.value}))}
function newDividend(){openModal('Propuesta de distribución','Propuesta interna. No es dividendo autorizado ni retención calculada.',inp('period','Trimestre','text',quarter)+inp('amount','Fondo bruto para ambos socios (MXN)','number')+inp('accounting_reference','Referencia contable o folio del acta (opcional)','text','',false,true),'Crear propuesta',f=>post('/api/dividends',{period:f.period.value,amount_cents:num(f.amount.value),accounting_reference:f.accounting_reference.value}))}
function newUser(){openModal('Acceso de consulta','Este perfil puede ver información pero no aprobar ni modificar finanzas.',inp('name','Nombre')+inp('email','Correo electrónico','email')+inp('password','Contraseña inicial de 12+ caracteres','password','',true,true),'Crear acceso',f=>post('/api/users',{name:f.name.value,email:f.email.value,password:f.password.value,role:'consulta'}))}
function changePassword(){openModal('Cambiar contraseña','Se cerrará tu sesión y tendrás que ingresar de nuevo.',inp('current_password','Contraseña actual','password','',true,true)+inp('new_password','Contraseña nueva (mínimo 12 caracteres)','password','',true,true),'Actualizar contraseña',async f=>{await post('/api/change-password',{current_password:f.current_password.value,new_password:f.new_password.value});setTimeout(()=>location.reload(),900)})}
async function action(item){
 if(item.startsWith('collab:'))return collabAction(item);
 if(item==='refresh')return navigate(page);
 if(item.startsWith('goto:'))return navigate(item.slice(5));
 if(item.startsWith('save-forecast:')){const period=item.split(':')[1],field=document.querySelector(`[data-forecast-value="${period}"]`);if(!field)return;try{const v=Number(field.value);if(!Number.isFinite(v)||v<0)throw Error('Importe inválido');await put('/api/forecast',{period,revenue_cents:Math.round(v*100)});showToast('Meta actualizada');return navigate('planning')}catch(e){return showToast(e.message,true)}}
 if(item==='new-transaction')return newMovement();
 if(item==='new-project')return newProject();
 if(item==='new-comp')return newComp();
 if(item==='new-dividend')return newDividend();
 if(item==='new-user')return newUser();
 if(item==='change-password')return changePassword();
 if(item.startsWith('approve-txn:'))return confirm('¿Aprobar el movimiento registrado por el otro socio?')&&mutate('/api/transactions/'+item.split(':')[1]+'/approve',{});
 if(item.startsWith('void:')){let reason=prompt('Motivo de anulación (quedará en auditoría):');if(!reason)return;return confirm('¿Anular el movimiento? No se eliminará del histórico.')&&mutate('/api/transactions/'+item.split(':')[1]+'/void',{reason})}
 if(item.startsWith('approve-comp:'))return confirm('¿Autorizar esta remuneración?')&&mutate('/api/compensations/'+item.split(':')[1]+'/approve',{});
 if(item.startsWith('pay-comp:'))return confirm('¿Confirmas que efectivamente se pagó esta remuneración? Se registrará como gasto.')&&mutate('/api/compensations/'+item.split(':')[1]+'/pay',{});
 if(item.startsWith('approve-dividend:'))return confirm('¿Aprobar esta propuesta? La distribución requiere las condiciones societarias y fiscales aplicables.')&&mutate('/api/dividends/'+item.split(':')[1]+'/approve',{});
 if(item.startsWith('pay-dividend:')){let ref=prompt('Indica folio del acta + constancia de validación del contador:');if(!ref)return;return confirm('ATENCIÓN: se registrarán DOS salidas de efectivo 50/50. Confirma únicamente si el reparto fue realmente pagado y los requisitos legales están acreditados.')&&mutate('/api/dividends/'+item.split(':')[1]+'/pay',{accounting_reference:ref})}
}
async function mutate(url,data){try{await post(url,data);showToast('Operación completada y auditada');await navigate(page)}catch(e){showToast(e.message,true)}}
async function restoreSession(){
 try{const me=await get('/api/me');user=me.user;env=me.mode;dbMode=me.database;showShell()}catch{showLogin()}
}
function showLogin(){$('shell').classList.add('hidden');$('login').classList.remove('hidden');}
function showShell(){$('login').classList.add('hidden');$('shell').classList.remove('hidden');$('environment').textContent=env==='local'?'LOCAL · SIN PRECARGA':env.toUpperCase();$('environment').className='env'+(env==='production'?' prod':'');$('dbMode').textContent=(dbMode==='sqlite'?(env==='local'?'Base local · sin precarga':'Demo · SQLite'):'Central · SQL Server');$('avatar').textContent=(user.name||'V').split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase();$('today').textContent=new Date().toLocaleDateString('es-MX',{day:'numeric',month:'long',year:'numeric'});navigate('dashboard')}
$('loginForm').addEventListener('submit',async ev=>{ev.preventDefault();$('loginError').textContent='';try{await post('/api/login',{email:$('email').value,password:$('password').value});$('password').value='';await restoreSession()}catch(e){$('loginError').textContent=e.message;if(e.code==='must_change_password'){$('firstPasswordForm').classList.remove('hidden');$('newPassword').focus()}}});$('firstPasswordForm').addEventListener('submit',async ev=>{ev.preventDefault();$('loginError').textContent='';if($('newPassword').value!==$('newPasswordAgain').value){$('loginError').textContent='Las contraseñas nuevas no coinciden';return}try{await post('/api/first-password',{email:$('email').value,current_password:$('password').value,new_password:$('newPassword').value});$('password').value='';$('newPassword').value='';$('newPasswordAgain').value='';$('firstPasswordForm').classList.add('hidden');$('loginError').textContent='Contraseña actualizada. Inicia sesión con la nueva contraseña.'}catch(e){$('loginError').textContent=e.message}});
$('nav').addEventListener('click',ev=>{const e=ev.target.closest('[data-nav]');if(e)navigate(e.dataset.nav)});
$('content').addEventListener('click',ev=>{let e=ev.target.closest('[data-action]');if(e)action(e.dataset.action)});
$('content').addEventListener('click',ev=>{let e=ev.target.closest('[data-filter]');if(e){filterType=e.dataset.filter;renderTransactions()}});
$('content').addEventListener('change',ev=>{let e=ev.target.closest('[data-projectstatus]');if(e){post('/api/projects/'+e.dataset.projectstatus+'/status',{status:e.value}).then(()=>{showToast('Estado actualizado');renderProjects()}).catch(x=>showToast(x.message,true))}});
$('logout').onclick=async()=>{try{await post('/api/logout',{})}finally{user=null;showLogin()}};
$('closeModal').onclick=closeModal;
$('modal').addEventListener('click',e=>{if(e.target===$('modal'))closeModal()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
restoreSession();
