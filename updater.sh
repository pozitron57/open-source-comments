#!/bin/bash
cd /home/slisakov/open-source-comments

# Update the data on gh stars, last commit etc
python3 get_gh_data.py

# generate data.js (read by index.html)
python3 yaml_2_js.py

# deploy changes
rsync -auvx --delete --numeric-ids data.js index.html /var/www/lisakov.com/projects/open-source-comments/
rsync -auvx --delete --numeric-ids images/ /var/www/lisakov.com/projects/open-source-comments/images/
rsync -auvx --delete --numeric-ids css/ /var/www/lisakov.com/projects/open-source-comments/css/
rsync -auvx --delete --numeric-ids js/ /var/www/lisakov.com/projects/open-source-comments/js/
