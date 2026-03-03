# AutoVoice Skill 設計文件

**日期：** 2026-03-03
**專案：** AutoVoice - 影片聲音克隆配音 Claude Code Skill

---

## 概覽

將 AutoVoice 實作為 Claude Code 的 `/autovoice` skill。
使用者在 Claude Code 中執行 `/autovoice <影片路徑或YouTube URL>`，
Claude 作為 orchestrator，依序透過 Bash 工具呼叫 Python 腳本，
翻譯和校對則使用 Claude 自身的 LLM 能力。

---

## 架構

```
autovoice/
├── .claude/
│   └── skills/
│       └── autovoice/
│           └── SKILL.md        ← /autovoice skill 定義
├── scripts/
│   ├── extract_audio.py        ← 從影片提取完整音訊
│   ├── clip_reference.py       ← 截取 30 秒參考音訊
│   ├── run_whisper.py          ← Whisper Large-v3 語音辨識
│   ├── run_tts.py              ← Qwen3-TTS Base 聲音克隆 + 合成
│   └── merge_audio.py          ← 將新音軌合回影片
├── pyproject.toml              ← uv 依賴管理
├── app.py                      ← 現有 Qwen3-TTS 參考實作
└── CLAUDE.md
```

---

## 技術選型

| 功能         | 技術                        | 理由                              |
|--------------|-----------------------------|------------------------------------|
| 影片下載     | yt-dlp                      | 系統已安裝，支援 YouTube           |
| 音訊提取     | ffmpeg (Bash)               | 系統已安裝，零依賴                 |
| 語音辨識 ASR | faster-whisper large-v3     | 比原版 whisper 快 4x，VRAM 更省   |
| 文字校對     | Claude LLM (內建)           | 零 API 成本，Claude Code 原生能力 |
| 翻譯         | Claude LLM (內建)           | 零 API 成本，支援所有語言          |
| 語音克隆 TTS | Qwen3-TTS Base (app.py 參考) | 高品質聲音克隆                    |
| 音訊合成     | ffmpeg (Bash)               | 系統已安裝                         |
| 套件管理     | uv + .venv                  | 使用者偏好                         |

---

## 工作流程

```
/autovoice <input> [--lang <語言>]

1. 解析輸入
   - 若為 YouTube URL → yt-dlp 下載影片
   - 若為本機路徑 → 直接使用

2. 提取音訊
   - scripts/extract_audio.py
   - 輸出: output/<basename>/audio.wav (16kHz mono)

3. 截取 30 秒參考音訊
   - scripts/clip_reference.py
   - 從第 10 秒開始截取（跳過片頭）
   - 輸出: output/<basename>/ref_30s.wav

4. ASR 語音辨識
   - scripts/run_whisper.py
   - 使用 faster-whisper large-v3
   - 輸出: output/<basename>/transcript.txt（含時間戳記）

5. 文字校對 [Claude LLM]
   - Claude 讀取 transcript.txt
   - 校正錯字、標點、ASR 誤辨識
   - 儲存: output/<basename>/transcript_corrected.txt

6. 詢問目標語言
   - 若未指定 --lang，詢問使用者
   - 支援: 中文/日文/英文/韓文/法文/德文/西班牙文/葡萄牙文

7. 翻譯 [Claude LLM]
   - Claude 將校對後文字翻譯成目標語言
   - 儲存: output/<basename>/transcript_<lang>.txt

8. 語音克隆 + TTS
   - scripts/run_tts.py
   - 使用 ref_30s.wav 作為聲音參考
   - 使用翻譯後文字合成語音
   - 輸出: output/<basename>/dubbed_<lang>.wav

9. 合成配音影片
   - scripts/merge_audio.py
   - 將 dubbed_<lang>.wav 替換原始音軌
   - 輸出: output/<basename>/<basename>_dubbed_<lang>.mp4

10. 完成報告
    - 顯示輸出檔案路徑和處理摘要
```

---

## Python 依賴（pyproject.toml）

```toml
[project]
name = "autovoice"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "faster-whisper",
    "torch",
    "torchaudio",
    "qwen-tts",          # Qwen3-TTS
    "transformers",
    "ffmpeg-python",
    "soundfile",
    "numpy",
]
```

---

## SKILL.md 觸發條件

- 使用者提到「配音」「dubbing」「語音克隆」「翻譯影片」
- 使用者輸入 `/autovoice`
- 使用者提供影片路徑或 YouTube URL 並要求翻譯配音

---

## 錯誤處理

| 情境                      | 處理方式                               |
|---------------------------|----------------------------------------|
| 影片沒有音訊              | 報錯並提示                             |
| VRAM 不足                 | 建議分段處理或使用較小模型             |
| Whisper 辨識語言不確定    | 顯示信心分數，詢問使用者確認           |
| 翻譯文字長度超過 TTS 限制 | 自動分段合成後串接                     |
| yt-dlp 下載失敗           | 提示網路或版權問題                     |

---

## 輸出目錄結構

```
output/
└── test/
    ├── audio.wav                    ← 提取的完整音訊
    ├── ref_30s.wav                  ← 30 秒參考音訊
    ├── transcript.txt               ← 原始 ASR 結果（含時間戳）
    ├── transcript_corrected.txt     ← Claude 校對後
    ├── transcript_ja.txt            ← 日文翻譯
    ├── dubbed_ja.wav                ← 克隆聲音讀日文
    └── test_dubbed_ja.mp4           ← 最終配音影片
```
