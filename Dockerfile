ARG STRIP_RUNTIME_IMAGE=python:3.12-slim
FROM ${STRIP_RUNTIME_IMAGE}
USER root
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8000 STRIP_DATA=/var/lib/stripdesk
WORKDIR /opt/stripdesk
COPY requirements.txt scripts/check_dependencies.py ./
RUN (python check_dependencies.py || python -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: -r requirements.txt) \
    && python check_dependencies.py && python -m pip check
COPY stripdesk ./stripdesk
COPY image_lab ./image_lab
COPY static ./static
COPY templates ./templates
RUN useradd -U -u 11577 inspector && install -d -o inspector -g inspector /var/lib/stripdesk
USER inspector
EXPOSE 8000
CMD ["python", "-B", "-m", "stripdesk"]
