FROM python:3.14-slim

WORKDIR /app

# Чтобы установливались зависимости не в venv
ENV POETRY_VIRTUALENVS_CREATE=false

# Ставим poetry
RUN pip install "poetry"

# Копируем метаданные и устанавливаем зависимости
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --only main

# Копируем код после устанвоки зависимостей для кеширования
COPY src ./src

# Запускаем API
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]