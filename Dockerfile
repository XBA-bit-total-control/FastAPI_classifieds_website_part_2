FROM python:3.13-alpine

RUN apk add --no-cache gcc musl-dev linux-headers

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .
