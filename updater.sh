#!/bin/bash
cd /home/slisakov/open-source-comments
nice -n5 git pull

# Update the data on gh stars, last commit etc
nice -n5 python3 get_gh_data.py

# generate data.js (read by index.html)
nice -n5 python3 yaml_2_js.py

# deploy changes
nice -n5 rsync -auvx --delete --numeric-ids data.js index.html /var/www/lisakov.com/projects/open-source-comments/
nice -n5 rsync -auvx --delete --numeric-ids images/ /var/www/lisakov.com/projects/open-source-comments/images/
nice -n5 rsync -auvx --delete --numeric-ids css/ /var/www/lisakov.com/projects/open-source-comments/css/
nice -n5 rsync -auvx --delete --numeric-ids js/ /var/www/lisakov.com/projects/open-source-comments/js/

# update github repo  https://github.com/pozitron57/open-source-comments
nice -n5 git add *
nice -n5 git commit -m 'automatic update'
nice -n5 git push origin master
