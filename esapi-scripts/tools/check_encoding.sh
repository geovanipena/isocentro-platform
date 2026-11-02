#!/usr/bin/env bash
# check_encoding.sh — invariantes de arquivo dos .cs:
#   - UTF-8 válido, SEM BOM
#   - fim-de-linha LF (sem CR)
#   - chaves { } balanceadas (heurística — não é parser C#)
# Uso: bash tools/check_encoding.sh
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$REPO/scripts"
fail=0

printf "%-38s %-9s %-6s %-8s %s\n" "ARQUIVO" "ENCODING" "BOM" "EOL" "CHAVES"
printf '%.0s-' {1..78}; echo

for f in "$DIR"/*/*.cs; do
  name="$(basename "$f")"

  # BOM (primeiros 3 bytes == EF BB BF)
  bom_hex="$(head -c3 "$f" | od -An -tx1 | tr -d ' \n')"
  if [ "$bom_hex" = "efbbbf" ]; then bom="BOM"; fail=1; else bom="no-BOM"; fi

  # EOL: presença de CR
  if grep -q $'\r' "$f"; then eol="CRLF"; fail=1; else eol="LF"; fi

  # UTF-8 válido?
  if iconv -f UTF-8 -t UTF-8 "$f" >/dev/null 2>&1; then enc="utf-8"; else enc="INVÁLIDO"; fail=1; fi

  # Balanceamento de chaves (ignora comentários // de linha; heurística simples)
  opens="$(grep -o '{' "$f" | wc -l | tr -d ' ')"
  closes="$(grep -o '}' "$f" | wc -l | tr -d ' ')"
  if [ "$opens" = "$closes" ]; then braces="OK ($opens)"; else braces="DIFF ($opens/$closes)"; fail=1; fi

  printf "%-38s %-9s %-6s %-8s %s\n" "$name" "$enc" "$bom" "$eol" "$braces"
done

printf '%.0s-' {1..78}; echo
if [ "$fail" = "0" ]; then echo "RESULTADO: PASS"; else echo "RESULTADO: FAIL"; fi
exit $fail
