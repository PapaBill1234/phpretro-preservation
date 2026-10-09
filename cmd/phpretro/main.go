package main

import (
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/PapaBill1234/phpretro-preservation/internal/server"
)

func main() {
	port, err := server.PortFromEnv(os.Getenv("PORT"))
	if err != nil {
		log.Fatal(err)
	}
	srv := &http.Server{
		Addr:              ":" + port,
		Handler:           server.New(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	// PortFromEnv already checked the range; log a numeric value so the logger
	// never receives text originating in the environment.
	portNumber, err := strconv.Atoi(port)
	if err != nil {
		log.Fatal("invalid normalized port")
	}
	log.Printf("phpretro listening on :%d", portNumber)
	log.Fatal(srv.ListenAndServe())
}
