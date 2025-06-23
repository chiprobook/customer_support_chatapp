Customer Support ChatApp
A real-time, multi-client chat application built in Python that authenticates users via session_token, redirects unauthenticated clients to login, and emits server-side notifications on new messages.

Features
🔒 Token-based Authentication Clients must send a valid session_token on connect; otherwise server emits a redirect_to_login event.

💬 One-to-One & Group Chat Each client has an isolated channel; support for private or support-agent group rooms.

🚨 Server Notifications Emits server-side logs and WebSocket events whenever a user sends a message.

⚡ Asyncio + WebSockets High-performance, non-blocking I/O for hundreds of concurrent clients.

Tech Stack
Python 3.9+

asyncio

websockets

PyJWT (for token validation)

uvicorn (optional, for HTTP fallback)

Getting Started
Prerequisites
Python 3.9 or higher

pip package manager
