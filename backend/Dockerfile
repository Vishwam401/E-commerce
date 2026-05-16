# 1. Python ka base image uthao
FROM python:3.11-slim

# 2. Container ke andar ka working directory
WORKDIR /app

# 3. System dependencies install karo (Postgres ke liye zaroori hain)
RUN apt-get update && apt-get install -y libpq-dev gcc

# 4. Requirements copy aur install karo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Baaki saara code copy karo
COPY . .

# 6. Port 8000 pe FastAPI chalayenge
EXPOSE 8000

# 7. Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]