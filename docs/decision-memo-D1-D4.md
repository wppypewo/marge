# D1～D4 決策備忘錄

2026-11-06 整理。對象：PM。內容是 [PRD](../PRD.md) 3.2 四個待定決策的選項、現有證據、建議，以及要問授課老師的問題。
證據都引用評測報告 `../local-first-ai/測試計畫.md`（以下稱「報告」）的節次，這裡不重抄數據細節。

## 結論先講

| 決策 | 建議 | 現在能定嗎 | 卡在哪 |
|---|---|---|---|
| D1 模型與供應商 | 先實測 Cerebras（OI-1），結果不差於 dots 就用 Cerebras 當主要、dots 當備用；Nemotron 只給同意作文被拿去訓練的學生 | 不能 | OI-1 沒測；要 Cerebras、Cloudflare 帳號 |
| D2 學生端 App | iPhone 用 Open Minis＋iCloud Drive；Android 等老師回覆 | 不能 | 學生用什麼手機（OI-5） |
| D3 prompt 交付 | 先維持每次貼上；D1、D2 定了再包 skill | 可以先定「暫不包」 | 包 skill 綁定 Open Minis，D2 沒定前做了可能白做 |
| D4 結果存哪 | iPhone 學生存 iCloud Drive、Mac 學生存 Google Drive，一律存 `.md` 或 `.docx` | 不能 | iCloud 讀寫沒測（ADR-007）；老師收不收一般檔案 |

四個決策裡 D1 最先要定：D3 等 D1（OI-7），D2、D4 互相綁在一起，都要老師回答。

## D1 用哪個模型和供應商

| 選項 | 品質（報告 3.1、3.6） | 資料去向（報告 4.4） | 額度與速度 | 已測 |
|---|---|---|---|---|
| Nemotron 3.5 Super VL（OpenRouter） | 受測雲端免費模型裡最好；1 處改錯、2 個理由不合理 | **要開「免費端點可用請求資料訓練」** | 每天約 7 份（3.5，n=1 推估）；OCR＋批閱約 235 秒 | 是，n=1 |
| dots-3-note-preview（OpenRouter） | 多數項目不如 Nemotron：要多回一則 `oui`、⚠️ 16 個超過上限、13 處改了沒標 | 不必開訓練選項，仍經過 OpenRouter 與模型公司 | 約 325 秒；preview 版可能下架 | 是，n=1 |
| Cerebras `qwen-3.8-27b` | 未知 | 隱私政策：不保存推論的輸入和輸出 | 每天 100 萬 token，約 9 份；每分鐘未快取 3 萬 token，Open Minis 一則送 2～3 筆、每筆 14K～19K，可能被擋 | **否** |
| Cloudflare Workers AI | 未知 | 官方：不拿來訓練、處理完不保存 | 每天 1 萬 neurons，約 2 份 | **否** |
| 本機 Qwen3.6-35B-A3B | 程式判斷項目不如 Nemotron；總字數兩次都報錯；同設定兩次差很多（4.6） | 不離開電腦 | 要 24 GB 記憶體的電腦；約 3.5～4.5 分鐘 | 是，n=2（另見 2026-11-06 修正版 prompt 的結果） |

建議理由：

- PRD 目標 3（作文不被拿去訓練）是 P0（F5）。現在品質最好的 Nemotron 違反它，所以 Nemotron 不能當預設。
- 剩下的選項裡，dots 是唯一測過的，但品質差、又是 preview 版。Cerebras 額度最多、條款最好，缺的只有實測。
- Cerebras 的 `qwen-3.8-27b` 和本機測的 Qwen3.6 同一家族，本機結果顯示這個家族報總字數不準。F6 已規定字數由程式算，這個缺點可以繞開。
- 本機模型要求學生有 24 GB 記憶體的電腦，不適合當全班方案。

要做的事：照 `grading-eval` skill 實測 Cerebras 和 Cloudflare（OI-1）。需要你建立兩個帳號、取得 API key；Claude 不能代為註冊。

