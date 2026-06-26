import os
import shutil
import subprocess
import logging
from pathlib import Path
import urllib.request
from typing import Any, AsyncGenerator
import asyncio

logger = logging.getLogger("controlbox.streaming")

# Global registries for tracking active streams
# channel_id -> subprocess.Popen
ACTIVE_INGESTS: dict[str, subprocess.Popen] = {}
# channel_id -> set of client_connection_ids
CHANNEL_VIEWERS: dict[str, set[str]] = {}


class StreamRelayManager:
    def __init__(self, streams_dir: str = "/var/lib/controlbox/streams") -> None:
        self.streams_dir = Path(streams_dir)
        self.streams_dir.mkdir(parents=True, exist_ok=True)

    def get_hls_path(self, channel_id: str) -> Path:
        return self.streams_dir / channel_id

    def is_ingesting(self, channel_id: str) -> bool:
        proc = ACTIVE_INGESTS.get(channel_id)
        if proc:
            if proc.poll() is None:
                return True
            else:
                # Process died
                del ACTIVE_INGESTS[channel_id]
        return False

    async def start_hls_ingest(self, channel_id: str, stream_url: str) -> None:
        """Spawns an FFmpeg background process to segment the stream into HLS."""
        if self.is_ingesting(channel_id):
            return

        channel_dir = self.get_hls_path(channel_id)
        # Clear existing segment cache
        if channel_dir.exists():
            shutil.rmtree(channel_dir)
        channel_dir.mkdir(parents=True, exist_ok=True)

        m3u8_output = channel_dir / "index.m3u8"

        # FFmpeg command: copy codecs (minimal CPU) and segment into HLS
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-i", stream_url,
            "-c", "copy",
            "-hls_time", "4",
            "-hls_list_size", "5",
            "-hls_flags", "delete_segments",
            "-f", "hls",
            str(m3u8_output)
        ]

        logger.info(f"Starting FFmpeg ingest for channel {channel_id}: {' '.join(cmd)}")
        try:
            # Run in background
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True if os.name != 'nt' else False
            )
            ACTIVE_INGESTS[channel_id] = proc
            
            # Wait a few seconds for index.m3u8 to be created
            for _ in range(10):
                if m3u8_output.exists():
                    break
                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to start FFmpeg for channel {channel_id}: {e}")

    def stop_hls_ingest(self, channel_id: str) -> None:
        """Terminates the FFmpeg ingestion process for a channel."""
        proc = ACTIVE_INGESTS.get(channel_id)
        if proc:
            logger.info(f"Stopping FFmpeg ingest for channel {channel_id}")
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            if channel_id in ACTIVE_INGESTS:
                del ACTIVE_INGESTS[channel_id]

        # Clean up files
        channel_dir = self.get_hls_path(channel_id)
        if channel_dir.exists():
            try:
                shutil.rmtree(channel_dir)
            except Exception as e:
                logger.error(f"Error cleaning up channel {channel_id} directory: {e}")

    def register_viewer(self, channel_id: str, connection_id: str) -> None:
        if channel_id not in CHANNEL_VIEWERS:
            CHANNEL_VIEWERS[channel_id] = set()
        CHANNEL_VIEWERS[channel_id].add(connection_id)

    def unregister_viewer(self, channel_id: str, connection_id: str) -> None:
        if channel_id in CHANNEL_VIEWERS:
            CHANNEL_VIEWERS[channel_id].discard(connection_id)
            if not CHANNEL_VIEWERS[channel_id]:
                # 0 viewers remaining, stop HLS ingest
                self.stop_hls_ingest(channel_id)
                del CHANNEL_VIEWERS[channel_id]

    @staticmethod
    async def ts_proxy_generator(
        stream_url: str,
        on_chunk_read: Any = None
    ) -> AsyncGenerator[bytes, None]:
        """Direct MPEG-TS HTTP stream proxy generator."""
        req = urllib.request.Request(
            stream_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VLC/3.0.18"}
        )
        
        loop = asyncio.get_running_loop()
        
        def open_connection():
            return urllib.request.urlopen(req, timeout=10)

        try:
            response = await loop.run_in_executor(None, open_connection)
        except Exception as e:
            logger.error(f"Failed to open source stream {stream_url}: {e}")
            return

        try:
            chunk_size = 65536  # 64KB chunks
            while True:
                def read_chunk():
                    return response.read(chunk_size)

                chunk = await loop.run_in_executor(None, read_chunk)
                if not chunk:
                    break

                if on_chunk_read:
                    await on_chunk_read(len(chunk))

                yield chunk
        except asyncio.CancelledError:
            logger.info("Client disconnected from TS stream")
        finally:
            try:
                response.close()
            except Exception:
                pass
StreamRelayManager().streams_dir = Path("/var/lib/controlbox/streams")
