# Marge 任務清單

最後更新：2026-10-24（交付 script 與 skill）

## Handover（新 session 先讀這段）

- **現況**：評測完成（2026-10-16～10-23，證據在 `../local-first-ai/`）。10-24 老師建議把專案當成服務性產品、建治理文件，於是新建本 repo，寫了 `PRD.md` 草稿。產品本身還沒開始做。
- **卡在哪**：功能需求要等 PRD 3.2 的四個決策（D1 供應商、D2 學生端 App、D3 prompt 交付方式、D4 存檔位置）。D1 要先實測 Cerebras、Cloudflare（OI-1）；D2、D4 要先問老師學生用什麼手機（OI-5、OI-9）。
- **下一步**：見下方「待辦」第一項。
- **工具**：腳本在 `tools/`、skill 在 `.claude/skills/`（報告同步、新模型評測、供應商查證），用哪個看 `CLAUDE.md` 第二張路由表。
- **注意**：`../local-first-ai` 不是 git repo，相對位置是依賴，見 `CLAUDE.md`。同步雲端前 Google Drive 電腦版常沒開（10-17、10-18、10-23、10-24 都是），`sync_drive.sh` 會自己啟動。

## 待辦

- [x] Claude：交付評測 session 用過的 script 與 skill（老師 10-24 來信第 4 點，10-24 完成）
  - [x] `../local-first-ai/bench/` 複製（不是搬）到 `tools/bench/`，原檔留著對應報告引用。沒有寫死的 API key（`run_bench.py` 從環境變數讀）；參考轉寫 20 個長句片段在本 repo 搜尋 0 命中。改動：證據路徑改成 `MARGE_EVIDENCE`（預設 `../local-first-ai`）、用法改成 `../marge/tools/bench/`、`make_blind_pack.py` 的「測試計畫 8.1」改成現行的「附錄 A.2」
  - [x] 驗證：`check_grading.py`、`fill_blind_md.py`、`make_blind_html.py` 新舊版輸出逐位元相同；`ocr_diff.py`、`make_blind_pack.py` 跑得起來（後者順序隨機，無法逐位元比）
  - [x] 新增 `tools/report/`：`md2html.py`（原本只在 session 暫存目錄）、`build_pdf.sh`（重建 24 頁，文字與現版 PDF 相同）、`sync_drive.sh`（`--check` 跑過；Drive 電腦版又沒開，腳本自動啟動）
  - [x] 寫 3 個 skill：`report-publish`、`grading-eval`、`provider-policy-check`
  - [x] `CLAUDE.md` 加第二張路由表與環境變數；`.gitignore` 加 `tools/bench/results/`；`../local-first-ai/CLAUDE.md`（新檔）指回本 repo
- [x] 你：commit、push 上面這批（10-24）
- [x] 你：initial commit（10-24，`238e4d0`）
- [x] 建 GitHub remote：`wppypewo/marge`（10-24 建立，10-25 帳號由 zhuang060329-bit 改名；同日為公開而重寫歷史，拿掉老師姓名與課名，重建為 public。舊歷史留在 private 的 `marge-old-private`、`marge-old-private-2`）
- [x] 把 marge 記進工作區 `~/ClaudeCode/CLAUDE.md` 的 repo 清單與 `WORKSPACE_STATE.md`（10-24）
- [ ] 你：寫信問老師 PRD 2.1「待問老師」的問題（OI-9）
- [ ] 實測 Cerebras `qwen-3.8-27b`、Cloudflare Workers AI（OI-1），流程同報告 2.3
- [ ] 跑修正版 prompt（OI-2）、同模型重跑一次（OI-3）

## 已完成

- [x] 2026-10-24：老師來信三題已在對話中回答（命名、PRD 時機、skill 候選）
- [x] 2026-10-24：使用者決定產品名 Marge、新建資料夾、寫 PRD、`git init`（ADR-011）
- [x] 2026-10-24：建立 `projects/marge`，`git init -b main`，寫 `PRD.md`、`CLAUDE.md`、`TASKS.md`、`.gitignore`
- [x] 2026-10-24：交付 script 與 skill 到 `tools/`、`.claude/skills/`，路由寫進 `CLAUDE.md`
