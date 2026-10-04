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

// Winsock on top of BSD sockets. WSAE* error codes map directly to errno values,
// so WSAGetLastError() simply returns errno.
#pragma once

#include <windows.h>

#include <arpa/inet.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR (-1)

typedef struct hostent HOSTENT;
typedef struct hostent* PHOSTENT;
typedef struct hostent* LPHOSTENT;
typedef struct sockaddr SOCKADDR;
typedef struct sockaddr* PSOCKADDR;
typedef struct sockaddr* LPSOCKADDR;
typedef struct sockaddr_in SOCKADDR_IN;
typedef struct sockaddr_in* PSOCKADDR_IN;
typedef struct sockaddr_in* LPSOCKADDR_IN;
typedef struct in_addr IN_ADDR;
typedef struct in_addr* PIN_ADDR;
typedef struct in_addr* LPIN_ADDR;
typedef struct timeval TIMEVAL;
typedef struct linger LINGER;

#define WSADESCRIPTION_LEN 256
#define WSASYS_STATUS_LEN 128
typedef struct WSAData {
	WORD wVersion;
	WORD wHighVersion;
	char szDescription[WSADESCRIPTION_LEN + 1];
	char szSystemStatus[WSASYS_STATUS_LEN + 1];
	unsigned short iMaxSockets;
	unsigned short iMaxUdpDg;
	char* lpVendorInfo;
} WSADATA, *LPWSADATA;

inline int WSAStartup(WORD version, LPWSADATA data)
{
	if (data)
	{
		memset(data, 0, sizeof(*data));
		data->wVersion = version;
		data->wHighVersion = version;
		data->iMaxSockets = 1024;
		data->iMaxUdpDg = 65467;
	}
	return 0;
}
inline int WSACleanup() { return 0; }
inline int WSAGetLastError() { return errno; }
inline void WSASetLastError(int err) { errno = err; }
inline int closesocket(SOCKET s) { return close(s); }
inline int ioctlsocket(SOCKET s, long cmd, u_long* arg)
{
	if (cmd == (long)FIONBIO)
	{
		int flags = fcntl(s, F_GETFL, 0);
		return fcntl(s, F_SETFL, *arg ? (flags | O_NONBLOCK) : (flags & ~O_NONBLOCK));
	}
	int value = (int)*arg;
	int rc = ioctl(s, (unsigned long)cmd, &value);
	*arg = (u_long)value;
	return rc;
}

#define WSABASEERR 10000
#define WSAEINTR EINTR
#define WSAEBADF EBADF
#define WSAEACCES EACCES
#define WSAEFAULT EFAULT
#define WSAEINVAL EINVAL
#define WSAEMFILE EMFILE
#define WSAEWOULDBLOCK EWOULDBLOCK
#define WSAEINPROGRESS EINPROGRESS
#define WSAEALREADY EALREADY
#define WSAENOTSOCK ENOTSOCK
#define WSAEDESTADDRREQ EDESTADDRREQ
#define WSAEMSGSIZE EMSGSIZE
#define WSAEPROTOTYPE EPROTOTYPE
#define WSAENOPROTOOPT ENOPROTOOPT
#define WSAEPROTONOSUPPORT EPROTONOSUPPORT
#define WSAESOCKTNOSUPPORT ESOCKTNOSUPPORT
#define WSAEOPNOTSUPP EOPNOTSUPP
#define WSAEPFNOSUPPORT EPFNOSUPPORT
#define WSAEAFNOSUPPORT EAFNOSUPPORT
#define WSAEADDRINUSE EADDRINUSE
#define WSAEADDRNOTAVAIL EADDRNOTAVAIL
#define WSAENETDOWN ENETDOWN
#define WSAENETUNREACH ENETUNREACH
#define WSAENETRESET ENETRESET
#define WSAECONNABORTED ECONNABORTED
#define WSAECONNRESET ECONNRESET
#define WSAENOBUFS ENOBUFS
#define WSAEISCONN EISCONN
#define WSAENOTCONN ENOTCONN
#define WSAESHUTDOWN ESHUTDOWN
#define WSAETOOMANYREFS ETOOMANYREFS
#define WSAETIMEDOUT ETIMEDOUT
#define WSAECONNREFUSED ECONNREFUSED
#define WSAELOOP ELOOP
#define WSAENAMETOOLONG ENAMETOOLONG
#define WSAEHOSTDOWN EHOSTDOWN
#define WSAEHOSTUNREACH EHOSTUNREACH
#define WSAENOTEMPTY ENOTEMPTY
#define WSAEPROCLIM EPROCLIM
#define WSAEUSERS EUSERS
#define WSAEDQUOT EDQUOT
#define WSAESTALE ESTALE
#define WSAEREMOTE EREMOTE
#define WSAEDISCON (WSABASEERR + 101)
#define WSASYSNOTREADY (WSABASEERR + 91)
#define WSAVERNOTSUPPORTED (WSABASEERR + 92)
#define WSANOTINITIALISED (WSABASEERR + 93)
#define WSAHOST_NOT_FOUND (WSABASEERR + 1001)
#define WSATRY_AGAIN (WSABASEERR + 1002)
#define WSANO_RECOVERY (WSABASEERR + 1003)
#define WSANO_DATA (WSABASEERR + 1004)

#define SD_RECEIVE SHUT_RD
#define SD_SEND SHUT_WR
#define SD_BOTH SHUT_RDWR

// Winsock takes int* for address lengths where POSIX uses socklen_t*.
inline int getsockname(SOCKET s, struct sockaddr* addr, int* len)
{
	socklen_t l = (socklen_t)*len;
	int rc = ::getsockname(s, addr, &l);
	*len = (int)l;
	return rc;
}
inline int getpeername(SOCKET s, struct sockaddr* addr, int* len)
{
	socklen_t l = (socklen_t)*len;
	int rc = ::getpeername(s, addr, &l);
	*len = (int)l;
	return rc;
}
inline int recvfrom(SOCKET s, char* buf, int bufLen, int flags, struct sockaddr* from, int* fromLen)
{
	socklen_t l = fromLen ? (socklen_t)*fromLen : 0;
	int rc = (int)::recvfrom(s, buf, (size_t)bufLen, flags, from, fromLen ? &l : nullptr);
	if (fromLen)
		*fromLen = (int)l;
	return rc;
}
inline int getsockopt(SOCKET s, int level, int name, char* value, int* len)
{
	socklen_t l = (socklen_t)*len;
	int rc = ::getsockopt(s, level, name, value, &l);
	*len = (int)l;
	return rc;
}
