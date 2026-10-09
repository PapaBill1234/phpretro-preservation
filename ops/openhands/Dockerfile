# Tool build caches never enter the worker image.
FROM golang:1.26.9-bookworm AS tools
ENV GOTOOLCHAIN=local
RUN --mount=type=cache,target=/root/.cache/go-build --mount=type=cache,target=/go/pkg/mod \
    GOMEMLIMIT=1000MiB GOGC=50 GOFLAGS=-p=1 GOBIN=/opt/tools go install honnef.co/go/tools/cmd/staticcheck@v0.7.0 && \
    GOMEMLIMIT=1000MiB GOGC=50 GOFLAGS=-p=1 GOBIN=/opt/tools go install github.com/securego/gosec/v2/cmd/gosec@v2.28.0 && \
    GOMEMLIMIT=1000MiB GOGC=50 GOFLAGS=-p=1 GOBIN=/opt/tools go install golang.org/x/vuln/cmd/govulncheck@v1.7.0
COPY go.mod go.sum /opt/source/
RUN cd /opt/source && GOMODCACHE=/opt/gomod go mod download

FROM node:26.10.0-bookworm-slim
COPY --from=tools /usr/local/go /usr/local/go
RUN apt-get update && apt-get install -y --no-install-recommends bash git python3 ca-certificates curl unzip gcc libc6-dev coreutils procps && rm -rf /var/lib/apt/lists/*
ENV PATH=/opt/tools:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin \
    HOME=/home/worker GOTOOLCHAIN=local GOMODCACHE=/opt/gomod GOCACHE=/tmp/go-cache \
    GOPATH=/tmp/go GOPROXY=off GOSUMDB=off PHPRETRO_TOOLBIN=/opt/tools \
    PHPRETRO_VULNDB=file:///opt/vulndb PYTHONDONTWRITEBYTECODE=1
COPY --from=tools /opt/tools /opt/tools
COPY --from=tools /opt/gomod /opt/gomod
RUN mkdir -p /opt/frontend /opt/vulndb /home/worker /repo
COPY frontend/package.json frontend/package-lock.json /opt/frontend/
RUN cd /opt/frontend && npm ci --no-audit --no-fund
# Official bulk snapshot supports offline use with the same foundation gate.
RUN curl --fail --silent --show-error --location https://vuln.go.dev/vulndb.zip -o /tmp/vulndb.zip && \
    unzip -q /tmp/vulndb.zip -d /opt/vulndb && rm /tmp/vulndb.zip && date -u +%s > /opt/vulndb/fetched-at
RUN git config --system safe.directory /repo && chmod -R a+rX /opt && chmod 755 /home/worker
USER 65532:65532
WORKDIR /repo
CMD ["sleep", "infinity"]
