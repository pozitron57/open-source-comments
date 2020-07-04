#!/bin/bash
## Local
cd /home/slisakov/yadisk/sites/open-source-comments
## Remote
#cd /home/slisakov/open-source-comments
echo 'git pull'
nice -n5 git pull

# Update the data on gh stars, last commit etc
echo 'python3 get_data.py'
nice -n5 python3 get_data.py

# Update date in index.html
echo 'python3 md_to_html.py'
nice -n5 python3 md_to_html.py

# generate data.js (read by index.html)
echo 'python3 yaml_2_js.py'
nice -n5 python3 yaml_2_js.py

# Plot stars-vs-date and save stars-v-date.png
echo 'python3 plot-stars.py'
nice -n5 python3 plot-stars.py

# deploy changes
echo 'rsync'
## Local
nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.png slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/
nice -n5 rsync -auvx --delete --numeric-ids images/                             slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/images/
nice -n5 rsync -auvx --delete --numeric-ids css/                                slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/css/
nice -n5 rsync -auvx --delete --numeric-ids js/                                 slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/js/

## Remote
#nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.png /var/www/lisakov.com/projects/open-source-comments/
#nice -n5 rsync -auvx --delete --numeric-ids images/                             /var/www/lisakov.com/projects/open-source-comments/images/
#nice -n5 rsync -auvx --delete --numeric-ids css/                                /var/www/lisakov.com/projects/open-source-comments/css/
#nice -n5 rsync -auvx --delete --numeric-ids js/                                 /var/www/lisakov.com/projects/open-source-comments/js/

# update github repo  https://github.com/pozitron57/open-source-comments
echo 'git add *'
nice -n5 git add *
echo 'git commit -m 'automatic update''
nice -n5 git commit -m 'automatic update'
echo 'git push origin master'
nice -n5 git push origin master
