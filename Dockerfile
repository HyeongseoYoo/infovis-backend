ARG PYTHON_VERSION=3.10-slim

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies.
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    build-essential \
    git \
    wget \
    cmake \
    curl \
    xz-utils \
    postgresql-client \
    libpq-dev \
    gcc \
    clang-14 \
    llvm-14 \
    libclang-14-dev \
    jq \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /code

WORKDIR /code

# clang/clang++ 심볼릭 링크 설정
RUN ln -s /usr/bin/clang-14 /usr/bin/clang && \
    ln -s /usr/bin/clang++-14 /usr/bin/clang++

COPY requirements.txt /tmp/requirements.txt
RUN set -ex && \
    pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /root/.cache/

RUN pip install cpplint lizard

RUN VERSION=1.2.0 && \
    wget -q https://github.com/facebook/infer/releases/download/v${VERSION}/infer-linux-x86_64-v${VERSION}.tar.xz && \
    tar -xJf infer-linux-x86_64-v${VERSION}.tar.xz && \
    mv infer-linux-x86_64-v${VERSION} /opt/infer && \
    ln -sf /opt/infer/bin/infer /usr/local/bin/infer && \
    rm infer-linux-x86_64-v${VERSION}.tar.xz


COPY . /code

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn --bind :8000 --workers 2 backend.wsgi"]