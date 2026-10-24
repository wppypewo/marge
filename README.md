# Marge

用免費或自己掌控的 AI 模型，批閱學生的手寫法文作文。名稱取自法文 marge（頁邊），老師在作文旁寫批改的地方。

**階段：評測完成，產品還沒開始做。** 本 repo 放產品需求、決策紀錄和評測工具；學生端的 App 還不存在。

## 要解決的問題

一門法文寫作課的學生每週手寫一份短文，用老師提供的批閱 prompt 在 Gemini 上拍照、OCR、批閱。2026-10-09 起 Gemini 免費版把多數請求交給 Flash-Lite，批閱品質下降：同一份作文，prompt 規定 ⚠️ 少於 12 個，Flash-Lite 標了 28 個，而且只標位置、不寫改正形式。

免費的替代模型多半要拿作文資料訓練。2026-10-16～10-23 的評測比較了：

- Gemini 免費版與付費版
- OpenRouter 上的 Nemotron 3.5 Super VL、dots
- 本機的 Qwen3.6

評測結果：品質最好的免費模型 Nemotron，要開啟「免費端點可用請求資料訓練」才能用。不必開這個選項的 dots，多數項目比不上 Nemotron。四項待定決策見 [PRD 第 3.2 節](PRD.md#32-待定決策)。

## 檔案

| 檔案 | 內容 |
|---|---|
| [`PRD.md`](PRD.md) | 問題、目標用戶、功能需求 F1～F11、待定決策 D1～D4、ADR、Log、Open issues |
| [`TASKS.md`](TASKS.md) | 進度與交接 |
| [`CLAUDE.md`](CLAUDE.md) | 給 Claude Code 的路由表：什麼問題讀哪個檔、什麼工作用哪個 skill 或腳本 |
| [`.claude/skills/`](.claude/skills/) | 三個重複出現的工作流程：更新報告並同步、評測新模型、查證供應商資料政策 |
| [`tools/bench/`](tools/bench/) | 評測腳本：本機模型跑批閱流程、OCR 比對、批閱格式檢查、盲評表產生與回填 |
| [`tools/report/`](tools/report/) | 報告轉 PDF、同步到 Google Drive |

## 評測證據不公開

評測報告、模型回覆和 OCR 原文放在旁邊的 `../local-first-ai/` 目錄，裡面有學生作文，所以沒有放上 GitHub。PRD 裡指向 `../local-first-ai/` 的連結在 GitHub 上打不開，只有本機能用。

## 工具用法

Python 腳本只用標準函式庫。`build_pdf.sh` 用 Google Chrome 無頭模式列印 PDF，`sync_drive.sh` 需要 Google Drive 電腦版，兩者都只在 macOS 上測過。各腳本開頭有用法。在證據目錄執行：

```bash
# 比對 OCR 與參考轉寫
python3 -I ../marge/tools/bench/ocr_diff.py OCR_模型名.txt
# 檢查批閱格式（⚠️ 數量、字數、7 段標題）
python3 -I ../marge/tools/bench/check_grading.py 回覆_模型名.txt
```

證據目錄預設是 `../local-first-ai`，可用環境變數 `MARGE_EVIDENCE` 改。
