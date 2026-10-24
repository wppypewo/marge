---
name: grading-eval
description: 用 C4-B1 批閱 prompt 評測一個新的 AI 模型或供應商（雲端免費模型或本機模型）：照三則流程跑批閱、用程式檢查 OCR 與格式、做盲評表給人判斷、把結果寫進報告與 PRD。用在「測一下某某模型」「補測」「加測本機模型」「這個模型批得怎樣」這類要求。
---

# 新模型批閱評測

評測方法以報告 `../local-first-ai/測試計畫.md` 第 2.3、2.4 節與附錄 A.1 為準，本檔只列操作步驟。指令在 `../local-first-ai/` 執行，腳本在本 repo 的 `tools/bench/`。

## 0. 開始前

- **查資料政策**：先用 `provider-policy-check` skill 查這個供應商的免費層會不會拿資料訓練。會訓練的話，要使用者同意才跑（ADR-001 的做法：開訓練選項只限評測，測完關回）。
- **記下**模型 ID（OpenRouter 要用完整 ID，例如 `dots-studio/dots-3-note-preview:free`）、供應商、日期。

## 1. 跑三則流程（報告 2.3）

- **雲端模型（使用者在 Open Minis 上跑）**：新對話、關閉記憶。三則依序是 prompt 原文、學習單照片、參考轉寫〈轉寫〉一節。請使用者記兩段時間（第二則到 OCR 回完、第三則到批閱完成），存完整對話與 OpenRouter Logs 截圖。
- **本機或 OpenAI 相容 API（Claude 可以自己跑）**：
  ```bash
  python3 -I ../marge/tools/bench/run_grading_local.py --base-url http://127.0.0.1:18434/v1 \
      --label "模型名 設定" --thinking off --out 回覆_本機_模型名.txt
  ```
- **模型不按流程走時**（例如 dots 要求再回 `oui`）：照它的要求補送，並在報告寫明。等太久就重傳的那次不採用，要新開對話重跑一次。

## 2. 程式判斷

```bash
python3 -I ../marge/tools/bench/ocr_diff.py OCR_模型名.txt
python3 -I ../marge/tools/bench/check_grading.py 回覆_模型名.txt
```

- `OCR_*.txt` 只放轉錄本身，模型前後加的說明要刪掉。
- 計字一律用空白分隔（ADR-005）。

## 3. 人工判斷（盲評）

```bash
python3 -I ../marge/tools/bench/make_blind_pack.py 回覆_A.txt 回覆_B.txt --out 盲評表_X.md --key 盲評對照_X.md
python3 -I ../marge/tools/bench/make_blind_html.py 盲評表_X.md --out 盲評表_X.html
# 使用者在瀏覽器填完、匯出 JSON 後
python3 -I ../marge/tools/bench/fill_blind_md.py 盲評表_X.md 結果.json --out 盲評表_X_已填.md
```

- 語言判斷（誤判、漏掉的錯、理由合不合理）由使用者評，Claude 不當評分者。使用者填完前不要打開對照檔。
- 只有一個模型時不是盲評，報告要寫明。
- 內建瀏覽器的分頁不能下載檔案：使用者在那裡填的話，從頁面的 localStorage 讀出結果。

## 4. 寫進文件

- 報告：結果補進 3.1、附錄 A.2，再改摘要、結論。之後用 `report-publish` skill 重做 PDF、同步雲端（要先問使用者）。
- `PRD.md`：第 3.2 節 D1 的選項與證據；若因此做了決定，在第 4 節新增 ADR；第 5 節 Log 加一列；對應的 Open issue（例如 OI-1）標「已解決」。
- 雲端模型只跑一次的，結論要註明 n=1（OI-3）。

## 不要做

- 不把學生姓名、學號、作文照片 commit 進本 repo。
- 不用模型自己報的字數當結果。
