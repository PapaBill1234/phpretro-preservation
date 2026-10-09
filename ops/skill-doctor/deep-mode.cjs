// Manual upstream AI scans use the admitted A6API Responses transport for Sol.
const original=globalThis.fetch;
globalThis.fetch=async function(input,options={}) {
  if(String(input)!=='https://api.a6api.com/v1/chat/completions')return original(input,options);
  let body;try{body=JSON.parse(options.body);}catch{return original(input,options);}
  if(body.model!=='gpt-6.1-sol')return original(input,options);
  const request={model:body.model,input:body.messages,reasoning:{effort:'high'},
    max_output_tokens:Math.max(16,Math.min(4096,body.max_tokens||4096))};
  if(body.response_format?.type==='json_object')request.text={format:{type:'json_object'}};
  const result=await original('https://api.a6api.com/v1/responses',{...options,body:JSON.stringify(request)});
  if(!result.ok)return result;
  const data=await result.json();
  const content=(data.output||[]).filter(x=>x.type==='message').flatMap(x=>x.content||[])
    .filter(x=>x.type==='output_text').map(x=>x.text).join('');
  if(!content||data.status==='incomplete')return new Response(JSON.stringify({error:'Analysis response incomplete'}),{status:502});
  return new Response(JSON.stringify({model:data.model,choices:[{message:{role:'assistant',content},finish_reason:'stop'}],
    usage:{prompt_tokens:data.usage?.input_tokens,completion_tokens:data.usage?.output_tokens,total_tokens:data.usage?.total_tokens}}),
    {status:200,headers:{'Content-Type':'application/json'}});
};
