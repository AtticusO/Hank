import http.server
import socketserver


songs = [["Plush", "Man in the Box", "Evenflow"]]
PORT = 8000
# "" binds to all available network interfaces on the LAN
Handler = http.server.SimpleHTTPRequestHandler


with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving LAN HTTP server on port {PORT}")
    httpd.serve_forever()
