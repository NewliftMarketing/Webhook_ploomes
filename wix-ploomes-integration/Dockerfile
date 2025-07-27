# Use a imagem oficial do Python como base
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia os arquivos de requisitos primeiro (para aproveitar o cache do Docker)
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código da aplicação
COPY . .

# Expõe a porta que a aplicação vai usar
EXPOSE 8080

# Define variáveis de ambiente para produção
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Comando para executar a aplicação com Gunicorn
CMD ["gunicorn", "--config", "gunicorn.conf.py", "run_server:app"]

