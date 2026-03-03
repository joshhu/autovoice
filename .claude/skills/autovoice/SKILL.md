---
name: autovoice
description: Use when the user wants to dub a video into another language using voice cloning. Triggered by video file paths, YouTube URLs, or requests for dubbing, voice cloning, or translated narration.
---

# AutoVoice - 影片聲音克隆配音

## 概覽

將影片中的說話聲音克隆，翻譯成指定語言後重新配音，輸出配音影片。
使用 Claude 的 Bash 工具執行 Python 腳本，翻譯和校對由 Claude LLM 直接完成。

## 環境確認

每次執行前確認環境：
```bash
cd /home/joshhu/workspace/autovoice
source .venv/bin/activate 2>/dev/null || echo "使用 .venv/bin/python 直接呼叫"
```

## 輸入格式

接受以下輸入：
- 本機影片路徑：`/path/to/video.mp4` 或相對路徑 `test.mp4`
- YouTube URL：`https://www.youtube.com/watch?v=...`
- 帶語言參數：`/autovoice video.mp4 --lang ja`

**YouTube URL 下載：**
```bash
cd /home/joshhu/workspace/autovoice
yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]" \
  --merge-output-format mp4 \
  -o "output/%(title).50s.%(ext)s" \
  <YouTube_URL>
```

## 執行流程

設定：BASENAME = 影片檔名（不含副檔名，不含路徑）
設定：WORKDIR = /home/joshhu/workspace/autovoice

### 步驟 1：提取音訊
```bash
cd /home/joshhu/workspace/autovoice
.venv/bin/python scripts/extract_audio.py \
  <input_video> \
  output/<BASENAME>/audio.wav
```

### 步驟 2：截取 30 秒參考音訊
```bash
cd /home/joshhu/workspace/autovoice
.venv/bin/python scripts/clip_reference.py \
  output/<BASENAME>/audio.wav \
  output/<BASENAME>/ref_30s.wav
```

### 步驟 3：語音辨識（Whisper Large-v3）
```bash
cd /home/joshhu/workspace/autovoice
.venv/bin/python scripts/run_whisper.py \
  output/<BASENAME>/audio.wav \
  output/<BASENAME>/transcript.json
```

辨識完成後，讀取 `output/<BASENAME>/transcript.txt`，顯示辨識語言和前 200 字給使用者確認。

### 步驟 4：擷取 30 秒文字稿（Claude 執行）

從 `output/<BASENAME>/transcript.json` 讀取 segments，
找出 start < 40 秒（含步驟 2 截取從第 10-40 秒）的片段文字，
合併後存入 `output/<BASENAME>/ref_30s_transcript.txt`。

這個文字稿是聲音克隆的關鍵，必須對應 ref_30s.wav 的內容。

### 步驟 5：文字校對（Claude LLM 直接執行）

讀取 `output/<BASENAME>/transcript.txt`，Claude 直接：
- 修正錯別字和 ASR 誤辨識（諧音錯誤）
- 修正標點符號
- 保持原文語意不變

將校對後文字寫入 `output/<BASENAME>/transcript_corrected.txt`。

### 步驟 6：詢問目標語言

若使用者未指定 `--lang`，詢問：
「偵測到原始語言為 [語言]，請問要配音成哪種語言？（例如：日文、英文、韓文）」

### 步驟 7：翻譯（Claude LLM 直接執行）

讀取 `output/<BASENAME>/transcript_corrected.txt`，Claude 翻譯成目標語言：
- 保持口語自然，適合朗讀
- 句子不要過長（超過 50 字就拆句）
- 語氣與原文一致

將翻譯結果寫入 `output/<BASENAME>/transcript_<lang_code>.txt`
（lang_code：ja / en / ko / fr / de / es / pt / ru / zh）

### 步驟 8：聲音克隆 + 合成

**注意：target_text 可能含特殊字元，使用 @file 方式傳遞**

```bash
cd /home/joshhu/workspace/autovoice
.venv/bin/python scripts/run_tts.py \
  output/<BASENAME>/ref_30s.wav \
  output/<BASENAME>/ref_30s_transcript.txt \
  "$(cat output/<BASENAME>/transcript_<lang_code>.txt)" \
  <TARGET_LANGUAGE_EN> \
  output/<BASENAME>/dubbed_<lang_code>.wav \
  1.7B
```

TARGET_LANGUAGE_EN：Chinese / Japanese / English / Korean / French / German / Spanish / Portuguese / Russian

**若 VRAM 不足（OOM 錯誤）**，改用 0.6B：
```bash
.venv/bin/python scripts/run_tts.py \
  output/<BASENAME>/ref_30s.wav \
  output/<BASENAME>/ref_30s_transcript.txt \
  "$(cat output/<BASENAME>/transcript_<lang_code>.txt)" \
  <TARGET_LANGUAGE_EN> \
  output/<BASENAME>/dubbed_<lang_code>.wav \
  0.6B
```

### 步驟 9：合成配音影片

```bash
cd /home/joshhu/workspace/autovoice
.venv/bin/python scripts/merge_audio.py \
  <input_video_path> \
  output/<BASENAME>/dubbed_<lang_code>.wav \
  output/<BASENAME>/<BASENAME>_dubbed_<lang_code>.mp4
```

### 步驟 10：完成報告

顯示：
```
AutoVoice 完成！
  原始語言：[語言]
  配音語言：[目標語言]
  輸出影片：output/<BASENAME>/<BASENAME>_dubbed_<lang_code>.mp4
  配音時長：[N] 秒

中間檔案：
  output/<BASENAME>/audio.wav          <- 完整音訊
  output/<BASENAME>/ref_30s.wav        <- 參考音訊（30s）
  output/<BASENAME>/transcript.txt     <- 原始文字稿
  output/<BASENAME>/transcript_corrected.txt <- 校對後
  output/<BASENAME>/transcript_<lang>.txt    <- 翻譯
  output/<BASENAME>/dubbed_<lang>.wav  <- 配音音訊
```

## 錯誤處理

| 情境 | 處理方式 |
|------|----------|
| VRAM 不足（OOM） | 改用 0.6B 模型 |
| 影片無音訊 | 告知使用者並停止 |
| Whisper 信心 < 80% | 警告並詢問確認語言 |
| yt-dlp 下載失敗 | 檢查 URL 或網路 |
| ref_30s_transcript.txt 為空 | 手動輸入參考文字 |

## 腳本位置

所有腳本在 `/home/joshhu/workspace/autovoice/scripts/`：
- `extract_audio.py` - 音訊提取
- `clip_reference.py` - 參考音訊截取
- `run_whisper.py` - Whisper ASR
- `run_tts.py` - Qwen3-TTS 聲音克隆
- `merge_audio.py` - 配音合成
