#!/usr/bin/env python3
"""
Launcher for MKCL Course Showcase & Presentation Application
Opens the interactive presentation in your default browser.
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        # Keep console clean
        pass

def main():
    os.chdir(DIRECTORY)
    for p in range(PORT, PORT + 20):
        try:
            with socketserver.TCPServer(("", p), Handler) as httpd:
                url = f"http://localhost:{p}/index.html"
                print("=" * 65)
                print("🎓 MKCL Course Showcase & Parent-Student Presentation Application")
                print("=" * 65)
                print(f"Server running at: {url}")
                print("Opening your default browser...")
                print("Press Ctrl+C to stop the presentation server.")
                print("=" * 65)
                
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                
                httpd.serve_forever()
                break
        except OSError:
            continue

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nPresentation server stopped.")
        sys.exit(0)
