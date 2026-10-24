#!/usr/bin/env bash
# 把評測報告（Markdown）轉成 A4 PDF：md2html.py 產 HTML，再用 Chrome 無頭模式列印。
# 只用 macOS 內建的 python3 與已安裝的 Google Chrome，不需要額外套件。
#
# 用法（在 local-first-ai 目錄執行）：
#   ../marge/tools/report/build_pdf.sh 測試計畫.md 測試計畫.pdf
#
# 輸出檔已經存在時直接覆寫，所以先確認舊版有備份（或在 git／雲端有舊版）。
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "用法：$0 輸入.md 輸出.pdf" >&2
  exit 2
fi
src=$1
dst=$2
here=$(cd "$(dirname "$0")" && pwd)
chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 暫存目錄放 HTML 與 Chrome 設定檔，結束時刪掉
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# 1. Markdown → HTML（-I：不從目前目錄載入模組）
python3 -I "$here/md2html.py" "$src" "$tmp/report.html"

# 2. HTML → PDF；獨立的 user-data-dir 避免動到使用者自己的 Chrome 設定
"$chrome" --headless --disable-gpu --no-pdf-header-footer \
  --user-data-dir="$tmp/chrome-profile" \
  --print-to-pdf="$tmp/report.pdf" "file://$tmp/report.html" 2>/dev/null

# 3. 寫到目的地（cat 覆寫，保留原檔的 inode，雲端資料夾裡的檔案 ID 不變）
cat "$tmp/report.pdf" > "$dst"

# 4. 回報頁數與大小，方便和上一版比
pages=$(python3 -I -c "import re,sys;print(len(re.findall(rb'/Type\s*/Page[^s]',open(sys.argv[1],'rb').read())))" "$dst")
echo "$dst：$pages 頁，$(stat -f %z "$dst") bytes"
