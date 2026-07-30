#!/bin/bash

PATH="$HOME/.local/bin:$PATH"
export PATH

OSC_ALERT_EMAIL=${OSC_ALERT_EMAIL:-lisakov57@gmail.com}
OSC_MOVE_NOTICE_FILE=${OSC_MOVE_NOTICE_FILE:-/tmp/open-source-comments-repository-moves.txt}
OSC_GET_DATA_SCRIPT=${OSC_GET_DATA_SCRIPT:-get_data.py}
export OSC_MOVE_NOTICE_FILE

notify_failure() {
    status=$1
    step=$2
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S%z')
    message="open-source-comments update failed on $(hostname) at ${timestamp}: ${step} exited with status ${status}"

    printf '%s\n' "$message" >&2
    if command -v logger >/dev/null 2>&1; then
        logger -t open-source-comments-updater -- "$message"
    fi

    if [ -n "${OSC_ALERT_EMAIL:-}" ]; then
        if command -v mail >/dev/null 2>&1; then
            printf '%s\n' "$message" | mail -s "open-source-comments update failed" "$OSC_ALERT_EMAIL"
        else
            printf '%s\n' "OSC_ALERT_EMAIL is set, but the mail command is unavailable" >&2
        fi
    fi

    exit "$status"
}

run_step() {
    step=$1
    shift
    echo "$step"
    "$@" || notify_failure "$?" "$step"
}

notify_repository_moves() {
    if [ ! -s "$OSC_MOVE_NOTICE_FILE" ]; then
        return
    fi

    timestamp=$(date '+%Y-%m-%dT%H:%M:%S%z')
    heading="open-source-comments followed a repository redirect on $(hostname) at ${timestamp}. The update will continue."

    printf '%s\n' "$heading" >&2
    cat "$OSC_MOVE_NOTICE_FILE" >&2
    if command -v logger >/dev/null 2>&1; then
        logger -t open-source-comments-updater -- "$heading $(tr '\n' ' ' < "$OSC_MOVE_NOTICE_FILE")"
    fi

    if [ -n "${OSC_ALERT_EMAIL:-}" ]; then
        if command -v mail >/dev/null 2>&1; then
            {
                printf '%s\n\n' "$heading"
                cat "$OSC_MOVE_NOTICE_FILE"
            } | mail -s "open-source-comments repository moved" "$OSC_ALERT_EMAIL" ||
                printf '%s\n' "Could not send repository redirect email" >&2
        else
            printf '%s\n' "OSC_ALERT_EMAIL is set, but the mail command is unavailable" >&2
        fi
    fi
}

## Local
#cd /home/slisakov/yadisk/sites/open-source-comments
#cd /Users/slisakov/Yandex.Disk.localized/sites/open-source-comments

## Remote
cd /home/slisakov/open-source-comments

run_step 'git pull' nice -n5 git pull

# Update the data on gh stars, last commit etc
run_step 'python3 get_data.py' nice -n5 python3 "$OSC_GET_DATA_SCRIPT"
notify_repository_moves

# Update date in index.html
run_step 'python3 md_to_html.py' nice -n5 python3 md_to_html.py

# generate data.js (read by index.html)
run_step 'python3 yaml_2_js.py' nice -n5 python3 yaml_2_js.py

# Plot stars-vs-date and save stars-v-date.svg
run_step 'python3 plot-stars.py' nice -n5 python3 plot-stars.py

## Deploy changes
echo 'rsync'

### Local
#nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.svg slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/
#nice -n5 rsync -auvx --delete --numeric-ids images/                             slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/images/
#nice -n5 rsync -auvx --delete --numeric-ids css/                                slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/css/
#nice -n5 rsync -auvx --delete --numeric-ids js/                                 slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/js/

# Remote
run_step 'deploy generated files' nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.svg /var/www/lisakov.com/projects/open-source-comments/
run_step 'deploy images' nice -n5 rsync -auvx --delete --numeric-ids images/ /var/www/lisakov.com/projects/open-source-comments/images/
run_step 'deploy CSS' nice -n5 rsync -auvx --delete --numeric-ids css/ /var/www/lisakov.com/projects/open-source-comments/css/
run_step 'deploy JavaScript' nice -n5 rsync -auvx --delete --numeric-ids js/ /var/www/lisakov.com/projects/open-source-comments/js/

# update github repository https://github.com/pozitron57/open-source-comments
run_step 'stage generated data' nice -n5 git add -- apigh/history.json data.js data.yaml index.html stars-v-date.svg
if git diff --cached --quiet; then
    echo 'No generated changes to commit'
else
    run_step 'commit generated data' nice -n5 git commit -m 'automatic update'
fi
run_step 'git push origin master' nice -n5 git push origin master
