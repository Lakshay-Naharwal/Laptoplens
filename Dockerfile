FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 7860 (Required by Hugging Face Spaces)
EXPOSE 7860

# Command to run the application using gunicorn on port 7860
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:7860"]
