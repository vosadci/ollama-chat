import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

typedef TokenCallback = void Function(String token);
typedef DoneCallback = void Function();
typedef ErrorCallback = void Function(String error, {bool isConnectionError});
typedef SourcesCallback = void Function(List<Map<String, String>> sources);

class ChatService {
  static const String _baseUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://localhost:8000/api/v1',
  );

  /// Optional factory for creating the HTTP client. Defaults to [http.Client.new].
  /// Override in tests to inject a mock or fake client.
  final http.Client Function() _clientFactory;

  ChatService({http.Client Function()? clientFactory})
      : _clientFactory = clientFactory ?? http.Client.new;

  http.Client? _activeClient;
  bool _cancelled = false;

  void cancel() {
    _cancelled = true;
    _activeClient?.close();
  }

  Future<void> sendMessages({
    required List<Map<String, String>> messages,
    required TokenCallback onToken,
    required DoneCallback onDone,
    required ErrorCallback onError,
    required SourcesCallback onSources,
  }) async {
    final uri = Uri.parse('$_baseUrl/chat');
    final request = http.Request('POST', uri)
      ..headers['Content-Type'] = 'application/json'
      ..headers['Accept'] = 'text/event-stream'
      ..body = jsonEncode({'messages': messages});

    _cancelled = false;
    _activeClient = _clientFactory();
    final client = _activeClient!;
    try {
      final response = await client
          .send(request)
          .timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        onError('Server error: ${response.statusCode}');
        return;
      }

      await for (final line in response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())) {
        if (!line.startsWith('data: ')) continue;

        final data = line.substring(6).trim();

        if (data == '[DONE]') {
          onDone();
          break;
        }

        try {
          final json = jsonDecode(data) as Map<String, dynamic>;
          if (json.containsKey('error')) {
            onError(json['error'] as String);
            break;
          }
          if (json.containsKey('token')) {
            onToken(json['token'] as String);
          }
          if (json.containsKey('sources')) {
            final raw = json['sources'] as List<dynamic>;
            onSources(raw.map((s) => Map<String, String>.from(s as Map)).toList());
          }
        } catch (_) {
          // Malformed SSE line — skip
        }
      }
    } on TimeoutException {
      onError('Request timed out', isConnectionError: true);
    } on SocketException {
      onError('Could not connect to server', isConnectionError: true);
    } catch (e) {
      if (_cancelled) {
        onDone();
      } else {
        onError('Network error: $e', isConnectionError: true);
      }
    } finally {
      _activeClient = null;
      client.close();
    }
  }
}
