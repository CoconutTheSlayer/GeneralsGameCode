// Command relay forwards the game's UDP traffic between players in the same room, so that online
// games work like LAN games without anyone opening ports. Each player gets a virtual address in
// 10.77.0.0/16; the game wraps every datagram in a small header naming the virtual address and
// port it is for (or the broadcast address), and the relay delivers it to the matching players.
//
// Protocol (all integers big endian), every packet starts with "GZ", version 1 and a type:
//
//	HELLO   c->s  session[8] room[32] token[128] [vip[4]]  join a room, preferably at vip (when rejoining)
//	WELCOME s->c  session[8] vip[4]                  the virtual address of the session
//	BIND    c->s  session[8] vport[2]                this socket receives the virtual port (keepalive too)
//	BOUND   s->c  vport[2]
//	SEND    c->s  srcport[2] dstvip[4] dstport[2] payload
//	RECV    s->c  srcvip[4] srcport[2] payload
//	ERROR   s->c  code[1]                            1 bad token, 2 room full, 3 unknown session
//
// Tokens are checked with RELAY_SECRET (see internal/token); without it every token is accepted, for
// local tests.
package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"flag"
	"log"
	"net"
	"net/http"
	"net/netip"
	"os"
	"sync"
	"time"

	"generalsgamecode/server/internal/token"
)

const (
	typeHello   = 1
	typeWelcome = 2
	typeBind    = 3
	typeBound   = 4
	typeSend    = 5
	typeRecv    = 6
	typeError   = 7

	errBadToken       = 1
	errRoomFull       = 2
	errUnknownSession = 3

	headerLen      = 4
	maxPlayers     = 8
	sessionTimeout = 2 * time.Minute
	maxDatagram    = 2048
)

var virtualNet = [2]byte{10, 77}

type endpoint struct {
	addr     netip.AddrPort
	lastSeen time.Time
}

type session struct {
	id        [8]byte
	ip        netip.Addr // sockets may only bind from the address that joined
	room      *room
	vip       [4]byte
	player    string // from the token, for logs
	endpoints map[uint16]*endpoint
	lastSeen  time.Time
}

type room struct {
	name     string
	sessions map[[8]byte]*session
}

type binding struct {
	session *session
	vport   uint16
}

type relay struct {
	verbose  bool
	mu       sync.Mutex
	conn     *net.UDPConn
	secret   []byte
	rooms    map[string]*room
	sessions map[[8]byte]*session
	bindings map[netip.AddrPort]binding
}

func header(t byte) []byte { return []byte{'G', 'Z', 1, t} }

func (r *relay) reply(to netip.AddrPort, t byte, body ...[]byte) {
	pkt := header(t)
	for _, b := range body {
		pkt = append(pkt, b...)
	}
	r.conn.WriteToUDPAddrPort(pkt, to)
}

func cString(b []byte) string {
	if i := bytes.IndexByte(b, 0); i >= 0 {
		b = b[:i]
	}
	return string(b)
}

func (r *relay) handleHello(from netip.AddrPort, body []byte) {
	if len(body) < 8+32+128 {
		return
	}
	var id [8]byte
	copy(id[:], body[:8])
	roomName := cString(body[8:40])
	player, ok := token.Check(r.secret, cString(body[40:168]), time.Now())
	if !ok || roomName == "" {
		r.reply(from, typeError, []byte{errBadToken})
		return
	}
	if s := r.sessions[id]; s != nil {
		if s.ip != from.Addr() {
			r.reply(from, typeError, []byte{errUnknownSession})
			return
		}
		// A repeated HELLO (lost WELCOME) gets the same address.
		s.lastSeen = time.Now()
		r.reply(from, typeWelcome, id[:], s.vip[:])
		return
	}
	rm := r.rooms[roomName]
	if rm == nil {
		rm = &room{name: roomName, sessions: map[[8]byte]*session{}}
		r.rooms[roomName] = rm
	}
	if len(rm.sessions) >= maxPlayers {
		r.reply(from, typeError, []byte{errRoomFull})
		return
	}
	// The address asked for when rejoining, if it is free, else the lowest free address in the room.
	free := func(vip [4]byte) bool {
		for _, other := range rm.sessions {
			if other.vip == vip {
				return false
			}
		}
		return true
	}
	var vip [4]byte
	if len(body) >= 8+32+128+4 {
		copy(vip[:], body[168:172])
	}
	if !(vip[0] == virtualNet[0] && vip[1] == virtualNet[1] && vip[2] == 0 && vip[3] != 0 && vip[3] != 255 && free(vip)) {
		for n := 1; n < 255; n++ {
			vip = [4]byte{virtualNet[0], virtualNet[1], 0, byte(n)}
			if free(vip) {
				break
			}
		}
	}
	s := &session{id: id, ip: from.Addr(), room: rm, vip: vip, player: player, endpoints: map[uint16]*endpoint{}, lastSeen: time.Now()}
	rm.sessions[id] = s
	r.sessions[id] = s
	log.Printf("%s joined room %q as %d.%d.%d.%d from %s", player, roomName, vip[0], vip[1], vip[2], vip[3], from)
	r.reply(from, typeWelcome, id[:], vip[:])
}

