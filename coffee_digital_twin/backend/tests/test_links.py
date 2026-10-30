from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from contextlib import contextmanager
from tools.check_links import check


def test_delivery_links_head_only_and_formal_path_isolated(tmp_path):
    methods = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_HEAD(self):
            methods.append(('HEAD', self.path))
            self.send_response(302 if self.path == '/redirect' else 200)
            if self.path == '/redirect': self.send_header('Location', '/ok')
            self.end_headers()
        def do_GET(self):
            methods.append(('GET', self.path)); self.send_response(500); self.end_headers()
    server = HTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    try:
        (tmp_path/'coffee_digital_twin').mkdir()
        (tmp_path/'coffee_digital_twin/file.txt').write_text('test')
        doc = tmp_path/'delivery.md'
        base = f'http://127.0.0.1:{server.server_port}'
        doc.write_text('`coffee_digital_twin/file.txt`\n[online]('+base+'/redirect)\n'+
                       '`实验资料/06_正式测试资料/never-read`\n`coffee_digital_twin/missing`\n'+
                       '[bad](http://user:secret@127.0.0.1:1/no)', encoding='utf-8')
        rows = check(doc, tmp_path)
        assert sum(r['status'] == 'PASS' for r in rows) == 2
        assert sum(r['status'] == 'FAIL' for r in rows) == 3
        assert methods == [('HEAD', '/redirect'), ('HEAD', '/ok')]
        assert 'secret' not in str(rows)
        assert not (tmp_path/'实验资料').exists()
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=3)
