'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const net=require('node:net');
const path=require('node:path');
function freePort(){return new Promise((resolve,reject)=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});s.on('error',reject);});}
async function ready(url){for(let i=0;i<60;i++){try{const r=await fetch(url+'/health');if(r.status===200)return;}catch{}await new Promise(r=>setTimeout(r,100));}throw new Error('Servidor não iniciou.');}
test('site WEB DEV: health, login, consulta segura, envio ao webhook e polling Airtable',async()=>{
  const port=await freePort();
  const child=spawn(process.execPath,['--require',path.join(__dirname,'mock-fetch.js'),'server.js'],{
    cwd:path.join(__dirname,'..'),stdio:'pipe',env:{...process.env,PORT:String(port),APP_PASSWORD:'SENHA-FICTICIA-1234',SESSION_SECRET:'a'.repeat(64),CLASSIFIER_DEV_BASE_ID:'app12345678901234',CLASSIFIER_DEV_TABLE_ID:'tbl12345678901234',AIRTABLE_DEV_PAT:'token-ficticio',N8N_DEV_WEBHOOK_URL:'https://mock-n8n.example/webhook/review-v4-otimizado-dev'}});
  try {
    const base=`http://127.0.0.1:${port}`;await ready(base);
    assert.equal((await fetch(base+'/')).status,200);
    assert.equal((await fetch(base+'/api/reviews')).status,401);
    const bad=await fetch(base+'/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:'errada'})});
    assert.equal(bad.status,401);
    const login=await fetch(base+'/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:'SENHA-FICTICIA-1234'})});
    assert.equal(login.status,200);
    const cookie=login.headers.get('set-cookie').split(';')[0];
    const h={Cookie:cookie};
    const list=await (await fetch(base+'/api/reviews',{headers:h})).json();
    assert.equal(list.reviews.length,1);
    assert.equal(list.reviews[0].sentiment,'positivo');
    assert.equal(Object.hasOwn(list.reviews[0],'customer_name'),false);
    assert.equal(Object.hasOwn(list.reviews[0],'review_text'),false);
    const sent=await fetch(base+'/api/submit',{method:'POST',headers:{...h,'Content-Type':'application/json'},body:JSON.stringify({rating:1,review_text:'O pedido fictício chegou muito atrasado.'})});
    assert.equal(sent.status,200);
    const answer=await sent.json();assert.equal(answer.confirmed,true);
    assert.equal(answer.record.sentiment,'negativo');
    assert.match(answer.record.review_id,/^ETAPA3-DEMO-/);
    const pii=await fetch(base+'/api/submit',{method:'POST',headers:{...h,'Content-Type':'application/json'},body:JSON.stringify({rating:5,review_text:'Meu email é aluno@exemplo.com e quero ajuda.'})});
    assert.equal(pii.status,400);
    assert.equal((await fetch(base+'/api/session',{headers:h})).status,200);
  } finally {child.kill('SIGTERM');}
});
