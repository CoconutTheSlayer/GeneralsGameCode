package main

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"
	"time"

	"generalsgamecode/server/internal/token"
)

const steamID = "76561197960287930"

// fakeSteam answers check_authentication and GetOwnedGames like Steam.
func fakeSteam(t *testing.T, valid bool, owned int) *httptest.Server {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/openid/login":
			r.ParseForm()
			if r.Form.Get("openid.mode") != "check_authentication" {
				t.Errorf("mode %q", r.Form.Get("openid.mode"))
			}
			fmt.Fprintf(w, "ns:http://specs.openid.net/auth/2.0\nis_valid:%v\n", valid)
		case strings.HasPrefix(r.URL.Path, "/IPlayerService/GetOwnedGames"):
			if r.URL.Query().Get("steamid") != steamID {
				t.Errorf("steamid %q", r.URL.Query().Get("steamid"))
			}
			fmt.Fprintf(w, `{"response":{"game_count":%d}}`, owned)
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newServer(steam *httptest.Server, apiKey string) *server {
	return &server{
		publicURL:   "https://auth.example.org",
		secret:      []byte("secret"),
		apiKey:      apiKey,
		appIDs:      []string{"2732960"},
		tokenLife:   time.Hour,
		openIDURL:   steam.URL + "/openid/login",
		steamAPIURL: steam.URL,
		client:      steam.Client(),
		nonces:      map[string]time.Time{},
	}
}

func callbackQuery(nonce string) string {
	q := url.Values{
		"port":                  {"50123"},
		"openid.ns":             {"http://specs.openid.net/auth/2.0"},
		"openid.mode":           {"id_res"},
		"openid.op_endpoint":    {steamOpenID},
		"openid.claimed_id":     {"https://steamcommunity.com/openid/id/" + steamID},
		"openid.identity":       {"https://steamcommunity.com/openid/id/" + steamID},
		"openid.return_to":      {"https://auth.example.org/callback?port=50123"},
		"openid.response_nonce": {nonce},
		"openid.assoc_handle":   {"1234567890"},
		"openid.signed":         {"signed,op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle"},
		"openid.sig":            {"c2lnbmF0dXJl"},
	}
	return "/callback?" + q.Encode()
}

func get(s *server, path string) *httptest.ResponseRecorder {
	w := httptest.NewRecorder()
	s.handler().ServeHTTP(w, httptest.NewRequest(http.MethodGet, path, nil))
	return w
}

func TestLoginRedirectsToSteam(t *testing.T) {
	s := newServer(fakeSteam(t, true, 1), "")
	w := get(s, "/login?port=50123")
	loc, _ := url.Parse(w.Header().Get("Location"))
	if w.Code != http.StatusFound || loc.Query().Get("openid.return_to") != "https://auth.example.org/callback?port=50123" {
		t.Fatalf("%d %s", w.Code, loc)
	}
	if w := get(s, "/login?port=80"); w.Code != http.StatusBadRequest {
		t.Fatalf("privileged port accepted: %d", w.Code)
	}
}

func TestCallbackGivesTokenToGame(t *testing.T) {
	s := newServer(fakeSteam(t, true, 1), "key")
	w := get(s, callbackQuery("2026-10-07T10:00:00Zabc"))
	loc, err := url.Parse(w.Header().Get("Location"))
	if w.Code != http.StatusFound || err != nil || loc.Host != "127.0.0.1:50123" || loc.Path != "/token" {
		t.Fatalf("%d %q", w.Code, w.Header().Get("Location"))
	}
	player, ok := token.Check(s.secret, loc.Query().Get("t"), time.Now())
	if !ok || player != steamID {
		t.Fatalf("token for %q ok=%v", player, ok)
	}
	// The same assertion cannot be used twice.
	if w := get(s, callbackQuery("2026-10-07T10:00:00Zabc")); w.Code != http.StatusForbidden {
		t.Fatalf("replay accepted: %d", w.Code)
	}
}

func TestCallbackRefusesForgedAndUnowned(t *testing.T) {
	forged := newServer(fakeSteam(t, false, 1), "")
	if w := get(forged, callbackQuery("n1")); w.Code != http.StatusForbidden {
		t.Fatalf("forged accepted: %d", w.Code)
	}
	unowned := newServer(fakeSteam(t, true, 0), "key")
	w := get(unowned, callbackQuery("n2"))
	body, _ := io.ReadAll(w.Body)
	if w.Code != http.StatusForbidden || !strings.Contains(string(body), "public") {
		t.Fatalf("unowned: %d %s", w.Code, body)
	}
	// Without an API key ownership is not checked.
	if w := get(newServer(fakeSteam(t, true, 0), ""), callbackQuery("n3")); w.Code != http.StatusFound {
		t.Fatalf("no key: %d", w.Code)
	}
	// An assertion for another site is refused.
	other := strings.Replace(callbackQuery("n4"), "auth.example.org", "evil.example.org", 1)
	if w := get(newServer(fakeSteam(t, true, 1), ""), other); w.Code != http.StatusForbidden {
		t.Fatalf("other site: %d", w.Code)
	}
}
