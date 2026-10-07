# Online play

Online games go through a relay server (`server/relay`, Go): every player connects to it, gets a
virtual address in a room, and the relay forwards the game's UDP traffic between the players of
the room. To the game this looks like a LAN, so the LAN lobby, chat and games work over the internet
on every platform, and nobody has to open ports.

## Running the relay

    docker build -t generals-relay server/relay
    docker run -d -p 7900:7900/udp -e RELAY_SECRET=<secret> generals-relay [-v]

`RELAY_SECRET` checks the players' tokens (`<player>.<expiry>.<HMAC-SHA256>`, see
`server/relay/token.go`), which the login service will hand out. Without it every token is
accepted, for tests. `-v` logs binds and refused or dropped datagrams.

## Playing through it

    GENERALS_RELAY=relay.example.org[:7900] GENERALS_RELAY_ROOM=<room> GENERALS_RELAY_TOKEN=<token> generalszh

Then open Multiplayer, Network: everyone in the same room sees each other's games as on a LAN. A room
holds up to 8 players.

## How it works

- The game's sockets (`Core/GameEngine/Source/GameNetwork/udp.cpp`) send through
  `GameNetwork/Relay.cpp` when `GENERALS_RELAY` is set. Each datagram gets a 12 byte header with the
  virtual address and port it is for, or the broadcast address.
- The relay only forwards between sockets that joined the same room with a valid token. A socket can
  only bind to a session from the address that joined it, so the relay cannot be used to send traffic
  anywhere else.
- Sessions that are idle for two minutes end. A game whose session ended joins again at the same
  address, so a long loading screen or a relay restart does not break the game.

## Testing

`scripts/crossplay/online_match.sh` plays a game between the Linux build and the Windows x64 build
under Wine, on two networks that only the relay connects, and checks that both compute the same
CRCs. `go test` in `server/relay` tests the relay itself.
