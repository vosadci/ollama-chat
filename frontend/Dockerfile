# Stage 1: Build the Flutter web app
# Flutter SDK in this image is root-owned; FLUTTER_ALLOW_SUPERUSER suppresses the
# root warning. This is safe — only static build output reaches the runtime stage.
FROM ghcr.io/cirruslabs/flutter:stable AS builder

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