func (r *relay) handleBind(from netip.AddrPort, body []byte) {
	if len(body) < 10 {
		return
	}
	var id [8]byte
	copy(id[:], body[:8])
	s := r.sessions[id]
	if s == nil || s.ip != from.Addr() {
		if r.verbose {
			log.Printf("refused bind from %s", from)
		}
		r.reply(from, typeError, []byte{errUnknownSession})
		return
	}
	vport := binary.BigEndian.Uint16(body[8:10])
	now := time.Now()
	if ep := s.endpoints[vport]; ep != nil && ep.addr != from {
		delete(r.bindings, ep.addr)
	}
	s.endpoints[vport] = &endpoint{addr: from, lastSeen: now}
	s.lastSeen = now
	if r.verbose && r.bindings[from].session == nil {
		log.Printf("%s bound port %d to %s", s.player, vport, from)
	}
	r.bindings[from] = binding{session: s, vport: vport}
	r.reply(from, typeBound, body[8:10])
}

func isBroadcast(vip [4]byte) bool {
	return vip == [4]byte{255, 255, 255, 255} || (vip[0] == virtualNet[0] && vip[1] == virtualNet[1] && vip[2] == 255 && vip[3] == 255)
}

func (r *relay) handleSend(from netip.AddrPort, body []byte) {
	if len(body) < 8 {
		return
	}
	b, ok := r.bindings[from]
	if !ok {
		if r.verbose {
			log.Printf("dropped datagram from unbound %s", from)
		}
		return
	}
	now := time.Now()
	b.session.lastSeen = now
	if ep := b.session.endpoints[b.vport]; ep != nil {
		ep.lastSeen = now
	}
	srcPort := body[0:2]
	var dst [4]byte
	copy(dst[:], body[2:6])
	dstPort := binary.BigEndian.Uint16(body[6:8])
	payload := body[8:]

	pkt := header(typeRecv)
	pkt = append(pkt, b.session.vip[:]...)
	pkt = append(pkt, srcPort...)
	pkt = append(pkt, payload...)
	for _, s := range b.session.room.sessions {
		if s == b.session || !(isBroadcast(dst) || s.vip == dst) {
			continue
		}
		if ep := s.endpoints[dstPort]; ep != nil {
			r.conn.WriteToUDPAddrPort(pkt, ep.addr)
		}
	}
}

func (r *relay) expire() {
	r.mu.Lock()
	defer r.mu.Unlock()
	now := time.Now()
	for id, s := range r.sessions {
		if now.Sub(s.lastSeen) < sessionTimeout {
			continue
		}
		for _, ep := range s.endpoints {
			delete(r.bindings, ep.addr)
		}
		delete(s.room.sessions, id)
		if len(s.room.sessions) == 0 {
			delete(r.rooms, s.room.name)
		}
		delete(r.sessions, id)
		log.Printf("%s left room %q", s.player, s.room.name)
	}
}

func (r *relay) serve() {
	buf := make([]byte, maxDatagram)
	for {
		n, from, err := r.conn.ReadFromUDPAddrPort(buf)
		if errors.Is(err, net.ErrClosed) {
			return
		}
		if err != nil {
			log.Printf("read: %v", err)
			continue
		}
		if n < headerLen || buf[0] != 'G' || buf[1] != 'Z' || buf[2] != 1 {
			continue
		}
		body := buf[headerLen:n]
		r.mu.Lock()
		switch buf[3] {
		case typeHello:
			r.handleHello(from, body)
		case typeBind:
			r.handleBind(from, body)
		case typeSend:
			r.handleSend(from, body)
		}
		r.mu.Unlock()
	}
}

func main() {
	listen := flag.String("listen", ":7900", "UDP address to listen on")
	verbose := flag.Bool("v", false, "log binds and dropped datagrams")
	httpListen := flag.String("http", ":7901", "HTTP address for the room list (GET /rooms), empty for none")
	flag.Parse()
	addr, err := net.ResolveUDPAddr("udp", *listen)
	if err != nil {
		log.Fatal(err)
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		log.Fatal(err)
	}
	r := &relay{
		verbose:  *verbose,
		conn:     conn,
		secret:   []byte(os.Getenv("RELAY_SECRET")),
		rooms:    map[string]*room{},
		sessions: map[[8]byte]*session{},
		bindings: map[netip.AddrPort]binding{},
	}
	if len(r.secret) == 0 {
		log.Printf("RELAY_SECRET is not set: accepting every token (test mode)")
	}
	go func() {
		for range time.Tick(5 * time.Second) {
			r.expire()
		}
	}()
	if *httpListen != "" {
		go func() { log.Fatal(http.ListenAndServe(*httpListen, r.httpHandler())) }()
	}
	log.Printf("relay listening on %s", conn.LocalAddr())
	r.serve()
}
