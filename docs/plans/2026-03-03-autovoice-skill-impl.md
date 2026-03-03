# AutoVoice Skill 實作計劃

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建立 `/autovoice` Claude Code Skill，自動從影片提取聲音、克隆人聲、翻譯並配音回影片。

**Architecture:** 各功能拆成獨立 Python 腳本，由 SKILL.md 指導 Claude 依序用 Bash 呼叫；翻譯與校對直接使用 Claude 內建 LLM；各腳本獨立執行避免 VRAM 衝突。

**Tech Stack:** faster-whisper (ASR), Qwen3-TTS Base (voice clone), ffmpeg (音訊/影片), uv (套件管理), Claude LLM (翻譯/校對)

---

## Task 1：建立 Python 環境

**Files:**
- Create: `pyproject.toml`

**Step 1: 建立 pyproject.toml**

```toml
[project]
name = "autovoice"
version = "0.1.0"
description = "影片聲音克隆配音工具"
requires-python = ">=3.12"
dependencies = [
    "faster-whisper>=1.1.0",
    "soundfile>=0.12.1",
    "numpy>=1.26.0",
    "torch>=2.2.0",
    "torchaudio>=2.2.0",
    "huggingface-hub>=0.25.0",
    "transformers>=4.46.0",
    "qwen-tts",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
]
```

**Step 2: 建立虛擬環境並安裝**

```bash
cd /home/joshhu/workspace/autovoice
uv venv
uv sync
```

Expected: `.venv/` 建立完成，所有套件安裝成功

**Step 3: 確認 qwen-tts 安裝方式**

```bash
uv pip install git+https://github.com/QwenLM/Qwen3-TTS.git || \
  uv pip install qwen-tts
```

若兩者皆失敗，從 app.py 所在位置安裝：
```bash
# 確認 app.py 中的 qwen_tts 模組來源
pip show qwen-tts 2>/dev/null || echo "需要從 GitHub 安裝"
```

**Step 4: 建立必要目錄**

```bash
mkdir -p /home/joshhu/workspace/autovoice/scripts
mkdir -p /home/joshhu/workspace/autovoice/output
mkdir -p /home/joshhu/workspace/autovoice/.claude/skills/autovoice
```

---

## Task 2：音訊提取腳本

**Files:**
- Create: `scripts/extract_audio.py`
- Test: `tests/test_extract_audio.py`

**Step 1: 寫測試（先寫）**

```python
# tests/test_extract_audio.py
import subprocess
import os
import pytest

def test_extract_audio_creates_wav(tmp_path):
    """測試能從 MP4 提取 WAV 音訊"""
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    output_wav = str(tmp_path / "audio.wav")

    result = subprocess.run(
        ["python", "scripts/extract_audio.py", input_video, output_wav],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(output_wav), "WAV 檔案未建立"
    assert os.path.getsize(output_wav) > 1000, "WAV 檔案太小"

def test_extract_audio_correct_format(tmp_path):
    """測試輸出格式為 16kHz mono"""
    import soundfile as sf
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    output_wav = str(tmp_path / "audio.wav")

    subprocess.run(["python", "scripts/extract_audio.py", input_video, output_wav])

    data, samplerate = sf.read(output_wav)
    assert samplerate == 16000, f"取樣率應為 16000，實際: {samplerate}"
    assert data.ndim == 1, "應為 mono（一維陣列）"
```

**Step 2: 跑測試確認失敗**

```bash
cd /home/joshhu/workspace/autovoice
source .venv/bin/activate
pytest tests/test_extract_audio.py -v
```

Expected: FAIL with "No such file or directory" (腳本還不存在)

**Step 3: 實作腳本**

```python
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

    print(f"✓ 音訊提取完成: {output_wav}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python extract_audio.py <input_video> <output_wav>")
        sys.exit(1)
    extract_audio(sys.argv[1], sys.argv[2])
```

**Step 4: 跑測試確認通過**

```bash
pytest tests/test_extract_audio.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/extract_audio.py tests/test_extract_audio.py pyproject.toml
git commit -m "feat: 新增音訊提取腳本與測試"
```

