import socket
import urllib.parse

# Define server address and port
HOST = '127.0.0.1'
PORT = 8080

# Create and configure the TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(1)

print(f"Server running at http://{HOST}:{PORT}")

# Load the HTML interface file
with open("index.html", "r") as file:
    html_content = file.read()

while True:
    # Accept incoming browser connections
    client_connection, client_address = server_socket.accept()
    
    # Receive the raw HTTP request data from the browser
    request_data = client_connection.recv(1024).decode('utf-8')
    
    if not request_data:
        client_connection.close()
        continue

    # Isolate the first line of the HTTP header (e.g., "GET /?song=John HTTP/1.1")
    top_line = request_data.split('\n')[0]
    print(f"Received Request: {top_line}")

    # Check if a form submission exists in the URL path
    if "?song=" in top_line:
        # Extract the segment after '?song=' up to the next space character
        query_string = top_line.split('?')[1].split(' ')[0]
        parsed_params = urllib.parse.parse_qs(query_string)
        
        # Extract and sanitize the final input string
        user_input = parsed_params.get('song', [''])[0]
        print(f"\n[SUCCESS] Extracted HTML field value: {user_input}\n")

    # Send a standard HTTP 200 OK header and render the HTML page
    response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html_content
    client_connection.sendall(response.encode('utf-8'))
    
    # Safely close the client connection
    client_connection.close()
