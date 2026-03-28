import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ollama_chat/models/message.dart';
import 'package:ollama_chat/widgets/message_bubble.dart';
import 'package:ollama_chat/widgets/typing_indicator.dart';

Widget _wrap(ChatMessage message) => MaterialApp(
      home: Scaffold(body: MessageBubble(message: message)),
    );

void main() {
  final ts = DateTime(2024, 1, 1, 14, 30);

  group('MessageBubble — streaming state', () {
    testWidgets('shows TypingIndicator when streaming with empty content',
        (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: '',
        timestamp: ts,
        isStreaming: true,
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.byType(TypingIndicator), findsOneWidget);
    });

    testWidgets('does not show TypingIndicator when content is non-empty',
        (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Hello',
        timestamp: ts,
        isStreaming: true,
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.byType(TypingIndicator), findsNothing);
    });
  });

  group('MessageBubble — content rendering', () {
    testWidgets('renders MarkdownBody for assistant messages', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Hello world',
        timestamp: ts,
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.byType(MarkdownBody), findsOneWidget);
    });

    testWidgets('renders plain Text for user messages', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Hello world',
        timestamp: ts,
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.byType(MarkdownBody), findsNothing);
      expect(find.text('Hello world'), findsOneWidget);
    });

    testWidgets('shows formatted time', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Hi',
        timestamp: ts,
      );
      await tester.pumpWidget(_wrap(msg));
      // Time should be rendered somewhere in the bubble
      expect(find.textContaining(':'), findsWidgets);
    });
  });

  group('MessageBubble — source chips', () {
    testWidgets('shows no source chips when sources are empty', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Answer',
        timestamp: ts,
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.byIcon(Icons.article_outlined), findsNothing);
    });

    testWidgets('shows source chip titles when sources are present',
        (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Answer',
        timestamp: ts,
        sources: [
          {'title': 'Getting Started', 'source': 'getting-started.html'},
        ],
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.text('Getting Started'), findsOneWidget);
      // SOURCE_BASE_URL is empty in tests, so chips show as plain labels
      expect(find.byIcon(Icons.article_outlined), findsOneWidget);
    });

    testWidgets('shows multiple source chips', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Answer',
        timestamp: ts,
        sources: [
          {'title': 'Pricing', 'source': 'pricing.html'},
          {'title': 'Features', 'source': 'features.html'},
        ],
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.text('Pricing'), findsOneWidget);
      expect(find.text('Features'), findsOneWidget);
    });

    testWidgets('does not show source chips for user messages', (tester) async {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Question',
        timestamp: ts,
        sources: [
          {'title': 'Some source', 'source': 'page.html'},
        ],
      );
      await tester.pumpWidget(_wrap(msg));
      expect(find.text('Some source'), findsNothing);
    });
  });
}