---

## Task 3：30 秒參考音訊截取腳本

**Files:**
- Create: `scripts/clip_reference.py`
- Test: `tests/test_clip_reference.py`

**Step 1: 寫測試**

```python
# tests/test_clip_reference.py
import subprocess
import os
import soundfile as sf
import pytest

def test_clip_creates_30s_wav(tmp_path):
    """測試截取 30 秒參考音訊"""
    # 先提取完整音訊
    full_wav = str(tmp_path / "audio.wav")
    subprocess.run([
        "python", "scripts/extract_audio.py",
        "/home/joshhu/workspace/autovoice/test.mp4", full_wav
    ])

    ref_wav = str(tmp_path / "ref_30s.wav")
    result = subprocess.run(
        ["python", "scripts/clip_reference.py", full_wav, ref_wav],
        capture_output=True, text=True
    )

    assert result.returncode == 0
    assert os.path.exists(ref_wav)

    data, sr = sf.read(ref_wav)
    duration = len(data) / sr
    # 允許 ±1 秒誤差
    assert 29 <= duration <= 31, f"時長應為 30 秒，實際: {duration:.1f}"
```

**Step 2: 跑測試確認失敗**

```bash
pytest tests/test_clip_reference.py -v
```

Expected: FAIL

**Step 3: 實作腳本**

```python
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

    print(f"✓ 參考音訊截取完成: {output_wav}")
    print(f"  從 {start_sec}s 開始，共 {duration_sec} 秒")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python clip_reference.py <input_wav> <output_wav> [start_sec] [duration]")
        sys.exit(1)
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    dur = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    clip_reference(sys.argv[1], sys.argv[2], start, dur)
```

**Step 4: 跑測試確認通過**

```bash
pytest tests/test_clip_reference.py -v
```

**Step 5: Commit**

```bash
git add scripts/clip_reference.py tests/test_clip_reference.py
git commit -m "feat: 新增 30 秒參考音訊截取腳本"
```

---

## Task 4：Whisper ASR 語音辨識腳本

**Files:**
- Create: `scripts/run_whisper.py`
- Test: `tests/test_run_whisper.py` (smoke test)

**Step 1: 寫 smoke test（不測試準確率，只測試腳本能執行）**

```python
# tests/test_run_whisper.py
import subprocess
import os
import json
import pytest

@pytest.mark.integration
def test_whisper_creates_transcript(tmp_path):
    """Smoke test: 確認 Whisper 能執行並輸出結果"""
    # 先準備參考音訊
    audio_wav = str(tmp_path / "audio.wav")
    subprocess.run([
        "python", "scripts/extract_audio.py",
        "/home/joshhu/workspace/autovoice/test.mp4", audio_wav
    ])

    transcript_json = str(tmp_path / "transcript.json")
    result = subprocess.run(
        ["python", "scripts/run_whisper.py", audio_wav, transcript_json],
        capture_output=True, text=True,
        timeout=300  # 5 分鐘 timeout
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(transcript_json), "JSON 結果未建立"

    with open(transcript_json) as f:
        data = json.load(f)

    assert "language" in data
    assert "text" in data
    assert "segments" in data
    assert len(data["text"]) > 0, "文字不應為空"
```

**Step 2: 跑測試確認失敗**

```bash
pytest tests/test_run_whisper.py -v -m integration
```

**Step 3: 實作腳本**

