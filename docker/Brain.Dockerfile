# Build using exact versions and an already verified immutable Node image.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG CODEX_VERSION
ARG CLAUDE_CODE_VERSION
RUN test -n "$CODEX_VERSION" && test -n "$CLAUDE_CODE_VERSION" \
 && npm install -g "@openai/codex@${CODEX_VERSION}" "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force
ENV HOME=/home/node
USER node
WORKDIR /tmp
