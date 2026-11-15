# Same SIGMA application image and OAuth implementation as the cloud backend.
# Built AFTER sigma-backend:<release> by deploy/release_image.py.
ARG SIGMA_RELEASE
FROM sigma-backend:${SIGMA_RELEASE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb scrot xdotool fonts-liberation ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /var/lib/sigma-auth /tmp/sigma-auth-browser-profile \
 && chown -R 10001:10001 /var/lib/sigma-auth /tmp/sigma-auth-browser-profile
COPY auth-browser-poc/entrypoint.sh /usr/local/bin/sigma-auth-browser
RUN chmod 0555 /usr/local/bin/sigma-auth-browser
ENV DISPLAY=:99 SIGMA_AUTH_HOME=/var/lib/sigma-auth
USER 10001:10001
EXPOSE 8765
ENTRYPOINT ["/usr/local/bin/sigma-auth-browser"]
