#!/usr/bin/env python3
"""
铉枢 API Rate Limiter & Proxy
Three endpoints simulating local machine's proxy architecture

敏感配置通过环境变量读取，本文件不应包含任何密钥。
"""
import os
import http.server
import json
import threading
import time
import urllib.request
import urllib.error
from collections import defaultdict

# --- Config — all keys from environment variables ---
PROXIES = {
    8083: {  # DeepSeek (for CC/试金/匠人)
        "name": "DeepSeek Gateway",
        "upstream": "https://api.deepseek.com",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
        "rpm": 30,
        "tpm": 100000,
    },
    8084: {  # MiMo 700M (for 矿工/望工/探工/铸师)
        "name": "MiMo 700M Gateway",
        "upstream": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key": os.environ.get("MIMO_API_KEY", ""),
        "rpm": 20,
        "tpm": 50000,
    },
    8085: {  # MiMo 200M (for Codex)
        "name": "MiMo 200M Gateway",
        "upstream": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key": os.environ.get("MIMO_API_KEY", ""),
        "rpm": 15,
        "tpm": 30000,
    },
}

class RateLimiter:
    def __init__(self, rpm, tpm):
        self.rpm = rpm
        self.tpm = tpm
        self.minute_requests = defaultdict(list)
        self.minute_tokens = defaultdict(int)
        self.lock = threading.Lock()
    
    def allow(self):
        now = time.time()
        minute_key = int(now // 60)
        with self.lock:
            self.minute_requests[minute_key].append(now)
            if len(self.minute_requests[minute_key]) > self.rpm:
                return False
            # Clean old keys
            old_keys = [k for k in self.minute_requests if k < minute_key - 1]
            for k in old_keys:
                del self.minute_requests[k]
                if k in self.minute_tokens:
                    del self.minute_tokens[k]
            return True

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self._proxy()
    
    def do_POST(self):
        self._proxy()
    
    def _proxy(self):
        port = self.server.server_port
        config = PROXIES.get(port)
        if not config:
            self.send_error(500, "No proxy config for this port")
            return
        
        # Health check
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "proxy": config["name"],
                "upstream": config["upstream"],
                "rpm_limit": config["rpm"],
            }).encode())
            return
        
        # Rate limit check
        if not self.server.rate_limiter.allow():
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "rate_limit", "message": "RPM exceeded"}).encode())
            return
        
        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else None
        
        # Forward request
        target_url = f"{config['upstream']}{self.path}"
        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        headers["Authorization"] = f"Bearer {config['api_key']}"
        headers["Content-Type"] = "application/json"
        
        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=headers,
                method=self.command,
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for key, val in resp.getheaders():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "proxy_error", "message": str(e)}).encode())
    
    def log_message(self, format, *args):
        port = self.server.server_port
        print(f"[{PROXIES.get(port, {}).get('name', port)}] {args[0]}")

def start_proxy(port):
    config = PROXIES[port]
    limiter = RateLimiter(config["rpm"], config["tpm"])
    server = http.server.HTTPServer(("127.0.0.1", port), ProxyHandler)
    server.rate_limiter = limiter
    print(f"  ✓ {config['name']} → {config['upstream']} (:{port}, RPM={config['rpm']})")
    server.serve_forever()

if __name__ == "__main__":
    print("铉枢 API Proxy Layer")
    print("=" * 40)
    threads = []
    for port in PROXIES:
        t = threading.Thread(target=start_proxy, args=(port,), daemon=True)
        t.start()
        threads.append(t)
    print(f"\nAll {len(threads)} proxies running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
