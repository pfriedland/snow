# Step 1: Use an official Python runtime as a parent image
FROM python:3.9-slim

# Step 2: Set the working directory in the container
WORKDIR /app

# Step 3: Copy the current directory contents into the container at /app
COPY . /app

# Step 4: Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Expose the Flask port
EXPOSE 5000

# Step 6: Define environment variable for Flask
ENV FLASK_APP=app.py

# Step 7: Run the application when the container starts
CMD ["flask", "run", "--host=0.0.0.0"]
