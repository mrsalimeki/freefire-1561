FROM python:3.12-slim

WORKDIR /app

COPY app.py .
COPY requirements.txt .

ENV PORT=7860
ENV DATA_DIR=/data

RUN mkdir -p /data

EXPOSE 7860

CMD ["python3", "app.py"]
