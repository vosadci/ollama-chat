import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ollama_chat/main.dart';
import 'package:ollama_chat/widgets/chat_screen.dart';

void main() {
  group('App', () {
    testWidgets('renders with Ollama Chat title', (tester) async {
      await tester.pumpWidget(const OllamaChatApp());
      expect(find.text('Ollama Chat'), findsOneWidget);
    });

    testWidgets('shows empty state on first launch', (tester) async {
      await tester.pumpWidget(const OllamaChatApp());
      expect(find.text('Start a conversation'), findsOneWidget);
    });
  });

  group('ChatScreen — empty state', () {
    testWidgets('shows suggested question chips', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: ChatScreen()));
      expect(find.text('What features are included in the Pro plan?'), findsOneWidget);
      expect(find.text('How do I get started?'), findsOneWidget);
      expect(find.text('What integrations are supported?'), findsOneWidget);
      expect(find.text('How is my data kept secure?'), findsOneWidget);
    });

    testWidgets('shows chat bubble icon', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: ChatScreen()));
      expect(find.byIcon(Icons.chat_bubble_outline), findsOneWidget);
    });

    testWidgets('shows clear button in AppBar', (tester) async {
      await tester.pumpWidget(const MaterialApp(home: ChatScreen()));
      expect(find.byIcon(Icons.delete_outline), findsOneWidget);
    });
  });
}
