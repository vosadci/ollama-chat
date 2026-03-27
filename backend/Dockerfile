# Pin the patch version for reproducible builds. Update deliberately on each release.
FROM python:3.11.12-slim

RUN useradd -m app
WORKDIR /home/app

# Install dependencies first so this layer is cached on code-only changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code — data/ and chroma_db/ are bind-mounted at runtime
COPY --chown=app config.py main.py dependencies.py ./
COPY --chown=app middleware/ middleware/
COPY --chown=app routers/ routers/
COPY --chown=app services/ services/

USER app

EXPOSE 8000

CMD ["python", "main.py"]
