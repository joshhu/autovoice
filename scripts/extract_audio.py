#!/usr/bin/env python3
# scripts/extract_audio.py
# 從影片或 YouTube URL 提取音訊為 16kHz mono WAV
import sys
import subprocess
import os


def extract_audio(input_path: str, output_wav: str) -> None:
    """從影片提取音訊，輸出為 16kHz mono WAV"""
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",                  # 不要影像
        "-acodec", "pcm_s16le", # 16-bit PCM
        "-ar", "16000",         # 16kHz
        "-ac", "1",             # mono
        output_wav
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 錯誤: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"音訊提取完成: {output_wav}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python extract_audio.py <input_video> <output_wav>")
        sys.exit(1)
    extract_audio(sys.argv[1], sys.argv[2])
