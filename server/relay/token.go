package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strconv"
	"strings"
	"time"
)

// Tokens are "<player>.<expiry unix seconds>.<hex HMAC-SHA256 of player.expiry>", issued by the login
// service with the same secret. The player is the Steam ID once login exists.
func makeToken(secret []byte, player string, expiry time.Time) string {
	payload := player + "." + strconv.FormatInt(expiry.Unix(), 10)
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(payload))
	return payload + "." + hex.EncodeToString(mac.Sum(nil))
}

// checkToken returns the player of a valid token. Without a secret (local tests) any token is
// accepted and names the player.
func checkToken(secret []byte, token string, now time.Time) (string, bool) {
	if len(secret) == 0 {
		if token == "" {
			token = "anonymous"
		}
		return token, true
	}
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return "", false
	}
	expiry, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil || now.Unix() > expiry {
		return "", false
	}
	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(parts[0] + "." + parts[1]))
	want := mac.Sum(nil)
	got, err := hex.DecodeString(parts[2])
	if err != nil || !hmac.Equal(want, got) {
		return "", false
	}
	return parts[0], true
}
