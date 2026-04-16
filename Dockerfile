FROM python:3.12-alpine

WORKDIR /app

# Install build deps for cryptography (needed on alpine) + wget for healthcheck
RUN apk add --no-cache gcc musl-dev libffi-dev wget

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Don't copy .env or data/ into the image — mount them at runtime
RUN rm -f .env && rm -rf data/

# Expose HTTP healthcheck / metrics port
EXPOSE 8080

# Liveness probe — Docker restarts the container if /ping stops responding
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD wget -qO- http://localhost:8080/ping || exit 1

CMD ["python", "bot.py"]
