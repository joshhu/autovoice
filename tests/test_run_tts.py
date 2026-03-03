# tests/test_run_tts.py
# Smoke test：確認 Qwen3-TTS 聲音克隆能執行並輸出音訊
import subprocess
import os
import soundfile as sf
import pytest
import tempfile


@pytest.mark.integration
def test_tts_clone_creates_audio(tmp_path):
    """Smoke test: 確認 Qwen3-TTS 聲音克隆能執行並輸出音訊"""
    # 先建立 30 秒參考音訊
    ref_wav = str(tmp_path / "ref_30s.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i",
        "/home/joshhu/workspace/autovoice/test.mp4",
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-ss", "10", "-t", "30",
        ref_wav
    ], capture_output=True, check=True)

    # 建立參考文字檔（用簡短文字）
    ref_txt = str(tmp_path / "ref.txt")
    with open(ref_txt, "w", encoding="utf-8") as f:
        f.write("這是參考音訊的文字內容，用於聲音克隆。")

    output_wav = str(tmp_path / "dubbed.wav")
    # 用短文字測試（避免等太久）
    test_text = "你好，這是聲音克隆測試。"

    result = subprocess.run(
        [
            "/home/joshhu/workspace/autovoice/.venv/bin/python", "scripts/run_tts.py",
            ref_wav, ref_txt,
            test_text, "Chinese",
            output_wav,
            "0.6B"  # 使用較小模型加快測試
        ],
        capture_output=True, text=True,
        timeout=600,  # 10 分鐘 timeout（含模型下載）
        cwd="/home/joshhu/workspace/autovoice"
    )

    assert result.returncode == 0, f"錯誤:\n{result.stderr}\n輸出:\n{result.stdout}"
    assert os.path.exists(output_wav), "音訊檔案未建立"

    data, sr = sf.read(output_wav)
    assert len(data) > 0, "輸出音訊是空的"
    duration = len(data) / sr
    print(f"輸出時長: {duration:.1f} 秒, 取樣率: {sr}")
    assert duration > 0.5, "輸出太短"
