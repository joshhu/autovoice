# AutoVoice 🎙️

> AI 驅動的影片配音工具：自動克隆說話者聲音，翻譯並重新配音

AutoVoice 能將任何影片的說話聲音克隆，透過 AI 翻譯成目標語言後，用**相同音色**重新配音並輸出新影片。

## 功能特色

- **聲音克隆**：使用 [Qwen3-TTS 1.7B Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base) 克隆說話者音色
- **語音辨識**：使用 [Whisper Large-v3](https://huggingface.co/openai/whisper-large-v3) 辨識原始語音內容
- **時間軸對齊**：逐句合成，每句配音精準對準原始說話時間點
- **自動校速**：若合成語音過長，自動微調語速以符合時間窗口
- **YouTube 支援**：直接輸入 YouTube URL 下載後配音
- **Claude Code Skill**：整合為 `/autovoice` 指令，在 Claude Code 中一鍵執行

## 支援語言

| 代碼 | 語言 |
|------|------|
| `zh` | 中文 |
| `ja` | 日文 |
| `en` | 英文 |
| `ko` | 韓文 |
| `fr` | 法文 |
| `de` | 德文 |
| `es` | 西班牙文 |
| `pt` | 葡萄牙文 |
| `ru` | 俄文 |

> ⚠️ **跨語言克隆限制**：Qwen3-TTS 對「中文音訊 → 其他語言」的跨語言克隆效果最佳。以其他語言（如日文）為來源時，輸出品質可能下降。

## 架構圖

```
輸入影片 / YouTube URL
        │
        ▼
┌─────────────────┐
│  extract_audio  │  ffmpeg 提取音訊軌道
└────────┬────────┘
         │ audio.wav
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌─────────────┐
│  clip   │ │ run_whisper │  同時進行
│reference│ │  (ASR)      │
└────┬────┘ └──────┬──────┘
     │              │
ref_30s.wav   transcript.json
     │              │
     │         ┌────┴────────────────┐
     │         │  Claude LLM         │
     │         │  ・校對文字          │
     │         │  ・翻譯至目標語言    │
     │         └────┬────────────────┘
     │              │ segments_<lang>.json
     │              │
     └──────┬───────┘
            ▼
┌─────────────────────┐
│  run_tts_aligned    │  Qwen3-TTS 逐句合成
│  （逐句 + 時間軸）   │  + 自動校速
└──────────┬──────────┘
           │ dubbed_<lang>.wav
           ▼
┌─────────────────────┐
│    merge_audio      │  ffmpeg 合入影片
└──────────┬──────────┘
           │
           ▼
    輸出配音影片 🎬
```

## 環境需求

- **OS**：Linux（推薦 Ubuntu 22.04+）
- **GPU**：NVIDIA GPU，VRAM ≥ 8GB（1.7B 模型）或 ≥ 4GB（0.6B 模型）
- **Python**：3.12+
- **套件管理**：[uv](https://docs.astral.sh/uv/)
- **系統工具**：`ffmpeg`、`yt-dlp`

## 安裝

### 1. 安裝系統相依套件

```bash
sudo apt install ffmpeg
pip install yt-dlp
```

### 2. 建立 Python 虛擬環境

```bash
git clone https://github.com/YOUR_USERNAME/autovoice.git
cd autovoice
uv sync
```

### 3. 安裝 Qwen3-TTS（需另行安裝）

```bash
# Qwen3-TTS 尚未在 PyPI 上架，請依官方說明安裝
# https://github.com/QwenLM/Qwen3-TTS
.venv/bin/pip install git+https://github.com/QwenLM/Qwen3-TTS.git
```

> 模型會在第一次執行時自動從 Hugging Face 下載（約 3–7GB）

## 使用方式

### 方式一：Claude Code Skill（推薦）

將 `.claude/` 目錄複製到你的 Claude Code 專案中，即可使用 `/autovoice` 指令：

```
/autovoice video.mp4 --lang ja
/autovoice https://www.youtube.com/watch?v=xxxxx --lang en
```

Claude 會自動完成所有步驟並輸出配音影片。

### 方式二：手動執行腳本

```bash
BASENAME="myvideo"
mkdir -p output/$BASENAME

# 步驟 1：提取音訊
.venv/bin/python scripts/extract_audio.py myvideo.mp4 output/$BASENAME/audio.wav

# 步驟 2：截取參考音訊（前 30 秒）
.venv/bin/python scripts/clip_reference.py \
  output/$BASENAME/audio.wav \
  output/$BASENAME/ref_30s.wav \
  0 30

# 步驟 3：語音辨識
.venv/bin/python scripts/run_whisper.py \
  output/$BASENAME/audio.wav \
  output/$BASENAME/transcript.json

# 步驟 4：準備時間軸翻譯 JSON（格式見下方說明）
# 手動或由 Claude 翻譯後寫入 output/$BASENAME/segments_ja.json

# 步驟 5：逐句合成配音（對齊時間軸）
.venv/bin/python scripts/run_tts_aligned.py \
  output/$BASENAME/ref_30s.wav \
  output/$BASENAME/ref_30s_transcript.txt \
  output/$BASENAME/segments_ja.json \
  Japanese \
  output/$BASENAME/dubbed_ja.wav \
  1.7B \
  <影片總秒數>

# 步驟 6：合成配音影片
.venv/bin/python scripts/merge_audio.py \
  myvideo.mp4 \
  output/$BASENAME/dubbed_ja.wav \
  output/$BASENAME/myvideo_dubbed_ja.mp4
```

## 腳本說明

### `scripts/extract_audio.py`

從影片提取音訊軌道為 WAV 格式。

```
用法: python extract_audio.py <input_video> <output_wav>
```

### `scripts/clip_reference.py`

截取音訊中的一段作為聲音克隆參考（建議 30 秒）。

```
用法: python clip_reference.py <input_wav> <output_wav> [start_sec] [duration_sec]
預設: 從第 0 秒開始，截取 30 秒
```

### `scripts/run_whisper.py`

使用 Whisper Large-v3 進行語音辨識，輸出帶時間戳的 JSON 和純文字。

```
用法: python run_whisper.py <input_wav> <output_json>

輸出:
  output.json  - 含時間戳的完整結果
  output.txt   - 純文字逐字稿
```

### `scripts/run_tts.py`

使用 Qwen3-TTS 聲音克隆，一次合成完整文字。

```
用法: python run_tts.py <ref_wav> <ref_txt> <target_text> <language> <output_wav> [model_size]
  model_size: 0.6B 或 1.7B（預設 1.7B）
```

### `scripts/run_tts_aligned.py`

逐句合成並對齊時間軸，適合完整影片配音。

```
用法: python run_tts_aligned.py <ref_wav> <ref_txt> <segments_json> <language> <output_wav> [model_size] [total_duration]

segments_json 格式:
[
  {
    "start": 0.0,
    "end": 6.0,
    "original": "原文句子",
    "translated": "翻譯後句子"
  },
  ...
]
```

當合成語音超過可用時間窗口時，自動使用 `ffmpeg atempo` 加速（最多支援任意倍速，自動串接多個 atempo 濾鏡）。

### `scripts/merge_audio.py`

將配音音訊合入影片，取代原始音軌。若配音比影片短，自動補靜音至影片結尾。

```
用法: python merge_audio.py <input_video> <dubbed_audio> <output_video>
```

## 輸出目錄結構

```
output/
└── <basename>/
    ├── audio.wav                  # 完整音訊
    ├── ref_30s.wav                # 聲音克隆參考音訊
    ├── ref_30s_transcript.txt     # 參考音訊文字稿
    ├── transcript.json            # Whisper 辨識結果（含時間戳）
    ├── transcript.txt             # 純文字逐字稿
    ├── transcript_corrected.txt   # 校對後文字稿
    ├── segments_<lang>.json       # 逐句翻譯 + 時間軸
    ├── dubbed_<lang>.wav          # 配音音訊
    └── <basename>_dubbed_<lang>.mp4  # 最終配音影片
```

## Gradio Demo

`app.py` 提供 Qwen3-TTS 的網頁介面，支援：
- **Voice Design**：用自然語言描述聲音特徵後合成
- **Voice Clone**：上傳參考音訊克隆聲音
- **CustomVoice**：使用預設說話者（Aiden、Ryan、Vivian 等）

```bash
.venv/bin/python app.py
```

## 常見問題

**Q：VRAM 不夠用怎麼辦？**

改用 0.6B 模型，在 `run_tts.py` 或 `run_tts_aligned.py` 的最後一個參數改為 `0.6B`。

**Q：配音和影片對不上時間？**

使用 `run_tts_aligned.py` 搭配 `segments_<lang>.json`（含時間戳的逐句翻譯），而非 `run_tts.py`（一次合成全部）。

**Q：支援哪些影片格式？**

任何 `ffmpeg` 支援的格式均可，包括 MP4、MKV、AVI、MOV 等。

**Q：YouTube 影片需要登入？**

使用 `yt-dlp --cookies-from-browser chrome` 帶入瀏覽器 Cookie。

## 授權

MIT License

---

Made with ❤️ using [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) + [Whisper](https://github.com/openai/whisper) + [Claude Code](https://claude.ai/claude-code)
