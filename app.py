import heapq
import os
import re

import av
import yt_dlp

url = input("YouTube URL: ").strip()

m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url)
if not m:
    raise ValueError("Could not extract YouTube video ID")
vid = m.group(1)

video_file = f"{vid}-video.mp4"
audio_file = f"{vid}-audio.m4a"
output_file = f"{vid}.mp4"


def download(fmt, path):
    opts = {"format": fmt, "outtmpl": path, "noplaylist": True, "overwrites": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


def timed_packets(container, stream, tag):
    for p in container.demux(stream):
        if p.dts is None:  # flush packet
            continue
        yield float(p.dts * p.time_base), tag, p


try:
    print("[1/3] Downloading video...")
    download("bestvideo[vcodec^=avc1][height<=720][ext=mp4]/bestvideo[height<=720]", video_file)

    print("[2/3] Downloading audio...")
    download("bestaudio[ext=m4a]/bestaudio", audio_file)

    print(f"[3/3] Muxing into {output_file}...")
    with av.open(video_file) as vin, av.open(audio_file) as ain, av.open(output_file, "w") as out:
        v_in, a_in = vin.streams.video[0], ain.streams.audio[0]
        v_out = out.add_stream_from_template(v_in)   # PyAV >= 14
        a_out = out.add_stream_from_template(a_in)   # older: add_stream(template=...)

        streams = {0: v_out, 1: a_out}
        merged = heapq.merge(
            timed_packets(vin, v_in, 0),
            timed_packets(ain, a_in, 1),
            key=lambda t: t[0],
        )
        for _, tag, packet in merged:
            packet.stream = streams[tag]
            out.mux(packet)
finally:
    for f in (video_file, audio_file):
        if os.path.exists(f):
            os.remove(f)

print(f"Done: {output_file}")
