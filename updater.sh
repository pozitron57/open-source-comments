#!/bin/bash

set -Euo pipefail
umask 022

PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PATH

OSC_ALERT_EMAIL=${OSC_ALERT_EMAIL:-lisakov57@gmail.com}
OSC_PROJECT_DIR=${OSC_PROJECT_DIR:-/home/slisakov/open-source-comments}
OSC_SCRIPT_DIR=${OSC_SCRIPT_DIR:-$OSC_PROJECT_DIR}
OSC_STATE_DIR=${OSC_STATE_DIR:-$HOME/.local/state/open-source-comments}
export OSC_ALERT_EMAIL
export PYTHONPATH="$OSC_SCRIPT_DIR:$OSC_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}"

generated_files=(
    apigh/history.json
    data.js
    data.yaml
    index.html
    star-history.js
    stars-v-date.svg
)

current_step="startup"
failure_alert_sent=0
transaction_active=0
backup_dir=""
fallback_lock_dir=""
run_log=""
dns_proxy_pid=""
dns_proxy_port_file=""
dns_fallback_notice_file=""


log_message() {
    printf '%s\n' "$*" >&2
    if command -v logger >/dev/null 2>&1; then
        logger -t open-source-comments-updater -- "$*" || true
    fi
}


send_mail() {
    subject=$1
    body=$2

    if [ -z "$OSC_ALERT_EMAIL" ]; then
        log_message "OSC_ALERT_EMAIL is empty; email alert was not sent"
        return 1
    fi
    if ! command -v mail >/dev/null 2>&1; then
        log_message "mail command is unavailable; email alert was not sent"
        return 1
    fi

    attempt=1
    while [ "$attempt" -le 3 ]; do
        if printf '%s\n' "$body" | mail -s "$subject" "$OSC_ALERT_EMAIL"; then
            return 0
        fi
        log_message "mail delivery attempt ${attempt}/3 failed"
        attempt=$((attempt + 1))
        if [ "$attempt" -le 3 ]; then
            sleep "$attempt"
        fi
    done
    return 1
}


rollback_generation() {
    if [ "$transaction_active" -ne 1 ] || [ -z "$backup_dir" ]; then
        return
    fi

    log_message "Rolling generated files back to their pre-run state"
    git reset --mixed HEAD -- "${generated_files[@]}" >/dev/null 2>&1 || true
    index=0
    for file in "${generated_files[@]}"; do
        backup="$backup_dir/files/$file"
        if [ -f "$backup" ]; then
            mkdir -p "$(dirname "$file")"
            cp -p "$backup" "$file"
        elif [ -f "$backup_dir/missing/$index" ]; then
            rm -f -- "$file"
        fi
        index=$((index + 1))
    done
    transaction_active=0
}


notify_failure() {
    status=$1
    step=$2
    trap - ERR
    failure_alert_sent=1
    rollback_generation

    timestamp=$(date '+%Y-%m-%dT%H:%M:%S%z')
    body="open-source-comments update failed on $(hostname) at ${timestamp}.

Step: ${step}
Exit status: ${status}

The generated files were not deployed."
    if [ -n "$run_log" ] && [ -f "$run_log" ]; then
        recent_output=$(tail -n 50 "$run_log" 2>/dev/null || true)
        body="${body}

Recent output:
${recent_output}"
    fi
    log_message "$body"
    send_mail "open-source-comments update failed: ${step}" "$body" || true
    exit "$status"
}


run_step() {
    current_step=$1
    shift
    printf '\n[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$current_step"
    "$@" || notify_failure "$?" "$current_step"
}


cleanup() {
    status=$?
    trap - ERR
    if [ "$status" -ne 0 ] && [ "$failure_alert_sent" -eq 0 ]; then
        rollback_generation
    fi
    if [ -n "$backup_dir" ] && [ -d "$backup_dir" ]; then
        rm -rf -- "$backup_dir"
    fi
    if [ -n "$fallback_lock_dir" ] && [ -d "$fallback_lock_dir" ]; then
        rmdir "$fallback_lock_dir" 2>/dev/null || true
    fi
    if [ -n "$dns_proxy_pid" ]; then
        kill "$dns_proxy_pid" 2>/dev/null || true
        wait "$dns_proxy_pid" 2>/dev/null || true
    fi
    if [ -n "$dns_proxy_port_file" ]; then
        rm -f -- "$dns_proxy_port_file"
    fi
}


unexpected_error() {
    status=$1
    notify_failure "$status" "$current_step"
}


handle_signal() {
    signal=$1
    notify_failure 130 "received signal ${signal} during ${current_step}"
}


trap cleanup EXIT
trap 'unexpected_error $?' ERR
trap 'handle_signal INT' INT
trap 'handle_signal TERM' TERM
trap 'handle_signal HUP' HUP

mkdir -p "$OSC_STATE_DIR"
dns_fallback_notice_file="$OSC_STATE_DIR/dns-fallback-notified"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$OSC_STATE_DIR/updater.lock"
    if ! flock -n 9; then
        body="A second open-source-comments updater tried to start on $(hostname), but another run still holds the lock."
        log_message "$body"
        send_mail "open-source-comments updater overlap" "$body" || true
        exit 75
    fi
else
    fallback_lock_dir="$OSC_STATE_DIR/updater.lock.d"
    if ! mkdir "$fallback_lock_dir" 2>/dev/null; then
        body="A second open-source-comments updater tried to start on $(hostname), but another run still holds the fallback lock."
        log_message "$body"
        send_mail "open-source-comments updater overlap" "$body" || true
        exit 75
    fi
