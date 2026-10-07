// Command auth signs players in with their Steam account and gives the game a token for the relay.
//
// The game opens /login?port=N in the browser. That sends the player to Steam's sign in (OpenID 2.0,
// the same as "Sign in through Steam" on web sites), Steam returns to /callback, which checks the
// answer with Steam, optionally checks that the account owns Zero Hour, and sends the browser on to
// http://127.0.0.1:N/token?t=<token>, where the game is waiting.
//
// Settings (environment):
//
//	PUBLIC_URL         the address players reach this service at, e.g. https://auth.example.org
//	TOKEN_SECRET       the secret shared with the relay (RELAY_SECRET there)
//	STEAM_API_KEY      optional: with it, players must own one of OWNERSHIP_APP_IDS, which needs
//	                   their Steam profile's game details to be public
//	OWNERSHIP_APP_IDS  comma separated, default 2732960 (Command & Conquer Generals Zero Hour)
//	TOKEN_HOURS        how long a token lasts, default 168 (a week)
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"html/template"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"generalsgamecode/server/internal/token"
)

const steamOpenID = "https://steamcommunity.com/openid/login"

var claimedIDPattern = regexp.MustCompile(`^https://steamcommunity\.com/openid/id/(\d{17})$`)

type server struct {
	publicURL   string
	secret      []byte
	apiKey      string
	appIDs      []string
	tokenLife   time.Duration
	openIDURL   string // Steam's, replaced in tests
	steamAPIURL string // Steam's, replaced in tests
	client      *http.Client

	mu     sync.Mutex
	nonces map[string]time.Time // assertions already used, so a captured one cannot be replayed
}

func (s *server) login(w http.ResponseWriter, r *http.Request) {
	port, err := strconv.Atoi(r.URL.Query().Get("port"))
	if err != nil || port < 1024 || port > 65535 {
		http.Error(w, "missing or bad port", http.StatusBadRequest)
		return
	}
	q := url.Values{
		"openid.ns":         {"http://specs.openid.net/auth/2.0"},
		"openid.mode":       {"checkid_setup"},
		"openid.return_to":  {fmt.Sprintf("%s/callback?port=%d", s.publicURL, port)},
		"openid.realm":      {s.publicURL},
		"openid.identity":   {"http://specs.openid.net/auth/2.0/identifier_select"},
		"openid.claimed_id": {"http://specs.openid.net/auth/2.0/identifier_select"},
	}
	http.Redirect(w, r, s.openIDURL+"?"+q.Encode(), http.StatusFound)
}

// verify asks Steam whether the assertion in the callback is genuine and returns the Steam ID.
func (s *server) verify(q url.Values) (string, error) {
	if q.Get("openid.mode") != "id_res" {
		return "", fmt.Errorf("sign in was cancelled")
	}
	if q.Get("openid.op_endpoint") != steamOpenID {
		return "", fmt.Errorf("not from Steam")
	}
	if rt := q.Get("openid.return_to"); !strings.HasPrefix(rt, s.publicURL+"/callback?") {
		return "", fmt.Errorf("wrong return address")
	}
	m := claimedIDPattern.FindStringSubmatch(q.Get("openid.claimed_id"))
	if m == nil {
		return "", fmt.Errorf("no Steam ID")
	}
	nonce := q.Get("openid.response_nonce")
	s.mu.Lock()
	_, used := s.nonces[nonce]
	if !used {
		s.nonces[nonce] = time.Now()
	}
	s.mu.Unlock()
	if nonce == "" || used {
		return "", fmt.Errorf("sign in already used")
	}

	check := url.Values{}
	for k, v := range q {
		if strings.HasPrefix(k, "openid.") {
			check[k] = v
		}
	}
	check.Set("openid.mode", "check_authentication")
	resp, err := s.client.PostForm(s.openIDURL, check)
	if err != nil {
		return "", fmt.Errorf("Steam is not reachable")
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if !strings.Contains(string(body), "is_valid:true") {
		return "", fmt.Errorf("Steam did not confirm the sign in")
	}
	return m[1], nil
}

// ownsGame checks the account's games through the Steam Web API. It only sees them when the
// profile's game details are public.
func (s *server) ownsGame(steamID string) (bool, error) {
	q := url.Values{"key": {s.apiKey}, "steamid": {steamID}, "include_played_free_games": {"1"}}
	for i, id := range s.appIDs {
		q.Set(fmt.Sprintf("appids_filter[%d]", i), id)
	}
	resp, err := s.client.Get(s.steamAPIURL + "/IPlayerService/GetOwnedGames/v1/?" + q.Encode())
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()
	var result struct {
		Response struct {
			GameCount int `json:"game_count"`
		} `json:"response"`
	}
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<16)).Decode(&result); err != nil {
		return false, err
	}
	return result.Response.GameCount > 0, nil
}

