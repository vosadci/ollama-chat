/// Compile-time configuration read from --dart-define values.
///
/// Pass values at build / run time, e.g.:
///
///   flutter run \
///     --dart-define=SUGGESTION_CHIPS="What can you do?|Tell me more.|How do I start?"
///
/// The pipe character (|) is the delimiter — it is not valid in a
/// natural-language question, so no escaping is needed.
///
/// If the env var is absent the app falls back to [defaultSuggestions].
library;

/// Default suggestion chips shown on the empty state screen.
///
/// Override at build time with --dart-define=SUGGESTION_CHIPS="q1|q2|q3".
const List<String> defaultSuggestions = [
  'What types of accounts are available?',
  'Tell me about card options.',
  'What loan products are offered?',
  'How do I open an account?',
];

/// Suggestion chips resolved from the compile-time environment.
///
/// Returns [defaultSuggestions] when [SUGGESTION_CHIPS] is not set.
List<String> get suggestionChips {
  const raw = String.fromEnvironment('SUGGESTION_CHIPS');
  if (raw.isEmpty) return defaultSuggestions;
  return raw
      .split('|')
      .map((s) => s.trim())
      .where((s) => s.isNotEmpty)
      .toList();
}
