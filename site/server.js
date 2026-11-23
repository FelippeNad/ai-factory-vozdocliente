'use strict';

// VozDoCliente CX — aplicação de demonstração (Etapa 3).
// Usa somente APIs Node.js nativas. Não registra nem retorna tokens ou dados pessoais.
const http = require('node:http');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');

const PORT = Number(process.env.PORT || 3000);
const SESSION_SECRET = process.env.SESSION_SECRET || '';
const APP_PASSWORD = process.env.APP_PASSWORD || '';
const CONFIG = Object.freeze({
  base: process.env.CLASSIFIER_DEV_BASE_ID || '',
  table: process.env.CLASSIFIER_DEV_TABLE_ID || '',
  airtableToken: process.env.AIRTABLE_DEV_PAT || '',
  webhookUrl: process.env.N8N_DEV_WEBHOOK_URL || '',
  webhookAuthName: process.env.N8N_DEV_WEBHOOK_AUTH_HEADER || '',
  webhookAuthValue: process.env.N8N_DEV_WEBHOOK_AUTH_VALUE || '',
});
const STATIC = path.join(__dirname, 'public');
const LIMIT = new Map();
const MAX_SESSION_AGE = 12 * 60 * 60 * 1000;

if (!APP_PASSWORD || APP_PASSWORD.length < 10 || !SESSION_SECRET || SESSION_SECRET.length < 24) {
  throw new Error('Configure APP_PASSWORD (min. 10 caracteres) e SESSION_SECRET (min. 24 caracteres) antes de iniciar.');
}
function webUrlIsDev(raw) {
  try {
    const u = new URL(raw);
    return u.protocol === 'https:' && /\/webhook\/review-v4-otimizado-dev\/?$/.test(u.pathname) && !u.username && !u.password && !u.search;
  } catch { return false; }
}
function configValid() {
  return /^app[A-Za-z0-9]{14}$/.test(CONFIG.base) && /^tbl[A-Za-z0-9]{14}$/.test(CONFIG.table)
    && Boolean(CONFIG.airtableToken) && webUrlIsDev(CONFIG.webhookUrl)
    && ((!CONFIG.webhookAuthName && !CONFIG.webhookAuthValue) || (Boolean(CONFIG.webhookAuthName) && Boolean(CONFIG.webhookAuthValue)));
}
function json(res, status, data, cookie) {
  const headers = { 'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff' };
  if (cookie) headers['Set-Cookie'] = cookie;
  res.writeHead(status, headers);
  res.end(JSON.stringify(data));
}
function cookies(req) { return Object.fromEntries((req.headers.cookie || '').split(';').map(v => v.trim()).filter(Boolean).map(v => { const i=v.indexOf('=');return i<0?[v,'']:[v.slice(0,i),v.slice(i+1)]; })); }
function signature(t) { return crypto.createHmac('sha256', SESSION_SECRET).update(t).digest('hex'); }
function safeEquals(a,b) { const x=Buffer.from(String(a));const y=Buffer.from(String(b));return x.length===y.length && crypto.timingSafeEqual(x,y); }
function authorized(req) {
  const c=cookies(req).vdc_auth;
  if(!c) return false;
  const [t,s]=c.split('.');
  const ts=Number(t);
  return /^\d{13}$/.test(t || '') && /^[a-f0-9]{64}$/.test(s || '') && Number.isSafeInteger(ts)
    && ts <= Date.now() && Date.now() - ts < MAX_SESSION_AGE && safeEquals(signature(t), s);
}
function makeCookie(value, age) { return `vdc_auth=${value}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${age}`; }
async function parseJson(req) {
  if (!(req.headers['content-type'] || '').startsWith('application/json')) throw Object.assign(new Error('Formato não aceito.'), {status:415});
  let total=0; const pieces=[];
  for await (const chunk of req) { total += chunk.length; if(total>8192) throw Object.assign(new Error('Dados acima do limite.'),{status:413}); pieces.push(chunk); }
  try{return JSON.parse(Buffer.concat(pieces).toString('utf8'));} catch {throw Object.assign(new Error('JSON inválido.'),{status:400});}
}
function corsCheck(req) {
  if(!['POST','PUT','PATCH','DELETE'].includes(req.method)) return true;
  const origin=req.headers.origin;
  const hostname=req.headers.host;
  if(!origin) return true;
  try{return new URL(origin).host===hostname;}catch{return false;}
}
function limited(req) {
  const ip=String(req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'unknown').split(',')[0].trim();
  const now=Date.now(); const arr=(LIMIT.get(ip)||[]).filter(t=>now-t<600000);
  if(arr.length>=8) { LIMIT.set(ip,arr); return true; }
  arr.push(now);LIMIT.set(ip,arr);
  if(LIMIT.size>3000) LIMIT.clear();
  return false;
}
function authHeaders() { return { Authorization:`Bearer ${CONFIG.airtableToken}` }; }
async function airtable(url) {
  const response=await fetch(url,{headers:authHeaders(),signal:AbortSignal.timeout(12000)});
  if(!response.ok) throw new Error(`Airtable DEV indisponível (HTTP ${response.status}).`);
  return response.json();
}
function airtableUrl() { return `https://api.airtable.com/v0/${CONFIG.base}/${CONFIG.table}`; }
function publicRecord(record) {
  const v=record?.fields || {};
  return {
    review_id:String(v.review_id || ''), sentiment:String(v.sentiment || ''), theme:String(v.theme || ''),
    rating:Number(v.rating || 0), source:String(v.source || ''), processed_at:String(v.processed_at || '')
  }; // Nunca enviar review_text, customer_name ou o objeto Airtable original.
}
async function findReview(id) {
  const u=new URL(airtableUrl());
  u.searchParams.set('maxRecords','1');
  u.searchParams.set('filterByFormula',`{review_id}='${id}'`); // ID criado pelo servidor: [A-Za-z0-9-] somente.
  const data=await airtable(u);
  return data.records?.[0]?publicRecord(data.records[0]):null;
}
async function getReviews() {
  const u=new URL(airtableUrl());u.searchParams.set('maxRecords','100');
  for(const f of ['review_id','sentiment','theme','rating','source','processed_at'])u.searchParams.append('fields[]',f);
  const data=await airtable(u);
  return (data.records || []).map(publicRecord).filter(v=>v.review_id).sort((a,b)=>b.processed_at.localeCompare(a.processed_at));
}
async function sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
function sanitizeInput(data) {
  const text=typeof data.review_text==='string'?data.review_text.trim():'';
  const rating=Number(data.rating);
  if(text.length<10 || text.length>700 || !Number.isInteger(rating) || rating<1 || rating>5) {
    throw Object.assign(new Error('Informe uma avaliação fictícia de 10 a 700 caracteres e nota de 1 a 5.'),{status:400});
  }
  // O workflow DEV armazena texto original no Airtable: rejeite dados pessoais no formulário público.
  if(/[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}/.test(text) || /\b(?:\d[\s.()-]?){9,}\b/.test(text) || /(?:https?:\/\/|www\.)\S+/i.test(text)) {
    throw Object.assign(new Error('Use somente dados fictícios, sem contatos, documentos ou links.'),{status:400});
  }
  return {text,rating};
}
async function submit(data) {
  const {text,rating}=sanitizeInput(data);
  const id=`ETAPA3-DEMO-${Date.now()}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
  const payload={review_id:id,customer_name:'Cliente Fictício',source:'formulario',rating,review_text:text};
  const headers={'Content-Type':'application/json'};
  if(CONFIG.webhookAuthName && CONFIG.webhookAuthValue) headers[CONFIG.webhookAuthName]=CONFIG.webhookAuthValue;
  const r=await fetch(CONFIG.webhookUrl,{method:'POST',headers,body:JSON.stringify(payload),signal:AbortSignal.timeout(18000)});
  if(!r.ok) throw Object.assign(new Error(`Webhook DEV respondeu HTTP ${r.status}. Verifique se o fluxo DEV está publicado.`),{status:502});
  // O webhook padrão do n8n responde assim que a execução COMEÇA. Confirmamos no Airtable.
  let lastError;
  for(let i=0;i<13;i++) {
    await sleep(1250);
    try { const found=await findReview(id);if(found) return {accepted:true,confirmed:true,record:found}; }
    catch(e){lastError=e.message;break;}
  }
  return {accepted:true,confirmed:false,review_id:id,message:lastError||'Recebido pelo webhook DEV, mas ainda sem confirmação de gravação no Airtable. Confira Executions no n8n.'};
}
const files={ '/':'index.html', '/index.html':'index.html', '/styles.css':'styles.css', '/app.js':'app.js' };
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8'};
async function handle(req,res) {
  res.setHeader('X-Frame-Options','DENY');
  res.setHeader('Referrer-Policy','no-referrer');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
  if(!corsCheck(req)) return json(res,403,{error:'Origem não autorizada.'});
  const url=new URL(req.url||'/',`http://${req.headers.host || 'localhost'}`);
  if(req.method==='GET' && url.pathname==='/health')return json(res,200,{status:'online'});
  if(req.method==='POST' && url.pathname==='/api/login') {
    if(limited(req))return json(res,429,{error:'Muitas tentativas. Tente novamente mais tarde.'});
    const input=await parseJson(req);if(!safeEquals(crypto.createHash('sha256').update(String(input.password||'')).digest('hex'),crypto.createHash('sha256').update(APP_PASSWORD).digest('hex')))
      return json(res,401,{error:'Senha de demonstração incorreta.'});
    const t=String(Date.now());return json(res,200,{ok:true},makeCookie(`${t}.${signature(t)}`,43200));
  }
  if(req.method==='POST' && url.pathname==='/api/logout')return json(res,200,{ok:true},makeCookie('',0));
  if(req.method==='GET' && url.pathname==='/api/session')return json(res,200,{authenticated:authorized(req)});
  if(url.pathname.startsWith('/api/')) {
    if(!authorized(req))return json(res,401,{error:'Faça login na demonstração.'});
    if(req.method==='GET' && url.pathname==='/api/reviews') {
      if(!configValid())return json(res,503,{error:'Integrações DEV ainda não configuradas no serviço web.'});
      const reviews=await getReviews();return json(res,200,{reviews,scope:'Amostra de até 100 registros da base DEV. Não representa toda a produção.'});
    }
    if(req.method==='POST' && url.pathname==='/api/submit') {
      if(!configValid())return json(res,503,{error:'Integrações DEV ainda não configuradas no serviço web.'});
      if(limited(req))return json(res,429,{error:'Limite de demonstrações atingido (8 a cada 10 minutos por origem).'});
      return json(res,200,await submit(await parseJson(req)));
    }
    return json(res,404,{error:'Rota inexistente.'});
  }
  if(req.method==='GET' && files[url.pathname]) {
    const file=path.join(STATIC,files[url.pathname]);
    const content=await fs.readFile(file);
    res.writeHead(200,{'Content-Type':types[path.extname(file)],'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
    return res.end(content);
  }
  return json(res,404,{error:'Não encontrado.'});
}
http.createServer((req,res)=>Promise.resolve(handle(req,res)).catch(err=>{
  // Sem tokens, payloads, stack traces ou respostas de fornecedores em logs públicos.
  const status=err.status || (err.name==='TimeoutError'?504:502);
  const message=err.status?err.message:err.message?.startsWith('Airtable DEV indisponível')?err.message:'Integração indisponível. Verifique a execução do n8n e a configuração DEV.';
  if(!res.headersSent)json(res,status,{error:message});else res.end();
})).listen(PORT,'0.0.0.0',()=>console.log(`VozDoCliente CX: web online na porta ${PORT} | integrações DEV configuradas: ${configValid()}`));
