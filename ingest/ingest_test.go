package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func setupTestStorage(t *testing.T) (*Storage, string) {
	tmpFile, err := os.CreateTemp("", "kairos_test_*.db")
	if err != nil {
		t.Fatalf("failed to create temp file: %v", err)
	}
	dbPath := tmpFile.Name()
	tmpFile.Close()

	storage, err := NewStorage(dbPath)
	if err != nil {
		t.Fatalf("failed to init storage: %v", err)
	}
	return storage, dbPath
}

func TestRingBufferCapacityAndDrop(t *testing.T) {
	buf := NewRingBuffer(4) // capacity rounds to 4

	for i := 0; i < 4; i++ {
		ev := &EventPayload{EventID: fmt.Sprintf("ev_%d", i)}
		if err := buf.Push(ev); err != nil {
			t.Fatalf("unexpected error pushing %d: %v", i, err)
		}
	}

	// 5th push should fail with ErrBufferFull
	evOverflow := &EventPayload{EventID: "ev_overflow"}
	err := buf.Push(evOverflow)
	if err != ErrBufferFull {
		t.Fatalf("expected ErrBufferFull, got %v", err)
	}

	if buf.DroppedCount() != 1 {
		t.Fatalf("expected 1 dropped, got %d", buf.DroppedCount())
	}

	batch := buf.PopBatch(10)
	if len(batch) != 4 {
		t.Fatalf("expected batch size 4, got %d", len(batch))
	}
}

func TestBatchIngestAndIdempotency(t *testing.T) {
	storage, dbPath := setupTestStorage(t)
	defer os.Remove(dbPath)
	defer storage.Close()

	ringBuffer := NewRingBuffer(64)
	server := NewServer(storage, ringBuffer)

	events := []*EventPayload{
		{
			EventID:       "ev_1",
			RunID:         "run_100",
			SeqID:         0,
			TimestampNS:   1000,
			EventType:     "run_started",
			Payload:       map[string]interface{}{"task": "test_sql"},
			PrevEventHash: "0000",
			EventHash:     "hash_1",
		},
		{
			EventID:       "ev_2",
			RunID:         "run_100",
			SeqID:         1,
			TimestampNS:   2000,
			EventType:     "tool_executed",
			Payload:       map[string]interface{}{"tool": "execute_sql"},
			PrevEventHash: "hash_1",
			EventHash:     "hash_2",
		},
	}

	reqBody, _ := json.Marshal(BatchRequest{Events: events})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/events/batch", bytes.NewReader(reqBody))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	server.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp BatchResponse
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if resp.Accepted != 2 || resp.Duplicates != 0 {
		t.Fatalf("expected 2 accepted, 0 duplicates; got accepted=%d, duplicates=%d", resp.Accepted, resp.Duplicates)
	}

	// Verify Outbox pending count equals 2
	pending, err := storage.CountOutboxPending()
	if err != nil || pending != 2 {
		t.Fatalf("expected 2 pending outbox items, got %d (err: %v)", pending, err)
	}

	// Send duplicate batch: should report 2 duplicates, 0 accepted
	reqDup := httptest.NewRequest(http.MethodPost, "/api/v1/events/batch", bytes.NewReader(reqBody))
	wDup := httptest.NewRecorder()
	server.ServeHTTP(wDup, reqDup)

	var respDup BatchResponse
	_ = json.Unmarshal(wDup.Body.Bytes(), &respDup)
	if respDup.Accepted != 0 || respDup.Duplicates != 2 {
		t.Fatalf("expected 0 accepted, 2 duplicates; got accepted=%d, duplicates=%d", respDup.Accepted, respDup.Duplicates)
	}

	// Query Run Events
	reqGet := httptest.NewRequest(http.MethodGet, "/api/v1/runs/run_100", nil)
	wGet := httptest.NewRecorder()
	server.ServeHTTP(wGet, reqGet)

	if wGet.Code != http.StatusOK {
		t.Fatalf("expected status 200 for get run, got %d", wGet.Code)
	}
}
