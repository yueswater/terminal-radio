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
radio --help
```

不安裝也能用 `make run`、`make api` 或 `uv run radio ...` 執行。

## 版本更新

每次開啟時，最多一天一次，會向索引問有沒有新版本。有的話會告知，如果這份是用它
驅動得動的套件管理工具裝的（`uv tool` 或 `pipx`），就一併提供更新。選擇更新會先
關閉收音機再執行升級，因為程式沒辦法替換自己正在執行的檔案。

選**稍後再說**的話，下次開啟還會再提醒，總共三次，之後就安靜，直到出現一個還沒
提醒過的版本為止。從原始碼執行的那份永遠不會被提議更新，只會告知有新版。完全不想
被問的話設 `RADIO_CHECK_FOR_UPDATES=0`。

要自己手動更新的話，看當初怎麼裝的：

```sh
uv tool upgrade radiotui-tw
pipx upgrade radiotui-tw
```

## 命令列操控

不開介面也能操控整台收音機。

```sh
radio play news98
radio pause / radio resume / radio stop
radio status
radio status --json      # 給腳本用：radio status --json | jq -r .program
radio volume 50          # 絕對音量
radio volume +10         # 相對調整
radio mute / radio unmute
radio sleep 30           # 三十分鐘後停止
radio sleep off
radio now                # 現在正在播的電台和曲目
radio now-playing        # 播報過的完整紀錄
```

**播放器只能有一個擁有者。**它會持有一個鎖檔，並在執行期目錄的 unix socket 上
接收指令。兩個擁有者代表兩條音訊串流、兩個搶著寫同一份狀態檔的程序，所以第二個
會被拒絕。

擁有者會自動啟動：沒有任何程序在跑時執行 `radio play`，會在背景開一個無介面的
擁有者；而無介面的擁有者若沒在播放、也沒人下指令，五分鐘後會自行退場。終端機
介面開著時它就是擁有者，所以在另一個視窗打 `radio play` 會操控畫面上那台收音機，
而不是另外開一台。

```sh
radio daemon             # 在前景執行一個
radio daemon status      # 顯示是哪個程序擁有播放器
radio daemon stop        # 請它關閉
```

每個操控指令都是走那個 socket 的 HTTP 請求，跟 `radio api` 用連接埠對外提供的是
同一套應用程式。socket 的權限只開給啟動它的使用者。

## 終端機介面

分頁包括**首頁**、FM、AM、**我的最愛**、**收聽紀錄**、**曲目紀錄**、**聆聽統計**、**佈景主題**、**設定**和**關於**。每次啟動都先回首頁，即使程式同時續播了上次的電台。底部狀態列會顯示播放狀態、頻率、電台、節目名稱、播放時間、音訊輸出、睡眠計時和音量；點左下角的播放狀態即可暫停或繼續。輸出裝置名稱最多顯示十五個字元。預設會在啟動時續播上次的電台。

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
| `q` | 離開，並在告別畫面期間把聲音淡出 |

離開時聲音會在 `RADIO_GOODBYE_SECONDS` 的時間內淡出，而不是硬切，剛好就是告別畫面
停留的那一刻。淡出不會動到你設定的音量，所以下次開機還是原本的大小。把時間設成 0
就直接離開。

## 捲動

欄位比視窗寬時可以用滑鼠或觸控板水平捲動，水平捲軸則會隱藏，避免看起來像音量條。左右方向鍵仍然只切換分頁。

如果表格的列數沒有超出畫面、但欄位太寬，滾輪向下會往右移，向上會往左移。若下方還有資料列，滾輪就維持一般的上下捲動。FM、AM、我的最愛、收聽紀錄和設定表格會使用相同的上下間距並置中；頁面本身不動，只有表格內容會捲動。

我的最愛、音量、靜音、自動播放、斷線重連、電台檢查、語言、上次播放的電台和佈景主題都會記錄在 `<狀態目錄>/state.json`。

## 設定檔

| 檔案 | 內容 |
| --- | --- |
| `app/data/stations.toml` | 電台識別、分類與串流位址 |
| `app/data/themes.yml` | 所有配色及預設主題 |
| `app/data/locales/*.yml` | 英文與繁體中文介面文字 |
| `app/tui/radio.tcss` | 終端機介面版面 |
| `<狀態目錄>/history.jsonl` | 收聽紀錄，每個事件一列 JSON |
| `<狀態目錄>/now-playing.jsonl` | 各台播報過的曲目，每筆一列 |
| `<狀態目錄>/state.json` | 我的最愛、音量、靜音、自動播放、動畫、語言、電台和主題 |
| `<狀態目錄>/custom-stations.toml` | 從設定頁新增的自訂電台 |
| `<執行期目錄>/control.sock` | 所有指令送達擁有者的 socket |
| `<執行期目錄>/control.lock` | 播放器的所有權，由擁有者持有 |

`<狀態目錄>` 是程式寫入的個人目錄，位於安裝目錄之外，升級或重裝都不會遺失紀錄：
macOS 為 `~/Library/Application Support/terminal-radio`，Linux 為
`~/.local/state/terminal-radio`。可用 `RADIO_DATA_DIR` 覆寫。

`<執行期目錄>` 只放執行中的收音機需要、且不該撐過重開機的東西：
`$XDG_RUNTIME_DIR/terminal-radio`，或系統暫存目錄底下的個人目錄。刻意不放在
狀態目錄，因為 unix socket 路徑上限接近一百個位元組，而在 macOS 上光是狀態
目錄就佔掉大半。可用 `RADIO_RUNTIME_DIR` 覆寫。

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

network = "Example Network"       # 選填，把同一家的多個頻率歸在一起
regions = ["taipei"]              # 選填，主要收聽區域
genres = ["news", "talk"]         # 選填，播送內容
languages = ["zh-Hant"]           # 選填，BCP 47 語言標籤

url = "https://example.com/live/playlist.m3u8"
fallback_urls = []                # 選填，主要位址沒聲音時依序接手
```

`regions` 和 `genres` 是封閉集合，可用的值列在
`terminal_radio/enums/station.py`；填了以外的值會在載入時直接報錯，而不是變成一個
永遠搜不到的電台。

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

## 找電台

在任何地方按 `/`，或點分頁列右邊的搜尋圖示。同一套查詢語法在介面、命令列和 HTTP
上都通用：

```sh
radio stations "genre:news region:taipei"
radio stations "genre:news genre:talk"    # 同一個 key 會放寬
radio stations --genre classical --json
```

篩選條件有 `genre:`、`region:`、`lang:`、`network:` 和 `band:`。不同 key 之間是
交集，同一個 key 之間是聯集。不是篩選條件的字就當作自由文字，排序上會讓完整打出
的頻率排在「說明裡剛好有那幾個數字」的電台前面。

每個電台還會記錄所屬聯播網、主要收聽區域、播送內容和語言。這些在資料檔裡是語言
中立的代碼，在畫面上才翻成名稱。詳見 `terminal_radio/data/stations.toml` 開頭的
註解。

## 備援串流

電台可以在 `url` 旁邊列出 `fallback_urls`。第一個位址永遠先試。串流斷掉時，原本
的重連延遲完全不變，只是每次重試會輪到下一個位址。之後就留在能用的那個，不會為
了回到主要位址而再中斷一次聲音；下次主動點播該電台時才會重新從主要位址開始。只有
在備援位址撐著的時候，底部狀態列才會出現一個低調的標記。

只要任一個位址有回應，該電台就算上線，健康檢查也會在第一個有回應的位址就停下來。

## 曲目紀錄

開始播放時會直接向電台索取現在的曲目，不必等播放進度走到第一個 metadata block，
所以曲目跟聲音幾乎同時出現，而不是慢兩秒。太長的曲目會跑馬燈捲動；不想要的話可以
在**設定**關掉，或用 `RADIO_SCROLL_TITLES=0`。

會發布曲目的電台其實不多。內建清單裡有三台會送，其餘的不論走 ICY 或 HLS，都只送
電台名稱、不送曲目。

收音機執行期間，各台播報的曲目會寫進 `<狀態目錄>/now-playing.jsonl`。這是**電台的**
時間軸，和屬於**聽眾的**收聽紀錄分開存放。同一個曲名不會連續寫兩次，所以重連不會
讓同一首歌變成兩筆；超過 `RADIO_NOW_PLAYING_RETENTION_DAYS` 天（預設 30 天）的
資料會隨著檔案成長被清掉。

**曲目紀錄**分頁會把同樣的內容顯示在畫面上，最新的在最前面，並附匯出 CSV 和清除兩顆按鈕。

```sh
radio now                        # 只看現在播什麼
radio now-playing --limit 10
radio now-playing --station icrt
radio now-playing --json
```

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
