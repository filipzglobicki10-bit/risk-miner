FROM python:3.12.8-slim-bookworm
# OCR skanów (opcjonalnie) — tesseract z językiem polskim + poppler (pdftoppm, pdftotext)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol poppler-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-optional.txt .
RUN pip install --no-cache-dir -r requirements-optional.txt
COPY . .
RUN useradd -m riskminer && mkdir -p /app/data && chown -R riskminer /app/data && [ -f config.json ] || cp config.example.json config.json
USER riskminer
ENV RISKMINER_HOST=0.0.0.0 PORT=8080
EXPOSE 8080
CMD ["python", "app.py"]
