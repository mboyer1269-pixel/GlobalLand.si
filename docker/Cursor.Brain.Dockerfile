# Use scripts/build_cursor_image.sh to verify and tag the existing local image.
ARG EXISTING_BRAIN_IMAGE=globalland-brain:cursor-base-required
FROM ${EXISTING_BRAIN_IMAGE}
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# Cursor documents this installer; record it and the installed version in the image.
# The resulting image ID pins the resolved CLI; never update the host installation.
RUN install -d -m 755 /opt/cursor-cli \
 && curl --proto '=https' --tlsv1.2 -fsSL https://cursor.com/install -o /tmp/cursor-install.sh \
 && sha256sum /tmp/cursor-install.sh > /opt/cursor-cli/INSTALLER_SHA256 \
 && HOME=/opt/cursor-cli bash /tmp/cursor-install.sh \
 && ln -s /opt/cursor-cli/.local/bin/agent /usr/local/bin/cursor-agent \
 && chmod -R a+rX /opt/cursor-cli \
 && HOME=/tmp cursor-agent --version > /opt/cursor-cli/VERSION \
 && rm /tmp/cursor-install.sh
ENV HOME=/home/node
USER node
WORKDIR /tmp
