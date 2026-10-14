"""Loopback-only DataKit-shaped capture endpoint for future real simulator runs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json,time
OUT=Path(__file__).parent/'logs'/'receiver-events.jsonl'
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"ok":true}')
 def do_POST(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  with OUT.open('a') as f:f.write(json.dumps({'time':time.time(),'path':self.path,'body':body.decode('utf-8',errors='replace')})+'\n')
  self.send_response(200);self.end_headers();self.wfile.write(b'{}')
 def log_message(self,*args):pass
if __name__=='__main__':
 print('Loopback simulator receiver listening on 127.0.0.1:19529',flush=True)
 ThreadingHTTPServer(('127.0.0.1',19529),Handler).serve_forever()
