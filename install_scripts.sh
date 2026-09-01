#!/bin/bash

# Install this repository's scripts into the directory cron runs them from.
#
# The updater executes its Python from OSC_SCRIPT_DIR, not from the checkout,
# so that `git pull` cannot swap code out from under a running job. The price
# is that the two can drift: a new build step committed here is not a build
# step cron knows about until it is installed. Run this after changing any
# script, or let updater.sh do it — it installs everything except itself.
#
#   ./install_scripts.sh
#   OSC_SCRIPT_DIR=/somewhere/else ./install_scripts.sh

set -Eeuo pipefail

project_dir=$(cd "$(dirname "$0")" && pwd)
script_dir=${OSC_SCRIPT_DIR:-$HOME/.local/share/open-source-comments}

if [ "$project_dir" = "$script_dir" ]; then
    echo "OSC_SCRIPT_DIR is the checkout itself; nothing to install."
    exit 0
fi

cd "$project_dir"
mkdir -p "$script_dir"

installed=0
changed=()
for file in $(git ls-files '*.py' 'updater.sh' 'install_scripts.sh'); do
    if ! cmp -s "$file" "$script_dir/$file"; then
        changed+=("$file")
    fi
    install -m 700 "$file" "$script_dir/$file"
    installed=$((installed + 1))
done

# Bytecode from a module that has since been deleted or renamed would keep
# importing after the source is gone.
rm -rf "$script_dir/__pycache__"

printf 'Installed %d script(s) into %s\n' "$installed" "$script_dir"
if [ ${#changed[@]} -gt 0 ]; then
    printf 'Updated: %s\n' "${changed[*]}"
else
    printf 'Everything was already current.\n'
fi
