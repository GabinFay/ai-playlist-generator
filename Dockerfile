FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai_playlist_generator.py .
COPY Util /app/Util

EXPOSE 8080

CMD ["streamlit", "run", "ai_playlist_generator.py", "--server.port=8080", "--server.address=0.0.0.0"]