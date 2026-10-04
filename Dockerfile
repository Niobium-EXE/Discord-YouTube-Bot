
FROM python:3.12-slim

# Prevent Python from creating .pyc files
# and make logs appear immediately in Railway.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Everything inside the container lives here.
WORKDIR /app

# Install dependencies first.
# Keeping this separate allows Docker to cache this layer.
COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --upgrade pip \
    && pip install \
    --no-cache-dir \
    -r requirements.txt

# Copy the rest of the project.
COPY . .

# Create a non-root user for the bot.
RUN useradd \
    --create-home \
    --shell /bin/bash \
    botuser

RUN chown -R botuser:botuser /app

USER botuser

# Start the Discord bot.
CMD ["python", "main.py"]
