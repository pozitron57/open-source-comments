#!/bin/bash

# Install this repository's scripts where cron runs them from.
#
# Two destinations:
#   OSC_BIN_DIR/open-source-comments-update  <- cron_wrapper.sh, the crontab entry
#   OSC_SCRIPT_DIR/*.py, updater.sh          <- the code the wrapper hands over to
#
# The updater executes its Python from OSC_SCRIPT_DIR, not from the checkout,
# so that `git pull` cannot swap code out from under a running job. The price
# is that the two can drift: a new build step committed here is not a build
# step cron knows about until it is installed. updater.sh now installs the
# Python itself on every run; this script covers the rest — itself, the
# wrapper, and updater.sh, none of which can safely replace themselves while
# they are executing.
#
#   ./install_scripts.sh
#   OSC_SCRIPT_DIR=/elsewhere OSC_BIN_DIR=/elsewhere/bin ./install_scripts.sh

set -Eeuo pipefail

project_dir=$(cd "$(dirname "$0")" && pwd)
script_dir=${OSC_SCRIPT_DIR:-$HOME/.local/share/open-source-comments}
bin_dir=${OSC_BIN_DIR:-$HOME/.local/bin}
wrapper_name=open-source-comments-update

cd "$project_dir"
changed=()

if [ "$project_dir" = "$script_dir" ]; then
    echo "OSC_SCRIPT_DIR is the checkout itself; skipping the script install."
    installed=0
else
    mkdir -p "$script_dir"
    installed=0
    for file in $(git ls-files '*.py' 'updater.sh' 'install_scripts.sh'); do
        cmp -s "$file" "$script_dir/$file" || changed+=("$file")
        install -m 700 "$file" "$script_dir/$file"
        installed=$((installed + 1))
    done
    # Bytecode of a module that has since been renamed or deleted would keep
    # importing after its source is gone.
    rm -rf "$script_dir/__pycache__"
fi

mkdir -p "$bin_dir"
cmp -s cron_wrapper.sh "$bin_dir/$wrapper_name" || changed+=("$wrapper_name")
install -m 700 cron_wrapper.sh "$bin_dir/$wrapper_name"

printf 'Installed %d script(s) into %s\n' "$installed" "$script_dir"
printf 'Installed the cron wrapper as %s/%s\n' "$bin_dir" "$wrapper_name"
if [ ${#changed[@]} -gt 0 ]; then
    printf 'Updated: %s\n' "${changed[*]}"
else
    printf 'Everything was already current.\n'
fi

printf '\nThe crontab entry should name %s/%s — check with `crontab -l`.\n' \
    "$bin_dir" "$wrapper_name"
