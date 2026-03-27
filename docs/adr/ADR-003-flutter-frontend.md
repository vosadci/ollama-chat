# ADR-003 — Use Flutter for the frontend

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2024-01 |
| Deciders | Project team |

## Context

The project needs a chat UI that communicates with a FastAPI backend over SSE (Server-Sent Events).  The application is primarily local (desktop + browser) but should be portable to mobile without a separate codebase.

Candidates evaluated:

| Framework | Language | Bundle | SSE support | Cross-platform |
|---|---|---|---|---|
| **Flutter** | Dart | ~8 MB (web) | `http` package (chunked transfer) | Web, Android, iOS, desktop |
| React (Vite/CRA) | TypeScript | ~200 KB (web only) | Native `EventSource` API | Web only |
| Vue 3 | TypeScript | ~150 KB (web only) | Native `EventSource` API | Web only |
| React Native | TypeScript | Native | Community packages | Android, iOS |
| Svelte | TypeScript | ~50 KB (web only) | Native `EventSource` API | Web only |

## Decision

Use **Flutter** (stable channel, Material 3) for the frontend.

Key reasons:

1. **Single codebase, multiple targets**: The same Dart code runs as a web app, a macOS/Windows/Linux desktop app, and an Android/iOS app.  This is the primary reason Flutter was chosen over React/Vue/Svelte, which target web only.

2. **SSE via chunked HTTP**: Flutter's `http` package exposes `Response.bodyBytes` as a `Stream<List<int>>` when using `Client.send()`.  This allows SSE to be consumed as a raw byte stream without a browser-specific `EventSource` API, making the same code work on desktop and mobile.  The `ChatService` implementation streams token chunks in real time via this mechanism.

3. **Material 3**: Flutter's built-in Material 3 component library (`ActionChip`, `SnackBar`, `TextField`, `StreamingResponse`) requires zero additional UI dependencies, reducing bundle size and licensing risk.

4. **Dart's strong null safety**: Null-safety is enforced at compile time, reducing a class of runtime errors common in JavaScript/TypeScript.

5. **`dart-define` for runtime configuration**: Compile-time environment injection (`--dart-define=KEY=VALUE`) enables configuration (e.g. `SUGGESTION_CHIPS`, `API_BASE_URL`) without environment files or a build-time bundler plugin.

### Trade-offs accepted

- **Larger initial web bundle**: Flutter's web output is ~8 MB (canvaskit renderer) vs. < 1 MB for a React SPA.  This is acceptable for an intranet/local deployment where bandwidth is not a concern.  The HTML renderer (Skia-less) produces a ~2 MB bundle when needed.
- **Dart ecosystem**: Dart has a smaller ecosystem than JavaScript.  Dependencies are evaluated more carefully; the project deliberately minimises third-party packages (only `http`, `mocktail` for tests).
- **No native `EventSource`**: The browser's `EventSource` API handles reconnection and `Last-Event-ID` automatically.  Flutter's manual chunked-stream approach requires the application to implement reconnection if needed (currently out of scope).

## Consequences

**Positive**:
- One test suite covers all platforms.
- UI components are platform-native in appearance on desktop targets.
- `ChatService` is fully unit-testable with a `clientFactory` injection pattern — no browser environment needed.

**Negative / trade-offs**:
- Web bundle size is larger than a React equivalent.  Mitigated by using the HTML renderer for web-only deployments.
- Developers unfamiliar with Dart face a learning curve; Dart's syntax is similar to Java/Kotlin/TypeScript which mitigates this.
- `flutter test` requires the Flutter SDK to be available in CI; the Docker build for the web target must include the Flutter toolchain.

## Alternatives rejected

- **React (Vite)**: Excellent for web; rejected because it does not run on desktop/mobile without React Native.
- **React Native**: Targets mobile only (web is experimental); no native desktop support.
- **Svelte**: Smallest bundle; rejected for the same reason as React — web only.
