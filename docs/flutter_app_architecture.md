# Executive Assistant - Flutter App Architecture

> **Version:** 1.0  
> **Last Updated:** 2026-03-11  
> **Status:** Planning

---

## 1. Overview

### Purpose
Cross-platform Flutter application (Desktop + Mobile + Web) for interacting with the Executive Assistant agent.

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUTTER APP (All Platforms)                        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                              UI Layer                                   │ │
│  │   ├── Chat Screen (messages, input, streaming)                        │ │
│  │   ├── Settings Screen (LLM, storage, connection)                      │ │
│  │   ├── History Screen (conversation history)                          │ │
│  │   └── Onboarding (first-time setup)                                   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         State Management                                │ │
│  │   └── Riverpod (providers for: connection, messages, settings)        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Data Layer                                      │ │
│  │   ├── API Client (HTTP + SSE)                                         │ │
│  │   ├── Local Storage (SQLite via drift)                                │ │
│  │   └── Secure Storage (API keys)                                       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Local Docker   │      │   Cloud API     │      │  Mobile Only   │
│  (Desktop)      │      │   (Default)     │      │  (Cloud only)  │
│                 │      │                 │      │                 │
│ http://localhost│      │ https://api...  │      │ Cloud API      │
│     :8000       │      │                 │      │ only           │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## 2. Project Structure

```
executive-assistant-flutter/
├── lib/
│   ├── main.dart                    # App entry point
│   ├── app.dart                     # MaterialApp configuration
│   │
│   ├── core/
│   │   ├── constants/
│   │   │   ├── api_constants.dart   # API URLs, timeouts
│   │   │   └── storage_keys.dart    # SharedPreferences keys
│   │   ├── theme/
│   │   │   ├── app_theme.dart       # Light/dark themes
│   │   │   ├── colors.dart          # Brand colors
│   │   │   └── typography.dart     # Text styles
│   │   ├── router/
│   │   │   └── app_router.dart      # GoRouter configuration
│   │   └── utils/
│   │       ├── extensions.dart      # String, date extensions
│   │       └── validators.dart      # Input validation
│   │
│   ├── features/
│   │   ├── chat/
│   │   │   ├── data/
│   │   │   │   ├── models/
│   │   │   │   │   ├── message_model.dart
│   │   │   │   │   └── chat_state.dart
│   │   │   │   └── repositories/
│   │   │   │       └── chat_repository.dart
│   │   │   ├── presentation/
│   │   │   │   ├── screens/
│   │   │   │   │   └── chat_screen.dart
│   │   │   │   ├── widgets/
│   │   │   │   │   ├── message_bubble.dart
│   │   │   │   │   ├── message_input.dart
│   │   │   │   │   ├── typing_indicator.dart
│   │   │   │   │   └── tool_result_card.dart
│   │   │   │   └── providers/
│   │   │   │       └── chat_provider.dart
│   │   │   └── domain/
│   │   │       └── entities/
│   │   │           └── message.dart
│   │   │
│   │   ├── settings/
│   │   │   ├── data/
│   │   │   │   ├── models/
│   │   │   │   │   └── settings_model.dart
│   │   │   │   └── repositories/
│   │   │   │       └── settings_repository.dart
│   │   │   ├── presentation/
│   │   │   │   ├── screens/
│   │   │   │   │   └── settings_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       ├── connection_selector.dart
│   │   │   │       ├── llm_config_card.dart
│   │   │   │       └── docker_status_card.dart
│   │   │   └── providers/
│   │   │       └── settings_provider.dart
│   │   │
│   │   ├── history/
│   │   │   ├── data/
│   │   │   │   └── repositories/
│   │   │   │       └── history_repository.dart
│   │   │   ├── presentation/
│   │   │   │   ├── screens/
│   │   │   │   │   └── history_screen.dart
│   │   │   │   └── widgets/
│   │   │   │       └── conversation_tile.dart
│   │   │   └── providers/
│   │   │       └── history_provider.dart
│   │   │
│   │   └── onboarding/
│   │       ├── presentation/
│   │       │   ├── screens/
│   │       │   │   ├── welcome_screen.dart
│   │       │   │   ├── connection_choice_screen.dart
│   │       │   │   ├── cloud_setup_screen.dart
│   │       │   │   ├── local_setup_screen.dart
│   │       │   │   └── api_key_screen.dart
│   │       │   └── providers/
│   │       │       └── onboarding_provider.dart
│   │       └── domain/
│   │           └── steps.dart
│   │
│   ├── shared/
│   │   ├── widgets/
│   │   │   ├── loading_indicator.dart
│   │   │   ├── error_view.dart
│   │   │   ├── empty_state.dart
│   │   │   └── status_badge.dart
│   │   ├── providers/
│   │   │   └── providers.dart          # Shared providers
│   │   └── utils/
│   │       └── date_utils.dart
│   │
│   └── services/
│       ├── api/
│       │   ├── api_client.dart         # HTTP client (dio)
│       │   ├── api_exception.dart      # Custom exceptions
│       │   └── sse_client.dart         # Server-Sent Events
│       ├── storage/
│       │   ├── local_storage.dart      # SQLite (drift)
│       │   └── secure_storage.dart     # API keys (flutter_secure_storage)
│       ├── docker/
│       │   └── docker_service.dart     # Docker status/check
│       └── connection/
│           ├── connection_manager.dart # Connection state
│           └── mDns_discovery.dart    # Local network discovery
│
├── test/                              # Unit/widget tests
├── integration_test/                  # Integration tests
├── ios/
├── android/
├── linux/
├── macos/
├── windows/
├── web/
│
├── pubspec.yaml
├── analysis_options.yaml
└── README.md
```

