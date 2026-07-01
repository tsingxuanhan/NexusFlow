# -*- coding: utf-8 -*-
"""
铉枢·炉守 Hub本地服务器
用法: python serve-hub.py
访问: http://127.0.0.1:3000
"""

import http.server
import socketserver
import os
import sys

PORT = 3000
DEMO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'demo')

os.chdir(DEMO_DIR)

class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # 允许Hub页面请求本地API
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        # 简化日志
        pass

try:
    with socketserver.TCPServer(("", PORT), CORSHandler) as httpd:
        print(f"\n  🔮 铉枢·炉守 Hub")
        print(f"  http://127.0.0.1:{PORT}/hub.html")
        print(f"\n  Ctrl+C 停止服务\n")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n  服务已停止")
except OSError as e:
    if "Address already in use" in str(e):
        print(f"\n  ⚠ 端口 {PORT} 已被占用，请检查或更换端口")
    else:
        raise
