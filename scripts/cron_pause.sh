#!/usr/bin/env bash
# Sourced by the administrative upgrader; never by a task or cron.
GLOBALLAND_PAUSED_CRON=()

pause_globalland_cron() {
  local cron_root=$1 backup_root=$2 name
  for name in globalland globalland-think; do
    if [[ -e $cron_root/$name || -L $cron_root/$name ]]; then
      if [[ ! -f $cron_root/$name || -L $cron_root/$name || -e $backup_root/cron-$name || -L $backup_root/cron-$name ]]; then
        echo 'Cannot pause GlobalLand cron safely; inspect files and backup.' >&2
        return 1
      fi
    fi
  done
  for name in globalland globalland-think; do
    if [[ -f $cron_root/$name ]]; then
      mv -- "$cron_root/$name" "$backup_root/cron-$name" || return 1
      GLOBALLAND_PAUSED_CRON+=("$name")
    fi
  done
}

restore_globalland_cron() {
  local cron_root=$1 backup_root=$2 name result=0
  local remaining=()
  for name in "${GLOBALLAND_PAUSED_CRON[@]}"; do
    if ! install -m 644 -- "$backup_root/cron-$name" "$cron_root/$name"; then
      remaining+=("$name")
      result=1
    fi
  done
  GLOBALLAND_PAUSED_CRON=("${remaining[@]}")
  return "$result"
}
