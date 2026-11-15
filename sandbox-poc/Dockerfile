FROM python:3.12.8-slim@sha256:2199a62885a12290dc9c5be3ca0681d367576ab7bf037da120e564723292a2f0
COPY requirements.txt /tmp/requirements.txt
COPY runner.py /opt/sigma/runner.py
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
RUN useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin researcher
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["python", "-I", "/opt/sigma/runner.py"]
