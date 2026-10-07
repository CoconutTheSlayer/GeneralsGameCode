package main

import (
	"encoding/binary"
	"net"
	"net/netip"
	"testing"
	"time"

	"generalsgamecode/server/internal/token"
)

func startRelay(t *testing.T, secret string) netip.AddrPort {
	t.Helper()
	conn, err := net.ListenUDP("udp", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	r := &relay{conn: conn, secret: []byte(secret), rooms: map[string]*room{}, sessions: map[[8]byte]*session{}, bindings: map[netip.AddrPort]binding{}}
	go r.serve()
	return conn.LocalAddr().(*net.UDPAddr).AddrPort()
}

type client struct {
	t     *testing.T
	conn  *net.UDPConn
	relay netip.AddrPort
}

func newClient(t *testing.T, relay netip.AddrPort) *client {
	conn, err := net.ListenUDP("udp", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return &client{t: t, conn: conn, relay: relay}
}

func (c *client) send(t byte, body ...[]byte) {
	pkt := header(t)
	for _, b := range body {
		pkt = append(pkt, b...)
	}
	c.conn.WriteToUDPAddrPort(pkt, c.relay)
}

func (c *client) recv() []byte {
	c.conn.SetReadDeadline(time.Now().Add(time.Second))
	buf := make([]byte, 2048)
	n, _, err := c.conn.ReadFromUDPAddrPort(buf)
	if err != nil {
		return nil
	}
	return buf[:n]
}

func field(s string, n int) []byte {
	b := make([]byte, n)
	copy(b, s)
	return b
}

func port(p uint16) []byte { return binary.BigEndian.AppendUint16(nil, p) }

// join says HELLO and binds vport, returning the virtual address.
func (c *client) join(session, room, token string, vport uint16) [4]byte {
	c.send(typeHello, field(session, 8), field(room, 32), field(token, 128))
	welcome := c.recv()
	if len(welcome) != headerLen+12 || welcome[3] != typeWelcome {
		c.t.Fatalf("no welcome: %v", welcome)
	}
	var vip [4]byte
	copy(vip[:], welcome[headerLen+8:])
	c.send(typeBind, field(session, 8), port(vport))
	if bound := c.recv(); len(bound) < headerLen || bound[3] != typeBound {
		c.t.Fatalf("no bound: %v", bound)
	}
	return vip
}

func TestRelayForwardsWithinRooms(t *testing.T) {
	relay := startRelay(t, "")
	a, b, other := newClient(t, relay), newClient(t, relay), newClient(t, relay)
	vipA := a.join("sessionA", "room1", "alice", 8086)
	vipB := b.join("sessionB", "room1", "bob", 8086)
	other.join("sessionC", "room2", "carol", 8086)
	if vipA == vipB {
		t.Fatalf("same address %v", vipA)
	}

	// Broadcast reaches the other player in the room, not the sender or another room.
	a.send(typeSend, port(8086), []byte{255, 255, 255, 255}, port(8086), []byte("hello"))
	got := b.recv()
	want := append(append(append(header(typeRecv), vipA[:]...), port(8086)...), "hello"...)
	if string(got) != string(want) {
		t.Fatalf("broadcast: got %v want %v", got, want)
	}
	if x := other.recv(); x != nil {
		t.Fatalf("other room received %v", x)
	}

	// Direct send, and nothing for a port nobody bound.
	b.send(typeSend, port(8086), vipA[:], port(8086), []byte("reply"))
	if got := a.recv(); string(got[headerLen+6:]) != "reply" {
		t.Fatalf("unicast: %v", got)
	}
	b.send(typeSend, port(8086), vipA[:], port(9999), []byte("lost"))
	if x := a.recv(); x != nil {
		t.Fatalf("unbound port received %v", x)
	}
}

func TestRelayChecksTokens(t *testing.T) {
	secret := "test secret"
	relay := startRelay(t, secret)
	c := newClient(t, relay)
	c.send(typeHello, field("s1", 8), field("room", 32), field("forged.9999999999.00", 128))
	if got := c.recv(); len(got) != headerLen+1 || got[3] != typeError || got[4] != errBadToken {
		t.Fatalf("forged token: %v", got)
	}
	expired := token.Make([]byte(secret), "765611980", time.Now().Add(-time.Minute))
	c.send(typeHello, field("s1", 8), field("room", 32), field(expired, 128))
	if got := c.recv(); len(got) < headerLen || got[3] != typeError {
		t.Fatalf("expired token: %v", got)
	}
	good := token.Make([]byte(secret), "765611980", time.Now().Add(time.Hour))
	if vip := c.join("s1", "room", good, 8086); vip[0] != 10 {
		t.Fatalf("vip %v", vip)
	}
}

func TestRelayRejoinKeepsAddress(t *testing.T) {
	relay := startRelay(t, "")
	a, b := newClient(t, relay), newClient(t, relay)
	a.join("sessionA", "room", "alice", 8086)
	vipB := b.join("sessionB", "room", "bob", 8086)
	// A new session asking for bob's address gets another one while bob holds it...
	c := newClient(t, relay)
	c.send(typeHello, field("sessionC", 8), field("room", 32), field("carol", 128), vipB[:])
	if w := c.recv(); w == nil || [4]byte(w[headerLen+8:headerLen+12]) == vipB {
		t.Fatalf("got a taken address: %v", w)
	}
	// ...and a free address asked for is granted.
	want := [4]byte{10, 77, 0, 42}
	d := newClient(t, relay)
	d.send(typeHello, field("sessionD", 8), field("room", 32), field("dave", 128), want[:])
	if w := d.recv(); w == nil || [4]byte(w[headerLen+8:headerLen+12]) != want {
		t.Fatalf("rejoin address: %v", w)
	}
}
