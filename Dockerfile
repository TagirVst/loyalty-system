FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Создаем директории для логов
RUN mkdir -p logs/api logs/client_bot logs/barista_bot logs/admin_panel logs/postgres

RUN pip install black isort flake8 pre-commit

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
