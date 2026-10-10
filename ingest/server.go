package main

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync/atomic"
)

type Server struct {
	storage    *Storage
	buffer     *RingBuffer
	mux        *http.ServeMux
	totalRecv  uint64
	totalSaved uint64
}

type BatchRequest struct {
	Events []*EventPayload `json:"events"`
}

type BatchResponse struct {
	Accepted   int    `json:"accepted"`
	Duplicates int    `json:"duplicates"`
	Dropped    uint64 `json:"dropped"`
	Status     string `json:"status"`
}

type HealthResponse struct {
	Status         string `json:"status"`
	TotalReceived  uint64 `json:"total_received"`
	TotalSaved     uint64 `json:"total_saved"`
	BufferDropped  uint64 `json:"buffer_dropped"`
	OutboxPending  int    `json:"outbox_pending"`
	BufferCapacity uint64 `json:"buffer_capacity"`
}

func NewServer(storage *Storage, buffer *RingBuffer) *Server {
	s := &Server{
		storage: storage,
		buffer:  buffer,
		mux:     http.NewServeMux(),
	}
	s.registerRoutes()
	return s
}

func (s *Server) registerRoutes() {
	s.mux.HandleFunc("/healthz", s.handleHealthz)
	s.mux.HandleFunc("/api/v1/events/batch", s.handleBatch)
	s.mux.HandleFunc("/api/v1/runs/", s.handleGetRun)
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) handleHealthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	pending, _ := s.storage.CountOutboxPending()
	resp := HealthResponse{
		Status:         "healthy",
		TotalReceived:  atomic.LoadUint64(&s.totalRecv),
		TotalSaved:     atomic.LoadUint64(&s.totalSaved),
		BufferDropped:  s.buffer.DroppedCount(),
		OutboxPending:  pending,
		BufferCapacity: s.buffer.capacity,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleBatch(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req BatchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON body: "+err.Error(), http.StatusBadRequest)
		return
	}

	atomic.AddUint64(&s.totalRecv, uint64(len(req.Events)))

	// Push into ring buffer, and flush to persistent storage
	var toStore []*EventPayload
	for _, ev := range req.Events {
		if err := s.buffer.Push(ev); err != nil {
			// Buffer full: backpressure dropped
			continue
		}
	}

	// Drain available batch from ring buffer to storage
	toStore = s.buffer.PopBatch(len(req.Events) + 64)
	accepted, duplicates, err := s.storage.StoreBatch(toStore)
	if err != nil {
		http.Error(w, "Storage failure: "+err.Error(), http.StatusInternalServerError)
		return
	}

	atomic.AddUint64(&s.totalSaved, uint64(accepted))

	resp := BatchResponse{
		Accepted:   accepted,
		Duplicates: duplicates,
		Dropped:    s.buffer.DroppedCount(),
		Status:     "ok",
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleGetRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Path: /api/v1/runs/{id}
	runID := strings.TrimPrefix(r.URL.Path, "/api/v1/runs/")
	if runID == "" {
		http.Error(w, "Missing run ID", http.StatusBadRequest)
		return
	}

	events, err := s.storage.GetRunEvents(runID)
	if err != nil {
		http.Error(w, "Failed to query run: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"run_id": runID,
		"events": events,
		"count":  len(events),
	})
}
