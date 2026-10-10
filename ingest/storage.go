package main

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	_ "modernc.org/sqlite"
)

type Storage struct {
	db *sql.DB
}

type OutboxItem struct {
	OutboxID    string
	AggregateID string
	EventType   string
	PayloadJSON string
	Status      string
	CreatedAt   int64
}

func NewStorage(dbPath string) (*Storage, error) {
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open sqlite database: %w", err)
	}

	// Optimize for concurrent local reads and writes
	db.SetMaxOpenConns(1) // SQLite single-writer safety

	s := &Storage{db: db}
	if err := s.initSchema(); err != nil {
		return nil, err
	}

	return s, nil
}

func (s *Storage) initSchema() error {
	schema := `
	CREATE TABLE IF NOT EXISTS runs (
		run_id TEXT PRIMARY KEY,
		created_at INTEGER NOT NULL,
		status TEXT NOT NULL
	);

	CREATE TABLE IF NOT EXISTS steps (
		run_id TEXT NOT NULL,
		seq_id INTEGER NOT NULL,
		timestamp_ns INTEGER NOT NULL,
		event_type TEXT NOT NULL,
		payload_json TEXT NOT NULL,
		prev_hash TEXT NOT NULL,
		event_hash TEXT NOT NULL,
		PRIMARY KEY(run_id, seq_id)
	);

	CREATE TABLE IF NOT EXISTS outbox (
		outbox_id TEXT PRIMARY KEY,
		aggregate_id TEXT NOT NULL,
		event_type TEXT NOT NULL,
		payload_json TEXT NOT NULL,
		status TEXT NOT NULL CHECK(status IN ('PENDING', 'PROCESSED', 'FAILED')),
		created_at INTEGER NOT NULL
	);

	CREATE TABLE IF NOT EXISTS idempotency_keys (
		key TEXT PRIMARY KEY,
		created_at INTEGER NOT NULL
	);
	`
	_, err := s.db.Exec(schema)
	return err
}

func (s *Storage) StoreBatch(events []*EventPayload) (int, int, error) {
	if len(events) == 0 {
		return 0, 0, nil
	}

	tx, err := s.db.Begin()
	if err != nil {
		return 0, 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	accepted := 0
	duplicates := 0
	now := time.Now().UnixNano()

	stepStmt, err := tx.Prepare(`
		INSERT INTO steps (run_id, seq_id, timestamp_ns, event_type, payload_json, prev_hash, event_hash)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(run_id, seq_id) DO NOTHING;
	`)
	if err != nil {
		return 0, 0, err
	}
	defer stepStmt.Close()

	outboxStmt, err := tx.Prepare(`
		INSERT INTO outbox (outbox_id, aggregate_id, event_type, payload_json, status, created_at)
		VALUES (?, ?, ?, ?, 'PENDING', ?);
	`)
	if err != nil {
		return 0, 0, err
	}
	defer outboxStmt.Close()

	runStmt, err := tx.Prepare(`
		INSERT INTO runs (run_id, created_at, status)
		VALUES (?, ?, 'ACTIVE')
		ON CONFLICT(run_id) DO NOTHING;
	`)
	if err != nil {
		return 0, 0, err
	}
	defer runStmt.Close()

	for _, ev := range events {
		// Ensure run record exists
		_, _ = runStmt.Exec(ev.RunID, now)

		payloadBytes, err := json.Marshal(ev.Payload)
		if err != nil {
			payloadBytes = []byte("{}")
		}

		res, err := stepStmt.Exec(
			ev.RunID,
			ev.SeqID,
			ev.TimestampNS,
			ev.EventType,
			string(payloadBytes),
			ev.PrevEventHash,
			ev.EventHash,
		)
		if err != nil {
			return accepted, duplicates, fmt.Errorf("failed to insert step: %w", err)
		}

		rows, err := res.RowsAffected()
		if err != nil {
			return accepted, duplicates, err
		}

		if rows == 0 {
			// Idempotent duplicate
			duplicates++
		} else {
			accepted++
			// Write transactional outbox entry in the same transaction
			outboxID := uuid.New().String()
			_, err = outboxStmt.Exec(outboxID, ev.RunID, ev.EventType, string(payloadBytes), now)
			if err != nil {
				return accepted, duplicates, fmt.Errorf("failed to write outbox: %w", err)
			}
		}
	}

	if err := tx.Commit(); err != nil {
		return 0, 0, fmt.Errorf("failed to commit transaction: %w", err)
	}

	return accepted, duplicates, nil
}

func (s *Storage) GetRunEvents(runID string) ([]*EventPayload, error) {
	rows, err := s.db.Query(`
		SELECT run_id, seq_id, timestamp_ns, event_type, payload_json, prev_hash, event_hash
		FROM steps
		WHERE run_id = ?
		ORDER BY seq_id ASC;
	`, runID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []*EventPayload
	for rows.Next() {
		var ev EventPayload
		var payloadStr string
		err := rows.Scan(
			&ev.RunID,
			&ev.SeqID,
			&ev.TimestampNS,
			&ev.EventType,
			&payloadStr,
			&ev.PrevEventHash,
			&ev.EventHash,
		)
		if err != nil {
			return nil, err
		}
		var p map[string]interface{}
		_ = json.Unmarshal([]byte(payloadStr), &p)
		ev.Payload = p
		events = append(events, &ev)
	}

	return events, nil
}

func (s *Storage) CountOutboxPending() (int, error) {
	var count int
	err := s.db.QueryRow(`SELECT COUNT(*) FROM outbox WHERE status = 'PENDING';`).Scan(&count)
	return count, err
}

func (s *Storage) Close() error {
	return s.db.Close()
}
