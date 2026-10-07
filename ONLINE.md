# Online play

Online games go through a relay server (`server/relay`, Go): every player connects to it, gets a
virtual address in a room, and the relay forwards the game's UDP traffic between the players of
the room. To the game this looks like a LAN, so the LAN lobby, chat and games work over the internet
on every platform, and nobody has to open ports.

## Running the relay

    docker build --target relay -t generals-relay server
    docker run -d -p 7900:7900/udp -e RELAY_SECRET=<secret> generals-relay [-v]

`RELAY_SECRET` checks the players' tokens (`<player>.<expiry>.<HMAC-SHA256>`, see
`server/internal/token`), which the login service hands out. Without it every token is accepted,
for tests. `-v` logs binds and refused or dropped datagrams.

## Signing in with Steam

`server/auth` signs players in with their Steam account ("Sign in through Steam", OpenID) and
gives the game a token for the relay:

    docker build --target auth -t generals-auth server
    docker run -d -p 8080:8080 -e PUBLIC_URL=https://auth.example.org -e TOKEN_SECRET=<RELAY_SECRET> \
        [-e STEAM_API_KEY=<key>] generals-auth

- `PUBLIC_URL` must be the HTTPS address players reach the service at (behind a reverse proxy
  such as Caddy).
- Steam is the players' account, not proof that they bought the game: Zero Hour is also sold
  outside Steam (EA app, Origin, CDs), and on Steam it comes with EA Play or the Ultimate
  Collection. Players need their own copy of the game data to play; nothing of EA's is
  distributed.
- With `STEAM_API_KEY` (from https://steamcommunity.com/dev/apikey) the launcher shows Steam names
  and avatars. `REQUIRE_OWNERSHIP=1` additionally lets only accounts that own Zero Hour on Steam
  (app 2732960, `OWNERSHIP_APP_IDS` to change) sign in; Steam shows an account's games only when its
  profile's game details are public.
- Tokens last a week (`TOKEN_HOURS`).

With `GENERALS_AUTH=https://auth.example.org` the game opens the sign in page in the browser the
first time it goes online, waits for the token on a local port, and keeps it in `OnlineToken.txt`
in the user data folder until it expires. While it waits for the browser the game does not
respond; signing in from the menus comes later.

## Playing through it

    GENERALS_RELAY=relay.example.org[:7900] GENERALS_AUTH=https://auth.example.org GENERALS_RELAY_ROOM=<room> generalszh

(`GENERALS_RELAY_TOKEN=<token>` gives a token directly instead of signing in.)

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
CRCs. `go test ./...` in `server` tests the relay and the login service (against a fake Steam).
