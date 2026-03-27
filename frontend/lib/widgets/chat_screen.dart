import 'dart:async';
import 'dart:math' show Random;

import 'package:flutter/material.dart';

import '../config/app_config.dart';
import '../models/message.dart';
import '../services/chat_service.dart';
import 'input_bar.dart';
import 'message_bubble.dart';

// Pixels from the bottom edge at which the view is considered "at bottom".
const double _kScrollAtBottomThreshold = 80.0;

// Minimum interval between auto-scroll animations while tokens are streaming.
const Duration _kScrollDebounce = Duration(milliseconds: 100);

// Maximum number of messages retained in the conversation history.
const int _kMaxMessageHistory = 200;

class ChatScreen extends StatefulWidget {
  final ChatService? service;

  /// Suggestion chips shown on the empty-state screen.
  ///
  /// Defaults to [suggestionChips] from [app_config.dart], which in turn
  /// reads the compile-time ``SUGGESTION_CHIPS`` dart-define (pipe-separated).
  /// Pass an explicit list here for testing or widget customisation.
  final List<String>? suggestions;

  const ChatScreen({super.key, this.service, this.suggestions});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final _service = widget.service ?? ChatService();
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  // Insertion-ordered Map gives O(1) lookup by ID while preserving display order.
  final _messages = <String, ChatMessage>{};
  bool _isLoading = false;
  bool _atBottom = true;
  String? _pendingText;
  Timer? _scrollDebounce;
  int _maxMessageLength = 32000; // overwritten by fetchConfig() on init

  // Generates a cryptographically random 128-bit hex ID.
  // Avoids the uuid package to keep dependencies minimal.
  String _uid() {
    final rng = Random.secure();
    return List.generate(32, (_) => rng.nextInt(16).toRadixString(16)).join();
  }

  /// Updates message [id] in place. O(1) via Map lookup.
  /// Must be called inside [setState].
  void _updateMsg(String id, ChatMessage Function(ChatMessage) updater) {
    final msg = _messages[id];
    if (msg != null) _messages[id] = updater(msg);
  }

  /// Adds [msgs] to the conversation, trimming the oldest entries if the
  /// history cap ([_kMaxMessageHistory]) is exceeded.
  void _addMessages(List<ChatMessage> msgs) {
    for (final m in msgs) {
      _messages[m.id] = m;
    }
    while (_messages.length > _kMaxMessageHistory) {
      _messages.remove(_messages.keys.first);
    }
  }

  @override
  void initState() {
    super.initState();
    // Fetch server config asynchronously; keep the compile-time default until
    // the response arrives or if the request fails.
    _service.fetchConfig().then((cfg) {
      if (!mounted) return;
      final limit = cfg?['max_message_length'];
      if (limit is int && limit > 0) {
        setState(() => _maxMessageLength = limit);
      }
    });
    _scrollController.addListener(() {
      if (!_scrollController.hasClients) return;
      final atBottom = _scrollController.position.pixels >=
          _scrollController.position.maxScrollExtent - _kScrollAtBottomThreshold;
      if (atBottom != _atBottom) setState(() => _atBottom = atBottom);
    });
  }

  void _scrollToBottom({bool immediate = false}) {
    if (!immediate) {
      // Debounce rapid calls (e.g. one per streaming token) to avoid
      // queuing hundreds of animations that cause jank.
      if (_scrollDebounce?.isActive ?? false) return;
      _scrollDebounce = Timer(_kScrollDebounce, _doScrollToBottom);
    } else {
      _scrollDebounce?.cancel();
      _doScrollToBottom();
    }
  }

