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

// Online games through the relay server (server/relay): every UDP socket of the game talks to the
// relay instead of the network, under a virtual address in a room, so the LAN lobby and the game
// work over the internet without opening ports. GENERALS_RELAY=host[:port] turns it on, with
// GENERALS_RELAY_ROOM (default "lobby") and GENERALS_RELAY_TOKEN from the login service.

#pragma once

struct sockaddr_in;

namespace Relay
{
	// Whether games go through the relay.
	bool isEnabled();

	// The virtual address of this game in host byte order, joining the room on the first call;
	// 0 when the relay cannot be reached.
	UnsignedInt virtualIP();

	// For the UDP class: the socket fd now receives the virtual port.
	void bind(int fd, UnsignedShort vport);

	// Sends a datagram from vport to a virtual address (INADDR_BROADCAST for everyone in the room).
	Int send(int fd, UnsignedShort vport, const unsigned char *msg, UnsignedInt len, UnsignedInt ip, UnsignedShort port);

	// Receives the next datagram from another player; returns its length and fills in its virtual
	// address, 0 when nothing is waiting, -1 on errors.
	Int receive(int fd, UnsignedShort vport, unsigned char *msg, UnsignedInt len, sockaddr_in *from);
}
