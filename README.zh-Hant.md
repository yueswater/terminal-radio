# Terminal Radio

<p align="right">
  <a href="https://github.com/yueswater/terminal-radio/blob/main/README.md">English</a> · <strong>繁體中文</strong>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yueswater/terminal-radio/main/assets/terminal-radio-logo.svg" width="560"
       alt="終端機畫面與 RADIO 字樣的彩色漸層 ASCII Logo">
</p>

![python](https://img.shields.io/badge/python-3.12%2B-3fb950?style=flat-square&logo=python&logoColor=white) ![Textual](https://img.shields.io/badge/Textual-8.2-3fb950?style=flat-square) ![FastAPI](https://img.shields.io/badge/FastAPI-0.141-3fb950?style=flat-square&logo=fastapi&logoColor=white) ![player](https://img.shields.io/badge/player-mpv-3fb950?style=flat-square&logo=mpv&logoColor=white) ![stations](https://img.shields.io/badge/stations-44-3fb950?style=flat-square) ![themes](https://img.shields.io/badge/themes-14-3fb950?style=flat-square) ![i18n](https://img.shields.io/badge/i18n-zh--Hant%20%7C%20en-3fb950?style=flat-square) ![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-3fb950?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square)

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

> **僅支援 macOS 與 Linux。** 播放器透過 unix socket 與 mpv 溝通。Windows 不支援，
> 也沒有測試。在 WSL 底下可以執行。

## 安裝

```sh
curl -LsSf https://raw.githubusercontent.com/yueswater/terminal-radio/main/install.sh | sh
```

腳本會在缺少 uv 時先裝 uv，接著裝好 `radio` 指令；若你還沒有 mpv，它會告訴你該下哪一行。
**不需要 clone**。

想自己來的話：

```sh
uv tool install radiotui-tw
# 或
pipx install radiotui-tw
```

要移除時執行 `uv tool uninstall radiotui-tw`。

### 開發用

clone 之後以 editable 方式安裝，改動立即生效、不必重裝：

```sh
make link      # uv tool install --editable . --force
make unlink    # 移除
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

分頁包括**首頁**、FM、AM、**我的最愛**、**收聽紀錄**、**聆聽統計**、**佈景主題**、**設定**和**關於**。每次啟動都先回首頁，即使程式同時續播了上次的電台。底部狀態列會顯示播放狀態、頻率、電台、節目名稱、播放時間、音訊輸出、睡眠計時和音量；點左下角的播放狀態即可暫停或繼續。輸出裝置名稱最多顯示十五個字元。預設會在啟動時續播上次的電台。

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
| `/` | 搜尋內建與自訂電台 |
| `?` | 開啟鍵盤快捷鍵說明 |
| `q` | 離開 |

## 捲動

欄位比視窗寬時可以用滑鼠或觸控板水平捲動，水平捲軸則會隱藏，避免看起來像音量條。左右方向鍵仍然只切換分頁。

如果表格的列數沒有超出畫面、但欄位太寬，滾輪向下會往右移，向上會往左移。若下方還有資料列，滾輪就維持一般的上下捲動。FM、AM、我的最愛、收聽紀錄和設定表格會使用相同的上下間距並置中；頁面本身不動，只有表格內容會捲動。

我的最愛、音量、靜音、自動播放、斷線重連、電台檢查、語言、上次播放的電台和佈景主題都會記錄在 `<狀態目錄>/state.json`。

## 設定檔

| 檔案 | 內容 |
| --- | --- |
| `app/data/stations.toml` | 電台代號、名稱、頻段、頻率和串流網址 |
| `app/data/themes.yml` | 所有配色及預設主題 |
| `app/data/locales/*.yml` | 英文與繁體中文介面文字 |
| `app/tui/radio.tcss` | 終端機介面版面 |
| `<狀態目錄>/history.jsonl` | 收聽紀錄，每個事件一列 JSON |
| `<狀態目錄>/state.json` | 我的最愛、音量、靜音、自動播放、動畫、語言、電台和主題 |
| `<狀態目錄>/custom-stations.toml` | 從設定頁新增的自訂電台 |

`<狀態目錄>` 是程式寫入的個人目錄，位於安裝目錄之外，升級或重裝都不會遺失紀錄：
macOS 為 `~/Library/Application Support/terminal-radio`，Linux 為
`~/.local/state/terminal-radio`。可用 `RADIO_DATA_DIR` 覆寫。

內建的電台清單、佈景主題與語言檔是唯讀的。想用自己的版本又不動到安裝目錄，
可以把 `stations.toml`、`themes.yml` 或 `locales/` 放進設定目錄——macOS 為
`~/Library/Application Support/terminal-radio`，Linux 為 `~/.config/terminal-radio`
——程式會優先讀取。

內建電台放在 `app/data/stations.toml`。若不想改專案檔，可從**設定**開啟**自訂電台**，直接新增、編輯或刪除本機電台；串流網址限 HTTP 或 HTTPS。要新增內建電台時，在 `app/data/stations.toml` 加上一個區塊：

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

## 播放工具

按 `/` 可依頻率、電台名稱、說明或波段搜尋，輸入時會即時篩選，按 `enter` 播放游標所在電台。

斷線重連預設開啟。串流中斷後會依序等待 1、2、4、8、15 秒再試，第五次仍失敗就停止；可在**設定**關閉。

睡眠計時可關閉，也可設為 15、30、60 分鐘或自訂 1 到 1440 分鐘。倒數會顯示在底部狀態列，關閉程式後不會保留。

Radio 可檢查串流是否正常、緩慢或離線。自動檢查結果會快取五分鐘，選擇**立即檢查所有電台**則會重新檢查；同時最多檢查四個串流。

## 語言

目前只內建 English 和繁體中文，分別放在 `app/data/locales/en.yml` 與 `app/data/locales/zh-Hant.yml`，預設為繁體中文。按 `w` 可在兩者之間切換，**設定**頁也會顯示目前語言。

程式自己的文字都有翻譯；電台名稱、電台說明和節目名稱來自清單或串流資料，因此保留原文。若修改介面文案，兩份語系檔要一起更新。缺少翻譯鍵時會先回退到繁體中文，再顯示鍵名本身。

## 主題、設定與關於

**佈景主題**頁會預覽 `themes.yml` 裡的每組配色，每張卡片使用自己的背景、前景和色票。按 `enter` 套用游標所在主題，再回到這個頁面時，游標會留在使用中的主題。

**設定**頁包含自動播放、斷線重連、睡眠計時、電台檢查、自訂電台、鍵盤快捷鍵、動畫、語言、主題和音量。可修改的項目用 `enter` 操作；唯讀項目會顯示數值和可覆寫它的環境變數。選擇**恢復預設**並確認，即可重設偏好；我的最愛、自訂電台、上次電台及收聽紀錄會保留。

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
  "preferences": { "favorites": [], "volume": 100, "...": "..." },
  "custom_stations": []
}
```

按 `i` 會在相同資料夾裡尋找 `.radio.config`，並依新到舊列出。匯入後會還原自訂電台、我的最愛、音量、靜音、主題、語言、自動播放、斷線重連、電台檢查和動畫，所有頁面也會立即更新。舊版檔案沒有 `custom_stations` 也能照常匯入。

程式只會套用 `preferences`。`settings` 用來記錄匯出當下的執行環境，其中的路徑和指令屬於原裝置，不會直接搬移。格式錯誤或值的型別不符時會拒絕匯入；已不存在的電台也不會留在我的最愛或上次播放紀錄中。

## 收聽紀錄

每次工作階段開始、結束、播放、暫停和繼續，都會附帶時間寫入 `<狀態目錄>/history.jsonl`。`play_ended` 會記錄總經過、暫停及斷線時間，實際收聽時間會扣除暫停與斷線重連。表格中的時間固定顯示為 `HH:MM:SS`。

選擇**匯出 CSV**可儲存完整的電台收聽摘要，檔案使用 UTF-8 BOM，欄位名稱會依目前介面語言切換。選擇**清除收聽紀錄**並確認，即可刪除全部紀錄。

**聆聽統計**會讀取全部有效紀錄，使用終端機字元繪出總收聽時間、播放次數、收聽天數、最常聽前十名、近 14 天趨勢、每週分布、時段分布及 FM／AM 占比；只計算已完成的播放。

## API 端點

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/stations?band=FM&q=警廣` | 列出電台，可依頻段或文字篩選 |
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

送出 PR 之前請先閱讀 [CONTRIBUTING.md](https://github.com/yueswater/terminal-radio/blob/main/CONTRIBUTING.md)。安全漏洞請依 [SECURITY.md](https://github.com/yueswater/terminal-radio/blob/main/SECURITY.md) 私下回報，切勿開公開 issue。參與專案時請遵守[行為準則](CODE_OF_CONDUCT.md)。

## 授權

Radio 採用 [MIT License](https://github.com/yueswater/terminal-radio/blob/main/LICENSE)。
