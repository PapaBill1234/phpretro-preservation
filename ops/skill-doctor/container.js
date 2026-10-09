// Upstream deliberately listens on loopback. Forward the published container
// port to that loopback listener; authentication remains upstream and gateway-owned.
const http=require('node:http'),{spawn}=require('node:child_process');
const root='/home/ubuntu/phpretro-skill-doctor';
const child=spawn(process.execPath,[root+'/runtime/node_modules/.bin/skill-doctor','ui',process.argv[2],'--port','38123','--no-open'],{stdio:'inherit'});
const server=http.createServer((request,response)=>{
  const upstream=http.request({hostname:'127.0.0.1',port:38123,path:request.url,method:request.method,
    headers:{...request.headers,host:'127.0.0.1:38123'}},result=>{
      response.writeHead(result.statusCode,result.headers);result.pipe(response);
  });
  upstream.on('error',()=>{if(!response.headersSent)response.writeHead(502);response.end();});
  request.pipe(upstream);
});
server.listen(38124,'0.0.0.0');
child.on('exit',code=>server.close(()=>process.exit(code||0)));
for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>child.kill(signal));
