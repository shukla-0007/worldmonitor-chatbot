FROM python:3.11-slim

RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    SENTENCE_TRANSFORMERS_HOME=/home/user/.cache/st \
    TOKENIZERS_PARALLELISM=false

WORKDIR $HOME/app

COPY --chown=user . .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 7860

CMD ["uvicorn", "scripts.chat_api:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips=*"]
