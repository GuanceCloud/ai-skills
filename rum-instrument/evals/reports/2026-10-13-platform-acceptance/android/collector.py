from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import gzip,zlib,json,threading,time
out=Path(__file__).parent/'evidence'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self): self.handle_request()
 def do_POST(self): self.handle_request()
 def handle_request(self):
  raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
  if self.headers.get('Transfer-Encoding','').lower()=='chunked':
   chunks=[]
   while True:
    size=int(self.rfile.readline().strip().split(b';')[0],16)
    if not size:
     self.rfile.readline();break
    chunks.append(self.rfile.read(size));self.rfile.read(2)
   raw=b''.join(chunks)
  if self.headers.get('Content-Encoding')=='deflate': raw=zlib.decompress(raw)
  if self.headers.get('Content-Encoding')=='gzip': raw=gzip.decompress(raw)
  if self.server.server_port==19529:
   entry={'path':self.path,'encoding':self.headers.get('Content-Encoding'),'body':raw.decode('utf-8',errors='replace')}
   with (out/'payloads.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
   data=b'{"content":null,"errorCode":"","message":"","success":true}'
  else:
   entry={'path':self.path,'method':self.command,'synthetic_header_seen':self.headers.get('Authorization')=='Bearer HEADER_CANARY_ANDROID_ACCEPTANCE','synthetic_body_seen':raw==b'BODY_CANARY_ANDROID_ACCEPTANCE','trace_headers':[k for k in self.headers if k.lower() in ['traceparent','tracestate','x-datadog-trace-id']]}
   with (out/'resource-requests.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
   data=b'LOCAL_RESOURCE_OK'
  self.send_response(200);self.send_header('Content-Type','application/json' if self.server.server_port==19529 else 'text/plain');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
for port in [19529,19530]:
 s=ThreadingHTTPServer(('127.0.0.1',port),Handler);threading.Thread(target=s.serve_forever,daemon=True).start()
print('Local mock receivers ready 127.0.0.1:19529 / 19530',flush=True)
while True:time.sleep(1)
