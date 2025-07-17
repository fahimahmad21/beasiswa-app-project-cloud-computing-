# Gunakan base image Python
FROM python:3.9-slim

# Install tools sistem yang dibutuhkan
RUN apt-get update && apt-get install -y build-essential

# Tentukan direktori kerja dalam container
WORKDIR /app

# Salin semua file dari folder lokal ke dalam container
COPY . /app

# Install semua dependensi dari requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Jalankan aplikasi utama
CMD ["python", "beasiswa.py"]
