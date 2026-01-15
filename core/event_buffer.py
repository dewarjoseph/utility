"""
Event Buffer: High-performance SQLite-backed circular buffer for real-time event streaming.

This module provides O(1) insertion with automatic pruning, temporal aggregations,
and thread-safe access for concurrent daemon + dashboard operation.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

log = logging.getLogger("core.event_buffer")


@dataclass
class QuantumEvent:
    """Represents a single quantum scan event with ML metadata."""
    timestamp: float
    lat: float
    lon: float
    utility_score: float
    ml_error: float
    is_surprise: bool
    mismatch_types: str  # Comma-separated for SQLite storage
    mismatch_count: int
    mismatch_severity_max: float
    features_json: str  # JSON-encoded feature dict
    trace_json: str  # JSON-encoded reasoning trace


class EventBuffer:
    """
    SQLite-backed circular buffer for real-time quantum event streaming.
    
    Features:
    - O(1) amortized insertion with automatic oldest-event pruning
    - Pre-computed sliding window aggregations (velocity, anomaly rate, error trend)
    - Event classification (high-value, anomaly, learning events)
    - Temporal bucketing for gauge chart data (1-minute buckets)
    - Thread-safe for concurrent daemon + dashboard access
    - Graceful degradation on SQLite failures (logs and continues)
    
    Usage:
        buffer = EventBuffer()  # Uses default file path
        buffer.insert_event(quantum_dict, score=7.5, ml_error=0.3, mismatches=[...])
        recent = buffer.get_recent_events(100)
        velocity = buffer.get_high_value_velocity()
    """
    
    DEFAULT_DB_PATH = "event_buffer.db"
    MAX_EVENTS = 1000
    HIGH_VALUE_THRESHOLD = 5.0
    VELOCITY_WINDOW_SECONDS = 60
    PRUNE_BATCH_SIZE = 100  # Events to delete when pruning
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the EventBuffer.
        
        Args:
            db_path: Path to SQLite database. Use ':memory:' for in-memory buffer.
                     If None, uses DEFAULT_DB_PATH in current directory.
        """
        self.db_path = db_path or os.path.join(os.getcwd(), self.DEFAULT_DB_PATH)
        self._lock = threading.RLock()
        self._connection_pool: Dict[int, sqlite3.Connection] = {}
        
        # In-memory cache for ultra-fast recent queries
        self._recent_cache: deque = deque(maxlen=100)
        self._last_prune_time = 0
        
        # Aggregation caches (updated on insert)
        self._velocity_cache = 0.0
        self._velocity_cache_time = 0
        self._mismatch_summary_cache: Dict[str, int] = {}
        self._mismatch_cache_time = 0
        
        self._init_db()
        log.info(f"EventBuffer initialized at {self.db_path} (max {self.MAX_EVENTS} events)")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection with optimized settings."""
        thread_id = threading.get_ident()
        
        if thread_id not in self._connection_pool:
            conn = sqlite3.connect(
                self.db_path,
                timeout=5.0,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False
            )
            # Performance optimizations
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            self._connection_pool[thread_id] = conn
            log.debug(f"Created new SQLite connection for thread {thread_id}")
        
        return self._connection_pool[thread_id]
    
    @contextmanager
    def _transaction(self):
        """Context manager for transaction handling with error recovery."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            log.error(f"SQLite transaction failed: {e}")
            raise
    
    def _init_db(self) -> None:
        """Initialize database schema with indexes for fast queries."""
        with self._lock:
            try:
                with self._transaction() as conn:
                    # Main events table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS quantum_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp REAL NOT NULL,
                            lat REAL NOT NULL,
                            lon REAL NOT NULL,
                            utility_score REAL NOT NULL,
                            ml_error REAL DEFAULT 0,
                            is_surprise INTEGER DEFAULT 0,
                            mismatch_types TEXT DEFAULT '',
                            mismatch_count INTEGER DEFAULT 0,
                            mismatch_severity_max REAL DEFAULT 0,
                            features_json TEXT,
                            trace_json TEXT
                        )
                    """)
                    
                    # Indexes for common queries
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_timestamp 
                        ON quantum_events(timestamp DESC)
                    """)
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_utility 
                        ON quantum_events(utility_score DESC)
                    """)
                    conn.execute("""
                        CREATE INDEX IF NOT EXISTS idx_surprise 
                        ON quantum_events(is_surprise)
                    """)
                    
                    # Temporal aggregation table (1-minute buckets)
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS temporal_buckets (
                            bucket_minute INTEGER PRIMARY KEY,
                            event_count INTEGER DEFAULT 0,
                            high_value_count INTEGER DEFAULT 0,
                            total_ml_error REAL DEFAULT 0,
                            surprise_count INTEGER DEFAULT 0,
                            avg_utility REAL DEFAULT 0
                        )
                    """)
                    
                    log.info("EventBuffer database schema initialized")
                    
            except sqlite3.Error as e:
                log.error(f"Failed to initialize EventBuffer DB: {e}")
                raise RuntimeError(f"EventBuffer initialization failed: {e}")
    
    def insert_event(
        self,
        quantum_data: Dict,
        score: float,
        ml_error: float = 0.0,
        mismatches: Optional[List] = None,
        features: Optional[Dict] = None,
        trace: Optional[List] = None
    ) -> bool:
        """
        Insert a new quantum event into the buffer.
        
        Args:
            quantum_data: Raw quantum dictionary with lat/lon
            score: Calculated utility score
            ml_error: Absolute prediction error
            mismatches: List of Mismatch objects or dicts
            features: Extracted ML features
            trace: Reasoning trace list
            
        Returns:
            True on success, False on failure (logged, not raised)
        """
        timestamp = time.time()
        lat = quantum_data.get('lat', 0.0)
        lon = quantum_data.get('lon', 0.0)
        is_surprise = quantum_data.get('is_surprise', False) or ml_error > 1.0
        
        # Process mismatches
        mismatches = mismatches or []
        mismatch_types = []
        max_severity = 0.0
        for m in mismatches:
            if hasattr(m, 'mismatch_type'):
                mismatch_types.append(m.mismatch_type)
                max_severity = max(max_severity, getattr(m, 'severity', 0))
            elif isinstance(m, dict):
                mismatch_types.append(m.get('mismatch_type', 'unknown'))
                max_severity = max(max_severity, m.get('severity', 0))
        
        event = QuantumEvent(
            timestamp=timestamp,
            lat=lat,
            lon=lon,
            utility_score=score,
            ml_error=ml_error,
            is_surprise=is_surprise,
            mismatch_types=','.join(mismatch_types),
            mismatch_count=len(mismatches),
            mismatch_severity_max=max_severity,
            features_json=json.dumps(features) if features else '{}',
            trace_json=json.dumps(trace) if trace else '[]'
        )
        
        with self._lock:
            try:
                with self._transaction() as conn:
                    # Insert event
                    conn.execute("""
                        INSERT INTO quantum_events (
                            timestamp, lat, lon, utility_score, ml_error, is_surprise,
                            mismatch_types, mismatch_count, mismatch_severity_max,
                            features_json, trace_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.timestamp, event.lat, event.lon, event.utility_score,
                        event.ml_error, int(event.is_surprise), event.mismatch_types,
                        event.mismatch_count, event.mismatch_severity_max,
                        event.features_json, event.trace_json
                    ))
                    
                    # Update temporal bucket
                    bucket_minute = int(timestamp // 60)
                    is_high_value = score >= self.HIGH_VALUE_THRESHOLD
                    
                    conn.execute("""
                        INSERT INTO temporal_buckets 
                            (bucket_minute, event_count, high_value_count, total_ml_error, 
                             surprise_count, avg_utility)
                        VALUES (?, 1, ?, ?, ?, ?)
                        ON CONFLICT(bucket_minute) DO UPDATE SET
                            event_count = event_count + 1,
                            high_value_count = high_value_count + excluded.high_value_count,
                            total_ml_error = total_ml_error + excluded.total_ml_error,
                            surprise_count = surprise_count + excluded.surprise_count,
                            avg_utility = (avg_utility * event_count + excluded.avg_utility) / (event_count + 1)
                    """, (
                        bucket_minute, int(is_high_value), ml_error,
                        int(is_surprise), score
                    ))
                
                # Update in-memory cache
                self._recent_cache.appendleft({
                    'timestamp': timestamp,
                    'lat': lat,
                    'lon': lon,
                    'utility_score': score,
                    'ml_error': ml_error,
                    'is_surprise': is_surprise,
                    'mismatch_types': mismatch_types,
                    'mismatch_count': len(mismatches)
                })
                
                # Invalidate aggregation caches
                self._velocity_cache_time = 0
                self._mismatch_cache_time = 0
                
                # Periodic pruning (amortized O(1))
                self._maybe_prune()
                
                log.debug(f"Inserted event: ({lat:.4f}, {lon:.4f}) score={score:.2f}")
                return True
                
            except sqlite3.Error as e:
                log.error(f"Failed to insert event: {e}")
                return False
    
    def _maybe_prune(self) -> None:
        """Prune old events if buffer exceeds max size. Amortized O(1)."""
        current_time = time.time()
        
        # Only check every 10 seconds
        if current_time - self._last_prune_time < 10:
            return
        
        self._last_prune_time = current_time
        
        try:
            conn = self._get_connection()
            count = conn.execute("SELECT COUNT(*) FROM quantum_events").fetchone()[0]
            
            if count > self.MAX_EVENTS + self.PRUNE_BATCH_SIZE:
                # Delete oldest events in batch
                delete_count = count - self.MAX_EVENTS
                conn.execute("""
                    DELETE FROM quantum_events 
                    WHERE id IN (
                        SELECT id FROM quantum_events 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    )
                """, (delete_count,))
                conn.commit()
                log.info(f"Pruned {delete_count} old events from buffer")
                
                # Also prune old temporal buckets (keep last 60 minutes)
                cutoff_bucket = int((current_time - 3600) // 60)
                conn.execute("DELETE FROM temporal_buckets WHERE bucket_minute < ?", 
                           (cutoff_bucket,))
                conn.commit()
                
        except sqlite3.Error as e:
            log.warning(f"Prune operation failed: {e}")
    
    def get_recent_events(self, limit: int = 100) -> List[Dict]:
        """
        Get most recent events for display.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries, newest first
        """
        # Use cache for small limits
        if limit <= len(self._recent_cache):
            return list(self._recent_cache)[:limit]
        
        with self._lock:
            try:
                conn = self._get_connection()
                rows = conn.execute("""
                    SELECT timestamp, lat, lon, utility_score, ml_error, is_surprise,
                           mismatch_types, mismatch_count, mismatch_severity_max,
                           features_json, trace_json
                    FROM quantum_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)).fetchall()
                
                return [{
                    'timestamp': row['timestamp'],
                    'lat': row['lat'],
                    'lon': row['lon'],
                    'utility_score': row['utility_score'],
                    'ml_error': row['ml_error'],
                    'is_surprise': bool(row['is_surprise']),
                    'mismatch_types': row['mismatch_types'].split(',') if row['mismatch_types'] else [],
                    'mismatch_count': row['mismatch_count'],
                    'features': json.loads(row['features_json']) if row['features_json'] else {},
                    'trace': json.loads(row['trace_json']) if row['trace_json'] else []
                } for row in rows]
                
            except sqlite3.Error as e:
                log.error(f"Failed to get recent events: {e}")
                return list(self._recent_cache)[:limit]
    
    def get_high_value_velocity(self) -> float:
        """
        Calculate high-value target acquisition rate (targets per minute).
        
        Returns:
            High-value targets per minute over the last 60 seconds
        """
        current_time = time.time()
        
        # Use cache if fresh (within 5 seconds)
        if current_time - self._velocity_cache_time < 5:
            return self._velocity_cache
        
        with self._lock:
            try:
                conn = self._get_connection()
                cutoff_time = current_time - self.VELOCITY_WINDOW_SECONDS
                
                row = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM quantum_events
                    WHERE timestamp > ? AND utility_score >= ?
                """, (cutoff_time, self.HIGH_VALUE_THRESHOLD)).fetchone()
                
                count = row['count'] if row else 0
                velocity = count  # Already per minute since window is 60 seconds
                
                self._velocity_cache = velocity
                self._velocity_cache_time = current_time
                
                return velocity
                
            except sqlite3.Error as e:
                log.error(f"Failed to calculate velocity: {e}")
                return self._velocity_cache
    
    def get_mismatch_summary(self) -> Dict[str, int]:
        """
        Get aggregated mismatch counts by type for the radar chart.
        
        Returns:
            Dict mapping mismatch type to count (last 100 events)
        """
        current_time = time.time()
        
        # Use cache if fresh
        if current_time - self._mismatch_cache_time < 5:
            return self._mismatch_summary_cache
        
        with self._lock:
            try:
                conn = self._get_connection()
                
                rows = conn.execute("""
                    SELECT mismatch_types
                    FROM quantum_events
                    WHERE mismatch_types != ''
                    ORDER BY timestamp DESC
                    LIMIT 100
                """).fetchall()
                
                summary = {'slope': 0, 'zoning': 0, 'flood': 0, 'utility': 0, 'surprise': 0}
                
                for row in rows:
                    types = row['mismatch_types'].split(',')
                    for t in types:
                        t = t.strip().lower()
                        if t in summary:
                            summary[t] += 1
                
                # Add surprise events
                surprise_count = conn.execute("""
                    SELECT COUNT(*) FROM quantum_events
                    WHERE is_surprise = 1
                    ORDER BY timestamp DESC
                    LIMIT 100
                """).fetchone()[0]
                summary['surprise'] = surprise_count
                
                self._mismatch_summary_cache = summary
                self._mismatch_cache_time = current_time
                
                return summary
                
            except sqlite3.Error as e:
                log.error(f"Failed to get mismatch summary: {e}")
                return self._mismatch_summary_cache or {
                    'slope': 0, 'zoning': 0, 'flood': 0, 'utility': 0, 'surprise': 0
                }
    
    def get_learning_curve(self, minutes: int = 10) -> List[Dict]:
        """
        Get error trend over time for learning curve visualization.
        
        Args:
            minutes: Number of minutes of history to return
            
        Returns:
            List of dicts with 'bucket_minute', 'avg_error', 'event_count'
        """
        with self._lock:
            try:
                conn = self._get_connection()
                cutoff = int((time.time() - minutes * 60) // 60)
                
                rows = conn.execute("""
                    SELECT bucket_minute, 
                           event_count,
                           total_ml_error / NULLIF(event_count, 0) as avg_error,
                           high_value_count,
                           surprise_count
                    FROM temporal_buckets
                    WHERE bucket_minute >= ?
                    ORDER BY bucket_minute ASC
                """, (cutoff,)).fetchall()
                
                return [{
                    'minute': row['bucket_minute'],
                    'event_count': row['event_count'],
                    'avg_error': row['avg_error'] or 0,
                    'high_value_count': row['high_value_count'],
                    'surprise_count': row['surprise_count']
                } for row in rows]
                
            except sqlite3.Error as e:
                log.error(f"Failed to get learning curve: {e}")
                return []
    
    def get_stats(self) -> Dict:
        """Get overall buffer statistics."""
        with self._lock:
            try:
                conn = self._get_connection()
                
                stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total_events,
                        AVG(utility_score) as avg_utility,
                        AVG(ml_error) as avg_error,
                        SUM(CASE WHEN utility_score >= ? THEN 1 ELSE 0 END) as high_value_count,
                        SUM(is_surprise) as surprise_count,
                        MIN(timestamp) as oldest_event,
                        MAX(timestamp) as newest_event
                    FROM quantum_events
                """, (self.HIGH_VALUE_THRESHOLD,)).fetchone()
                
                return {
                    'total_events': stats['total_events'] or 0,
                    'avg_utility': stats['avg_utility'] or 0,
                    'avg_error': stats['avg_error'] or 0,
                    'high_value_count': stats['high_value_count'] or 0,
                    'surprise_count': stats['surprise_count'] or 0,
                    'buffer_time_range_seconds': (
                        (stats['newest_event'] - stats['oldest_event'])
                        if stats['newest_event'] and stats['oldest_event'] else 0
                    )
                }
                
            except sqlite3.Error as e:
                log.error(f"Failed to get stats: {e}")
                return {
                    'total_events': 0, 'avg_utility': 0, 'avg_error': 0,
                    'high_value_count': 0, 'surprise_count': 0, 'buffer_time_range_seconds': 0
                }
    
    def close(self) -> None:
        """Close all database connections gracefully."""
        with self._lock:
            for thread_id, conn in self._connection_pool.items():
                try:
                    conn.close()
                    log.debug(f"Closed SQLite connection for thread {thread_id}")
                except Exception as e:
                    log.warning(f"Error closing connection: {e}")
            self._connection_pool.clear()
        log.info("EventBuffer closed")
    
    def __del__(self):
        """Destructor to ensure connections are closed."""
        try:
            self.close()
        except:
            pass
