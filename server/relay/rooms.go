package main

import (
	"encoding/json"
	"net/http"
	"sort"
)

// roomInfo is what the launcher's server browser shows of a room.
type roomInfo struct {
	Name    string   `json:"name"`
	Players []string `json:"players"` // the players' ids from their tokens (Steam IDs)
	Max     int      `json:"max"`
}

// roomList lists the rooms with players, fullest first.
func (r *relay) roomList() []roomInfo {
	r.mu.Lock()
	defer r.mu.Unlock()
	list := make([]roomInfo, 0, len(r.rooms))
	for _, rm := range r.rooms {
		info := roomInfo{Name: rm.name, Players: []string{}, Max: maxPlayers}
		for _, s := range rm.sessions {
			info.Players = append(info.Players, s.player)
		}
		sort.Strings(info.Players)
		list = append(list, info)
	}
	sort.Slice(list, func(i, j int) bool {
		if len(list[i].Players) != len(list[j].Players) {
			return len(list[i].Players) > len(list[j].Players)
		}
		return list[i].Name < list[j].Name
	})
	return list
}

func (r *relay) httpHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /rooms", func(w http.ResponseWriter, req *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Access-Control-Allow-Origin", "*")
		json.NewEncoder(w).Encode(r.roomList())
	})
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, req *http.Request) { w.Write([]byte("ok")) })
	return mux
}
