/// End-to-end integration tests — run against a live backend.
///
/// Prerequisites:
///   1. ollama serve
///   2. cd backend && .venv/bin/python main.py
///
/// Run:
///   make e2e
///   # or directly:
///   flutter test integration_test/ -d macos    # macOS
///   flutter test integration_test/ -d linux    # Linux (requires display server)
///
/// A native desktop window opens; you can watch the app as tests drive it.
/// (Web targets are not supported by the integration_test package.)

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:ollama_chat/main.dart' as app;
import 'package:ollama_chat/widgets/typing_indicator.dart';

// Generous timeout for real Ollama streaming responses.
const _llmTimeout = Duration(seconds: 90);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Ollama Chat — E2E', () {
    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /// Launches the app and waits for the initial frame.
    Future<void> launch(WidgetTester tester) async {
      app.main();
      await tester.pumpAndSettle();
    }

    /// Types [text] and taps the send button.
    Future<void> sendMessage(WidgetTester tester, String text) async {
      await tester.enterText(find.byType(TextField), text);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('send')));
      await tester.pump();
    }

    /// Waits for the LLM to finish streaming (typing indicator gone).
    Future<void> waitForResponse(WidgetTester tester) async {
      await tester.pumpAndSettle(_llmTimeout);
    }

    // -----------------------------------------------------------------------
    // 1. Empty state
    // -----------------------------------------------------------------------

    testWidgets('app loads with empty state and suggested chips', (tester) async {
      await launch(tester);

      expect(find.byKey(const Key('emptyState')), findsOneWidget);
      expect(find.text('Start a conversation'), findsOneWidget);
      expect(find.text('What types of accounts are available?'), findsOneWidget);
      expect(find.text('Tell me about card options.'), findsOneWidget);
      expect(find.text('What loan products are offered?'), findsOneWidget);
      expect(find.text('How do I open an account?'), findsOneWidget);
    });

    // -----------------------------------------------------------------------
    // 2. Send a message and receive a real response
    // -----------------------------------------------------------------------

    testWidgets('send message and receive assistant response', (tester) async {
      await launch(tester);

      await sendMessage(tester, 'What services do you offer?');

      // User bubble appears immediately
      expect(find.text('What services do you offer?'), findsOneWidget);

      // Message list is visible (empty state gone)
      expect(find.byKey(const Key('messageList')), findsOneWidget);

      // Wait for streaming to complete
      await waitForResponse(tester);

      // Stop button gone, send button back
      expect(find.byKey(const ValueKey('stop')), findsNothing);
      expect(find.byKey(const ValueKey('send')), findsOneWidget);

      // At least one assistant bubble with content exists
      // (MarkdownBody renders the assistant reply)
      expect(find.byType(MarkdownBody), findsWidgets);
    });

    // -----------------------------------------------------------------------
    // 3. Typing indicator appears while streaming
    // -----------------------------------------------------------------------

    testWidgets('typing indicator visible during streaming', (tester) async {
      await launch(tester);

      await sendMessage(tester, 'Salut');

      // Pump a few frames — streaming started, indicator should appear
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byType(TypingIndicator), findsOneWidget);

      // Wait for completion — indicator should be gone
      await waitForResponse(tester);
      expect(find.byType(TypingIndicator), findsNothing);
    });

    // -----------------------------------------------------------------------
    // 4. RAG sources appear after a knowledge-base question
    // -----------------------------------------------------------------------

    testWidgets('source chips appear after RAG-relevant question', (tester) async {
      await launch(tester);

      await sendMessage(tester, 'What card options are available?');
      await waitForResponse(tester);

      // At least one source chip (open_in_new icon) should be present
      expect(find.byIcon(Icons.open_in_new), findsWidgets);
    });

    // -----------------------------------------------------------------------
    // 5. Tap a suggested chip
    // -----------------------------------------------------------------------

    testWidgets('tapping suggested chip sends message', (tester) async {
      await launch(tester);

      const chipText = 'What types of accounts are available?';
      await tester.tap(find.text(chipText));
      await tester.pump();

      // User bubble with chip text appears
      expect(find.text(chipText), findsOneWidget);

      // Wait for response
      await waitForResponse(tester);
      expect(find.byKey(const ValueKey('send')), findsOneWidget);
    });

    // -----------------------------------------------------------------------
    // 6. Clear conversation
    // -----------------------------------------------------------------------

    testWidgets('clear conversation returns to empty state', (tester) async {
      await launch(tester);

      // Send a message first
      await sendMessage(tester, 'Test');
      await waitForResponse(tester);

      // Tap clear button
      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      // Confirm dialog
      expect(find.text('Clear conversation?'), findsOneWidget);
      await tester.tap(find.text('Clear'));
      await tester.pumpAndSettle();

      // Empty state back
      expect(find.byKey(const Key('emptyState')), findsOneWidget);
    });

    // -----------------------------------------------------------------------
    // 7. Multi-turn conversation
    // -----------------------------------------------------------------------

    testWidgets('multi-turn conversation keeps all messages', (tester) async {
      await launch(tester);

      await sendMessage(tester, 'What types of accounts are available?');
      await waitForResponse(tester);

      await sendMessage(tester, 'Tell me about card options.');
      await waitForResponse(tester);

      // Both user messages should be visible
      expect(find.text('What types of accounts are available?'), findsOneWidget);
      expect(find.text('Tell me about card options.'), findsOneWidget);

      // Two assistant bubbles (MarkdownBody widgets)
      expect(find.byType(MarkdownBody), findsNWidgets(2));
    });
  });
}
