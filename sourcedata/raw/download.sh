#!/bin/bash
# Robust sequential downloader for figshare raw dataset.
# Skips files whose md5 already matches; retries; re-fetches corrupt files.
set -u
cd "$(dirname "$0")"
# Hard mutex: only one instance may run (harness can double-spawn).
exec 9>.download.lock
if ! flock -n 9; then
  echo "$(date '+%F %T') another download.sh holds the lock; exiting" >> download_progress.log
  exit 0
fi
MANIFEST=manifest.tsv
LOG=download_progress.log
ok=0; fail=0; skip=0; n=0
total=$(wc -l < "$MANIFEST")
echo "$(date '+%F %T') START download, $total files" | tee -a "$LOG"
while IFS=$'\t' read -r url name md5; do
  n=$((n+1))
  # already present and correct?
  if [ -f "$name" ]; then
    have=$(md5sum "$name" | awk '{print $1}')
    if [ "$have" = "$md5" ]; then
      skip=$((skip+1)); echo "$(date '+%T') [$n/$total] SKIP  $name (md5 ok)" | tee -a "$LOG"; continue
    fi
  fi
  # download with retries. First attempt resumes a partial; on any md5
  # mismatch we delete and re-fetch fresh (avoids corrupt-but-complete files).
  attempt=0; done=0
  while [ $attempt -lt 6 ]; do
    attempt=$((attempt+1))
    if [ $attempt -eq 1 ] && [ -f "$name" ]; then
      curl -L -s --fail -C - --connect-timeout 30 --max-time 1800 \
           --retry 3 --retry-delay 5 -o "$name" "$url"
    else
      rm -f "$name"
      curl -L -s --fail --connect-timeout 30 --max-time 1800 \
           --retry 3 --retry-delay 5 -o "$name" "$url"
    fi
    rc=$?
    have=$(md5sum "$name" 2>/dev/null | awk '{print $1}')
    if [ "$have" = "$md5" ]; then done=1; break; fi
    echo "$(date '+%T') [$n/$total] retry $attempt $name (rc=$rc md5=$have want=$md5)" | tee -a "$LOG"
    sleep 5
  done
  if [ $done -eq 1 ]; then
    ok=$((ok+1)); echo "$(date '+%T') [$n/$total] OK    $name" | tee -a "$LOG"
  else
    fail=$((fail+1)); echo "$(date '+%T') [$n/$total] FAIL  $name" | tee -a "$LOG"
  fi
done < "$MANIFEST"
echo "$(date '+%F %T') DONE ok=$ok skip=$skip fail=$fail total=$total" | tee -a "$LOG"
