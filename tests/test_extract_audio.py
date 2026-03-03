# tests/test_extract_audio.py
import subprocess
import os
import pytest

def test_extract_audio_creates_wav(tmp_path):
    """測試能從 MP4 提取 WAV 音訊"""
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    output_wav = str(tmp_path / "audio.wav")

    result = subprocess.run(
        [".venv/bin/python", "scripts/extract_audio.py", input_video, output_wav],
        capture_output=True, text=True,
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(output_wav), "WAV 檔案未建立"
    assert os.path.getsize(output_wav) > 1000, "WAV 檔案太小"

def test_extract_audio_correct_format(tmp_path):
    """測試輸出格式為 16kHz mono"""
    import soundfile as sf
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    output_wav = str(tmp_path / "audio.wav")

    subprocess.run(
        [".venv/bin/python", "scripts/extract_audio.py", input_video, output_wav],
        cwd="/home/joshhu/workspace/autovoice"
    )

    data, samplerate = sf.read(output_wav)
    assert samplerate == 16000, f"取樣率應為 16000，實際: {samplerate}"
    assert data.ndim == 1, "應為 mono（一維陣列）"
