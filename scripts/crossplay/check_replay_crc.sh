#!/bin/bash
# Plays a replay headless on every platform build that exists and checks that all of them compute
# the same game state CRCs, which crossplay needs.
#
#   scripts/crossplay/check_replay_crc.sh <replay name>.rep
#
# Builds used when present (build them first, see MACOS.md, LINUX.md and WINDOWS.md):
#   build/macos                 macOS, native
#   build/macos-x86_64          macOS x86-64, under Rosetta
#   build/linux                 Linux arm64, Docker image generals-linux
#   build/linux-x64             Linux x86-64, Docker image generals-linux-amd64
#   build/windows-x64           Windows x64, Wine in Docker image generals-windows-test
#
# GENERALS_ZH_DIR is the Zero Hour folder (with the base game in ZH_Generals) and GENERALS_DATA_DIR
# the user data folder holding Replays/.

set -u
REPLAY="${1:?usage: $0 <replay name>.rep}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GAME="${GENERALS_ZH_DIR:-$HOME/Games/GeneralsZH}"
DATA="${GENERALS_DATA_DIR:-$HOME/Documents/Command and Conquer Generals Zero Hour Data}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

if [ ! -f "$DATA/Replays/$REPLAY" ]; then
	echo "Replay not found: $DATA/Replays/$REPLAY" >&2
	exit 2
fi

run_native() # name, executable
{
	(cd "$GAME" && GENERALS_CRC_LOG=1 "$2" -useCwd -headless -replay "$REPLAY" 2>&1 | grep CRC_LOG > "$OUT/$1.txt")
}

run_linux() # name, image, build directory
{
	docker run --rm -v "$ROOT":/src -v "$GAME":/game \
		-v "$DATA":"/root/Documents/Command and Conquer Generals Zero Hour Data" \
		-e SDL_VIDEODRIVER=offscreen -e SDL_AUDIODRIVER=dummy -e GENERALS_CRC_LOG=1 \
		-e GENERALS_ZH_PATH=/game -e GENERALS_PATH=/game/ZH_Generals -w /game "$2" \
		/src/"$3"/GeneralsMD/generalszh -useCwd -headless -replay "$REPLAY" 2>&1 | grep CRC_LOG > "$OUT/$1.txt"
}

run_windows() # name, build directory
{
	cat > "$OUT/generals.reg" <<'EOF'
REGEDIT4

[HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Command and Conquer Generals Zero Hour]
"InstallPath"="Z:\\game\\"
"Language"="english"

[HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Generals]
"InstallPath"="Z:\\game\\ZH_Generals\\"
"Language"="english"
EOF
	docker run --rm --platform linux/amd64 -v "$ROOT/$2/GeneralsMD":/bin-win -v "$OUT":/out -v "$GAME":/game \
		-v "$DATA":"/root/.wine/drive_c/users/root/Documents/Command and Conquer Generals Zero Hour Data" \
		-e GENERALS_CRC_LOG=1 -w /game generals-windows-test sh -c \
		"wine regedit /out/generals.reg 2>/dev/null; wineserver -w;
		 xvfb-run -a wine /bin-win/generalszh.exe -useCwd -headless -replay '$REPLAY' 2>&1 >/dev/null | grep CRC_LOG | tr -d '\r'" \
		> "$OUT/$1.txt"
}

has_image() { docker image inspect "$1" >/dev/null 2>&1; }

PLATFORMS=()
if [ "$(uname)" = Darwin ]; then
	[ -x "$ROOT/build/macos/GeneralsMD/generalszh" ] && run_native macos-arm64 "$ROOT/build/macos/GeneralsMD/generalszh" & PLATFORMS+=(macos-arm64)
	[ -x "$ROOT/build/macos-x86_64/GeneralsMD/generalszh" ] && run_native macos-x86_64 "$ROOT/build/macos-x86_64/GeneralsMD/generalszh" & PLATFORMS+=(macos-x86_64)
fi
if command -v docker >/dev/null; then
	[ -x "$ROOT/build/linux/GeneralsMD/generalszh" ] && has_image generals-linux && run_linux linux-arm64 generals-linux build/linux & PLATFORMS+=(linux-arm64)
	[ -x "$ROOT/build/linux-x64/GeneralsMD/generalszh" ] && has_image generals-linux-amd64 && run_linux linux-x86_64 generals-linux-amd64 build/linux-x64 & PLATFORMS+=(linux-x86_64)
	[ -f "$ROOT/build/windows-x64/GeneralsMD/generalszh.exe" ] && has_image generals-windows-test && run_windows windows-x64 build/windows-x64 & PLATFORMS+=(windows-x64)
fi
wait

REFERENCE=""
STATUS=0
for p in "${PLATFORMS[@]}"; do
	f="$OUT/$p.txt"
	if [ ! -s "$f" ]; then
		echo "$p: skipped (no build or no output)"
		continue
	fi
	if [ -z "$REFERENCE" ]; then
		REFERENCE="$p"
		echo "$p: $(wc -l < "$f" | tr -d ' ') CRCs (reference)"
	elif cmp -s "$OUT/$REFERENCE.txt" "$f"; then
		echo "$p: identical"
	else
		echo "$p: DIFFERS from $REFERENCE, first difference:"
		diff "$OUT/$REFERENCE.txt" "$f" | head -4
		STATUS=1
	fi
done
[ -n "$REFERENCE" ] || { echo "No platform produced output" >&2; exit 2; }
exit $STATUS
