FROM python:3.10-slim

WORKDIR /app

# Install flask
RUN pip install flask

COPY server.py .

# Run on port 5000
EXPOSE 5000

CMD ["python", "server.py"]