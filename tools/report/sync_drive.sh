#!/usr/bin/env bash
# 把成品同步到分享給老師的 Google Drive 資料夾（Google Drive 電腦版的串流模式掛載）。
# 這是對外動作：每次執行前都要先取得使用者同意。
#
# 用法（在 local-first-ai 目錄執行）：
#   ../marge/tools/report/sync_drive.sh --check                 # 只列出雲端現況，不寫入
#   ../marge/tools/report/sync_drive.sh 測試計畫.pdf 模型輸出_補測_dots.md
#
# 雲端資料夾預設用 glob 找；找不到或找到多個時，用 MARGE_DRIVE_DIR 指定。
# 每次寫入成功後，把內容的 SHA-256 記在本機狀態檔（MARGE_SYNC_STATE，預設
# ~/.local/state/marge/sync_drive.tsv）。下次同步時，雲端內容和本機不同，而且
# 雲端雜湊也不是上次記下的值，就代表雲端被人改過：一個都不寫並結束（結束碼 3）；
# 確認後用 MARGE_FORCE=1 重跑。沒有紀錄的檔案（第一次用這版）內容不同時也一樣先停下。
#
# 過去踩過的坑（見 local-first-ai/TASKS.md）：
#   - 10-17、10-18、10-23 三次 Google Drive 電腦版沒在執行，檔案寫進掛載點卻沒上傳。
#   - 10-17 雲端被帳號本人存回舊版，本機以為已同步。所以寫入前後都列出雲端現況給人看。
#   - 用 cat > 覆寫而不是 cp 或先刪再建，雲端檔案 ID 不變，老師手上的分享連結照樣能開。
set -euo pipefail

folder_name="免費AI批閱與雲端串接測試"

# 1. 找雲端資料夾
if [ -n "${MARGE_DRIVE_DIR:-}" ]; then
  dir=$MARGE_DRIVE_DIR
else
  matches=()
  for d in "$HOME"/Library/CloudStorage/GoogleDrive-*/*/"$folder_name"; do
    [ -d "$d" ] && matches+=("$d")
  done
  if [ ${#matches[@]} -ne 1 ]; then
    echo "找到 ${#matches[@]} 個「$folder_name」資料夾，請用 MARGE_DRIVE_DIR 指定" >&2
    exit 1
  fi
  dir=${matches[0]}
fi
echo "雲端資料夾：$dir"

# 2. 確認 Google Drive 電腦版在執行，沒有就啟動並等它起來
if ! pgrep -q -f "Google Drive.app/Contents/MacOS/Google Drive"; then
  echo "Google Drive 電腦版沒在執行，啟動中"
  open -a "Google Drive"
  for _ in $(seq 1 30); do
    pgrep -q -f "Google Drive.app/Contents/MacOS/Google Drive" && break
    sleep 1
  done
  pgrep -q -f "Google Drive.app/Contents/MacOS/Google Drive" || { echo "啟動失敗" >&2; exit 1; }
fi

# 3. 寫入前的雲端現況
echo "== 寫入前"
ls -lT "$dir"
[ "${1:-}" = "--check" ] && exit 0
[ $# -ge 1 ] || { echo "用法：$0 檔案…（或 --check）" >&2; exit 2; }

# 4. 全部檢查完才開始寫。判斷「雲端有沒有被人改過」只看內容雜湊，不看修改時間：
#    本機檔在雲端被改之後才編輯，本機時間會比較新，舊做法會直接蓋掉別人的修改；
#    Google Drive 存回舊版時，修改時間也不一定反映內容。
state=${MARGE_SYNC_STATE:-$HOME/.local/state/marge/sync_drive.tsv}

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

# 狀態檔一行一筆：雜湊<TAB>雲端檔案絕對路徑
recorded() {
  [ -f "$state" ] || return 0
  awk -F'\t' -v p="$1" '$2 == p { h = $1 } END { if (h != "") print h }' "$state"
}

newer=()
for f in "$@"; do
  [ -f "$f" ] || { echo "找不到本機檔案：$f" >&2; exit 1; }
  target="$dir/$(basename "$f")"
  if [ -f "$target" ] && ! cmp -s "$f" "$target" && [ "$(sha "$target")" != "$(recorded "$target")" ]; then
    newer+=("$(basename "$f")")
  fi
done
if [ ${#newer[@]} -gt 0 ] && [ "${MARGE_FORCE:-}" != 1 ]; then
  echo "雲端這些檔案和上次同步的內容不同（或沒有同步紀錄），可能被人改過：${newer[*]}" >&2
  echo "一個都沒寫入。確認要用本機版覆寫，再用 MARGE_FORCE=1 重跑。" >&2
  exit 3
fi

# 5. 逐檔覆寫、逐位元比對，成功後更新狀態檔
mkdir -p "$(dirname "$state")"
for f in "$@"; do
  target="$dir/$(basename "$f")"
  cat "$f" > "$target"
  cmp "$f" "$target"
  # 先寫暫存檔再改名，中途失敗不會留下半份狀態檔
  tmp_state="$state.tmp.$$"
  { [ -f "$state" ] && awk -F'\t' -v p="$target" '$2 != p' "$state"
    printf '%s\t%s\n' "$(sha "$target")" "$target"; } > "$tmp_state"
  mv "$tmp_state" "$state"
  echo "OK $(basename "$f")（$(stat -f %z "$f") bytes）"
done

echo "== 寫入後"
ls -lT "$dir"
echo "掛載點已寫入。上傳是否完成，請用 Google Drive connector 或網頁確認大小。"
