import 'dart:async';

import 'package:url_launcher/url_launcher.dart';

/// Opens [url] in the platform's default external browser.
///
/// Works on Android, iOS, macOS, Windows, and Linux via the url_launcher
/// package.  The web build uses its own implementation
/// (url_launcher_helper_web.dart) to ensure the link opens in a new tab.
void openUrl(String url) {
  unawaited(launchUrl(
    Uri.parse(url),
    mode: LaunchMode.externalApplication,
  ));
}
