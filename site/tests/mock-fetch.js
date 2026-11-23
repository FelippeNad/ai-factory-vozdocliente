'use strict';
const rows=[{fields:{review_id:'SMOKE-POS-001',sentiment:'positivo',theme:'produto',rating:5,source:'formulario',processed_at:'2026-11-22T18:00:00Z'}}];
globalThis.fetch=async (url,opts={})=>{
  const u=new URL(String(url));
  if(u.hostname==='mock-n8n.example'){
    const data=JSON.parse(opts.body);
    rows.push({fields:{review_id:data.review_id,sentiment:data.rating<=2?'negativo':'positivo',theme:data.rating<=2?'entrega':'produto',rating:data.rating,source:'formulario',processed_at:new Date().toISOString()}});
    return new Response(JSON.stringify({message:'Workflow started'}),{status:200});
  }
  if(u.hostname==='api.airtable.com') {
    const formula=u.searchParams.get('filterByFormula');
    const selected=formula?rows.filter(r=>formula.includes(r.fields.review_id)):rows;
    return new Response(JSON.stringify({records:selected}),{status:200});
  }
  throw new Error('Fetch inesperado no teste (rede não autorizada).');
};
