FROM python:3.14-slim

WORKDIR /app

# Копируем и устанавливаем зависимости из pyproject.toml
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Копируем наш код
COPY src ./src

# Запускаем API на 8000 порту
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]