```python
#!/usr/bin/env python3
# scripts/run_whisper.py
# 使用 faster-whisper Large-v3 進行語音辨識
import sys
import json
import os

def transcribe(input_wav: str, output_json: str,
               model_size: str = "large-v3") -> dict:
    """使用 faster-whisper 轉錄音訊"""
    from faster_whisper import WhisperModel

    print(f"載入 Whisper {model_size} 模型...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    print(f"開始辨識: {input_wav}")
    segments, info = model.transcribe(
        input_wav,
        beam_size=5,
        vad_filter=True,          # 過濾靜音段
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    # 收集所有片段
    segments_list = []
    full_text_parts = []

    for seg in segments:
        segments_list.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())
        print(f"  [{seg.start:.1f}s → {seg.end:.1f}s] {seg.text.strip()}")

    result = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "text": " ".join(full_text_parts),
        "segments": segments_list,
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 辨識完成")
    print(f"  語言: {info.language} (信心: {info.language_probability:.1%})")
    print(f"  段落數: {len(segments_list)}")
    print(f"  結果: {output_json}")

    # 同時輸出純文字版
    txt_path = output_json.replace(".json", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result["text"])
    print(f"  純文字: {txt_path}")

    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python run_whisper.py <input_wav> <output_json> [model_size]")
        print("  model_size: large-v3 (預設), medium, small")
        sys.exit(1)

    model = sys.argv[3] if len(sys.argv) > 3 else "large-v3"
    transcribe(sys.argv[1], sys.argv[2], model)
```

**Step 4: 跑 smoke test（需要 GPU，約 2-5 分鐘）**

```bash
pytest tests/test_run_whisper.py -v -m integration -s
```

Expected: PASS，顯示辨識進度

**Step 5: Commit**

```bash
git add scripts/run_whisper.py tests/test_run_whisper.py
git commit -m "feat: 新增 Whisper Large-v3 ASR 腳本"
```

---

## Task 5：Qwen3-TTS 聲音克隆 + 合成腳本

**Files:**
- Create: `scripts/run_tts.py`
- Test: `tests/test_run_tts.py` (smoke test)

**Step 1: 研讀 app.py 中的 voice clone 模式**

確認以下函數簽名（來自 app.py）：
```python
# app.py 第 112-128 行的模式
wavs, sr = tts.generate_voice_clone(
    text=target_text.strip(),   # 要朗讀的翻譯文字
    language=language,           # "Chinese", "Japanese", "English" 等
    ref_audio=audio_tuple,       # (wav_array_float32, sample_rate)
    ref_text=ref_text.strip(),   # 30秒參考音訊的文字稿（ASR 結果）
    x_vector_only_mode=False,    # False = 使用 ref_text（更高品質）
    max_new_tokens=2048,
)
```

**Step 2: 寫 smoke test**

```python
# tests/test_run_tts.py
import subprocess
import os
import soundfile as sf
import pytest

@pytest.mark.integration
def test_tts_creates_audio(tmp_path):
    """Smoke test: 確認 TTS 能執行並輸出音訊"""
    ref_wav = "/home/joshhu/workspace/autovoice/output/test/ref_30s.wav"
    ref_txt = "/home/joshhu/workspace/autovoice/output/test/ref_30s_transcript.txt"

    # 若參考檔案不存在，跳過（需先執行前面的步驟）
    if not os.path.exists(ref_wav) or not os.path.exists(ref_txt):
        pytest.skip("先執行 Task 2-4 建立參考檔案")

    output_wav = str(tmp_path / "dubbed.wav")
    test_text = "這是一個聲音克隆測試。"

    result = subprocess.run(
        [
            "python", "scripts/run_tts.py",
            ref_wav, ref_txt,
            test_text, "Chinese",
            output_wav
        ],
        capture_output=True, text=True, timeout=300
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(output_wav)

    data, sr = sf.read(output_wav)
    assert len(data) > 0
    print(f"輸出音訊: {len(data)/sr:.1f} 秒")
```

**Step 3: 跑測試確認失敗**

```bash
pytest tests/test_run_tts.py -v -m integration
```

**Step 4: 實作腳本（參考 app.py 模式）**

