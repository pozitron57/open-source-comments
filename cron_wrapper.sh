#!/bin/bash

# What cron runs. install_scripts.sh puts this at
# ~/.local/bin/open-source-comments-update, which is the path the crontab entry
# names; keep the two in step if either ever moves.
#
# Its only job is to choose the environment and hand over. The updater is
# executed from OSC_SCRIPT_DIR rather than from the checkout so that the
# `git pull` it performs cannot replace code while that code is running — see
# the note above the install step in updater.sh.
#
# cron starts with almost no environment, so PATH is set explicitly rather than
# inherited.

PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
OSC_SCRIPT_DIR="$HOME/.local/share/open-source-comments"
PYTHONPATH="$OSC_SCRIPT_DIR:$HOME/open-source-comments"
export PATH PYTHONPATH OSC_SCRIPT_DIR

exec /bin/bash "$OSC_SCRIPT_DIR/updater.sh"
