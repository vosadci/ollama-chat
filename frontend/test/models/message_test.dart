import 'package:flutter_test/flutter_test.dart';
import 'package:ollama_chat/models/message.dart';

void main() {
  group('MessageRole', () {
    test('has user and assistant values', () {
      expect(MessageRole.values, contains(MessageRole.user));
      expect(MessageRole.values, contains(MessageRole.assistant));
    });
  });

  group('ChatMessage', () {
    final timestamp = DateTime(2024, 1, 1, 12, 0);

    test('isUser returns true for user role', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Hello',
        timestamp: timestamp,
      );
      expect(msg.isUser, isTrue);
    });

    test('isUser returns false for assistant role', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Hello',
        timestamp: timestamp,
      );
      expect(msg.isUser, isFalse);
    });

    test('content is mutable', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: '',
        timestamp: timestamp,
      );
      msg.content += 'token1';
      msg.content += 'token2';
      expect(msg.content, 'token1token2');
    });

    test('isStreaming defaults to false', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: '',
        timestamp: timestamp,
      );
      expect(msg.isStreaming, isFalse);
    });

    test('isStreaming can be set to true', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: '',
        timestamp: timestamp,
        isStreaming: true,
      );
      expect(msg.isStreaming, isTrue);
    });

    test('sources defaults to empty list', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Hello',
        timestamp: timestamp,
      );
      expect(msg.sources, isEmpty);
    });

    test('sources can be assigned', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Answer',
        timestamp: timestamp,
      );
      msg.sources = [
        {'title': 'Credite', 'source': 'credite.html'},
        {'title': 'Carduri', 'source': 'carduri.html'},
      ];
      expect(msg.sources.length, 2);
      expect(msg.sources[0]['title'], 'Credite');
    });

    test('id is stored correctly', () {
      final msg = ChatMessage(
        id: 'abc-123',
        role: MessageRole.user,
        content: 'Hi',
        timestamp: timestamp,
      );
      expect(msg.id, 'abc-123');
    });

    test('timestamp is stored correctly', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.user,
        content: 'Hi',
        timestamp: timestamp,
      );
      expect(msg.timestamp, timestamp);
    });
  });
}
