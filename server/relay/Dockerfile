# The UDP relay for online games. Build from this directory:
#   docker build -t generals-relay server/relay && docker run -p 7900:7900/udp -e RELAY_SECRET=... generals-relay
FROM golang:1.25-alpine AS build
WORKDIR /src
COPY . .
RUN go test ./... && CGO_ENABLED=0 go build -o /relay .

FROM scratch
COPY --from=build /relay /relay
EXPOSE 7900/udp
ENTRYPOINT ["/relay"]
