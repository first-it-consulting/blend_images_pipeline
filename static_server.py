#!/usr/bin/env python3
"""
Simple static file server for morphed images
Run this alongside the pipelines server to serve static files
"""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

if __name__ == '__main__':
    # Change to static directory
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    os.chdir(static_dir)
    
    port = 9098
    print(f"Starting static file server on port {port}")
    print(f"Serving files from: {static_dir}")
    print(f"Files will be accessible at: http://localhost:{port}/morphs/")
    
    httpd = HTTPServer(('0.0.0.0', port), CORSRequestHandler)
    httpd.serve_forever()
