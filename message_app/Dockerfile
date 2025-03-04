FROM python:3.13-slim

WORKDIR /message_app

COPY . /message_app

RUN pip install --no-cache-dir -r /message_app/requirements.txt

EXPOSE 3000
EXPOSE 6000

CMD ["python", "main.py"]