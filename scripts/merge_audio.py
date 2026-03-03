#!/usr/bin/env python3
# scripts/merge_audio.py
# 將配音音訊替換回原始影片音軌
import sys
import subprocess
import os

def merge_audio(input_video: str, dubbed_audio: str, output_video: str) -> None:
    """將配音音訊合入影片，替換原始音軌"""
    os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,    # 原始影片（取影像）
        "-i", dubbed_audio,   # 配音音訊（取音軌）
        "-c:v", "copy",       # 影像直接複製，不重新編碼（快且不損畫質）
        "-c:a", "aac",        # 音訊轉 AAC
        "-b:a", "192k",
        "-map", "0:v:0",      # 取第一個輸入的影像串流
        "-map", "1:a:0",      # 取第二個輸入的音訊串流
        "-shortest",          # 以較短的串流為準（避免配音比影片短時產生黑屏）
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
