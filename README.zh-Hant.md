# Radio

<p align="right">
  <a href="README.md">English</a> · <strong>繁體中文</strong>
</p>

<p align="center">
  <img src="assets/radio-logo.svg" width="600" alt="彩色漸層 RADIO ASCII Logo">
</p>

![python](https://img.shields.io/badge/python-3.12%2B-3fb950?style=flat-square&logo=python&logoColor=white) ![Textual](https://img.shields.io/badge/Textual-8.2-3fb950?style=flat-square) ![FastAPI](https://img.shields.io/badge/FastAPI-0.141-3fb950?style=flat-square&logo=fastapi&logoColor=white) ![player](https://img.shields.io/badge/player-mpv-3fb950?style=flat-square&logo=mpv&logoColor=white) ![stations](https://img.shields.io/badge/stations-44-3fb950?style=flat-square) ![themes](https://img.shields.io/badge/themes-14-3fb950?style=flat-square) ![i18n](https://img.shields.io/badge/i18n-zh--Hant%20%7C%20en-3fb950?style=flat-square) ![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-3fb950?style=flat-square&logo=apple&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square)

台灣電台的終端機播放器。Textual 介面和 FastAPI 控制 API 共用同一套服務。

## 事前準備

Radio 需要 Python 3.12 以上、[uv](https://docs.astral.sh/uv/) 和 [mpv](https://mpv.io/)。先依系統安裝 mpv：

```sh
# macOS（Homebrew）
brew install mpv

# Ubuntu / Debian
sudo apt update
sudo apt install mpv

# Arch Linux
sudo pacman -S mpv
```

其他系統請參考 [mpv 安裝說明](https://mpv.io/installation/)。安裝後可執行 `mpv --version`，確認終端機找得到指令。

## 安裝

```sh
make link      # uv tool install --editable . --force
```

這會直接將 `radio` 指令裝進 PATH，之後從任何目錄都能執行。此為開發模式安裝，修改專案內容後會直接生效，毋需重新安裝；若要移除就跑

```sh
make unlink
```

## 執行

```sh
radio                     # 終端機介面
radio ui --no-autoplay    # 啟動時不要續播上次的電台
radio api                 # HTTP API，文件在 http://127.0.0.1:8000/docs
radio stations --band AM
radio --help
```

不安裝也能用 `make run`、`make api` 或 `uv run radio ...` 執行。

## 終端機介面

分頁包括**首頁**、FM、AM、**我的最愛**、**收聽紀錄**、**佈景主題**、**設定**和**關於**。每次啟動都先回首頁，即使程式同時續播了上次的電台。底部狀態列會顯示播放狀態、頻率、電台、節目名稱、播放時間、音訊輸出和音量；點左下角的播放狀態即可暫停或繼續。輸出裝置名稱最多顯示十五個字元。預設會在啟動時續播上次的電台。

| 按鍵 | 動作 |
| --- | --- |
| `←` `→` | 切換上一個或下一個分頁 |
| `↑` `↓` `j` `k` | 移動游標 |
| `enter` | 執行游標所在項目：播放或繼續電台、套用主題或切換設定 |
| `space` | 暫停或繼續播放 |
| `s` | 停止播放 |
| `f` | 加入或移出我的最愛 |
| `+` `=` | 調高音量 |
| `-` `_` | 調低音量 |
| `m` | 靜音或取消靜音 |
| `t` | 切到下一個佈景主題 |
| `e` | 匯出設定 |
| `i` | 匯入設定 |
| `w` | 切換英文／繁體中文 |
| `q` | 離開 |

## 捲動

欄位比視窗寬時可以用滑鼠或觸控板水平捲動，水平捲軸則會隱藏，避免看起來像音量條。左右方向鍵仍然只切換分頁。

如果表格的列數沒有超出畫面、但欄位太寬，滾輪向下會往右移，向上會往左移。若下方還有資料列，滾輪就維持一般的上下捲動。

我的最愛、音量、靜音、上次播放的電台和佈景主題都會記錄在 `.radio/state.json`。

## 設定檔

| 檔案 | 內容 |
| --- | --- |
| `stations.toml` | 電台代號、名稱、頻段、頻率和串流網址 |
| `themes.yml` | 所有配色及預設主題 |
| `locales/*.yml` | 英文與繁體中文介面文字 |
| `app/tui/radio.tcss` | 終端機介面版面 |
| `.radio/history.jsonl` | 收聽紀錄，每個事件一列 JSON |
| `.radio/state.json` | 我的最愛、音量、靜音、自動播放、動畫、語言、電台和主題 |

新增電台時，在 `stations.toml` 加上一個區塊：

```toml
[[stations]]
slug = "example"
name = "Example FM"
band = "FM"
frequency = "99.9"
description = "選填說明"
url = "https://example.com/live/playlist.m3u8"
```

## 音訊輸出

底部狀態列會顯示聲音送往哪個裝置。`mpv` 本身只回報 `auto`，所以 macOS 會在背景每十五秒執行一次 `system_profiler SPAudioDataType` 並快取結果。其他平台或偵測失敗時，就改顯示 mpv 的輸出驅動名稱。

## 語言

目前只內建 English 和繁體中文，分別放在 `locales/en.yml` 與 `locales/zh-Hant.yml`，預設為繁體中文。按 `w` 可在兩者之間切換，**設定**頁也會顯示目前語言。

程式自己的文字都有翻譯；電台名稱、電台說明和節目名稱來自清單或串流資料，因此保留原文。若修改介面文案，兩份語系檔要一起更新。缺少翻譯鍵時會先回退到繁體中文，再顯示鍵名本身。

## 主題、設定與關於

**佈景主題**頁會預覽 `themes.yml` 裡的每組配色，每張卡片使用自己的背景、前景和色票。按 `enter` 套用游標所在主題，再回到這個頁面時，游標會留在使用中的主題。

**設定**頁列出自動播放、動畫、語言、主題和音量等選項。可修改的項目用 `enter` 切換，備註欄會標示對應按鍵。唯讀項目則直接顯示數值，以及可覆寫它的環境變數。選擇**恢復預設**並確認，即可重設這些設定；我的最愛、上次電台及收聽紀錄會保留。

動畫預設關閉。

**關於**頁顯示版本、著作權和使用的套件。作者、年份和專案網址定義在 `app/core/about.py`。

## 匯出與匯入設定

按 `e` 或選擇**匯出設定**，會列出桌面、文件、下載、家目錄、專案目錄和資料目錄中實際存在的資料夾。按 `enter` 寫入，`escape` 取消。

檔名格式為 `settings_<timestamp>.radio.config`，時間精確到毫秒。

```json
{
  "version": "0.1.0",
  "exported_at": "2026-08-30T13:44:24.355+08:00",
  "settings": { "...": "..." },
  "preferences": { "favorites": [], "volume": 100, "...": "..." }
}
```

按 `i` 會在相同資料夾裡尋找 `.radio.config`，並依新到舊列出。匯入後會還原我的最愛、音量、靜音、主題、語言、自動播放和動畫，所有頁面也會立即更新。

程式只會套用 `preferences`。`settings` 用來記錄匯出當下的執行環境，其中的路徑和指令屬於原裝置，不會直接搬移。格式錯誤或值的型別不符時會拒絕匯入；已不存在的電台也不會留在我的最愛或上次播放紀錄中。

## 收聽紀錄

每次工作階段開始、結束、播放、暫停和繼續，都會附帶時間寫入 `.radio/history.jsonl`。`play_ended` 會記錄總經過時間及暫停時間，實際收聽時間就是 `duration_seconds - paused_seconds`。表格中的收聽及暫停時間固定顯示為 `HH:MM:SS`。選擇**清除收聽紀錄**並確認，即可刪除全部紀錄。

## API 端點

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/stations?band=FM` | 列出電台，可依頻段篩選 |
| GET | `/stations/{slug}` | 取得單一電台 |
| GET | `/player` | 取得播放狀態、節目名稱和計時 |
| POST | `/player/play` | 播放電台 |
| POST | `/player/toggle` | 切換指定電台的播放狀態 |
| POST | `/player/pause` | 暫停 |
| POST | `/player/resume` | 繼續播放 |
| POST | `/player/stop` | 停止 |
| GET | `/history` | 最近的收聽事件 |
| GET | `/history/summary` | 各電台收聽統計 |
| GET | `/themes` | 可用佈景主題 |

## 貢獻與安全性

送出 PR 之前請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)。安全漏洞請依 [SECURITY.md](SECURITY.md) 私下回報，切勿開公開 issue。參與專案時請遵守[行為準則](CODE_OF_CONDUCT.md)。

## 授權

Radio 採用 [MIT License](LICENSE)。
