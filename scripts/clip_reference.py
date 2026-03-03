#!/usr/bin/env python3
# scripts/clip_reference.py
# 截取音訊中段 30 秒作為聲音克隆參考
import sys
import subprocess
import os

def clip_reference(input_wav: str, output_wav: str,
                   start_sec: int = 10, duration_sec: int = 30) -> None:
    """截取音訊作為參考，預設從第 10 秒開始截 30 秒"""
    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_wav,
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        output_wav
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 錯誤: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"參考音訊截取完成: {output_wav}")
    print(f"  從 {start_sec}s 開始，共 {duration_sec} 秒")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python clip_reference.py <input_wav> <output_wav> [start_sec] [duration]")
        sys.exit(1)
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    dur = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    clip_reference(sys.argv[1], sys.argv[2], start, dur)
