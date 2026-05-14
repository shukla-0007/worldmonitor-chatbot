FROM python:3.11-slim

# HuggingFace Spaces requires a non-root user with UID 1000
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/st \
    TOKENIZERS_PARALLELISM=false

WORKDIR $HOME/app

# Install dependencies first (layer cache)
COPY --chown=user scripts/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the full project
COPY --chown=user . .

# HuggingFace Spaces default port is 7860
EXPOSE 7860

CMD ["uvicorn", "scripts.chat_api:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips=*"]