---

## 3. Connection Modes

### Mode A: Cloud (Default)
```
User → Your API (https://api.executive-assistant.dev)
```
- App connects to your hosted API
- No local setup required
- Works on all platforms

### Mode B: Local Docker (Desktop)
```
User → http://localhost:8000 (Docker)
```
- User runs Docker Compose locally
- All data stays on machine
- Desktop only

### Mode C: Local Network (Desktop + Mobile on same WiFi)
```
Mobile → http://<desktop-ip>:8000
```
- Mobile discovers desktop via mDNS
- Works when on same network

### Mode D: Tailscale (WAN)
```
Mobile → Tailscale VPN → Desktop
```
- Uses Tailscale for remote access

---

## 4. API Integration

### Existing API Endpoints (from src/http/main.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/ready` | GET | Readiness check |
| `/message` | POST | Send message (non-streaming) |
| `/message/stream` | POST | Send message (SSE streaming) |

### Request/Response Format

```dart
// POST /message
class MessageRequest {
  String message;
  String? model;      // Optional model override
  String? user_id;    // Optional user ID
}

class MessageResponse {
  String response;
  String? error;
}

// POST /message/stream (SSE)
// Response format:
// data: {"type": "tool", "content": "..."}
// data: {"type": "ai", "content": "..."}
// data: {"type": "done", "content": "final response"}
```

### Flutter API Client

```dart
class ApiClient {
  // Non-streaming
  Future<MessageResponse> sendMessage(String message);

  // Streaming (SSE)
  Stream<ChatChunk> sendMessageStream(String message);
}

class ChatChunk {
  final ChunkType type; // tool, ai, done
  final String content;
}

enum ChunkType { tool, ai, done }
```

---

## 5. State Management (Riverpod)

### Providers Structure

```dart
// Connection state
final connectionProvider = StateNotifierProvider<ConnectionNotifier, ConnectionState>

// Chat state
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>

// Settings
final settingsProvider = StateNotifierProvider<SettingsNotifier, SettingsState>

// Docker status (desktop only)
final dockerStatusProvider = StreamProvider<DockerStatus>

// Local agent discovery
final discoveredAgentsProvider = FutureProvider<List<DiscoveredAgent>>
```

### Connection State

```dart
enum ConnectionMode { cloud, local, localNetwork, tailscale }

class ConnectionState {
  final ConnectionMode mode;
  final String url;
  final bool isConnected;
  final String? errorMessage;
  final DockerStatus? dockerStatus;
}
```

### Chat State

```dart
class ChatState {
  final List<Message> messages;
  final bool isLoading;
  final String? error;
  final Set<String> activeTools;  // Tools currently being executed
}

class Message {
  final String id;
  final MessageRole role; // user, assistant, system
  final String content;
  final DateTime timestamp;
  final List<ToolCall>? toolCalls;
  final List<ToolResult>? toolResults;
}

enum MessageRole { user, assistant, system, tool }
```

