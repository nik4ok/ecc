import json
import os
import queue
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = 8085
DIRECTORY = "/Users/nikita.symnitelny/ecc"
CLIENT_QUEUES = []
QUEUES_LOCK = threading.Lock()

class SolarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = queue.Queue()
            with QUEUES_LOCK:
                CLIENT_QUEUES.append(q)

            try:
                # Send welcome event
                self.wfile.write(b"data: {\"from\": \"core\", \"to\": \"planner\", \"action\": \"SSE Live Stream Connected\"}\n\n")
                self.wfile.flush()

                while True:
                    try:
                        msg = q.get(timeout=15)
                        self.wfile.write(f"data: {json.dumps(msg)}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive heartbeat
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with QUEUES_LOCK:
                    if q in CLIENT_QUEUES:
                        CLIENT_QUEUES.remove(q)
            return

        if self.path == "/" or self.path == "/solar":
            self.path = "/agent-solar-system.html"

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/trigger":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                with QUEUES_LOCK:
                    for q in CLIENT_QUEUES:
                        q.put(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "delivered_to": len(CLIENT_QUEUES)}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SolarHandler)
    print(f"Solar Server (Multi-threaded SSE) running at http://localhost:{PORT}")
    server.serve_forever()
