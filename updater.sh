#!/bin/bash

## Local
#cd /home/slisakov/yadisk/sites/open-source-comments
#cd /Users/slisakov/Yandex.Disk.localized/sites/open-source-comments

## Remote
cd /home/slisakov/open-source-comments

echo 'git pull'
nice -n5 git pull

## Deploy changes
echo 'rsync'

### Local
#nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.png slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/
#nice -n5 rsync -auvx --delete --numeric-ids images/                             slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/images/
#nice -n5 rsync -auvx --delete --numeric-ids css/                                slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/css/
#nice -n5 rsync -auvx --delete --numeric-ids js/                                 slisakov@lisakov.com:/var/www/lisakov.com/projects/open-source-comments/js/

# Remote
nice -n5 rsync -auvx --delete --numeric-ids data.js index.html stars-v-date.png /var/www/lisakov.com/projects/open-source-comments/
nice -n5 rsync -auvx --delete --numeric-ids images/                             /var/www/lisakov.com/projects/open-source-comments/images/
nice -n5 rsync -auvx --delete --numeric-ids css/                                /var/www/lisakov.com/projects/open-source-comments/css/
nice -n5 rsync -auvx --delete --numeric-ids js/                                 /var/www/lisakov.com/projects/open-source-comments/js/
