---
name: report-publish
description: 更新 Marge 評測報告（../local-first-ai/測試計畫.md）後，重做 PDF 並同步到分享給老師的 Google Drive 資料夾。用在「報告改好了」「重做 PDF」「同步雲端」「更新給老師的資料夾」這類要求。
---

# 報告更新、重做 PDF、同步雲端

報告與成品在 `../local-first-ai/`（不是 git repo），所有指令在那個目錄執行。腳本在本 repo 的 `tools/report/`。

## 步驟

1. **改報告前先備份**：`cp 測試計畫.md` 到 scratchpad。local-first-ai 沒有版本控制，改壞了只能靠這份備份或雲端那份 zip。
2. **改內容**：新事實要寫出處（報告節次、檔名或官方網址）。改到數字時，摘要、正文、附錄、結論裡同一個數字要一起改，用 `grep` 找出所有出現的地方。
3. **重做 PDF**：
   ```bash
   ../marge/tools/report/build_pdf.sh 測試計畫.md 測試計畫.pdf
   ```
   腳本印出頁數與大小。頁數和上一版差很多時，用 `pdftoppm -r 60 -png -f N -l N` 轉幾頁出來看版面（表格最常跑版）。
4. **同步雲端前先問使用者**，列出要換掉或新增哪些檔案。雲端資料夾只放成品（報告 PDF、prompt、參考轉寫、照片、模型輸出、已填評分表），不放腳本或中間檔。
5. **先看雲端現況**：
   ```bash
   ../marge/tools/report/sync_drive.sh --check
   ```
   雲端有檔案的修改時間比本機最後一次同步還新，可能被人改過（10-17 發生過帳號本人存回舊版），先停下來問使用者。
6. **同步**：
   ```bash
   ../marge/tools/report/sync_drive.sh 測試計畫.pdf 其他檔案…
   ```
   腳本會確認 Google Drive 電腦版有在執行（10-17、10-18、10-23、10-24 都沒開），用 `cat >` 覆寫讓檔案 ID 不變，逐檔 `cmp`。
7. **確認真的上傳了**：掛載點寫入不等於上傳完成。用 Google Drive connector 查檔案大小，和本機相同才算完成。
8. **記錄**：在 `../local-first-ai/TASKS.md` 記下時間、同步了哪些檔、PDF 大小。若是里程碑，也寫進 `PRD.md` 第 5 節 Log。

## 不要做

- 不用 `cp` 或先刪再建來覆寫雲端檔：檔案 ID 會變，老師手上的分享連結會失效。
- 沒得到使用者同意不同步，也不寄信給老師。
