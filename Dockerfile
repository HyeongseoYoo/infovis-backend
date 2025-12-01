# Dockerfile (통합용)

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# 1. 시스템 패키지 설치 (기존 worker Dockerfile에서 쓰던 거 + web에 필요했던 것들)
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

# python / pip alias (있으면 편함)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# 2. Python 의존성
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. cpplint, lizard, infer 설치
RUN pip install cpplint lizard
RUN VERSION=1.2.0 && \
    wget -q https://github.com/facebook/infer/releases/download/v${VERSION}/infer-linux-x86_64-v${VERSION}.tar.xz && \
    tar -xJf infer-linux-x86_64-v${VERSION}.tar.xz && \
    mv infer-linux-x86_64-v${VERSION} /opt/infer && \
    ln -sf /opt/infer/bin/infer /usr/local/bin/infer && \
    rm infer-linux-x86_64-v${VERSION}.tar.xz

# 4. 소스 복사
COPY . /code
RUN chmod +x /code/scripts/*.sh

# 5. 기본 CMD – 실제 실행은 fly.toml의 [processes]에서 override 가능
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn --bind :8000 --workers 2 backend.wsgi"]