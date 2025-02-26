# Pobranie lekkiej wersji Pythona
FROM python:3.10

# Ustawienie katalogu roboczego
WORKDIR /app

# Skopiowanie zależności
COPY requirements.txt .

# Instalacja zależności
RUN pip install --no-cache-dir -r requirements.txt

# Skopiowanie kodu aplikacji
COPY . .

# Uruchomienie serwera FastAPI
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
 