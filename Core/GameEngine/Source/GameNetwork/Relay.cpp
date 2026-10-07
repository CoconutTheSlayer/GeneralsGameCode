/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2026 TheSuperHackers
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include "PreRTS.h"	// This must go first in EVERY cpp file in the GameEngine

#include "GameNetwork/Relay.h"
#include "GameNetwork/udp.h"
#include "Common/GlobalData.h"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <ctime>
#if defined(_WIN32)
#include <shellapi.h>
extern "C" BOOLEAN NTAPI SystemFunction036(PVOID buffer, ULONG length); // RtlGenRandom, in advapi32
#else
#include <spawn.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <sys/random.h>
#endif
extern char **environ;
#endif

// The protocol is described in server/relay/main.go.
namespace
{
enum
{
	TYPE_HELLO = 1,
	TYPE_WELCOME = 2,
	TYPE_BIND = 3,
	TYPE_BOUND = 4,
	TYPE_SEND = 5,
	TYPE_RECV = 6,
	TYPE_ERROR = 7,

	ERROR_UNKNOWN_SESSION = 3,

	HEADER_LEN = 4,
	SESSION_LEN = 8,
	ROOM_LEN = 32,
	TOKEN_LEN = 128,
	DEFAULT_PORT = 7900,
	MAX_DATAGRAM = 2048,
};

const unsigned KEEPALIVE_MS = 5000;

struct State
{
	bool configured = false;
	bool enabled = false;
	bool joinAttempted = false;
	sockaddr_in server {};
	unsigned char session[SESSION_LEN] {};
	std::string room;
	std::string token;
	UnsignedInt vip = 0;
	std::map<int, unsigned> lastBind; // fd -> time of the last BIND
};

State &state()
{
	static State s;
	return s;
}

// The session id is what lets a socket join the session, so it comes from the system's secure source.
void randomBytes(unsigned char *out, size_t length)
{
#if defined(_WIN32)
	SystemFunction036(out, (ULONG)length);
#else
	if (getentropy(out, length) != 0)
	{
		for (size_t i = 0; i < length; ++i)
			out[i] = (unsigned char)rand();
	}
#endif
}

unsigned nowMs()
{
	using namespace std::chrono;
	return (unsigned)duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

void putHeader(unsigned char *p, unsigned char type)
{
	p[0] = 'G';
	p[1] = 'Z';
	p[2] = 1;
	p[3] = type;
}

void putU16(unsigned char *p, UnsignedShort v)
{
	p[0] = (unsigned char)(v >> 8);
	p[1] = (unsigned char)v;
}

void putU32(unsigned char *p, UnsignedInt v)
{
	p[0] = (unsigned char)(v >> 24);
	p[1] = (unsigned char)(v >> 16);
	p[2] = (unsigned char)(v >> 8);
	p[3] = (unsigned char)v;
}

UnsignedInt getU32(const unsigned char *p)
{
	return ((UnsignedInt)p[0] << 24) | ((UnsignedInt)p[1] << 16) | ((UnsignedInt)p[2] << 8) | p[3];
}

//-------------------------------------------------------------------------------------------------
// Signing in (server/auth): the browser signs in with Steam and is sent back to a port of this
// game with a token, which is kept in the user data folder until it expires.
//-------------------------------------------------------------------------------------------------
std::string tokenFile()
{
	return std::string(TheGlobalData ? TheGlobalData->getPath_UserData().str() : "") + "OnlineToken.txt";
}

// Tokens are player.expiry.signature; one that expires within the hour is not worth using.
bool tokenFresh(const std::string &token)
{
	const size_t a = token.find('.');
	const size_t b = a == std::string::npos ? a : token.find('.', a + 1);
	if (b == std::string::npos)
		return false;
	const long long expiry = atoll(token.substr(a + 1, b - a - 1).c_str());
	return expiry > (long long)time(nullptr) + 3600;
}

std::string loadToken()
{
	std::string token;
	if (FILE *f = fopen(tokenFile().c_str(), "r"))
	{
		char line[512] = {};
		if (fgets(line, sizeof(line), f))
			token = line;
		fclose(f);
	}
	while (!token.empty() && (token.back() == '\n' || token.back() == '\r'))
		token.pop_back();
	return tokenFresh(token) ? token : std::string();
}

void saveToken(const std::string &token)
{
	if (FILE *f = fopen(tokenFile().c_str(), "w"))
	{
		fputs(token.c_str(), f);
		fclose(f);
	}
}

void openBrowser(const std::string &url)
{
#if defined(_WIN32)
	ShellExecuteA(nullptr, "open", url.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
#else
#if defined(__APPLE__)
	const char *opener = "open";
#else
	const char *opener = "xdg-open";
#endif
	// GENERALS_BROWSER replaces the browser, for tests (for example "curl -sL").
	if (const char *browser = getenv("GENERALS_BROWSER"))
	{
		const std::string command = std::string(browser) + " '" + url + "' >/dev/null 2>&1 &";
		char *argv[] = { (char *)"sh", (char *)"-c", (char *)command.c_str(), nullptr };
		pid_t pid;
		posix_spawnp(&pid, "sh", nullptr, nullptr, argv, environ);
		return;
	}
	char *argv[] = { (char *)opener, (char *)url.c_str(), nullptr };
	pid_t pid;
	posix_spawnp(&pid, opener, nullptr, nullptr, argv, environ);
#endif
}

std::string urlDecode(const std::string &in)
{
	std::string out;
	for (size_t i = 0; i < in.size(); ++i)
	{
		if (in[i] == '%' && i + 2 < in.size())
		{
			out += (char)strtol(in.substr(i + 1, 2).c_str(), nullptr, 16);
			i += 2;
		}
		else
			out += in[i] == '+' ? ' ' : in[i];
	}
	return out;
}

// Opens the sign in page and waits up to three minutes for the browser to bring the token back.
std::string signIn(const std::string &authURL)
{
	int listener = (int)socket(AF_INET, SOCK_STREAM, 0);
	if (listener < 0)
		return std::string();
	sockaddr_in local {};
	local.sin_family = AF_INET;
	local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	int localLen = sizeof(local);
	if (::bind(listener, (sockaddr *)&local, sizeof(local)) != 0 || listen(listener, 4) != 0
		|| getsockname(listener, (sockaddr *)&local, &localLen) != 0)
	{
		closesocket(listener);
		return std::string();
	}
	char port[16];
	snprintf(port, sizeof(port), "%u", (unsigned)ntohs(local.sin_port));
	fprintf(stderr, "Relay: signing in with Steam in the browser\n");
	openBrowser(authURL + "/login?port=" + port);

	std::string token;
	const unsigned deadline = nowMs() + 180000;
	while (token.empty() && (int)(deadline - nowMs()) > 0)
	{
		fd_set read;
		FD_ZERO(&read);
		FD_SET(listener, &read);
		timeval timeout { 1, 0 };
		if (select(listener + 1, &read, nullptr, nullptr, &timeout) <= 0)
			continue;
		int client = (int)accept(listener, nullptr, nullptr);
		if (client < 0)
			continue;
		char request[2048] = {};
		const int n = recv(client, request, sizeof(request) - 1, 0);
		// GET /token?t=<token> HTTP/1.1
		std::string line(request, n > 0 ? n : 0);
		const size_t start = line.find("GET /token?t=");
		const size_t end = start == std::string::npos ? start : line.find_first_of(" &", start + 13);
		const char *answer;
		if (end != std::string::npos)
		{
			token = urlDecode(line.substr(start + 13, end - start - 13));
			answer = "Signed in. You can go back to the game.";
		}
		else
			answer = "This page is for the game's sign in.";
		char response[512];
		snprintf(response, sizeof(response),
			"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
			"<!doctype html><title>Zero Hour</title><p style=\"font:18px sans-serif;margin:4em\">%s</p>", answer);
		send(client, response, (int)strlen(response), 0);
		closesocket(client);
	}
	closesocket(listener);
	if (token.empty())
		fprintf(stderr, "Relay: the sign in did not finish\n");
	else
		saveToken(token);
	return token;
}

void configure()
{
	State &s = state();
	if (s.configured)
		return;
	s.configured = true;
	const char *relay = getenv("GENERALS_RELAY");
	if (relay == nullptr || *relay == 0)
		return;

	std::string host = relay;
	UnsignedShort port = DEFAULT_PORT;
	const size_t colon = host.rfind(':');
	if (colon != std::string::npos)
	{
		port = (UnsignedShort)atoi(host.c_str() + colon + 1);
		host.resize(colon);
	}
	hostent *he = gethostbyname(host.c_str());
	if (he == nullptr || he->h_length != 4)
	{
		fprintf(stderr, "Relay: cannot resolve %s\n", host.c_str());
		return;
	}
	s.server.sin_family = AF_INET;
	s.server.sin_port = htons(port);
	memcpy(&s.server.sin_addr, he->h_addr_list[0], 4);

	const char *room = getenv("GENERALS_RELAY_ROOM");
	s.room = room && *room ? room : "lobby";
	// A token given directly, else the one kept from the last sign in, else sign in when there is
	// a login service (GENERALS_AUTH); without one the relay must be running in test mode.
	const char *token = getenv("GENERALS_RELAY_TOKEN");
	const char *auth = getenv("GENERALS_AUTH");
	if (token && *token)
		s.token = token;
	else if (auth && *auth)
	{
		s.token = loadToken();
		if (s.token.empty())
			s.token = signIn(auth);
	}
	randomBytes(s.session, SESSION_LEN);
	s.enabled = true;
}

bool fromServer(const sockaddr_in &from)
{
	const State &s = state();
	return from.sin_addr.s_addr == s.server.sin_addr.s_addr && from.sin_port == s.server.sin_port;
}

void sendBind(int fd, UnsignedShort vport)
{
	State &s = state();
	unsigned char pkt[HEADER_LEN + SESSION_LEN + 2];
	putHeader(pkt, TYPE_BIND);
	memcpy(pkt + HEADER_LEN, s.session, SESSION_LEN);
	putU16(pkt + HEADER_LEN + SESSION_LEN, vport);
	sendto(fd, (const char *)pkt, sizeof(pkt), 0, (const sockaddr *)&s.server, sizeof(s.server));
	s.lastBind[fd] = nowMs();
}

void keepAlive(int fd, UnsignedShort vport)
{
	State &s = state();
	auto it = s.lastBind.find(fd);
	if (it == s.lastBind.end() || nowMs() - it->second >= KEEPALIVE_MS)
		sendBind(fd, vport);
}

// HELLO, asking for the current virtual address again when there is one.
void sendHello(int fd)
{
	State &s = state();
	unsigned char hello[HEADER_LEN + SESSION_LEN + ROOM_LEN + TOKEN_LEN + 4] {};
	putHeader(hello, TYPE_HELLO);
	memcpy(hello + HEADER_LEN, s.session, SESSION_LEN);
	strncpy((char *)hello + HEADER_LEN + SESSION_LEN, s.room.c_str(), ROOM_LEN);
	strncpy((char *)hello + HEADER_LEN + SESSION_LEN + ROOM_LEN, s.token.c_str(), TOKEN_LEN);
	putU32(hello + HEADER_LEN + SESSION_LEN + ROOM_LEN + TOKEN_LEN, s.vip);
	sendto(fd, (const char *)hello, sizeof(hello), 0, (const sockaddr *)&s.server, sizeof(s.server));
}

// Joins the room with a socket of its own; waits up to about three seconds for the answer.
void join()
{
	State &s = state();
	s.joinAttempted = true;
	int fd = (int)socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0)
		return;
	for (int attempt = 0; attempt < 6 && s.vip == 0; ++attempt)
	{
		sendHello(fd);
		fd_set read;
		FD_ZERO(&read);
		FD_SET(fd, &read);
		timeval timeout { 0, 500000 };
		if (select(fd + 1, &read, nullptr, nullptr, &timeout) <= 0)
			continue;
		unsigned char reply[MAX_DATAGRAM];
		sockaddr_in from {};
		int fromLen = sizeof(from);
		const int n = recvfrom(fd, (char *)reply, sizeof(reply), 0, (sockaddr *)&from, &fromLen);
		if (n < HEADER_LEN + 1 || !fromServer(from) || reply[0] != 'G' || reply[1] != 'Z')
			continue;
		if (reply[3] == TYPE_ERROR)
		{
			fprintf(stderr, "Relay: refused to join room %s (error %d)\n", s.room.c_str(), reply[4]);
			break;
		}
		if (reply[3] == TYPE_WELCOME && n >= HEADER_LEN + SESSION_LEN + 4 && memcmp(reply + HEADER_LEN, s.session, SESSION_LEN) == 0)
			s.vip = getU32(reply + HEADER_LEN + SESSION_LEN);
	}
	closesocket(fd);
	if (s.vip != 0)
		fprintf(stderr, "Relay: joined room %s as %u.%u.%u.%u\n", s.room.c_str(), s.vip >> 24, (s.vip >> 16) & 0xFF, (s.vip >> 8) & 0xFF, s.vip & 0xFF);
	else
		fprintf(stderr, "Relay: no answer from the relay\n");
}
} // namespace

bool Relay::isEnabled()
{
	configure();
	return state().enabled;
}

UnsignedInt Relay::virtualIP()
{
	if (!isEnabled())
		return 0;
	if (state().vip == 0 && !state().joinAttempted)
		join();
	return state().vip;
}

void Relay::bind(int fd, UnsignedShort vport)
{
	sendBind(fd, vport);
}

Int Relay::send(int fd, UnsignedShort vport, const unsigned char *msg, UnsignedInt len, UnsignedInt ip, UnsignedShort port)
{
	if (len + HEADER_LEN + 8 > MAX_DATAGRAM)
		return -1;
	keepAlive(fd, vport);
	unsigned char pkt[MAX_DATAGRAM];
	putHeader(pkt, TYPE_SEND);
	putU16(pkt + HEADER_LEN, vport);
	putU32(pkt + HEADER_LEN + 2, ip);
	putU16(pkt + HEADER_LEN + 6, port);
	memcpy(pkt + HEADER_LEN + 8, msg, len);
	const State &s = state();
	const int sent = sendto(fd, (const char *)pkt, (int)(len + HEADER_LEN + 8), 0, (const sockaddr *)&s.server, sizeof(s.server));
	return sent < 0 ? -1 : (Int)len;
}

Int Relay::receive(int fd, UnsignedShort vport, unsigned char *msg, UnsignedInt len, sockaddr_in *from)
{
	keepAlive(fd, vport);
	unsigned char pkt[MAX_DATAGRAM];
	for (;;)
	{
		sockaddr_in sender {};
		int senderLen = sizeof(sender);
		const int n = recvfrom(fd, (char *)pkt, sizeof(pkt), 0, (sockaddr *)&sender, &senderLen);
		if (n < 0)
			return WSAGetLastError() == WSAEWOULDBLOCK ? 0 : -1;
		if (n < HEADER_LEN + 1 || !fromServer(sender) || pkt[0] != 'G' || pkt[1] != 'Z')
			continue;
		// The relay forgot the session (it was idle too long, or the relay restarted): join again,
		// at the same address if it is still free, and bind this socket again.
		if (pkt[3] == TYPE_ERROR && pkt[4] == ERROR_UNKNOWN_SESSION)
		{
			sendHello(fd);
			sendBind(fd, vport);
			continue;
		}
		// Only datagrams from players; BOUND and the like are skipped.
		if (n < HEADER_LEN + 6 || pkt[3] != TYPE_RECV)
			continue;
		const UnsignedInt payload = (UnsignedInt)n - (HEADER_LEN + 6);
		if (payload > len)
			continue;
		memcpy(msg, pkt + HEADER_LEN + 6, payload);
		if (from)
		{
			memset(from, 0, sizeof(*from));
			from->sin_family = AF_INET;
			memcpy(&from->sin_addr, pkt + HEADER_LEN, 4); // already big endian
			memcpy(&from->sin_port, pkt + HEADER_LEN + 4, 2);
		}
		return (Int)payload;
	}
}
