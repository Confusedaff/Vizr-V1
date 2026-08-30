import { useEffect, useRef, useState } from "react";
import { wsUrl } from "../api/client";

export interface LiveEvent {
  stage: string;
  event_type: string;
  message?: string | null;
}

/** Subscribes to /ws/jobs/{jobId} while the job is in-flight. Stops
 * reconnecting once the caller passes `active=false` (job reached a
 * terminal state) — no point holding a socket open for a completed job,
 * and the REST endpoints remain the durable source of truth regardless. */
export function useJobEvents(jobId: string | null, active: boolean) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!jobId || !active) return;

    const socket = new WebSocket(wsUrl(`/ws/jobs/${jobId}`));
    socketRef.current = socket;

    socket.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data) as LiveEvent;
        if (parsed.event_type === "heartbeat") return;
        setEvents((prev) => [...prev, parsed]);
      } catch {
        // ignore malformed frames
      }
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [jobId, active]);

  return events;
}
