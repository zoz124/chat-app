import socket
import threading
import os

# =========================
# Configuration
# =========================
HOST = '0.0.0.0'
PORT = int(os.environ.get("PORT", 50001))

# =========================
# Protocol
# =========================
DELIMITER = b'<|END_OF_MSG|>'
ESCAPE = b'\\'

clients = []


def broadcast(data, sender_conn):
    """Send message to all clients except sender"""

    disconnected_clients = []

    for client in clients:
        if client != sender_conn:
            try:
                client.sendall(data)

            except:
                disconnected_clients.append(client)

    # Remove disconnected clients
    for dc in disconnected_clients:
        if dc in clients:
            clients.remove(dc)


def handle_client(conn, addr):

    print(f"[+] New connection: {addr}")

    clients.append(conn)

    buffer = b""

    try:

        while True:

            chunk = conn.recv(4096)

            if not chunk:
                break

            buffer += chunk

            while True:

                found_idx = -1
                search_start = 0

                while True:

                    idx = buffer.find(DELIMITER, search_start)

                    if idx == -1:
                        break

                    # Check escaped delimiter
                    if idx > 0 and buffer[idx - 1:idx] == ESCAPE:

                        count = 0
                        i = idx - 1

                        while i >= 0 and buffer[i:i + 1] == ESCAPE:
                            count += 1
                            i -= 1

                        # odd number => escaped
                        if count % 2 == 1:
                            search_start = idx + len(DELIMITER)
                            continue

                    found_idx = idx
                    break

                if found_idx == -1:
                    break

                full_message = buffer[:found_idx + len(DELIMITER)]

                buffer = buffer[found_idx + len(DELIMITER):]

                broadcast(full_message, conn)

    except Exception as e:

        print(f"[!] Error handling {addr}: {e}")

    finally:

        print(f"[-] Connection closed: {addr}")

        if conn in clients:
            clients.remove(conn)

        conn.close()


def start_server():

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:

        server_socket.bind((HOST, PORT))

        server_socket.listen(10)

        print(f"[*] Server listening on {HOST}:{PORT}")

        while True:

            conn, addr = server_socket.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            )

            thread.start()

    except Exception as e:

        print(f"[!] Server error: {e}")

    finally:

        server_socket.close()


if __name__ == "__main__":
    start_server()