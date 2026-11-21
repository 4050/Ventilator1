FROM python:3.12-alpine
WORKDIR /app
COPY index.html server.py ./
EXPOSE 8080
CMD ["python3", "-u", "server.py"]