var pageTemplate = template.Must(template.New("page").Parse(`<!doctype html>
<meta charset="utf-8"><title>{{.Title}}</title>
<style>body{font:16px system-ui,sans-serif;max-width:36em;margin:4em auto;padding:0 1em;color:#222}</style>
<h1>{{.Title}}</h1><p>{{.Text}}</p>`))

func page(w http.ResponseWriter, status int, title, text string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	pageTemplate.Execute(w, struct{ Title, Text string }{title, text})
}

func (s *server) callback(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	port, err := strconv.Atoi(q.Get("port"))
	if err != nil || port < 1024 || port > 65535 {
		page(w, http.StatusBadRequest, "Sign in failed", "The request is missing the game's port. Start the sign in from the game again.")
		return
	}
	steamID, err := s.verify(q)
	if err != nil {
		page(w, http.StatusForbidden, "Sign in failed", err.Error()+". Start the sign in from the game again.")
		return
	}
	if s.apiKey != "" {
		owns, err := s.ownsGame(steamID)
		if err != nil {
			page(w, http.StatusBadGateway, "Sign in failed", "Steam could not tell us which games you own. Try again later.")
			return
		}
		if !owns {
			page(w, http.StatusForbidden, "Zero Hour not found",
				"We could not find Command & Conquer Generals Zero Hour on this Steam account. If you own it, set your Steam profile's game details to public and sign in again.")
			return
		}
	}
	t := token.Make(s.secret, steamID, time.Now().Add(s.tokenLife))
	log.Printf("signed in %s", steamID)
	http.Redirect(w, r, fmt.Sprintf("http://127.0.0.1:%d/token?t=%s", port, url.QueryEscape(t)), http.StatusFound)
}

func (s *server) forgetOldNonces() {
	for range time.Tick(time.Minute) {
		s.mu.Lock()
		for n, at := range s.nonces {
			if time.Since(at) > time.Hour {
				delete(s.nonces, n)
			}
		}
		s.mu.Unlock()
	}
}

func (s *server) handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /login", s.login)
	mux.HandleFunc("GET /callback", s.callback)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "ok") })
	return mux
}

func main() {
	listen := flag.String("listen", ":8080", "HTTP address to listen on")
	flag.Parse()
	s := &server{
		publicURL:   strings.TrimRight(os.Getenv("PUBLIC_URL"), "/"),
		secret:      []byte(os.Getenv("TOKEN_SECRET")),
		apiKey:      os.Getenv("STEAM_API_KEY"),
		appIDs:      []string{"2732960"},
		tokenLife:   7 * 24 * time.Hour,
		openIDURL:   steamOpenID,
		steamAPIURL: "https://api.steampowered.com",
		client:      &http.Client{Timeout: 10 * time.Second},
		nonces:      map[string]time.Time{},
	}
	if s.publicURL == "" || len(s.secret) == 0 {
		log.Fatal("PUBLIC_URL and TOKEN_SECRET must be set")
	}
	if ids := os.Getenv("OWNERSHIP_APP_IDS"); ids != "" {
		s.appIDs = strings.Split(ids, ",")
	}
	if h, err := strconv.Atoi(os.Getenv("TOKEN_HOURS")); err == nil && h > 0 {
		s.tokenLife = time.Duration(h) * time.Hour
	}
	if s.apiKey == "" {
		log.Printf("STEAM_API_KEY is not set: any Steam account can sign in")
	}
	go s.forgetOldNonces()
	log.Printf("auth listening on %s for %s", *listen, s.publicURL)
	log.Fatal(http.ListenAndServe(*listen, s.handler()))
}
