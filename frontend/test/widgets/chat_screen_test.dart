import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:ollama_chat/services/chat_service.dart';
import 'package:ollama_chat/widgets/chat_screen.dart';

// ---------------------------------------------------------------------------
// Mock
// ---------------------------------------------------------------------------

class MockChatService extends Mock implements ChatService {}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Wraps [ChatScreen] in a minimal MaterialApp so tests can pump it.
Widget _app(ChatService service) => MaterialApp(
      home: ChatScreen(service: service),
    );

/// Stubs [mock.sendMessages] to call [onToken] for each token in [tokens],
/// then call [onDone].
void _stubTokens(MockChatService mock, List<String> tokens) {
  when(
    () => mock.sendMessages(
      messages: any(named: 'messages'),
      onToken: any(named: 'onToken'),
      onDone: any(named: 'onDone'),
      onError: any(named: 'onError'),
      onSources: any(named: 'onSources'),
    ),
  ).thenAnswer((inv) async {
    final onToken = inv.namedArguments[#onToken] as TokenCallback;
    final onDone = inv.namedArguments[#onDone] as DoneCallback;
    for (final t in tokens) {
      onToken(t);
    }
    onDone();
  });
}

/// Stubs [mock.sendMessages] to call [onError] with [message].
void _stubError(
  MockChatService mock,
  String message, {
  bool isConnectionError = false,
}) {
  when(
    () => mock.sendMessages(
      messages: any(named: 'messages'),
      onToken: any(named: 'onToken'),
      onDone: any(named: 'onDone'),
      onError: any(named: 'onError'),
      onSources: any(named: 'onSources'),
    ),
  ).thenAnswer((inv) async {
    final onError = inv.namedArguments[#onError] as ErrorCallback;
    onError(message, isConnectionError: isConnectionError);
  });
}

/// Stubs [mock.sendMessages] to call [onSources] then [onDone].
void _stubSources(
  MockChatService mock,
  List<Map<String, String>> sources,
) {
  when(
    () => mock.sendMessages(
      messages: any(named: 'messages'),
      onToken: any(named: 'onToken'),
      onDone: any(named: 'onDone'),
      onError: any(named: 'onError'),
      onSources: any(named: 'onSources'),
    ),
  ).thenAnswer((inv) async {
    final onSources = inv.namedArguments[#onSources] as SourcesCallback;
    final onDone = inv.namedArguments[#onDone] as DoneCallback;
    onSources(sources);
    onDone();
  });
}

/// Types [text] into the TextField and taps the send button.
Future<void> _sendMessage(WidgetTester tester, String text) async {
  await tester.enterText(find.byType(TextField), text);
  await tester.pump();
  await tester.tap(find.byIcon(Icons.send_rounded));
  await tester.pump();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  late MockChatService mock;

  setUpAll(() {
    // mocktail needs fallback values for all callback typedefs so `any()` works.
    // Register fallback values for callback typedefs so any() matchers work.
    registerFallbackValue((String _) {} as TokenCallback);
    registerFallbackValue(() {} as DoneCallback);
    registerFallbackValue((String _, {bool isConnectionError = false}) {} as ErrorCallback);
    registerFallbackValue((List<Map<String, String>> _) {} as SourcesCallback);
    registerFallbackValue(<Map<String, String>>[]);
  });

  setUp(() {
    mock = MockChatService();
    when(() => mock.cancel()).thenAnswer((_) {});
  });

  // -------------------------------------------------------------------------
  // Sending a message
  // -------------------------------------------------------------------------

  group('Sending a message', () {
    testWidgets('user bubble appears after sending', (tester) async {
      _stubTokens(mock, ['Hello']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      expect(find.text('Salut'), findsOneWidget);
    });

    testWidgets('input field is cleared after sending', (tester) async {
      _stubTokens(mock, ['Hi']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Test message');
      await tester.pumpAndSettle();

      final tf = tester.widget<TextField>(find.byType(TextField));
      expect(tf.controller?.text, isEmpty);
    });

    testWidgets('sendMessages is called with correct message', (tester) async {
      _stubTokens(mock, []);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Ce carduri aveți?');
      await tester.pumpAndSettle();

      final captured = verify(
        () => mock.sendMessages(
          messages: captureAny(named: 'messages'),
          onToken: any(named: 'onToken'),
          onDone: any(named: 'onDone'),
          onError: any(named: 'onError'),
          onSources: any(named: 'onSources'),
        ),
      ).captured;

      final messages = captured.first as List<Map<String, String>>;
      expect(messages.last['role'], 'user');
      expect(messages.last['content'], 'Ce carduri aveți?');
    });
  });

  // -------------------------------------------------------------------------
  // Streaming response
  // -------------------------------------------------------------------------

  group('Streaming response', () {
    testWidgets('tokens accumulate in assistant bubble', (tester) async {
      _stubTokens(mock, ['Bună', ' ziua', '!']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      expect(find.text('Bună ziua!'), findsOneWidget);
    });

    testWidgets('send button re-enabled after onDone', (tester) async {
      _stubTokens(mock, ['OK']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      // Stop button should be gone, send button visible
      expect(find.byIcon(Icons.stop_rounded), findsNothing);
      expect(find.byIcon(Icons.send_rounded), findsOneWidget);
    });

    testWidgets('stop button visible while loading', (tester) async {
      // Never calls onDone — keeps loading state active
      when(
        () => mock.sendMessages(
          messages: any(named: 'messages'),
          onToken: any(named: 'onToken'),
          onDone: any(named: 'onDone'),
          onError: any(named: 'onError'),
          onSources: any(named: 'onSources'),
        ),
      ).thenAnswer((_) async {});

      await tester.pumpWidget(_app(mock));
      await _sendMessage(tester, 'Salut');

      expect(find.byIcon(Icons.stop_rounded), findsOneWidget);
    });
  });

  // -------------------------------------------------------------------------
  // Sources
  // -------------------------------------------------------------------------

  group('Sources', () {
    testWidgets('source chip appears when onSources is called', (tester) async {
      _stubSources(mock, [
        {'title': 'Carduri de debit', 'source': 'carduri/carduri-de-debit'},
      ]);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Ce carduri?');
      await tester.pumpAndSettle();

      expect(find.text('Carduri de debit'), findsOneWidget);
    });
  });

  // -------------------------------------------------------------------------
  // Error handling
  // -------------------------------------------------------------------------

  group('Error handling', () {
    testWidgets('connection error restores text to input field', (tester) async {
      _stubError(mock, 'Could not connect to server', isConnectionError: true);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      final tf = tester.widget<TextField>(find.byType(TextField));
      expect(tf.controller?.text, 'Salut');
    });

    testWidgets('connection error shows snackbar', (tester) async {
      _stubError(mock, 'Could not connect to server', isConnectionError: true);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
    });

    testWidgets('connection error removes messages from list', (tester) async {
      _stubError(mock, 'Could not connect to server', isConnectionError: true);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      // Empty state should be visible again
      expect(find.text('Start a conversation'), findsOneWidget);
    });

    testWidgets('server error shows warning in assistant bubble', (tester) async {
      _stubError(mock, 'Something went wrong', isConnectionError: false);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      expect(find.textContaining('⚠'), findsOneWidget);
    });
  });

  // -------------------------------------------------------------------------
  // Suggested chips
  // -------------------------------------------------------------------------

  group('Suggested chips', () {
    testWidgets('tapping a chip sends that message', (tester) async {
      _stubTokens(mock, ['Here are our account options.']);
      await tester.pumpWidget(_app(mock));

      // Tap the first suggested chip
      await tester.tap(find.text('What types of accounts are available?'));
      await tester.pumpAndSettle();

      expect(find.text('What types of accounts are available?'), findsOneWidget);
      verify(
        () => mock.sendMessages(
          messages: any(named: 'messages'),
          onToken: any(named: 'onToken'),
          onDone: any(named: 'onDone'),
          onError: any(named: 'onError'),
          onSources: any(named: 'onSources'),
        ),
      ).called(1);
    });
  });

  // -------------------------------------------------------------------------
  // Clear conversation
  // -------------------------------------------------------------------------

  group('Clear conversation', () {
    testWidgets('clear button shows confirmation dialog', (tester) async {
      _stubTokens(mock, ['OK']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      expect(find.text('Clear conversation?'), findsOneWidget);
    });

    testWidgets('confirming clear removes all messages', (tester) async {
      _stubTokens(mock, ['OK']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Clear'));
      await tester.pumpAndSettle();

      expect(find.text('Start a conversation'), findsOneWidget);
    });

    testWidgets('cancelling clear keeps messages', (tester) async {
      _stubTokens(mock, ['OK']);
      await tester.pumpWidget(_app(mock));

      await _sendMessage(tester, 'Salut');
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Salut'), findsOneWidget);
    });

    testWidgets('clear button disabled when no messages', (tester) async {
      await tester.pumpWidget(_app(mock));

      final btn = tester.widget<IconButton>(
        find.widgetWithIcon(IconButton, Icons.delete_outline),
      );
      expect(btn.onPressed, isNull);
    });
  });

  // -------------------------------------------------------------------------
  // Stop button
  // -------------------------------------------------------------------------

  group('Stop button', () {
    testWidgets('tapping stop calls cancel on service', (tester) async {
      when(
        () => mock.sendMessages(
          messages: any(named: 'messages'),
          onToken: any(named: 'onToken'),
          onDone: any(named: 'onDone'),
          onError: any(named: 'onError'),
          onSources: any(named: 'onSources'),
        ),
      ).thenAnswer((_) async {});

      await tester.pumpWidget(_app(mock));
      await _sendMessage(tester, 'Salut');

      await tester.tap(find.byIcon(Icons.stop_rounded));
      await tester.pump();

      verify(() => mock.cancel()).called(1);
    });
  });
}
