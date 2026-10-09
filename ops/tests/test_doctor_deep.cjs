const assert=require('node:assert/strict');
let calls=[];
globalThis.fetch=async(url,options)=>{
  calls.push({url,body:options?.body?JSON.parse(options.body):null});
  return new Response(JSON.stringify({status:'completed',model:'gpt-6.1-sol',output:[{type:'message',content:[{type:'output_text',text:'{"findings":[]}'}]}],usage:{input_tokens:12,output_tokens:20,total_tokens:32}}));
};
require('../skill-doctor/deep-mode.cjs');
(async()=>{
  const r=await fetch('https://api.a6api.com/v1/chat/completions',{body:JSON.stringify({model:'gpt-6.1-sol',messages:[{role:'user',content:'Synthetic JSON audit'}],response_format:{type:'json_object'}})});
  assert.equal(calls[0].url,'https://api.a6api.com/v1/responses');
  assert.equal(calls[0].body.reasoning.effort,'high');assert.equal(calls[0].body.max_output_tokens,4096);
  assert.equal(calls[0].body.text.format.type,'json_object');
  assert.equal((await r.json()).choices[0].message.content,'{"findings":[]}');
  await fetch('https://api.a6api.com/v1/embeddings',{body:JSON.stringify({model:'text-embedding-3-small',input:'synthetic'})});
  assert.equal(calls[1].url,'https://api.a6api.com/v1/embeddings');
  console.log('Manual Deep Scan Responses adapter: high reasoning, bounded output, JSON and embedding passthrough passed.');
})().catch(e=>{console.error(e);process.exit(1)});
