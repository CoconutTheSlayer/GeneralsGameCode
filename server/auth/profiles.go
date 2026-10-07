package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

var steamIDPattern = regexp.MustCompile(`^\d{17}$`)

// profile is a player's public Steam name and avatar, for the launcher's server browser.
type profile struct {
	SteamID string `json:"steamid"`
	Name    string `json:"name"`
	Avatar  string `json:"avatar,omitempty"`
}

type cachedProfile struct {
	profile
	fetched time.Time
}

// fetchProfiles asks Steam for the names of up to 100 accounts.
func (s *server) fetchProfiles(ids []string) (map[string]profile, error) {
	q := url.Values{"key": {s.apiKey}, "steamids": {strings.Join(ids, ",")}}
	resp, err := s.client.Get(s.steamAPIURL + "/ISteamUser/GetPlayerSummaries/v2/?" + q.Encode())
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var result struct {
		Response struct {
			Players []struct {
				SteamID     string `json:"steamid"`
				PersonaName string `json:"personaname"`
				AvatarFull  string `json:"avatarfull"`
			} `json:"players"`
		} `json:"response"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&result); err != nil {
		return nil, err
	}
	out := map[string]profile{}
	for _, p := range result.Response.Players {
		out[p.SteamID] = profile{SteamID: p.SteamID, Name: p.PersonaName, Avatar: p.AvatarFull}
	}
	return out, nil
}

// profiles answers GET /profiles?ids=a,b,c. Names are kept for an hour; without a Steam API key the
// names are the ids.
func (s *server) profiles(w http.ResponseWriter, r *http.Request) {
	var ids []string
	for _, id := range strings.Split(r.URL.Query().Get("ids"), ",") {
		if steamIDPattern.MatchString(id) && len(ids) < 100 {
			ids = append(ids, id)
		}
	}
	result := make([]profile, 0, len(ids))
	var missing []string
	s.mu.Lock()
	for _, id := range ids {
		if c, ok := s.profileCache[id]; ok && time.Since(c.fetched) < time.Hour {
			result = append(result, c.profile)
		} else {
			missing = append(missing, id)
		}
	}
	s.mu.Unlock()
	if len(missing) > 0 {
		fetched := map[string]profile{}
		if s.apiKey != "" {
			if f, err := s.fetchProfiles(missing); err == nil {
				fetched = f
			}
		}
		s.mu.Lock()
		for _, id := range missing {
			p, ok := fetched[id]
			if !ok {
				p = profile{SteamID: id, Name: id}
			}
			s.profileCache[id] = cachedProfile{profile: p, fetched: time.Now()}
			result = append(result, p)
		}
		s.mu.Unlock()
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	json.NewEncoder(w).Encode(result)
}
