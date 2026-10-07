# The online services. Build from this directory:
#   docker build --target relay -t generals-relay server
#   docker build --target auth -t generals-auth server
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY . .
RUN go vet ./... && go test ./... && CGO_ENABLED=0 go build -o /out/ ./relay ./auth

FROM scratch AS relay
COPY --from=build /out/relay /relay
EXPOSE 7900/udp
ENTRYPOINT ["/relay"]

FROM alpine:3 AS auth
RUN apk add --no-cache ca-certificates
COPY --from=build /out/auth /auth
EXPOSE 8080
ENTRYPOINT ["/auth"]
