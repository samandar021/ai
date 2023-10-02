FROM python:3.11-slim

WORKDIR /code

ENV PYTHONUNBUFFERED 1  
ENV PYTHONDONTWRITEBYTECODE 1
ENV DOCKER_BUILDKIT=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    sqlite3 \
    libsqlite3-dev \
    build-essential \
    binutils

COPY ./requirements.txt /code/
RUN pip install pip --upgrade && \
    pip install --no-cache-dir -r /code/requirements.txt


COPY . /code/

CMD bash -c "python manage.py collectstatic --noinput && \
            python manage.py migrate && \
            python manage.py runserver 0.0.0.0:8000"