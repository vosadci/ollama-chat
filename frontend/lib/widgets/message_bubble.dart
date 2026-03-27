import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:intl/intl.dart';
import '../utils/url_launcher_helper.dart';

import '../models/message.dart';
import 'typing_indicator.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;

  static const _sourceBaseUrl =
      String.fromEnvironment('SOURCE_BASE_URL');

  const MessageBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final colorScheme = Theme.of(context).colorScheme;
    final contentColor =
        isUser ? colorScheme.onPrimaryContainer : colorScheme.onSurface;

    final roleLabel = isUser ? 'You' : 'Assistant';
    final bubble = Semantics(
      // Announce role + content so screen readers describe each bubble.
      label: '$roleLabel: ${message.content.isEmpty ? (message.isStreaming ? 'typing' : '') : message.content}',
      child: Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: Key('msg-${message.id}'),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
        ),
        margin: EdgeInsets.only(
          top: 4,
          bottom: 4,
          left: isUser ? 48 : 12,
          right: isUser ? 12 : 48,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isUser
              ? colorScheme.primaryContainer
              : colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(isUser ? 18 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 18),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (message.isStreaming && message.content.isEmpty)
              const TypingIndicator()
            else if (isUser)
              // ExcludeSemantics: the outer Semantics label already announces
              // the full message content; suppress the redundant Text node.
              ExcludeSemantics(
                child: Text(
                  message.content,
                  style: TextStyle(
                    color: contentColor,
                    fontSize: 15,
                    height: 1.45,
                  ),
                ),
              )
            else
              // ExcludeSemantics: same reason — outer label covers the content.
              ExcludeSemantics(
                child: MarkdownBody(
                  data: message.content,
                  styleSheet: MarkdownStyleSheet(
                    p: TextStyle(color: contentColor, fontSize: 15, height: 1.45),
                    strong: TextStyle(
                        color: contentColor,
                        fontSize: 15,
                        fontWeight: FontWeight.bold),
                    em: TextStyle(
                        color: contentColor,
                        fontSize: 15,
                        fontStyle: FontStyle.italic),
                    listBullet:
                        TextStyle(color: contentColor, fontSize: 15, height: 1.45),
                    h1: TextStyle(
                        color: contentColor,
                        fontSize: 18,
                        fontWeight: FontWeight.bold),
                    h2: TextStyle(
                        color: contentColor,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                    h3: TextStyle(
                        color: contentColor,
                        fontSize: 15,
                        fontWeight: FontWeight.bold),
                    code: TextStyle(
                      color: contentColor,
                      fontSize: 13,
                      backgroundColor:
                          colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  DateFormat.jm().format(message.timestamp),
                  style: TextStyle(
                    fontSize: 10,
                    color: contentColor.withValues(alpha: 0.5),
                  ),
                ),
                if (!isUser && !message.isStreaming) ...[
                  const SizedBox(width: 6),
                  Semantics(
                    button: true,
                    label: 'Copy message to clipboard',
                    child: GestureDetector(
                      onTap: () {
                        Clipboard.setData(ClipboardData(text: message.content));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Copied'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                      },
                      child: Icon(
                        Icons.copy_outlined,
                        size: 12,
                        color: contentColor.withValues(alpha: 0.35),
                      ),
                    ),
                  ),
                ],
              ],
            ),
            if (!isUser && message.sources.isNotEmpty) ...[
              const SizedBox(height: 6),
              Wrap(
                spacing: 4,
                runSpacing: 4,
                children: message.sources.map((s) {
                  final source = s['source'] ?? '';
                  final path = source
                      .replaceAll(RegExp(r'\.html$'), '')
                      .replaceAll(RegExp(r'/index$'), '');
                  final url = (path.isNotEmpty && _sourceBaseUrl.isNotEmpty)
                      ? '$_sourceBaseUrl/$path'
                      : null;
                  return _SourceChip(
                    title: s['title'] ?? source,
                    url: url,
                    color: contentColor,
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
      ),
    );

    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.0, end: 1.0),
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
      builder: (context, value, child) => Opacity(
        opacity: value,
        child: Transform.translate(
          offset: Offset(0, (1 - value) * 12),
          child: child,
        ),
      ),
      child: bubble,
    );
  }
}

class _SourceChip extends StatelessWidget {
  final String title;
  final String? url;
  final Color color;

  const _SourceChip({required this.title, required this.color, this.url});

  @override
  Widget build(BuildContext context) {
    final chip = Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.25)),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            url != null ? Icons.open_in_new : Icons.article_outlined,
            size: 11,
            color: color.withValues(alpha: 0.5),
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              title,
              style: TextStyle(
                fontSize: 11,
                color: color.withValues(alpha: 0.6),
                decoration: url != null ? TextDecoration.underline : null,
                decorationColor: color.withValues(alpha: 0.4),
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );

    if (url == null) {
      return Semantics(
        label: 'Source: $title',
        child: chip,
      );
    }

    return Semantics(
      button: true,
      link: true,
      label: 'Source: $title. Tap to open.',
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        child: GestureDetector(
          onTap: () => openUrl(url!),
          behavior: HitTestBehavior.opaque,
          child: chip,
        ),
      ),
    );
  }
}