```python
#!/usr/bin/env python3
# scripts/run_tts.py
# 使用 Qwen3-TTS Base 進行聲音克隆與文字合成
# 參考 app.py 的 generate_voice_clone 用法
import sys
import os
import numpy as np
import soundfile as sf

# 語言名稱對應表（Qwen3-TTS 使用英文語言名）
LANG_MAP = {
    "zh": "Chinese", "chinese": "Chinese", "中文": "Chinese",
    "ja": "Japanese", "japanese": "Japanese", "日文": "Japanese", "日語": "Japanese",
    "en": "English", "english": "English", "英文": "English",
    "ko": "Korean", "korean": "Korean", "韓文": "Korean",
    "fr": "French", "french": "French", "法文": "French",
    "de": "German", "german": "German", "德文": "German",
    "es": "Spanish", "spanish": "Spanish", "西班牙文": "Spanish",
    "pt": "Portuguese", "portuguese": "Portuguese", "葡萄牙文": "Portuguese",
}

def normalize_language(lang: str) -> str:
    """將各種語言名稱標準化為 Qwen3-TTS 格式"""
    return LANG_MAP.get(lang.lower(), lang.capitalize())

def load_audio(wav_path: str) -> tuple:
    """載入 WAV 為 float32 陣列"""
    data, sr = sf.read(wav_path, dtype="float32")
    if data.ndim > 1:
        data = np.mean(data, axis=-1)
    return data, int(sr)

def split_text(text: str, max_chars: int = 200) -> list[str]:
    """將長文字按句子分割，避免超過 TTS 限制"""
    import re
    # 按標點符號分句
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)

    chunks = []
    current = ""
    for sent in sentences:
        if not sent.strip():
            continue
        if len(current) + len(sent) <= max_chars:
            current += sent + " "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sent + " "
    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]

def run_tts_clone(
    ref_wav_path: str,
    ref_text_path: str,
    target_text: str,
    language: str,
    output_wav_path: str,
    model_size: str = "1.7B",
) -> None:
    """使用聲音克隆合成目標文字"""
    import torch
    from huggingface_hub import snapshot_download
    from qwen_tts import Qwen3TTSModel

    # 標準化語言名稱
    lang = normalize_language(language)

    # 讀取參考音訊和文字
    ref_audio = load_audio(ref_wav_path)
    with open(ref_text_path, encoding="utf-8") as f:
        ref_text = f.read().strip()

    print(f"載入 Qwen3-TTS Base {model_size} 模型...")
    model_path = snapshot_download(f"Qwen/Qwen3-TTS-12Hz-{model_size}-Base")
    tts = Qwen3TTSModel.from_pretrained(
        model_path,
        device_map="cuda",
        dtype=torch.bfloat16,
        attn_implementation="kernels-community/flash-attn3",
    )

    # 分割長文字
    chunks = split_text(target_text)
    print(f"文字分為 {len(chunks)} 段合成")

    all_wavs = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  合成第 {i}/{len(chunks)} 段: {chunk[:30]}...")
        wavs, sr = tts.generate_voice_clone(
            text=chunk,
            language=lang,
            ref_audio=ref_audio,
            ref_text=ref_text,
            x_vector_only_mode=False,
            max_new_tokens=2048,
        )
        all_wavs.append(wavs[0])

    # 串接所有音訊片段
    combined = np.concatenate(all_wavs) if len(all_wavs) > 1 else all_wavs[0]

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    sf.write(output_wav_path, combined, sr)

    duration = len(combined) / sr
    print(f"\n✓ 合成完成: {output_wav_path}")
    print(f"  時長: {duration:.1f} 秒，語言: {lang}")

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("用法: python run_tts.py <ref_wav> <ref_txt> <target_text> <language> <output_wav> [model_size]")
        sys.exit(1)

    model = sys.argv[6] if len(sys.argv) > 6 else "1.7B"
    run_tts_clone(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], model)
```

**Step 5: 跑 smoke test**

```bash
pytest tests/test_run_tts.py -v -m integration -s
```

**Step 6: Commit**

```bash
git add scripts/run_tts.py tests/test_run_tts.py
git commit -m "feat: 新增 Qwen3-TTS 聲音克隆腳本"
```

---

## Task 6：配音合成腳本

**Files:**
- Create: `scripts/merge_audio.py`
- Test: `tests/test_merge_audio.py`

**Step 1: 寫測試**

