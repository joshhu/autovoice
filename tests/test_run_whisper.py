# tests/test_run_whisper.py
import subprocess
import os
import json
import pytest

@pytest.mark.integration
def test_whisper_creates_transcript(tmp_path):
    """Smoke test: 確認 Whisper 能執行並輸出結果"""
    # 先準備音訊（取前 60 秒加快測試速度）
    audio_wav = str(tmp_path / "audio_short.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i",
        "/home/joshhu/workspace/autovoice/test.mp4",
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", "60",  # 只取前 60 秒加快測試
        audio_wav
    ], capture_output=True)

    transcript_json = str(tmp_path / "transcript.json")
    result = subprocess.run(
        [".venv/bin/python", "scripts/run_whisper.py", audio_wav, transcript_json],
        capture_output=True, text=True,
        timeout=300,  # 5 分鐘 timeout
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}\n輸出: {result.stdout}"
    assert os.path.exists(transcript_json), "JSON 結果未建立"

    with open(transcript_json) as f:
        data = json.load(f)

    assert "language" in data, "缺少 language 欄位"
    assert "text" in data, "缺少 text 欄位"
    assert "segments" in data, "缺少 segments 欄位"
    assert len(data["text"]) > 0, "文字不應為空"
    assert isinstance(data["segments"], list), "segments 應為 list"
    print(f"辨識語言: {data['language']}, 文字長度: {len(data['text'])}")

@pytest.mark.integration
def test_whisper_creates_txt_file(tmp_path):
    """確認同時輸出純文字檔"""
    audio_wav = str(tmp_path / "audio_short.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i",
        "/home/joshhu/workspace/autovoice/test.mp4",
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", "60",
        audio_wav
    ], capture_output=True)

    transcript_json = str(tmp_path / "transcript.json")
    subprocess.run(
        [".venv/bin/python", "scripts/run_whisper.py", audio_wav, transcript_json],
        capture_output=True, text=True, timeout=300,
        cwd="/home/joshhu/workspace/autovoice"
    )

    # 確認純文字檔也建立了
    txt_path = transcript_json.replace(".json", ".txt")
    assert os.path.exists(txt_path), "純文字檔未建立"
    content = open(txt_path).read()
    assert len(content) > 0, "純文字檔不應為空"
