import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from multiprocessing import Process
import websockets
from datetime import datetime
import json
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)

class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/":
            self.send_html_file("index.html")
        elif parsed_url.path == "/message.html":
            self.send_html_file("message.html")
        elif parsed_url.path.startswith("/static/"):
            self.send_static_file(parsed_url.path[1:])
        else:
            self.send_html_file("error.html", 404)

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        parsed_data = parse_qs(post_data.decode("utf-8"))
        username = parsed_data.get("username", [""])[0]
        message = parsed_data.get("message", [""])[0]

        message_data = json.dumps({"username": username, "message": message})

        # Send message to WebSocket server without running a new event loop
        try:
            asyncio.get_event_loop().run_in_executor(None, self.send_to_websocket, message_data)
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Message sent!")
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Failed to send message")

    def send_to_websocket(self, message_data):
        # Synchronous wrapper for WebSocket send
        async def send_message():
            uri = "ws://localhost:6000"
            async with websockets.connect(uri) as websocket:
                await websocket.send(message_data)
        asyncio.run(send_message())

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())

    def send_static_file(self, filename, status=200):
        try:
            with open(filename, "rb") as file:
                self.send_response(status)
                if filename.endswith(".css"):
                    self.send_header("Content-type", "text/css")
                elif filename.endswith(".png"):
                    self.send_header("Content-type", "image/png")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_html_file("error.html", 404)

class WebSocketServer:
    def __init__(self):
        self.client = AsyncIOMotorClient("mongodb://mongodb:27017/")
        self.db = self.client["messaging"]
        self.collection = self.db["users_messages"]

    async def ws_handler(self, websocket):
        try:
            async for message in websocket:
                data = json.loads(message)
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                message_data = {
                    "date": date,
                    "username": data["username"],
                    "message": data["message"],
                }
                await self.collection.insert_one(message_data)  # Single async insert
                logging.info(f"Saved message: {message_data}")
        except websockets.ConnectionClosed:
            logging.info("WebSocket connection closed")
        except Exception as e:
            logging.error(f"WebSocket handler error: {e}")

    def close(self):
        self.client.close()

async def run_websocket_server():
    server = WebSocketServer()
    async with websockets.serve(server.ws_handler, "0.0.0.0", 6000):
        logging.info("WebSocket server started on port 6000")
        await asyncio.Future()

def start_websocket_server():
    asyncio.run(run_websocket_server())

def run_http_server():
    server_address = ("", 3000)
    httpd = HTTPServer(server_address, HttpHandler)
    logging.info("HTTP server started on port 3000")
    httpd.serve_forever()

if __name__ == "__main__":
    http_process = Process(target=run_http_server)
    ws_process = Process(target=start_websocket_server)

    http_process.start()
    ws_process.start()

    http_process.join()
    ws_process.join()