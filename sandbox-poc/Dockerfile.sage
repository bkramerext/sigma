# Official Sage 10.8 Linux amd64 image. Build only; execution never pulls.
FROM --platform=linux/amd64 sagemath/sagemath:10.8@sha256:fb96c7fb10d672f3be0d088399db3aeac52650416d1bb71f74f26429ea35778f
USER root
COPY runner.py /opt/sigma/runner.py
RUN mkdir -p /work && chmod 755 /home/sage /work /opt/sigma /opt/sigma/runner.py
ENV SIGMA_RESEARCH_RUNTIME=sagemath HOME=/tmp DOT_SAGE=/tmp/sigma-sage
USER 65532:65532
WORKDIR /work
ENTRYPOINT ["/home/sage/sage/sage", "-python", "-I", "/opt/sigma/runner.py"]
