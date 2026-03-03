# tests/test_merge_audio.py
import subprocess
import os
import pytest

def test_merge_creates_video(tmp_path):
    """測試能將新音訊合回影片"""
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    dubbed_audio = str(tmp_path / "dubbed.wav")
    output_video = str(tmp_path / "output.mp4")

    # 先建立假的配音 WAV（用原始音訊代替，只取前 10 秒）
    r = subprocess.run([
        "ffmpeg", "-y", "-i", input_video,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", "10",
        dubbed_audio
    ], capture_output=True)
    assert r.returncode == 0, "前置步驟 ffmpeg 失敗"

    result = subprocess.run(
        [".venv/bin/python", "scripts/merge_audio.py", input_video, dubbed_audio, output_video],
        capture_output=True, text=True,
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(output_video)
    assert os.path.getsize(output_video) > 10000, "輸出影片太小"

def test_merge_output_has_video_stream(tmp_path):
    """測試輸出影片確實有影像串流"""
    import json
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    dubbed_audio = str(tmp_path / "dubbed.wav")
    output_video = str(tmp_path / "output.mp4")

    subprocess.run([
        "ffmpeg", "-y", "-i", input_video,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", "10", dubbed_audio
    ], capture_output=True)

    subprocess.run(
        [".venv/bin/python", "scripts/merge_audio.py", input_video, dubbed_audio, output_video],
        capture_output=True, text=True,
        cwd="/home/joshhu/workspace/autovoice"
    )

    # 用 ffprobe 確認輸出有影像和音訊串流
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", output_video
    ], capture_output=True, text=True)

    data = json.loads(probe.stdout)
    stream_types = {s["codec_type"] for s in data["streams"]}
    assert "video" in stream_types, "輸出缺少影像串流"
    assert "audio" in stream_types, "輸出缺少音訊串流"
