FROM python:3.11-slim
WORKDIR /app 
COPY . /app  
RUN pip install --trusted-host pypi.python.org -r requirements.txt 
EXPOSE 80 
CMD ["python", "main.py"]
