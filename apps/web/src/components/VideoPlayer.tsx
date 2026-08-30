import { useState } from "react";
import * as api from "../api/client";
import "./VideoPlayer.css";

export function VideoPlayer({ jobId, videoUrl }: { jobId: string; videoUrl: string }) {
  const [url, setUrl] = useState(videoUrl);
  const [refreshing, setRefreshing] = useState(false);
  const [expired, setExpired] = useState(false);

  async function handleError() {
    // Presigned URLs expire; on playback error, try refreshing once
    // before giving up and telling the person what happened.
    if (refreshing) return;
    setRefreshing(true);
    try {
      const job = await api.refreshVideoUrl(jobId);
      if (job.video_url) {
        setUrl(job.video_url);
        setExpired(false);
      }
    } catch {
      setExpired(true);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="video-player">
      <video key={url} src={url} controls onError={handleError} className="video-player__el" />
      {expired && (
        <p className="video-player__expired">
          This link couldn't be refreshed. Try reloading the page.
        </p>
      )}
    </div>
  );
}