  void _doScrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    if (text.length > _maxMessageLength) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Message too long — max $_maxMessageLength characters '
            '(${text.length} entered).',
          ),
          duration: const Duration(seconds: 4),
        ),
      );
      return;
    }

    _pendingText = text;
    _controller.clear();

    final userMsgId = _uid();
    final assistantMsgId = _uid();

    final userMsg = ChatMessage(
      id: userMsgId,
      role: MessageRole.user,
      content: text,
      timestamp: DateTime.now(),
    );

    final assistantMsg = ChatMessage(
      id: assistantMsgId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );

    setState(() {
      _addMessages([userMsg, assistantMsg]);
      _isLoading = true;
    });
    _scrollToBottom(immediate: true);

    // Build history excluding the empty streaming placeholder
    final history = _messages.values
        .where((m) => m.id != assistantMsgId)
        .map((m) => {
              'role': m.isUser ? 'user' : 'assistant',
              'content': m.content,
            })
        .toList();

    await _service.sendMessages(
      messages: history,
      onSources: (sources) {
        if (!mounted) return;
        setState(() => _updateMsg(assistantMsgId, (m) => m.copyWith(sources: sources)));
      },
      onToken: (token) {
        if (!mounted) return;
        setState(() {
          _updateMsg(
            assistantMsgId,
            (m) => m.copyWith(content: m.content + token),
          );
        });
        _scrollToBottom();
      },
      onDone: () {
        if (!mounted) return;
        setState(() {
          _updateMsg(assistantMsgId, (m) => m.copyWith(isStreaming: false));
          _isLoading = false;
        });
        _scrollToBottom(immediate: true);
      },
      onError: (err, {bool isConnectionError = false}) {
        if (!mounted) return;
        setState(() {
          _messages.remove(userMsgId);
          _messages.remove(assistantMsgId);
          _isLoading = false;
        });
        if (isConnectionError) {
          _controller.text = _pendingText ?? '';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(err),
              duration: const Duration(seconds: 6),
              action: SnackBarAction(label: 'Retry', onPressed: _send),
            ),
          );
        } else {
          // Show a generic message to the user; the raw error may contain
          // server internals (stack traces, HTML error pages, etc.).
          setState(() {
            _addMessages([
              userMsg,
              assistantMsg.copyWith(
                content: '⚠ Something went wrong. Please try again.',
                isStreaming: false,
              ),
            ]);
          });
        }
      },
    );
  }

  Future<void> _confirmClear() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear conversation?'),
        content: const Text('This will remove all messages.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );
    if (confirm == true) setState(() => _messages.clear());
  }

  @override
  void dispose() {
    _scrollDebounce?.cancel();
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final messageList = _messages.values.toList();
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 14,
              backgroundColor: colorScheme.primary,
              child: Text(
                'AI',
                style: TextStyle(
                  color: colorScheme.onPrimary,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Ollama Chat',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                Text(
                  'Local AI Assistant',
                  style: TextStyle(
                    fontSize: 11,
                    color: colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              ],
            ),
          ],
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Clear conversation',
            onPressed: _isLoading || _messages.isEmpty ? null : _confirmClear,
          ),
        ],
      ),
      floatingActionButton: _atBottom
          ? null
          : FloatingActionButton.small(
              tooltip: 'Scroll to bottom',
              onPressed: _scrollToBottom,
              child: const Icon(Icons.keyboard_arrow_down),
            ),
      body: Column(
        children: [
          Expanded(
            child: messageList.isEmpty
                ? _EmptyStateView(
                    suggestions: widget.suggestions ?? suggestionChips,
                    onSuggestionTap: (q) {
                      _controller.text = q;
                      _send();
                    },
                  )
                : _MessageListView(
                    messages: messageList,
                    scrollController: _scrollController,
                  ),
          ),
          const Divider(height: 1),
          InputBar(
            controller: _controller,
            isLoading: _isLoading,
            onSend: _send,
            onStop: _service.cancel,
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Sub-widgets
// ---------------------------------------------------------------------------

class _EmptyStateView extends StatelessWidget {
  final List<String> suggestions;
  final void Function(String) onSuggestionTap;

  const _EmptyStateView({
    required this.suggestions,
    required this.onSuggestionTap,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      key: const Key('emptyState'),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Decorative icon — excluded from the a11y tree.
            ExcludeSemantics(
              child: Icon(Icons.chat_bubble_outline,
                  size: 64, color: Colors.grey.shade300),
            ),
            const SizedBox(height: 16),
            const Text(
              'Start a conversation',
              style: TextStyle(color: Colors.grey, fontSize: 16),
            ),
            const SizedBox(height: 24),
            Semantics(
              label: 'Suggested questions',
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: suggestions.map((q) {
                  return Semantics(
                    button: true,
                    label: 'Ask: $q',
                    child: ActionChip(
                      label: Text(q),
                      onPressed: () => onSuggestionTap(q),
                    ),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageListView extends StatelessWidget {
  final List<ChatMessage> messages;
  final ScrollController scrollController;

  const _MessageListView({
    required this.messages,
    required this.scrollController,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      key: const Key('messageList'),
      controller: scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: messages.length,
      itemBuilder: (_, i) => MessageBubble(message: messages[i]),
    );
  }
}
