package main

import (
	"errors"
	"sync"
	"sync/atomic"
)

var (
	ErrBufferFull  = errors.New("ring buffer is full; backpressure active")
	ErrBufferEmpty = errors.New("ring buffer is empty")
)

type EventPayload struct {
	EventID       string                 `json:"event_id"`
	RunID         string                 `json:"run_id"`
	SeqID         int                    `json:"seq_id"`
	TimestampNS   int64                  `json:"timestamp_ns"`
	EventType     string                 `json:"event_type"`
	Payload       map[string]interface{} `json:"payload"`
	PrevEventHash string                 `json:"prev_event_hash"`
	EventHash     string                 `json:"event_hash"`
}

type RingBuffer struct {
	capacity uint64
	mask     uint64
	nodes    []*EventPayload
	head     uint64
	tail     uint64
	dropped  uint64
	mu       sync.Mutex
}

func NewRingBuffer(capacity uint64) *RingBuffer {
	// Ensure power of 2 for fast bitmask wrapping
	pow2 := uint64(1)
	for pow2 < capacity {
		pow2 <<= 1
	}
	return &RingBuffer{
		capacity: pow2,
		mask:     pow2 - 1,
		nodes:    make([]*EventPayload, pow2),
	}
}

func (rb *RingBuffer) Push(event *EventPayload) error {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	if rb.head-rb.tail >= rb.capacity {
		atomic.AddUint64(&rb.dropped, 1)
		return ErrBufferFull
	}

	rb.nodes[rb.head&rb.mask] = event
	rb.head++
	return nil
}

func (rb *RingBuffer) PopBatch(maxBatch int) []*EventPayload {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	available := rb.head - rb.tail
	if available == 0 {
		return nil
	}

	batchSize := int(available)
	if batchSize > maxBatch {
		batchSize = maxBatch
	}

	batch := make([]*EventPayload, batchSize)
	for i := 0; i < batchSize; i++ {
		batch[i] = rb.nodes[rb.tail&rb.mask]
		rb.nodes[rb.tail&rb.mask] = nil // avoid memory leak
		rb.tail++
	}

	return batch
}

func (rb *RingBuffer) DroppedCount() uint64 {
	return atomic.LoadUint64(&rb.dropped)
}

func (rb *RingBuffer) Occupancy() uint64 {
	rb.mu.Lock()
	defer rb.mu.Unlock()
	return rb.head - rb.tail
}
