enum MessageRole { user, assistant }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isStreaming;
  final List<Map<String, String>> sources;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isStreaming = false,
    this.sources = const [],
  });

  bool get isUser => role == MessageRole.user;

  /// Returns a new [ChatMessage] with the given fields replaced.
  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    DateTime? timestamp,
    bool? isStreaming,
    List<Map<String, String>>? sources,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isStreaming: isStreaming ?? this.isStreaming,
      sources: sources ?? this.sources,
    );
  }
}
