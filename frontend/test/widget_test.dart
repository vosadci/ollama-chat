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
      expect(find.text('What types of accounts are available?'), findsOneWidget);
      expect(find.text('Tell me about card options.'), findsOneWidget);
      expect(find.text('What loan products are offered?'), findsOneWidget);
      expect(find.text('How do I open an account?'), findsOneWidget);
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