```python
# tests/test_merge_audio.py
import subprocess
import os
import pytest

def test_merge_creates_video(tmp_path):
    """測試能將新音訊合回影片"""
    input_video = "/home/joshhu/workspace/autovoice/test.mp4"
    dubbed_audio = str(tmp_path / "dubbed.wav")
    output_video = str(tmp_path / "output.mp4")

    # 先建立假的配音 WAV（用原始音訊代替）
    subprocess.run([
        "ffmpeg", "-y", "-i", input_video,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-t", "10",  # 只取前 10 秒
        dubbed_audio
    ], capture_output=True)

    result = subprocess.run(
        ["python", "scripts/merge_audio.py", input_video, dubbed_audio, output_video],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"錯誤: {result.stderr}"
    assert os.path.exists(output_video)
    assert os.path.getsize(output_video) > 1000
```

**Step 2: 跑測試確認失敗**

```bash
pytest tests/test_merge_audio.py -v
```

**Step 3: 實作腳本**

```python
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
        "-c:v", "copy",       # 影像直接複製，不重新編碼
        "-c:a", "aac",        # 音訊轉 AAC
        "-b:a", "192k",
        "-map", "0:v:0",      # 取第一個輸入的影像
        "-map", "1:a:0",      # 取第二個輸入的音訊
        "-shortest",          # 以較短的串流為準
        output_video
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg 錯誤: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(output_video) / 1024 / 1024
    print(f"✓ 配音影片完成: {output_video} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python merge_audio.py <input_video> <dubbed_audio> <output_video>")
        sys.exit(1)
    merge_audio(sys.argv[1], sys.argv[2], sys.argv[3])
```

**Step 4: 跑測試確認通過**

```bash
pytest tests/test_merge_audio.py -v
```

**Step 5: Commit**

```bash
git add scripts/merge_audio.py tests/test_merge_audio.py
git commit -m "feat: 新增配音合成腳本"
```

---

## Task 7：建立 /autovoice Claude Code Skill

**Files:**
- Create: `.claude/skills/autovoice/SKILL.md`

**Step 1: 建立目錄**

```bash
mkdir -p /home/joshhu/workspace/autovoice/.claude/skills/autovoice
```

**Step 2: 撰寫 SKILL.md**

```markdown
---
name: autovoice
description: Use when the user wants to dub a video into another language using voice cloning. Triggered by video file path, YouTube URL, or requests for dubbing, voice cloning, or translated narration.
---

# AutoVoice - 影片聲音克隆配音

## 概覽

將影片中的說話聲音克隆，翻譯成指定語言後重新配音，輸出配音影片。

## 環境確認

在開始前確認環境就緒：
```bash
cd /home/joshhu/workspace/autovoice
source .venv/bin/activate 2>/dev/null || (uv venv && uv sync && source .venv/bin/activate)
```

## 輸入解析

接受以下格式：
- 本機影片路徑：`/path/to/video.mp4`
- YouTube URL：`https://www.youtube.com/watch?v=...`
- 帶語言參數：`/autovoice video.mp4 --lang ja`

若輸入為 YouTube URL，先下載：
```bash
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" \
  --merge-output-format mp4 \
  -o "output/%(title)s.%(ext)s" \
  <YouTube_URL>
```

## 執行流程

**BASENAME** = 影片檔名（不含副檔名）

### 步驟 1：提取音訊
```bash
python scripts/extract_audio.py \
  <input_video> \
  output/<BASENAME>/audio.wav
```

### 步驟 2：截取 30 秒參考音訊
```bash
python scripts/clip_reference.py \
  output/<BASENAME>/audio.wav \
  output/<BASENAME>/ref_30s.wav
```

### 步驟 3：語音辨識（Whisper Large-v3）
```bash
python scripts/run_whisper.py \
  output/<BASENAME>/audio.wav \
  output/<BASENAME>/transcript.json
```

辨識完成後讀取 `output/<BASENAME>/transcript.txt`，顯示辨識到的語言和前 200 字給使用者確認。

### 步驟 4：文字校對（Claude LLM）

讀取 `output/<BASENAME>/transcript.txt`，作為 Claude 直接校對：
- 修正錯別字
- 修正標點符號
- 修正明顯的 ASR 誤辨識（諧音錯誤）
- 保持原文意思不變

將校對後文字存入 `output/<BASENAME>/transcript_corrected.txt`

