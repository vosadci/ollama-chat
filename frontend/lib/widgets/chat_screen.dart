import 'dart:math' show Random;

import 'package:flutter/material.dart';

import '../models/message.dart';
import '../services/chat_service.dart';
import 'input_bar.dart';
import 'message_bubble.dart';

class ChatScreen extends StatefulWidget {
  final ChatService? service;
  const ChatScreen({super.key, this.service});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  late final _service = widget.service ?? ChatService();
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _atBottom = true;
  String? _pendingText;

  // Generates a cryptographically random 128-bit hex ID.
  // Avoids the uuid package to keep dependencies minimal.
  String _uid() {
    final rng = Random.secure();
    return List.generate(32, (_) => rng.nextInt(16).toRadixString(16)).join();
  }

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(() {
      if (!_scrollController.hasClients) return;
      final atBottom = _scrollController.position.pixels >=
          _scrollController.position.maxScrollExtent - 80;
      if (atBottom != _atBottom) setState(() => _atBottom = atBottom);
    });
  }

  void _scrollToBottom() {
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

  static const _maxMessageLength = 32000;

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

    final userMsg = ChatMessage(
      id: _uid(),
      role: MessageRole.user,
      content: text,
      timestamp: DateTime.now(),
    );

    final assistantMsg = ChatMessage(
      id: _uid(),
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );

    setState(() {
      _messages.addAll([userMsg, assistantMsg]);
      _isLoading = true;
    });
    _scrollToBottom();

    // Build history excluding the empty streaming placeholder
    final history = _messages
        .where((m) => m != assistantMsg)
        .map((m) => {
              'role': m.isUser ? 'user' : 'assistant',
              'content': m.content,
            })
        .toList();

    await _service.sendMessages(
      messages: history,
      onSources: (sources) {
        if (!mounted) return;
        setState(() => assistantMsg.sources = sources);
      },
      onToken: (token) {
        if (!mounted) return;
        setState(() => assistantMsg.content += token);
        _scrollToBottom();
      },
      onDone: () {
        if (!mounted) return;
        setState(() {
          assistantMsg.isStreaming = false;
          _isLoading = false;
        });
        _scrollToBottom();
      },
      onError: (err, {bool isConnectionError = false}) {
        if (!mounted) return;
        setState(() {
          _messages.removeWhere(
            (m) => m == userMsg || m == assistantMsg,
          );
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
          setState(() {
            assistantMsg.content = '⚠ $err';
            assistantMsg.isStreaming = false;
            _messages.addAll([userMsg, assistantMsg]);
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
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
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
              onPressed: _scrollToBottom,
              child: const Icon(Icons.keyboard_arrow_down),
            ),
      body: Column(
        children: [
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    key: const Key('messageList'),
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: _messages.length,
                    itemBuilder: (_, i) => MessageBubble(message: _messages[i]),
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

  static const _suggestions = [
    'What types of accounts are available?',
    'Tell me about card options.',
    'What loan products are offered?',
    'How do I open an account?',
  ];

  Widget _buildEmptyState() {
    return Center(
      key: const Key('emptyState'),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline,
                size: 64, color: Colors.grey.shade300),
            const SizedBox(height: 16),
            Text(
              'Start a conversation',
              style: TextStyle(color: Colors.grey.shade500, fontSize: 16),
            ),
            const SizedBox(height: 24),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _suggestions.map((q) {
                return ActionChip(
                  label: Text(q),
                  onPressed: () {
                    _controller.text = q;
                    _send();
                  },
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}
