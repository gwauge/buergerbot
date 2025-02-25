FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN pip install playwright && \
    playwright install --with-deps

# Copy project files
COPY . /app

CMD ["python", "main.py"]
