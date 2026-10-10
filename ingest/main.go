package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	port := flag.String("port", "8080", "HTTP server port")
	dbPath := flag.String("db", "./kairos_events.db", "SQLite database path")
	bufCap := flag.Uint64("buffer", 8192, "Ring buffer capacity")
	flag.Parse()

	log.Printf("Starting Kairos Ingest Service on port %s (db: %s, buffer: %d)...", *port, *dbPath, *bufCap)

	storage, err := NewStorage(*dbPath)
	if err != nil {
		log.Fatalf("Fatal: storage initialization failed: %v", err)
	}
	defer storage.Close()

	ringBuffer := NewRingBuffer(*bufCap)
	server := NewServer(storage, ringBuffer)

	httpServer := &http.Server{
		Addr:    ":" + *port,
		Handler: server,
	}

	go func() {
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server error: %v", err)
		}
	}()

	log.Printf("Kairos Ingest Service listening on http://localhost:%s", *port)

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	log.Println("Shutting down Kairos Ingest Service gracefully...")
	_ = httpServer.Close()
	fmt.Println("Ingest service stopped.")
}
