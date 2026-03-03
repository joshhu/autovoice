#!/usr/bin/env python3
# scripts/merge_audio.py
# 將配音音訊替換回原始影片音軌
import sys
import subprocess
import os

def get_duration(path: str) -> float:
    """取得媒體檔案時長（秒）"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def merge_audio(input_video: str, dubbed_audio: str, output_video: str) -> None:
    """將配音音訊合入影片，替換原始音軌。
    若配音比影片短，補靜音至影片結尾；若配音比影片長，截斷至影片長度。
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)

    video_dur = get_duration(input_video)
    audio_dur = get_duration(dubbed_audio)

    # 配音比影片短 → 用 apad 補靜音到影片長度
    # 配音比影片長 → 截斷（atrim）
    if audio_dur < video_dur:
        audio_filter = f"apad=whole_dur={video_dur}"
    else:
        audio_filter = f"atrim=0:{video_dur}"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        "-i", dubbed_audio,
        "-c:v", "copy",
        "-filter_complex", f"[1:a]{audio_filter}[aout]",
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        output_video
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 錯誤: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(output_video) / 1024 / 1024
    print(f"配音影片完成: {output_video} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python merge_audio.py <input_video> <dubbed_audio> <output_video>")
        sys.exit(1)
    merge_audio(sys.argv[1], sys.argv[2], sys.argv[3])