---

## 6. Local Storage

### SQLite Schema (via Drift)

```dart
// Tables
class Conversations extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()();
  TextColumn get title => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();
}

class Messages extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get conversationId => integer().references(Conversations, #id)();
  TextColumn get role => text()(); // user, assistant, system, tool
  TextColumn get content => text()();
  DateTimeColumn get timestamp => dateTime()();
  TextColumn get toolCalls => text().nullable()(); // JSON
}
```

### Secure Storage (API Keys)

| Key | Description |
|-----|-------------|
| `api_key_openai` | OpenAI API key |
| `api_key_anthropic` | Anthropic API key |
| `api_key_firecrawl` | Firecrawl API key |
| `user_id` | Current user ID |
| `connection_url` | Custom connection URL |

---

## 7. UI Screens

### Screen 1: Chat Screen (Main)
```
┌─────────────────────────────────────────────────┐
│  ← Executive Assistant          ⚙️  📋        │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ 🤖 Hello! How can I help you today?     │  │
│  │     10:30 AM                              │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ I'd like to book a meeting with John     │  │
│  │     10:31 AM                              │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ 🔧 Creating todo: "Meeting with John"    │  │
│  │     ✓ Created in your todo list          │  │
│  │     10:31 AM                              │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ Typing...                                 │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
├─────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐ ┌───┐ │
│  │ Type your message...                │ │ ➤ │ │
│  └─────────────────────────────────────┘ └───┘ │
└─────────────────────────────────────────────────┘
```

### Screen 2: Settings Screen
```
┌─────────────────────────────────────────────────┐
│  ← Settings                                     │
├─────────────────────────────────────────────────┤
│                                                 │
│  CONNECTION                                     │
│  ┌───────────────────────────────────────────┐  │
│  │ Mode: [ ▼ Local / Cloud ]                │  │
│  │                                              │  │
│  │ ● Connected to Local                       │  │
│  │   http://localhost:8000                    │  │
│  │   Docker: ● Running                       │  │
│  │   Firecrawl: ● Running                   │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  AI PROVIDER                                    │
│  ┌───────────────────────────────────────────┐  │
│  │ [ ▼ OpenAI / Anthropic / Ollama ]         │  │
│  │                                              │  │
│  │ API Key: •••••••••••••• [Change]         │  │
│  │                                              │  │
│  │ [Test Connection] ✓ Connected             │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  STORAGE                                        │
│  ┌───────────────────────────────────────────┐  │
│  │ Data Location: ~/ExecutiveAssistant      │  │
│  │ Conversations: 42                        │  │
│  │ Storage Used: 24 MB                      │  │
│  │                                              │  │
│  │ [Clear History] [Export Data]             │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Screen 3: Onboarding Flow
```
Step 1: Welcome
┌─────────────────────────────────────────────────┐
│                                                 │
│           🤖 Executive Assistant              │
│                                                 │
│  Your AI assistant that works locally          │
│  or in the cloud.                              │
│                                                 │
│              [Get Started]                      │
│                                                 │
└─────────────────────────────────────────────────┘

Step 2: Choose Mode
┌─────────────────────────────────────────────────┐
│  How would you like to connect?                │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ ☑ Cloud (Recommended)                     │  │
│  │    Works everywhere, no setup             │  │
│  │    Your data on our servers              │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ ○ Local                                   │  │
│  │    Everything runs on your machine       │  │
│  │    Requires Docker Desktop               │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘

Step 3: API Key (Cloud) or Docker Setup (Local)
```

---

## 8. Platform-Specific Features

### Desktop (Windows, macOS, Linux)

| Feature | Implementation |
|---------|----------------|
| Docker status | Check if Docker daemon is running |
| Auto-start Docker | Prompt to start Docker Compose |
| System tray | Minimize to tray |
| Global shortcuts | Cmd+Shift+E to open |

### Mobile (iOS, Android)

| Feature | Implementation |
|---------|----------------|
| Local network discovery | Use bonjour/mDNS |
| Push notifications | FCM or local notifications |
| Background sync | WorkManager for iCloud sync |
| Biometric auth | LocalAuthentication |

### Web

| Feature | Implementation |
|---------|----------------|
| PWA support | Service worker, offline fallback |
| Responsive | Adapts to screen size |

---

## 9. Docker Integration (Desktop)

### Docker Compose for Local Mode

```yaml
# docker-compose.yml
services:
  agent:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000

  firecrawl:
    image: firecrawl/firecrawl
    ports:
      - "8002:8002"
