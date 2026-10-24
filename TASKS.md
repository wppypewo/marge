# Marge 任務清單

最後更新：2026-10-24

## Handover（新 session 先讀這段）

- **現況**：評測完成（2026-10-16～10-23，證據在 `../local-first-ai/`）。10-24 老師建議把專案當成服務性產品、建治理文件，於是新建本 repo，寫了 `PRD.md` 草稿。產品本身還沒開始做。
- **卡在哪**：功能需求要等 PRD 3.2 的四個決策（D1 供應商、D2 學生端 App、D3 prompt 交付方式、D4 存檔位置）。D1 要先實測 Cerebras、Cloudflare（OI-1）；D2、D4 要先問老師學生用什麼手機（OI-5、OI-9）。
- **下一步**：見下方「待辦」第一項。
- **注意**：`../local-first-ai` 不是 git repo，相對位置是依賴，見 `CLAUDE.md`。

## 待辦

- [ ] Claude：交付評測 session 用過的 script 與 skill（老師 10-24 來信第 4 點），等使用者下指令再做
  - [ ] 把 `../local-first-ai/bench/` 的腳本搬或複製進本 repo（`check_grading.py`、`ocr_diff.py`、`run_bench.py`、`run_grading_local.py`、盲評三支與模板、`prompts.json`），先確認哪些帶 API key 或學生資料
  - [ ] 補「報告轉 PDF 並同步雲端」的腳本（目前每次手動；10-17、10-18、10-23 都遇到 Google Drive app 沒開，10-17 雲端版本被舊檔蓋回）
  - [ ] 寫 3 個 skill：報告更新並同步雲端、新模型批閱評測、供應商資料政策查證
  - [ ] 在 `CLAUDE.md` 路由表加上腳本與 skill 的位置
- [ ] 你：決定 initial commit 的時間（目前檔案未提交）
- [ ] 你：決定要不要建 GitHub remote（private 或 public）
- [ ] 你：確認是否把 marge 記進工作區 `~/ClaudeCode/CLAUDE.md` 的 repo 清單與 `WORKSPACE_STATE.md`
- [ ] 你：寫信問老師 PRD 2.1「待問老師」的問題（OI-9）
- [ ] 實測 Cerebras `qwen-3.8-27b`、Cloudflare Workers AI（OI-1），流程同報告 2.3
- [ ] 跑修正版 prompt（OI-2）、同模型重跑一次（OI-3）

## 已完成

- [x] 2026-10-24：老師來信三題已在對話中回答（命名、PRD 時機、skill 候選）
- [x] 2026-10-24：使用者決定產品名 Marge、新建資料夾、寫 PRD、`git init`（ADR-011）
- [x] 2026-10-24：建立 `projects/marge`，`git init -b main`，寫 `PRD.md`、`CLAUDE.md`、`TASKS.md`、`.gitignore`
