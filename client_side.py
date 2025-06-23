
import flet as ft
import asyncio
import websockets
import sys

class WebSocketClient:
    def __init__(self, uri, message_callback):
        self.uri = uri
        self.websocket = None
        self.message_callback = message_callback
        self.username = None  # These will be automatically set.
        self.session_token = None

    async def connect(self):
        """Connect to the WebSocket server and authenticate."""
        try:
            self.websocket = await websockets.connect(self.uri)
            print("✅ Connected to WebSocket server.")
        
            # Immediately send auth credentials in the format "username|session_token"
            auth_message = f"{self.username}|{self.session_token}"
            await self.websocket.send(auth_message)
            print("✅ Sent authentication message:", auth_message)
        
            # Now start listening for incoming messages
            asyncio.create_task(self.receive_messages())
        except Exception as e:
            print("🔴 Connection failed. Retrying...")
            await asyncio.sleep(3)
            await self.connect()

    async def send_message(self, message):
        """Send a message to the server."""
        if self.websocket:
            await self.websocket.send(message)

    async def receive_messages(self):
        """Listen for messages from the server."""
        while True:
            try:
                message = await self.websocket.recv()
                self.message_callback(message)  # Send message to UI
            except websockets.exceptions.ConnectionClosed:
                print("⚠️ Connection closed.")
                break

class ChatApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.vertical_alignment = ft.CrossAxisAlignment.CENTER,
        self.page.width = self.page.width * 0.7
        self.page.height = self.page.height * 0.7
        self.page.update()
        try:
            self.username = sys.argv[1]  # First argument: username
            self.session_token = sys.argv[2]  # Second argument: session_token
        except IndexError:
            print("🔴 Missing credentials! Redirecting to login...")
            self.page.go("/login")  # Redirect if no valid credentials
            return
        
        self.ws_client = WebSocketClient("ws://localhost:8765", self.display_message)
        self.ws_client.username = self.username
        self.ws_client.session_token = self.session_token

        self.selected_files = []
        self.message_input = ft.TextField(label="Type a message...",  multiline=True, dense=True, border_radius=10)
        self.send_button = ft.ElevatedButton("Send", on_click=self.send_message, elevation=20)
        self.multimedia_button = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE,
            tooltip="Select file",
            on_click=self.pick_files
        )
        self.chat_box = ft.Container(
            content= ft.Column(scroll=True),
            border_radius=10,
            width=self.page.width * 0.5,
            height=self.page.height * 0.5,
            bgcolor="white",
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=5, color="grey")
        )

        self.file_picker = ft.FilePicker(on_result=self.on_file_picker_result)
        self.page.overlay.append(self.file_picker)

        self.chat_ui()
        self.page.run_task(self.ws_client.connect)  # Connect to server
    
    def chat_ui(self):
        self.page.overlay.clear()

        self.chat_header = ft.Container(
            content=ft.Text("What is on your mind", weight=ft.FontWeight.W_500, italic=True, opacity=10),
            gradient=ft.LinearGradient(colors=[
                ft.Colors.WHITE, ft.Colors.BLACK], tile_mode=ft.GradientTileMode.MIRROR
            ),
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=5, color="grey"), 
            width=self.page.width * 0.5   
        )

        self.wrap_control = ft.Container(
            ft.Row(
                controls=[self.multimedia_button, self.message_input, self.send_button],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY
            ),
            width=self.page.width * 0.5,
            bgcolor="green",
            shadow=ft.BoxShadow(blur_radius=3, spread_radius=5, color="black")
        )
        self.wrap_whole_control = ft.Container(
            content=ft.Container(
                content=  ft.Column(
                    controls=[
                        self.chat_header, self.chat_box, self.wrap_control
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                ),
                width=self.page.width * 0.7,
                height=self.page.height * 0.7,
                alignment=ft.alignment.bottom_left
            ),
            alignment=ft.alignment.center,
            expand=True
        )

        self.page.overlay.append(self.wrap_whole_control)
        self.page.update()

    def pick_files(self, e):
        """Triggers the file picker for selecting multimedia files."""
        self.file_picker.pick_files(allow_multiple=True, 
           file_type=ft.FilePickerFileType.MEDIA)
    
    def on_file_picker_result(self, result: ft.FilePickerResultEvent):
        if result.files:
            # Clear previous attachments if needed (or you can append)
            self.selected_files.clear()
            attached_names = []
            for file in result.files:
                self.selected_files.append(file.path)
                attached_names.append(file.name)
            current_text = self.message_input.value or ""
            self.message_input.value = current_text + " [Attached: " + ", ".join(attached_names) + "]"
        self.page.update()

    async def send_message(self, e):
        """Send the text and all attached media in one go."""
        text_msg = self.message_input.value.strip()

        if text_msg:
            formatted_message = f"{self.username}|server|{text_msg}"  # Use your required format
            await self.ws_client.send_message(formatted_message)
            self.display_message(f"{self.username}: {text_msg}")

        for file_path in self.selected_files:
            if file_path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                prefix = "IMAGE:"
            elif file_path.lower().endswith((".mp3", ".wav", ".ogg")):
                prefix = "AUDIO:"
            elif file_path.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
                prefix = "VIDEO:"
            else:
                prefix = "FILE:"  # Fallback for other media types.
            multimedia_message = f"{prefix} {file_path}"
            await self.ws_client.send_message(multimedia_message)
            self.display_message(multimedia_message)

        self.message_input.value = ""
        self.selected_files.clear()
        self.page.update()
    
    def display_message(self, message):
        """Show received messages with correct sender attribution, formatting, and alignment."""
    
        # Check for multimedia messages first
        if message.startswith("IMAGE:"):
            image_url = message[len("IMAGE:"):].strip()
            img_control = ft.Image(src=image_url, width=300)
            self.chat_box.content.controls.append(
                ft.Row(
                    controls=[img_control],
                    alignment=ft.MainAxisAlignment.END
                )
            )
        elif message.startswith("AUDIO:"):
            audio_url = message[len("AUDIO:"):].strip()
            audio_control = ft.Audio(src=audio_url)
            self.chat_box.content.controls.append(
                ft.Row(
                    controls=[audio_control],
                    alignment=ft.MainAxisAlignment.END
                )
            )
        elif message.startswith("VIDEO:"):
            video_url = message[len("VIDEO:"):].strip()
            video_control = ft.Video(src=video_url, width=400, height=300)
            self.chat_box.content.controls.append(
                ft.Row(
                    controls=[video_control],
                    alignment=ft.MainAxisAlignment.END
                )
            )
        else:
            # Handle text messages formatted as "sender: message"
            if ":" in message:
                sender, text = message.split(":", 1)
                sender = sender.strip()  # Clean sender name
                text = text.strip()      # Clean message content

                if sender == self.username:  # Sender is the current client
                    color = "blue"
                    alignment = ft.MainAxisAlignment.END  # Right-align own messages
                else:
                    color = "green"
                    alignment = ft.MainAxisAlignment.START  # Left-align messages from others

                self.chat_box.content.controls.append(
                    ft.Row(
                        controls=[ft.Text(f"{sender}: {text}", color=color)],
                        alignment=alignment
                    )
                )
            else:
                # If the message doesn't match the expected format, display it as a server message
                self.chat_box.content.controls.append(
                    ft.Row(
                        controls=[ft.Text(f"Server: {message}", color="purple")],
                        alignment=ft.MainAxisAlignment.CENTER
                    )
                )        
        self.page.update()

if __name__ == "__main__":
    ft.app(target=ChatApp)
