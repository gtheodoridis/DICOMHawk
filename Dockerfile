# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install build tools
RUN apt-get update && apt-get install -y build-essential gcc

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn WSGI server
RUN pip install gunicorn

# Expose the DICOM and Flask ports
EXPOSE 11112
EXPOSE 5000

# Define environment variable
ENV FLASK_APP dicomhawk.py

# Run the application using Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "dicomhawk:app"]
