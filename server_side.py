import flet as ft
import asyncio
import websockets
import sqlite3

class chatDatabase:
    def __init__(self):

        conn = sqlite3.connect('chat_messages.db')
        cursor = conn.cursor()

        # 🔹 Create table to store chat messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS Messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print("✅ Chat database initialized successfully!")
chatDatabase()

class ServerApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Customer Support Server"
        self.active_clients = {}
        self.message_queues = {}  # ✅ NEW: Store messages for each client
        self.client_notifications = {}  # ✅ NEW: Track clients with pending messages
        self.active_session = None

        # UI Components
        self.server_status = ft.Text("🔴 Server Offline", color="red")
        self.chat_box = ft.Container(
            content= ft.Column(scroll=True),
            border_radius=10,
            width=self.page.width * 0.6,
            height=self.page.height * 0.6,
            bgcolor="white",
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=5, color="grey")
        )
        self.message_input = ft.TextField(label="Type a reply...", multiline=True, border_radius=10, bgcolor="grey", dense=True)
        self.send_button = ft.ElevatedButton("Send", on_click=self.send_message, elevation=10,)

        self.history_button = ft.IconButton(
            icon=ft.Icons.HISTORY, 
            tooltip="Load Chat History", 
            on_click=self.load_chat_history
        )
        self.client_selection_dropdown = ft.Dropdown(
            label="Select Client to Respond",
            options=[],
            bgcolor="grey",
            width=500,
            dense=True,
            border_radius=10,
            on_change=self.activate_chat_session
        )
        self.chat_ui()
        # Start WebSocket Server
        self.page.run_task(self.start_server)

    def chat_ui(self):
        self.page.overlay.clear()

        self.wrap_bottom_control = ft.Container(
            ft.Row(
                controls=[self.message_input, self.send_button],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor=ft.Colors.GREEN_ACCENT,
            border=ft.Border.bottom,
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=7, color="brown"),
            alignment=ft.alignment.center
        )
    
        self.wrap_top_control = ft.Container(
            content=ft.Row(
                controls=[
                    self.client_selection_dropdown, self.history_button
                ],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor="white",
            border=ft.Border.bottom,
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=5, color="grey"),
        )
        self.wrap_whole_controls = ft.Container(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        self.server_status,
                        self.wrap_top_control,
                        self.chat_box,
                        self.wrap_bottom_control
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                width=self.page.width * 0.8,
                height=self.page.height,
                alignment=ft.alignment.center
            ),
            alignment=ft.alignment.center,
            expand=True
        )
        self.page.overlay.append(self.wrap_whole_controls)
        self.page.update()

    async def start_server(self):
        """Start the WebSocket server using the class-level handle_connection method."""
        self.server_status.value = "🟢 Server Online"
        self.server_status.color = "green"
        self.page.update()

        # Now using self.handle_connection for all connections
        server = await websockets.serve(self.handle_connection, "localhost", 8765)
        await server.wait_closed()

    async def handle_connection(self, websocket):
        """Handles incoming WebSocket connections and authenticates clients before allowing access."""
        try:
            # 🔍 Debugging: Show received authentication details BEFORE processing
            auth_data = await websocket.recv()

            # ✅ Extract username and session token
            username, session_token = auth_data.split("|", 1)

            # 🔹 Validate session token
            conn = sqlite3.connect('session_tokens.db')
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM Sessions WHERE username = ? AND session_token = ?', (username, session_token))
            result = cursor.fetchone()
            conn.close()

            if not result:
                await websocket.send("AUTH_FAILED")
                await websocket.close()
                return  # Stop processing

            # ✅ Authentication successful: Store active connection
            self.active_clients[username] = websocket
            print(f"🟢 Authenticated and connected: {username}")
           
           # In case not previously initialized, set up defaults
            if username not in self.message_queues:
                self.message_queues[username] = []
            if username not in self.client_notifications:
                self.client_notifications[username] = False

            # 🔹 Notify client that authentication succeeded
            await websocket.send("AUTH_SUCCESS")
            self.update_client_list()

            # 📡 Handle incoming messages
            async for message in websocket:
                try:
                    sender, receiver, message_text = message.split("|", 2)
                except ValueError:
                    print("❌ Malformed message received, ignoring...")
                    continue
                    
                # Store the message in the database (keeping your persistence intact)
                try:
                    conn = sqlite3.connect('chat_messages.db')
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO Messages (sender, receiver, message) VALUES (?, ?, ?)',
                       (sender, receiver, message_text))
                    conn.commit()
                    conn.close()
                except Exception as db_error:
                    print("🔥 Database error:", db_error)

                # --- Safe dictionary initialization begin ---
                if sender not in self.message_queues:
                    self.message_queues[sender] = []
                if sender not in self.client_notifications:
                    self.client_notifications[sender] = False
                # --- Safe dictionary initialization end ---

                if self.active_session == sender:
                    self.chat_box.content.controls.append(
                        ft.Row(controls=[ft.Text(f"{sender}: {message_text}", color="blue")],
                               alignment=ft.MainAxisAlignment.START)
                    )
                    self.page.update()
                else:
                    # Not the active session: queue the message and set a notification flag.
                    self.message_queues[sender].append(f"{sender}: {message_text}")
                    self.client_notifications[sender] = True
                    self.update_client_list()              
                            
        except websockets.exceptions.ConnectionClosed:
            print("⚠️ Connection closed for", username)
            if username in self.active_clients:  # username from authentication scope
                self.active_clients.pop(username, None)
            self.update_client_list()

        except Exception as e:
            print(f"🔥 Unexpected server error: {e}")

    def load_chat_history(self, e):
        """Fetches and displays previous chat messages."""
        username = "server"  # Change this dynamically based on the logged-in user

        conn = sqlite3.connect('chat_messages.db')
        cursor = conn.cursor()

        cursor.execute('SELECT sender, receiver, message, timestamp FROM Messages WHERE sender = ? OR receiver = ? ORDER BY timestamp ASC', 
           (username, username))
    
        chat_history = cursor.fetchall()
        conn.close()

        # 🔹 Display messages in the UI
        for msg in chat_history:
            self.chat_box.content.controls.append(ft.Row(
                controls=[ft.Text(f"{msg[3]} | {msg[0]} → {msg[1]}: {msg[2]}", color="gray")],
                alignment=ft.MainAxisAlignment.START
            ))
    
        self.page.update()
        print(f"✅ Chat history loaded for {username}")

    def update_client_list(self):
        # Build a mapping from the display text (option.text) to the clean username.
        self.option_map = {}
        new_options = []
        for username in self.active_clients.keys():
            display_text = f"{username}{' 🔔' if self.client_notifications.get(username, False) else ''}"
            new_options.append(ft.dropdown.Option(text=display_text))
            self.option_map[display_text] = username  # store the mapping
        self.client_selection_dropdown.options = new_options
        self.page.update()

    def activate_chat_session(self, e):
        """When a client is selected in the dropdown, load that client's queued messages."""
        if not self.client_selection_dropdown.value:
            return

        # Remove any trailing notification icon from the selected value.
        selected_display = self.client_selection_dropdown.value
        selected_client = selected_display.replace(" 🔔", "")
        self.active_session = selected_client
        
        # Clear previous chat window.
        self.chat_box.content.controls.clear()

        # Load queued messages (if any)
        queued = self.message_queues.get(selected_client, [])
        for msg in queued:
            self.chat_box.content.controls.append(
                ft.Row(
                    controls=[ft.Text(msg, color="blue")],
                    alignment=ft.MainAxisAlignment.START
                )
            )
        # After loading, clear the queue and remove notification.
        self.message_queues[selected_client] = []
        self.client_notifications[selected_client] = False

        self.update_client_list()
    
        # Additionally, force the selected dropdown value to update without icon.
        self.client_selection_dropdown.value = selected_client
        self.page.update()

    async def send_message(self, e):
        """When the server clicks Send, dispatch a reply to the active session."""
        message = self.message_input.value.strip()
        if not message:
            return

        # Ensure that a client is selected.
        if not self.client_selection_dropdown.value:
            print("No client selected!")
            return

        selected_client = self.client_selection_dropdown.value.replace(" 🔔", "")
        if selected_client in self.active_clients:
            try:
                # Send message to client
                await self.active_clients[selected_client].send(f"Server: {message}")
            except Exception as e:
                print("Error sending to client:", e)
                return

            # Display the message on the server's UI.
            self.chat_box.content.controls.append(
                ft.Row(
                    controls=[ft.Text(f"Server: {message}", color="green")],
                    alignment=ft.MainAxisAlignment.END
                )
            )
            self.message_input.value = ""
            self.page.update()
        else:
            print("Selected client not found in active clients.")

if __name__ == "__main__":
    ft.app(target=ServerApp)
