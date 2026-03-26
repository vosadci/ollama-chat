import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ollama_chat/widgets/input_bar.dart';

Widget _wrap({
  required TextEditingController controller,
  bool isLoading = false,
  VoidCallback? onSend,
  VoidCallback? onStop,
}) =>
    MaterialApp(
      home: Scaffold(
        body: InputBar(
          controller: controller,
          isLoading: isLoading,
          onSend: onSend ?? () {},
          onStop: onStop ?? () {},
        ),
      ),
    );

void main() {
  group('InputBar — send/stop button', () {
    testWidgets('shows send icon when not loading', (tester) async {
      await tester.pumpWidget(_wrap(controller: TextEditingController()));
      expect(find.byIcon(Icons.send_rounded), findsOneWidget);
      expect(find.byIcon(Icons.stop_rounded), findsNothing);
    });

    testWidgets('shows stop icon when loading', (tester) async {
      await tester.pumpWidget(
          _wrap(controller: TextEditingController(), isLoading: true));
      expect(find.byIcon(Icons.stop_rounded), findsOneWidget);
      expect(find.byIcon(Icons.send_rounded), findsNothing);
    });

    testWidgets('send button is disabled when input is empty', (tester) async {
      await tester.pumpWidget(_wrap(controller: TextEditingController()));
      await tester.pump();
      final btn = tester.widget<IconButton>(
        find.widgetWithIcon(IconButton, Icons.send_rounded),
      );
      expect(btn.onPressed, isNull);
    });

    testWidgets('send button is enabled when input has text', (tester) async {
      final ctrl = TextEditingController();
      await tester.pumpWidget(_wrap(controller: ctrl));
      await tester.enterText(find.byType(TextField), 'Hello');
      await tester.pump();
      final btn = tester.widget<IconButton>(
        find.widgetWithIcon(IconButton, Icons.send_rounded),
      );
      expect(btn.onPressed, isNotNull);
    });

    testWidgets('send button is disabled for whitespace-only input',
        (tester) async {
      final ctrl = TextEditingController();
      await tester.pumpWidget(_wrap(controller: ctrl));
      await tester.enterText(find.byType(TextField), '   ');
      await tester.pump();
      final btn = tester.widget<IconButton>(
        find.widgetWithIcon(IconButton, Icons.send_rounded),
      );
      expect(btn.onPressed, isNull);
    });

    testWidgets('tapping stop button calls onStop', (tester) async {
      bool stopped = false;
      await tester.pumpWidget(_wrap(
        controller: TextEditingController(),
        isLoading: true,
        onStop: () => stopped = true,
      ));
      await tester.tap(find.byIcon(Icons.stop_rounded));
      expect(stopped, isTrue);
    });

    testWidgets('tapping send button calls onSend', (tester) async {
      bool sent = false;
      final ctrl = TextEditingController(text: 'Hello');
      await tester.pumpWidget(_wrap(
        controller: ctrl,
        onSend: () => sent = true,
      ));
      await tester.pump();
      await tester.tap(find.byIcon(Icons.send_rounded));
      expect(sent, isTrue);
    });
  });

  group('InputBar — text field', () {
    testWidgets('renders text field with hint', (tester) async {
      await tester.pumpWidget(_wrap(controller: TextEditingController()));
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('accepts multi-line input', (tester) async {
      await tester.pumpWidget(_wrap(controller: TextEditingController()));
      final tf = tester.widget<TextField>(find.byType(TextField));
      expect(tf.maxLines, greaterThan(1));
    });
  });
}
