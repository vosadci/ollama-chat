enum MessageRole { user, assistant }

class ChatMessage {
  final String id;
  final MessageRole role;
  String content; // mutable — grows token-by-token during streaming
  final DateTime timestamp;
  bool isStreaming;
  List<Map<String, String>> sources;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isStreaming = false,
    this.sources = const [],
  });

  bool get isUser => role == MessageRole.user;
}