同時，截取前 30 秒對應的文字，存入 `output/<BASENAME>/ref_30s_transcript.txt`
（從 transcript.json 的 segments 中找出 0-30 秒的片段）

### 步驟 5：詢問目標語言

若使用者未指定 `--lang`，詢問：
「原始語言為 [辨識語言]，請問要配音成哪種語言？（例如：日文、英文、韓文、法文）」

### 步驟 6：翻譯（Claude LLM）

將 `transcript_corrected.txt` 翻譯成目標語言：
- 保持說話風格和語氣
- 適合口語朗讀（不要太書面）
- 注意句子長度，太長要拆開

將翻譯結果存入 `output/<BASENAME>/transcript_<lang_code>.txt`

### 步驟 7：聲音克隆 + 合成

```bash
python scripts/run_tts.py \
  output/<BASENAME>/ref_30s.wav \
  output/<BASENAME>/ref_30s_transcript.txt \
  "$(cat output/<BASENAME>/transcript_<lang_code>.txt)" \
  <TARGET_LANGUAGE> \
  output/<BASENAME>/dubbed_<lang_code>.wav
```

TARGET_LANGUAGE 使用英文名稱：Chinese, Japanese, English, Korean, French, German, Spanish, Portuguese

### 步驟 8：合成配音影片

```bash
python scripts/merge_audio.py \
  <input_video> \
  output/<BASENAME>/dubbed_<lang_code>.wav \
  output/<BASENAME>/<BASENAME>_dubbed_<lang_code>.mp4
```

### 步驟 9：完成報告

顯示：
- 輸出影片路徑
- 原始語言 → 目標語言
- 配音時長
- 所有中間檔案位置

## 錯誤處理

| 情境 | 處理方式 |
|------|----------|
| VRAM 不足 | 改用 0.6B 模型：在 run_tts.py 加上 `0.6B` 參數 |
| 影片無音訊 | 告知使用者並停止 |
| Whisper 語言信心 < 80% | 顯示警告，詢問使用者確認語言 |
| 翻譯文字過長 | run_tts.py 自動分段合成 |

## 支援語言

中文、日文、英文、韓文、法文、德文、西班牙文、葡萄牙文
```

**Step 3: 驗證 SKILL.md 格式**

```bash
# 確認 SKILL.md frontmatter 正確
head -10 .claude/skills/autovoice/SKILL.md
```

Expected: 顯示 `---`, `name: autovoice`, `description: ...`

**Step 4: 測試 Skill 是否載入**

在 Claude Code 中執行：
```
/autovoice test.mp4 --lang ja
```

觀察 Claude 是否按照 SKILL.md 的步驟依序執行。

**Step 5: Commit**

```bash
git add .claude/skills/autovoice/SKILL.md
git commit -m "feat: 新增 /autovoice Claude Code Skill"
```

---

## Task 8：端到端測試

**Goal:** 用 test.mp4 跑完整流程

**Step 1: 用 test.mp4 執行完整流程**

在 Claude Code 中：
```
/autovoice test.mp4
```

輸入目標語言：日文

**Step 2: 確認輸出**

```bash
ls -la output/test/
# 應看到：
# audio.wav
# ref_30s.wav
# transcript.json + transcript.txt
# transcript_corrected.txt
# ref_30s_transcript.txt
# transcript_ja.txt
# dubbed_ja.wav
# test_dubbed_ja.mp4
```

**Step 3: 播放確認**

```bash
ffplay output/test/test_dubbed_ja.mp4
```

**Step 4: 最終 Commit**

```bash
git add output/.gitkeep
git commit -m "feat: 完成 AutoVoice Skill 端對端測試"
```

---

## 備注

1. **VRAM 管理：** 各腳本獨立執行，run_whisper.py 與 run_tts.py 不會同時佔用 VRAM
2. **長影片：** 超過 10 分鐘的影片，TTS 會自動分段合成後串接
3. **qwen-tts 套件：** 若安裝失敗，參考 app.py 頂部的安裝指令
4. **ref_30s_transcript.txt：** 從 transcript.json 的 segments 中篩選 0-30 秒的文字，這是 Voice Clone 品質的關鍵
