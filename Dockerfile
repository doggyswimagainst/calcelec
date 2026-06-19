FROM python:3.12-slim

# Set up environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Create a non-root user with UID 1000 for Hugging Face Spaces security compliance
RUN useradd -m -u 1000 user

# Set up working directory inside the home folder
WORKDIR /home/user/app

# Install system build dependencies (e.g., GCC/headers for ReportLab if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies globally
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy all project files into the container
COPY . .

# Set ownership of the app directory explicitly to user 1000
RUN chown -R 1000:1000 /home/user/app

# Switch to the non-root user (UID 1000)
USER user

# Expose Hugging Face default port
EXPOSE 7860

# Command to run uvicorn on the correct port and host
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
