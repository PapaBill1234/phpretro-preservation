package main

import (
	"log"
	"net/http"
	"os"

	"github.com/PapaBill1234/phpretro-preservation/internal/server"
)

func main() {
	port, err := server.PortFromEnv(os.Getenv("PORT"))
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("phpretro listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, server.New()))
}
