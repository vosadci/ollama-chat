# Stage 1: Build the Flutter web app
# Flutter SDK in this image is root-owned; FLUTTER_ALLOW_SUPERUSER suppresses the
# root warning. This is safe — only static build output reaches the runtime stage.
#
# Pin to an exact version for reproducible builds. To update:
#   1. Check latest stable: https://docs.flutter.dev/release/release-notes
#   2. Update the tag below and the flutter-version in .github/workflows/ci.yml
FROM ghcr.io/cirruslabs/flutter:3.41.6 AS builder

ENV FLUTTER_ALLOW_SUPERUSER=1

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

COPY . .
RUN flutter build web --release \
    --dart-define=BACKEND_URL=/api/v1

# Stage 2: Serve with nginx
FROM nginx:alpine

COPY --from=builder /app/build/web /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