## D2 學生端用什麼 App

| 選項 | 證據 |
|---|---|
| Open Minis（iPhone） | 掛不上 Google Drive，掛得上 iCloud Drive（報告 3.3） |
| Open Minis（Mac） | Google Drive 讀寫成功、沒有越權（報告 3.3） |
| Gemini 官方介面 | 沒有資料夾讀寫；免費版自 10-09 起多數請求交給 Flash-Lite（PRD 1.1） |
| Android | 沒測，作者沒有 Android 裝置（OI-5） |

建議：iPhone 學生用 Open Minis＋iCloud Drive。全班若有 Android 使用者，要另找 App，篩選條件見報告第 7 節「其他 App」（能填 OpenRouter key、iOS 和 Windows 都有、能讀寫指定資料夾、有跨對話記憶）。

## D3 prompt 怎麼交給學生

| 選項 | 好處 | 代價 |
|---|---|---|
| 每次貼上（現行） | 不綁 App，換模型、換 App 都能用 | 學生每次要複製；版本可能不一致 |
| 包成 Open Minis skill `c4-b1-grading` | 一次安裝，版本一致 | 只在 Open Minis 能用；D2 若改用別的 App 就白做 |

建議：D1、D2 定案前維持貼上。prompt 文字確定後再包 skill 比較省事。

修正版 prompt（轉錄不修正、字數句改成明確格式）11-06 在本機 Qwen 跑了兩次（`../local-first-ai/OI-2_修正版prompt_本機Qwen_2026-11-06.md`）：

- 字數句：一次照新格式報對（156、多 36），一次報「約 145」。原版兩次都報錯
- 「轉錄不修正」：沒效，兩次仍把 4～5 個字改成標準拼法，和原版差不多
- 同設定兩次差很多：第 2 次 0 個 ⚠️、「還缺X個」的 X 沒填

所以字數句可以先換成新格式（沒看到變差），「轉錄不修正」不能取代學生核對 OCR。要不要整份換成修正版，等雲端模型也跑過再定。

## D4 結果存哪裡

| 選項 | 證據 |
|---|---|
| Google Drive | 老師現在看的地方；iPhone 上 Open Minis 掛不上；AI 讀不到 Google 文件的內容，只讀得到 `.docx`、`.md` 這類一般檔案（報告 3.3） |
| iCloud Drive | iPhone 掛得上；讀寫沒測（ADR-007） |

建議：結果一律存成 `.md` 或 `.docx`（F7）。iPhone 學生存 iCloud Drive、再由學生交給老師；這要老師接受「收一般檔案」而不是 Google 文件。定案前要補測 iCloud Drive 的讀寫，流程同報告 2.5。

## 要問授課老師的問題

這些合併成一封信（TASKS「寫信問老師」，OI-9）：

1. 修課人數多少？學生用 iPhone 還是 Android？（D2、OI-5）
2. 學生願不願意自己申請 API key？（D1）
3. 能不能接受作文被拿去訓練模型？如果不能，品質稍差但不訓練的選項可以嗎？（D1、F5）
4. 學習歷程能不能改收 `.docx` 或 `.md`，不收 Google 文件？（D4、F7）
5. 一次批閱可以等多久？PRD 暫定 5 分鐘。（F10）
6. iPhone 學生改用 iCloud Drive 可以嗎？（OI-4）

## 這份備忘錄沒處理的

- ADR-006（10-17）寫「通用版、修正版 prompt 不跑」，但 OI-2、TASKS 仍列為待辦。2026-11-06 已用本機 Qwen 跑了修正版（結果見 D3）；要不要新增 ADR 取代 ADR-006 由 PM 決定。（11-08：已新增 ADR-013 取代 ADR-006，字數句放進「C4-B1 正式版」。）
- 雲端模型重跑（OI-3）要用 OpenRouter 額度，這次沒跑。
