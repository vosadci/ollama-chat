# Ollama Chat — Frontend

Flutter frontend for Ollama Chat. A streaming AI chat interface with RAG source attribution, supporting iOS, Android, and Web.

## Architecture

- **Flutter / Dart** — cross-platform UI framework
- **Material 3** — design system with primary blue theme
- **SSE (Server-Sent Events)** — streaming chat responses from the backend
- **flutter_markdown** — renders assistant responses as formatted Markdown

## Prerequisites

- [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.11+
- Xcode (for iOS builds) or Chrome (for web)
- The [backend](../backend/README.md) running on `http://localhost:8000`

Verify your Flutter setup:

```bash
flutter doctor
```

## Docker (recommended for web)

From the repo root:

```bash
make setup   # copies .env, pulls Ollama models
make run     # starts backend + frontend via Docker Compose
open http://localhost:3000
```

See the root [README](../README.md) for the full Docker workflow.

## Local Setup

```bash
cd frontend
flutter pub get
```

## Running Locally

```bash
# iOS simulator
flutter run -d "iPhone 17 Pro Max" --no-enable-impeller

# List available devices/simulators
flutter devices

# Chrome (web) — connects to backend at localhost:8000
flutter run -d chrome
```

## Building

```bash
# iOS (release)
flutter build ios --release

# Web (for Docker — backend URL injected at build time)
flutter build web --release --dart-define=BACKEND_URL=/api/v1

# Android
flutter build apk
```

## Running Tests

### Widget tests (offline, ~3s)

```bash
flutter test        # all 50 tests
flutter test -v     # verbose
```

| File | What it covers |
|---|---|
| `test/models/message_test.dart` | `ChatMessage` model — 10 tests |
| `test/widgets/input_bar_test.dart` | Send/stop states, keyboard shortcut — 9 tests |
| `test/widgets/message_bubble_test.dart` | Streaming, markdown, source chips — 9 tests |
| `test/widget_test.dart` | Empty state, suggested chip labels — 5 tests |
| `test/widgets/chat_screen_test.dart` | Send/receive flow, error handling, clear dialog, stop — 17 tests |

All widget tests are fully offline — `ChatService` is replaced with a `MockChatService` (via `mocktail`).

### End-to-end tests (Chrome, real backend)

Drives the real app in Chrome with actual taps, receives real Ollama responses.
Runs on macOS and Linux. A Chrome window opens; you can watch the tests drive it.
For headless use, set `CHROME_FLAGS=--headless` or prefix with `xvfb-run`.

```bash
# Requires backend running:
cd ../backend && .venv/bin/python main.py

# Run E2E tests (opens Chrome):
flutter test integration_test/ -d chrome

# Or from repo root:
make e2e
```

| Test | What it covers |
|---|---|
| App loads | Initial render, 4 suggested chips visible |
| Send + receive | Full send → stream → display flow |
| Typing indicator | Shown during streaming, gone on completion |
| RAG sources | Source chips appear after knowledge-base questions |
| Suggested chip tap | Chip populates input and sends |
| Clear conversation | Delete → dialog → empty state |
| Multi-turn | Two exchanges, both messages retained |

## Project Structure

```
lib/
  main.dart                  # App entry point, theme setup
  models/
    message.dart             # ChatMessage model
  services/
    chat_service.dart        # Backend API client (SSE streaming)
  utils/
    url_launcher_helper.dart # Platform-aware URL opening (web vs mobile)
  widgets/
    chat_screen.dart         # Main screen: message list, send bar, empty state
    message_bubble.dart      # Individual message bubbles with Markdown + sources
    input_bar.dart           # Text input with send/stop toggle
    typing_indicator.dart    # Animated dots shown while streaming
test/
  models/                    # Model unit tests
  widgets/                   # Widget + ChatScreen functional tests
integration_test/
  app_test.dart              # E2E tests (visible macOS window, real backend)
```

## Configuration

The backend URL is set via a build-time `--dart-define` flag with a localhost fallback:

```dart
static const _baseUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000/api/v1',
);
```

| Scenario | Value |
|---|---|
| Local dev (mobile or Chrome) | `http://localhost:8000/api/v1` (default) |
| Docker web build | `/api/v1` (same-origin, proxied by nginx) |
| Custom deployment | Pass `--dart-define=BACKEND_URL=https://your-api/api/v1` |

Source link chips can optionally open the originating document. Set `SOURCE_BASE_URL` at build time to enable links:

```bash
flutter run --dart-define=SOURCE_BASE_URL=https://yourdomain.com
```

If not set, source chips are shown as plain labels.
