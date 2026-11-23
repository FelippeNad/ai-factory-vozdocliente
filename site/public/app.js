'use strict';
const el=(id)=>document.getElementById(id);
const positive='O produto chegou rapidamente, bem embalado e com ótima qualidade. Superou minhas expectativas!';
const negative='Meu pedido chegou com muito atraso e a embalagem estava danificada. Preciso de ajuda da equipe de atendimento.';
const sentimentLabels={positivo:'Positivo',neutro:'Neutro',negativo:'Negativo'};
const themeLabels={entrega:'Entrega',produto:'Produto',atendimento:'Atendimento',preco:'Preço',app_bug:'Problema no app'};
async function api(url, options={}) {
  let r;
  try { r=await fetch(url,{credentials:'same-origin',cache:'no-store',...options}); }
  catch {throw new Error('Falha de rede. Confira a conexão.');}
  let body={};try{body=await r.json();}catch{}
  if(!r.ok)throw new Error(body.error||`Falha HTTP ${r.status}.`);
  return body;
}
function feedback(id,text,kind='') {
  const box=el(id);box.hidden=false;box.className='notice'+(kind?' '+kind:'');box.textContent=text;
}
function show(which) {el('login').hidden=which!=='login';el('workspace').hidden=which!=='workspace';}
async function session() {
  try {const data=await api('/api/session');show(data.authenticated?'workspace':'login');if(data.authenticated)await load();}
  catch{show('login');feedback('login-feedback','Não foi possível verificar o acesso.','error');}
}
function textCell(tr,text,cls='') {const td=document.createElement('td');td.textContent=String(text);if(cls)td.className=cls;tr.append(td);return td;}
function status(sentiment) {const labels={positivo:'positive',neutro:'neutral',negativo:'negative'};return labels[sentiment]||'unknown';}
function dateFormat(value) {if(!value)return '—';const d=new Date(value);return Number.isNaN(d.getTime())?'—':new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(d);}
function drawRows(reviews) {
  const target=el('history-body');target.textContent='';
  if(!reviews.length){const tr=document.createElement('tr');textCell(tr,'Nenhuma avaliação classificada encontrada nesta amostra.','empty-row').colSpan=5;target.append(tr);return;}
  for(const rec of reviews.slice(0,20)){
    const tr=document.createElement('tr');textCell(tr,rec.review_id,'review-code');
    const td=document.createElement('td');const span=document.createElement('span');span.className=`sentiment-tag ${status(rec.sentiment)}`;span.textContent=sentimentLabels[rec.sentiment]||'Pendente';td.append(span);tr.append(td);
    textCell(tr,themeLabels[rec.theme]||'—');textCell(tr,rec.rating?`${rec.rating}/5`:'—');textCell(tr,dateFormat(rec.processed_at));target.append(tr);
  }
}
function drawStats(reviews) {
  const count=reviews.length;const valid=reviews.filter(r=>['positivo','neutro','negativo'].includes(r.sentiment));
  const n=valid.filter(r=>r.sentiment==='negativo').length;
  el('m-count').textContent=String(count);el('m-negative').textContent=String(n);el('m-negative-note').textContent=valid.length?`${Math.round(n/valid.length*100)}% entre ${valid.length} classificações conhecidas`:'Sem classificações confirmadas';
  el('m-themes').textContent=String(new Set(valid.map(r=>r.theme).filter(Boolean)).size);
  el('m-integration').innerHTML='<span class="status-dot"></span> Conectado';
  for(const [key,id] of [['positivo','positive'],['neutro','neutral'],['negativo','negative']]){
    const v=valid.filter(r=>r.sentiment===key).length;el(`bar-${id}-number`).textContent=String(v);
    el(`bar-${id}`).style.width=valid.length?`${v/valid.length*100}%`:'0%';
  }
}
async function load() {
  el('refresh').disabled=true;el('refresh').textContent='↻ Atualizando...';
  try {const data=await api('/api/reviews');drawStats(data.reviews);drawRows(data.reviews);el('global-feedback').hidden=true;}
  catch(e){feedback('global-feedback',e.message,'error');el('m-integration').textContent='Indisponível';el('history-body').textContent='';}
  finally{el('refresh').disabled=false;el('refresh').textContent='↻ Atualizar dados';}
}
el('login-form').addEventListener('submit',async e=>{
  e.preventDefault();const btn=e.currentTarget.querySelector('button');btn.disabled=true;el('login-feedback').hidden=true;
  try{await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:el('password').value})});el('password').value='';show('workspace');await load();}
  catch(err){feedback('login-feedback',err.message,'error');}
  finally{btn.disabled=false;}
});
el('logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});}catch{}show('login');});
el('refresh').addEventListener('click',load);
el('example-positive').addEventListener('click',()=>{el('review-text').value=positive;el('rating').value='5';});
el('example-negative').addEventListener('click',()=>{el('review-text').value=negative;el('rating').value='1';});
el('review-form').addEventListener('submit',async e=>{
  e.preventDefault();const btn=el('submit-review');const result=el('submit-result');result.hidden=false;result.className='submit-result pending';result.textContent='Enviando ao n8n DEV e aguardando confirmação no Airtable...';btn.disabled=true;btn.textContent='Classificando avaliação...';
  try {
    const r=await api('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_text:el('review-text').value,rating:Number(el('rating').value)})});
    result.className=`submit-result ${r.confirmed?'success':'pending'}`;result.textContent='';
    const title=document.createElement('strong');title.textContent=r.confirmed?'✓ Avaliação classificada!':'◷ Enviada; aguardando confirmação';result.append(title);
    const line=document.createElement('div');
    line.textContent=r.confirmed?`${sentimentLabels[r.record.sentiment]||r.record.sentiment} · ${themeLabels[r.record.theme]||r.record.theme} · Nota ${r.record.rating}/5`:(r.message||'Confira a execução no n8n.');result.append(line);
    const id=document.createElement('small');id.textContent=`ID: ${r.confirmed?r.record.review_id:r.review_id}`;result.append(id);
    if(r.confirmed)await load();
  } catch(err){result.className='submit-result error';result.textContent=`Não foi possível confirmar o envio: ${err.message}`;}
  finally{btn.disabled=false;btn.textContent='Enviar para classificação →';}
});
for(const link of document.querySelectorAll('.nav-item[href^="#"]')) link.addEventListener('click',()=>{
  for(const l of document.querySelectorAll('.nav-item[href^="#"]'))l.classList.remove('active');link.classList.add('active');
});
session();
