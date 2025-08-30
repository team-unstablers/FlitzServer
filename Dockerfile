FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_VIRTUALENVS_IN_PROJECT=false

# Install system dependencies and Poetry in one layer
RUN apt-get update && apt-get install -y \
    tzdata \
    locales \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8 \
    && curl -sSL https://install.python-poetry.org | python3 - --version 2.1.3 \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=en_US.utf8

WORKDIR /app

# Copy only dependency files first
COPY pyproject.toml poetry.lock ./

# Install Python dependencies (production only)
RUN poetry install --no-interaction --no-ansi --no-dev

# Copy the rest of the application
COPY . .

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE flitz.settings_prod

# Git commit hash from build argument
ARG GIT_COMMIT=unknown
ENV FLITZ_GIT_COMMIT=${GIT_COMMIT}

# run server
CMD ["poetry", "run", "daphne", "-b", "0.0.0.0", "-p", "8000", "flitz.asgi:application"]