fi

run_log="$OSC_STATE_DIR/last-run.log"
: > "$run_log"
exec > >(tee -a "$run_log") 2>&1

if ! getent ahostsv4 github.com >/dev/null 2>&1; then
    current_step='start DNS fallback proxy'
    dns_proxy_port_file="$OSC_STATE_DIR/dns-proxy.port"
    rm -f -- "$dns_proxy_port_file"
    python3 "$OSC_SCRIPT_DIR/dns_proxy.py" --port-file "$dns_proxy_port_file" &
    dns_proxy_pid=$!

    attempt=1
    while [ "$attempt" -le 20 ] && [ ! -s "$dns_proxy_port_file" ]; do
        if ! kill -0 "$dns_proxy_pid" 2>/dev/null; then
            notify_failure 1 "$current_step"
        fi
        sleep 0.25
        attempt=$((attempt + 1))
    done
    if [ ! -s "$dns_proxy_port_file" ]; then
        notify_failure 1 "$current_step"
    fi

    dns_proxy_port=$(tr -d '[:space:]' < "$dns_proxy_port_file")
    case "$dns_proxy_port" in
        ''|*[!0-9]*) notify_failure 1 "$current_step" ;;
    esac
    HTTPS_PROXY="http://127.0.0.1:$dns_proxy_port"
    HTTP_PROXY="$HTTPS_PROXY"
    https_proxy="$HTTPS_PROXY"
    http_proxy="$HTTPS_PROXY"
    NO_PROXY="127.0.0.1,localhost"
    no_proxy="$NO_PROXY"
    export HTTPS_PROXY HTTP_PROXY https_proxy http_proxy NO_PROXY no_proxy

    body="System DNS is unavailable on $(hostname). The updater activated its local DNS fallback proxy for this run. TLS hostname verification remains enabled."
    log_message "$body"
    if [ ! -e "$dns_fallback_notice_file" ]; then
        if send_mail "open-source-comments DNS fallback activated" "$body"; then
            touch "$dns_fallback_notice_file"
        fi
    fi
else
    rm -f -- "$dns_fallback_notice_file"
fi

cd "$OSC_PROJECT_DIR"

run_step 'verify clean repository before update' test -z "$(git status --porcelain --untracked-files=no)"
run_step 'pull repository with fast-forward only' nice -n5 git pull --ff-only
run_step 'verify clean repository after pull' test -z "$(git status --porcelain --untracked-files=no)"

backup_dir=$(mktemp -d "${TMPDIR:-/tmp}/open-source-comments-updater.XXXXXX")
mkdir -p "$backup_dir/files" "$backup_dir/missing"
index=0
for file in "${generated_files[@]}"; do
    if [ -f "$file" ]; then
        mkdir -p "$backup_dir/files/$(dirname "$file")"
        cp -p "$file" "$backup_dir/files/$file"
    else
        touch "$backup_dir/missing/$index"
    fi
    index=$((index + 1))
done
transaction_active=1

run_step 'collect repository data' nice -n5 python3 "$OSC_SCRIPT_DIR/get_data.py"
run_step 'render index.html' nice -n5 python3 "$OSC_SCRIPT_DIR/md_to_html.py"
run_step 'generate data.js' nice -n5 python3 "$OSC_SCRIPT_DIR/yaml_2_js.py"
run_step 'generate stars chart' nice -n5 python3 "$OSC_SCRIPT_DIR/plot-stars.py"
run_step 'generate star history' nice -n5 python3 "$OSC_SCRIPT_DIR/history_2_js.py"
run_step 'validate all generated outputs' nice -n5 python3 "$OSC_SCRIPT_DIR/validate_outputs.py"
run_step 'check generated diff for whitespace errors' git diff --check -- "${generated_files[@]}"
run_step 'stage generated data' nice -n5 git add -- "${generated_files[@]}"

if git diff --cached --quiet; then
    echo 'No generated changes to commit'
else
    run_step 'commit generated data' nice -n5 git commit -m 'automatic update'
fi
transaction_active=0

run_step 'push generated data' nice -n5 git push origin HEAD:master

deploy_root=/var/www/lisakov.com/projects/open-source-comments
run_step 'deploy generated files' nice -n5 rsync -a --delay-updates \
    data.js star-history.js index.html stars-v-date.svg "$deploy_root/"
# --delete keeps the deploy root a mirror of the repository. The GoAccess
# reports under /day/ and /week/ list this project's old DataTables URLs, but
# those are access-log entries, not references: no page links to them.
run_step 'deploy CSS' nice -n5 rsync -a --delete-delay --delay-updates \
    css/ "$deploy_root/css/"
run_step 'deploy JavaScript' nice -n5 rsync -a --delete-delay --delay-updates \
    js/ "$deploy_root/js/"
run_step 'verify deployed data.js' cmp -s data.js "$deploy_root/data.js"
run_step 'verify deployed star history' cmp -s star-history.js "$deploy_root/star-history.js"
run_step 'verify deployed index.html' cmp -s index.html "$deploy_root/index.html"
run_step 'verify deployed chart' cmp -s stars-v-date.svg "$deploy_root/stars-v-date.svg"
run_step 'verify clean repository after update' test -z "$(git status --porcelain --untracked-files=no)"

echo 'open-source-comments update completed successfully'
