FROM python:3.11-slim

WORKDIR /app

# System deps for pdfplumber (image handling) are already covered by slim; add
# build tooling only if a wheel is unavailable.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite data lives here; mount a volume in production to persist it.
RUN mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