```

### Docker Status Check

```dart
class DockerService {
  Future<DockerStatus> checkStatus() async {
    try {
      final result = await Process.run('docker', ['ps']);
      if (result.exitCode == 0) {
        return DockerStatus(
          isRunning: true,
          containers: _parseContainers(result.stdout),
        );
      }
    } catch (e) {
      // Docker not installed or not running
    }
    return DockerStatus(isRunning: false);
  }
}
```

---

## 10. Implementation Roadmap

### Phase 1: MVP (2-3 weeks)

| Week | Tasks |
|------|-------|
| 1 | Project setup, theme, router, basic providers |
| 2 | API client, Chat screen with non-streaming |
| 3 | Settings screen, onboarding flow, local storage |

**Deliverable**: Working app with cloud connection

### Phase 2: Local Mode (2 weeks)

| Week | Tasks |
|------|-------|
| 4 | Docker service, local API detection |
| 5 | Docker setup UI, status indicators |

**Deliverable**: Local Docker mode works

### Phase 3: Streaming & Polish (1 week)

| Week | Tasks |
|------|-------|
| 6 | SSE streaming, typing indicators |
| 7 | Error handling, loading states, polish |

**Deliverable**: Production-ready

### Phase 4: Mobile Enhancement (2 weeks)

| Week | Tasks |
|------|-------|
| 8 | Mobile UI adaptation, local network discovery |
| 9 | Push notifications, offline support |

**Deliverable**: Mobile app ready

### Phase 5: Advanced Features (ongoing)

| Feature | Notes |
|---------|-------|
| Tailscale integration | Document or SDK |
| iCloud sync | Future enhancement |
| Enterprise features | SSO, company mode |

---

## 11. Dependencies (pubspec.yaml)

```yaml
dependencies:
  flutter:
    sdk: flutter

  # State Management
  flutter_riverpod: ^2.4.0
  riverpod_annotation: ^2.3.0

  # Routing
  go_router: ^13.0.0

  # Networking
  dio: ^5.4.0
  sse_client: ^1.0.0  # Or custom implementation

  # Storage
  drift: ^2.14.0
  sqlite3_flutter_libs: ^0.5.0
  path_provider: ^2.1.0
  flutter_secure_storage: ^9.0.0

  # UI
  flutter_chat_ui: ^1.6.0  # Optional base
  cached_network_image: ^3.3.0
  shimmer: ^3.0.0

  # Desktop
  window_manager: ^0.3.0  # For desktop window management

  # Utilities
  uuid: ^4.2.0
  intl: ^0.18.0
  equatable: ^2.0.5
  freezed_annotation: ^2.4.0
  json_annotation: ^4.8.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
  freezed: ^2.4.0
  json_serializable: ^6.7.0
  drift_dev: ^2.14.0
  flutter_lints: ^3.0.0
```

---

## 12. API Expansion (Future)

Consider adding these endpoints to your backend for a complete Flutter app:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/conversations` | GET | List conversations |
| `/conversations/{id}` | GET | Get conversation messages |
| `/conversations/{id}` | DELETE | Delete conversation |
| `/settings` | GET/PUT | User settings |
| `/docker/status` | GET | Check Docker status (desktop) |
| `/docker/start` | POST | Start Docker Compose |
| `/tools/list` | GET | Available tools |
| `/tools/{tool}/schema` | GET | Tool schema for UI |

---

## 13. Summary

| Aspect | Decision |
|--------|----------|
| **Framework** | Flutter |
| **State** | Riverpod |
| **Routing** | GoRouter |
| **Storage** | Drift (SQLite) + flutter_secure_storage |
| **HTTP** | Dio |
| **Connection** | Cloud-first, local Docker optional |
| **Desktop** | Full support with Docker integration |
| **Mobile** | Cloud fallback, local network option |
| **Web** | Responsive, PWA-ready |

This architecture provides a solid foundation for a cross-platform AI assistant client that can work both in the cloud and locally via Docker.