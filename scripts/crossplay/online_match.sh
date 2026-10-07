#!/bin/bash
# Plays an online game through the relay server (server/relay) between the Linux build (host,
# Docker image generals-linux) and the Windows x64 build (joiner, Wine in Docker image
# generals-windows-test) with two AI players, then checks that both computed the same game state
# CRCs. The players are on separate networks that only the relay (Docker image generals-relay,
# docker build -t generals-relay server/relay) is on, so everything goes through it.
#
#   scripts/crossplay/online_match.sh [seconds, default 450]
#
# GENERALS_ZH_DIR is the Zero Hour folder (with the base game in ZH_Generals) and GENERALS_DATA_DIR
# the user data folder whose Options.ini both players start from. Logs and screenshots stay in the
# directory printed at the end.

set -u
DURATION="${1:-450}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GAME="${GENERALS_ZH_DIR:-$HOME/Games/GeneralsZH}"
DATA="${GENERALS_DATA_DIR:-$HOME/Documents/Command and Conquer Generals Zero Hour Data}"
OUT="$(mktemp -d)"

for side in linux win; do
	mkdir -p "$OUT/data_$side"
	[ -f "$DATA/Options.ini" ] && cp "$DATA/Options.ini" "$OUT/data_$side/"
done
cat > "$OUT/generals.reg" <<'EOF'
REGEDIT4

[HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Command and Conquer Generals Zero Hour]
"InstallPath"="Z:\\game\\"
"Language"="english"

[HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Generals]
"InstallPath"="Z:\\game\\ZH_Generals\\"
"Language"="english"
EOF

docker rm -f lan-linux lan-win lan-relay >/dev/null 2>&1
docker network create generals-net-a >/dev/null 2>&1
docker network create generals-net-b >/dev/null 2>&1
docker run -d --name lan-relay --network generals-net-a generals-relay -v >/dev/null
docker network connect generals-net-b lan-relay
RELAY_ENV="-e GENERALS_RELAY=lan-relay:7900 -e GENERALS_RELAY_ROOM=crossplay-test"
docker run -d --name lan-linux --network generals-net-a $RELAY_ENV -v "$ROOT":/src -v "$GAME":/game \
	-v "$OUT/data_linux":"/root/Documents/Command and Conquer Generals Zero Hour Data" -v "$OUT":/out \
	-e SDL_VIDEODRIVER=x11 -e SDL_AUDIODRIVER=dummy -e DISPLAY=:99 -e GENERALS_NO_MESSAGEBOX=1 -e GENERALS_ALWAYS_ACTIVE=1 \
	-e GENERALS_ZH_PATH=/game -e GENERALS_PATH=/game/ZH_Generals -e GENERALS_CRC_LOG=1 -e GENERALS_LAN_TEST=host:Linux \
	-w /game generals-linux sh -c "Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 & sleep 2;
		/src/build/linux/GeneralsMD/generalszh -noaudio -win -xres 1024 -yres 768 > /out/linux.log 2>&1" >/dev/null
docker run -d --name lan-win --platform linux/amd64 --network generals-net-b $RELAY_ENV -v "$ROOT/build/windows-x64/GeneralsMD":/bin-win \
	-v "$GAME":/game -v "$OUT/data_win":"/root/.wine/drive_c/users/root/Documents/Command and Conquer Generals Zero Hour Data" \
	-v "$OUT":/out -e DISPLAY=:99 -e WINEDLLOVERRIDES="d3d8,d3d9=n" -e GENERALS_CRC_LOG=1 -e GENERALS_LAN_TEST=join:Windows \
	-w /game generals-windows-test sh -c "wine regedit /out/generals.reg 2>/dev/null; wineserver -w;
		Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 & sleep 2;
		wine /bin-win/generalszh.exe -useCwd -noaudio -win -xres 1024 -yres 768 > /out/win.log 2>&1" >/dev/null

for t in $(seq 60 60 "$DURATION"); do
	sleep 60
	docker exec lan-linux import -window root "/out/linux_$t.png" 2>/dev/null
	docker exec lan-win import -window root "/out/win_$t.png" 2>/dev/null
	echo "${t}s: $(grep -c 'CRC_LOG frame' "$OUT/linux.log" 2>/dev/null) CRCs on Linux, $(grep -c 'CRC_LOG frame' "$OUT/win.log" 2>/dev/null) on Windows"
done
docker logs lan-relay > "$OUT/relay.log" 2>&1; tail -4 "$OUT/relay.log"
docker rm -f lan-linux lan-win lan-relay >/dev/null

grep 'Relay:' "$OUT/linux.log" "$OUT/win.log"
grep 'LAN_TEST chat' "$OUT/linux.log" "$OUT/win.log" | grep -v SYSTEM
grep 'CRC_LOG' "$OUT/linux.log" > "$OUT/linux_crc.txt"
grep 'CRC_LOG' "$OUT/win.log" | tr -d '\r' > "$OUT/win_crc.txt"
echo "Output: $OUT"
if [ ! -s "$OUT/linux_crc.txt" ]; then
	echo "The game did not start."
	exit 1
fi
if cmp -s "$OUT/linux_crc.txt" "$OUT/win_crc.txt"; then
	echo "Identical: $(grep -c frame "$OUT/linux_crc.txt") CRCs."
else
	echo "CRCs DIFFER:"
	diff "$OUT/linux_crc.txt" "$OUT/win_crc.txt" | head -4
	exit 1
fi
