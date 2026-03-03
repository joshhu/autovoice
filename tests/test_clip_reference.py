# tests/test_clip_reference.py
import subprocess
import os
import soundfile as sf
import pytest

def test_clip_creates_30s_wav(tmp_path):
    """測試截取 30 秒參考音訊"""
    # 先提取完整音訊
    full_wav = str(tmp_path / "audio.wav")
    subprocess.run(
        [".venv/bin/python", "scripts/extract_audio.py",
         "/home/joshhu/workspace/autovoice/test.mp4", full_wav],
        cwd="/home/joshhu/workspace/autovoice"
    )

    ref_wav = str(tmp_path / "ref_30s.wav")
    result = subprocess.run(
        [".venv/bin/python", "scripts/clip_reference.py", full_wav, ref_wav],
        capture_output=True, text=True,
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(ref_wav)

    data, sr = sf.read(ref_wav)
    duration = len(data) / sr
    # 允許 ±1 秒誤差
    assert 29 <= duration <= 31, f"時長應為 30 秒，實際: {duration:.1f}"

def test_clip_custom_start(tmp_path):
    """測試自訂截取起始點"""
    full_wav = str(tmp_path / "audio.wav")
    subprocess.run(
        [".venv/bin/python", "scripts/extract_audio.py",
         "/home/joshhu/workspace/autovoice/test.mp4", full_wav],
        cwd="/home/joshhu/workspace/autovoice"
    )

    ref_wav = str(tmp_path / "ref_custom.wav")
    result = subprocess.run(
        [".venv/bin/python", "scripts/clip_reference.py", full_wav, ref_wav, "20", "15"],
        capture_output=True, text=True,
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0
    assert os.path.exists(ref_wav)

    data, sr = sf.read(ref_wav)
    duration = len(data) / sr
    assert 14 <= duration <= 16, f"時長應為 15 秒，實際: {duration:.1f}"
