import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar
import os
from PIL import Image, ImageTk
import io
import datetime

# =========================
# Protocol Constants
# =========================
DELIMITER = b'<|END_OF_MSG|>'
ESCAPE = b'\\'

# =========================
# Message Types
# =========================
TYPE_TEXT = b'\x01'
TYPE_IMG  = b'\x02'
TYPE_FILE = b'\x03'


class ChatClient:

    def __init__(self, root, host='127.0.0.1', port=50001):

        self.root = root
        self.root.title("Multimedia Chat")
        self.root.geometry("650x800")
        self.root.configure(bg="#1e1e2e")

        self.host = host
        self.port = port
        self.client_socket = None
        self.hd_mode = tk.BooleanVar(value=False)
        self.image_refs = []

        self.setup_ui()
        self.connect_to_server()

    # =========================
    # UI
    # =========================
    def setup_ui(self):

        # --- Top Bar ---
        top_frame = tk.Frame(self.root, bg="#2a2a3d", height=50)
        top_frame.pack(fill=tk.X)

        tk.Label(
            top_frame,
            text="Network Chat",
            fg="white",
            bg="#2a2a3d",
            font=("Segoe UI", 13, "bold")
        ).pack(side=tk.LEFT, padx=15)

        tk.Checkbutton(
            top_frame,
            text="HD Mode",
            variable=self.hd_mode,
            bg="#2a2a3d",
            fg="#5865f2",
            selectcolor="#1e1e2e",
            activebackground="#2a2a3d",
            font=("Segoe UI", 10)
        ).pack(side=tk.RIGHT, padx=15)

        # --- Chat Display ---
        self.chat_display = tk.Text(
            self.root,
            state=tk.DISABLED,
            bg="#1e1e2e",
            fg="#e0e0e0",
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
            bd=0,
            wrap=tk.WORD
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        self.chat_display.tag_configure("right",  justify='right',  foreground="#a6e3a1")
        self.chat_display.tag_configure("left",   justify='left',   foreground="#ffffff")
        self.chat_display.tag_configure("system", justify='center', foreground="#888888")

        # --- Progress Bar Area (ثابتة دايماً) ---
        progress_area = tk.Frame(self.root, bg="#1e1e2e")
        progress_area.pack(fill=tk.X, padx=20, pady=(4, 0))

        self.progress = Progressbar(
            progress_area,
            orient=tk.HORIZONTAL,
            mode='determinate',
            maximum=100
        )
        self.progress.pack(fill=tk.X)

        self.progress_label = tk.Label(
            progress_area,
            text="",
            bg="#1e1e2e",
            fg="#888888",
            font=("Segoe UI", 9)
        )
        self.progress_label.pack()

        # نخفيهم في الأول
        progress_area.pack_forget()
        self.progress_area = progress_area

        # --- Input Area ---
        input_frame = tk.Frame(self.root, bg="#2a2a3d", pady=10)
        input_frame.pack(fill=tk.X)

        tk.Button(
            input_frame,
            text="📎",
            command=self.send_media,
            bg="#3b3b4f",
            fg="white",
            bd=0,
            width=4,
            font=("Segoe UI", 14)
        ).pack(side=tk.LEFT, padx=(10, 5))

        self.entry = tk.Entry(
            input_frame,
            bg="#3b3b4f",
            fg="white",
            bd=0,
            insertbackground="white",
            font=("Segoe UI", 11)
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        self.entry.bind("<Return>", lambda e: self.send_text())

        tk.Button(
            input_frame,
            text="Send",
            command=self.send_text,
            bg="#5865f2",
            fg="white",
            bd=0,
            width=8,
            font=("Segoe UI", 11, "bold")
        ).pack(side=tk.RIGHT, padx=10)

    # =========================
    # Progress Bar Helpers
    # =========================
    def _start_progress(self):
        self.progress['value'] = 0
        self.progress_label.config(text="0%")
        self.progress_area.pack(fill=tk.X, padx=20, pady=(4, 0))

    def _update_progress(self, percent):
        self.progress['value'] = percent
        self.progress_label.config(text=f"{percent}%")

    def _stop_progress(self):
        self.progress['value'] = 0
        self.progress_label.config(text="")
        self.progress_area.pack_forget()

    # =========================
    # Send With Progress
    # بنبعت على chunks ونحسب النسبة بنفسنا
    # بدون ما نبعت الحجم مسبقاً (ريكوايرمنت المشروع)
    # =========================
    def _send_with_progress(self, packet):
        total = len(packet)
        sent  = 0
        chunk_size = 4096

        while sent < total:
            end   = min(sent + chunk_size, total)
            chunk = packet[sent:end]
            self.client_socket.sendall(chunk)
            sent += len(chunk)
            percent = int((sent / total) * 100)
            self.root.after(0, lambda p=percent: self._update_progress(p))

    # =========================
    # Logging
    # =========================
    def log(self, msg, tag="system"):
        self.chat_display.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        self.chat_display.insert(tk.END, f"[{timestamp}] {msg}\n", tag)
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    # =========================
    # Connection
    # =========================
    def connect_to_server(self):

        def run():
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.host, self.port))
                self.log(f"Connected to {self.host}")
                threading.Thread(target=self.receive_loop, daemon=True).start()
            except Exception as e:
                self.log(f"Connection failed: {e}")

        threading.Thread(target=run, daemon=True).start()

    # =========================
    # Protocol
    # =========================
    def encode_data(self, data_type, payload):
        stuffed = payload.replace(b'\\', b'\\\\').replace(DELIMITER, b'\\DELIM')
        return data_type + stuffed + DELIMITER

    def decode_data(self, raw_payload):
        return raw_payload.replace(b'\\DELIM', DELIMITER).replace(b'\\\\', b'\\')

    # =========================
    # Receive Loop
    # =========================
    def receive_loop(self):

        buffer = b""

        while True:
            try:
                chunk = self.client_socket.recv(4096)
                if not chunk:
                    break

                buffer += chunk

                while True:
                    found_idx    = -1
                    search_start = 0

                    while True:
                        idx = buffer.find(DELIMITER, search_start)
                        if idx == -1:
                            break

                        # كشف الـ escaped delimiter
                        if idx > 0 and buffer[idx - 1:idx] == ESCAPE:
                            count = 0
                            i = idx - 1
                            while i >= 0 and buffer[i:i + 1] == ESCAPE:
                                count += 1
                                i -= 1
                            if count % 2 == 1:
                                search_start = idx + len(DELIMITER)
                                continue

                        found_idx = idx
                        break

                    if found_idx == -1:
                        break

                    full_packet = buffer[:found_idx]
                    buffer      = buffer[found_idx + len(DELIMITER):]

                    if not full_packet:
                        continue

                    msg_type = full_packet[0:1]
                    payload  = self.decode_data(full_packet[1:])
                    self.handle_incoming(msg_type, payload)

            except:
                self.log("Disconnected from server.")
                break

    # =========================
    # Incoming Messages
    # =========================
    def handle_incoming(self, msg_type, payload):

        if msg_type == TYPE_TEXT:
            text = payload.decode('utf-8', errors='ignore')
            self.root.after(0, lambda: self.log(f"Other: {text}", "left"))

        elif msg_type == TYPE_IMG:
            # عرض الصورة + حفظها في Downloads
            self.root.after(0, lambda: self.receive_image(payload))

        elif msg_type == TYPE_FILE:
            try:
                filename, filedata = payload.split(b'||FILENAME||', 1)
                filename  = filename.decode()
                downloads = os.path.join(os.path.expanduser("~"), "Downloads")
                save_path = os.path.join(downloads, filename)
                with open(save_path, "wb") as f:
                    f.write(filedata)
                self.root.after(0, lambda: self.log(f"Received file: {filename} → saved to Downloads", "left"))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"File receive error: {e}", "left"))

    # =========================
    # Receive Image (عرض + حفظ)
    # =========================
    def receive_image(self, data):
        # 1. عرض الصورة في الشات
        self.display_image(data, "left")

        # 2. حفظ الصورة في Downloads
        try:
            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(downloads, f"received_image_{timestamp}.jpg")
            with open(save_path, "wb") as f:
                f.write(data)
            self.log(f"Image saved → {save_path}", "system")
        except Exception as e:
            self.log(f"Could not save image: {e}", "system")

    # =========================
    # Send Text
    # =========================
    def send_text(self):
        msg = self.entry.get().strip()
        if msg and self.client_socket:
            packet = self.encode_data(TYPE_TEXT, msg.encode('utf-8'))
            try:
                self.client_socket.sendall(packet)
                self.log(f"You: {msg}", "right")
                self.entry.delete(0, tk.END)
            except:
                self.log("Failed to send.")

    # =========================
    # Media (اختيار نوع الملف)
    # =========================
    def send_media(self):
        file_path = filedialog.askopenfilename()
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.gif']:
            self.send_image(file_path)
        else:
            self.send_file(file_path)

    # =========================
    # Send Image
    # HD = بدون compression (raw)
    # Normal = thumbnail + JPEG quality 40
    # =========================
    def send_image(self, path):

        def run():
            try:
                if not self.client_socket:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Not connected to server!"))
                    return

                if self.hd_mode.get():
                    # HD: بعت الملف كما هو بدون أي تعديل
                    with open(path, "rb") as f:
                        data = f.read()
                else:
                    # Normal: compress
                    img = Image.open(path)
                    img = img.convert("RGB")
                    img.thumbnail((800, 800))
                    output = io.BytesIO()
                    img.save(output, format='JPEG', quality=40)
                    data = output.getvalue()

                packet = self.encode_data(TYPE_IMG, data)
                self._send_with_progress(packet)

                # عرض الصورة على جهة اليمين (اللي بعتها أنا)
                self.root.after(0, lambda: self.display_image(data, "right"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not send image: {e}"))
            finally:
                self.root.after(0, self._stop_progress)

        self._start_progress()
        threading.Thread(target=run, daemon=True).start()

    # =========================
    # Send File / Video
    # =========================
    def send_file(self, path):

        def run():
            try:
                if not self.client_socket:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Not connected to server!"))
                    return

                filename = os.path.basename(path).encode()
                with open(path, "rb") as f:
                    data = f.read()

                payload = filename + b'||FILENAME||' + data
                packet  = self.encode_data(TYPE_FILE, payload)
                self._send_with_progress(packet)

                self.root.after(0, lambda: self.log(f"Sent file: {os.path.basename(path)}", "right"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not send file: {e}"))
            finally:
                self.root.after(0, self._stop_progress)

        self._start_progress()
        threading.Thread(target=run, daemon=True).start()

    # =========================
    # Display Image في الشات
    # =========================
    def display_image(self, data, alignment):
        try:
            img = Image.open(io.BytesIO(data))
            img.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(img)
            self.image_refs.append(photo)

            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, "\n", alignment)
            self.chat_display.image_create(tk.END, image=photo)
            self.chat_display.insert(tk.END, "\n", alignment)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)
        except:
            self.log("[Image Error]", alignment)


if __name__ == "__main__":

    root = tk.Tk()

    # =========================
    # For ngrok:
    # host='0.tcp.ngrok.io'
    # port=xxxxx
    # =========================

    client = ChatClient(root, host='127.0.0.1', port=50001)

    root.mainloop()