## Deploy to Debian Web Server

Download net installer from  https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-9.4.0-amd64-netinst.iso

Burin into CD or USB

Insert into Server reboot to CD or USB

Select GUI install

Server Name: LogServer

Root Password: logadmin

New User: logadmin

New User Password: logadmin

Server  Type : Web Server uWSGI + SSH Server  + proFTPd Server(See screenshot)



## Config to add user to sudos on Debian

This allow you to use sudo to run root  commands

run as root

```bash
su root
apt-get update
apt-get install sudo -y
usermod -aG sudo username
```



## Disable Apache Server (we use uWSGI server)

```bash
sudo systemctl stop apache2
sudo systemctl disable apache2
```



## Install Python3.5 if not installed



```bash
sudo apt-get install python3

```

## Install python3 packages

```bash
sudo pip3 install uwsgi pandas plotly ipython jinja2 markdown 
sudo pip3 install flask humanize flask-socketio gevent  
```



## Configure to ssh to your Linux box Debian

Replace username with real user, e.g. logadmin

```
mkdir ~/.ssh
chown -R username:username /home/username/.ssh
chmod 0700 /home/username/.ssh
touch /home/username/.ssh/authorized_keys
chmod 0600 /home/username/.ssh/authorized_keys

Copy your publish key value to authorized_keys (you must have the private key on your Windows client) 
If you have your key in another ssh server you can use scp to copy it.
Sample cmd
scp account@myserver:/home/.ssh/account.pub ~/home/.ssh/authorized_keys

If not you can copy your pub key to usb then copy to the server.

(If needed reinsatall openssh-server and restart service)
apt-get install openssh-server 
service restart sshd
or 
seystemctl restart sshd 
```



## Install Git and Pull flask-file-server

User logadmin will manages all our code of loganalysis and flask web server

```bash
sudo apt-get install git
cd /home/logadmin

git clone https://github.com/ForrestFeng/flask-file-server.git
TODO 
git clone ...loganalysis form some where

```



## Create a new user xrslog with password xrslog 

Log files will be put to the home folder of the user. FTP user of xrslog can upload log files to their home folder easily.

```bash
sudo useradd xrslog 
```



## Install and  configure the proftp server

We will use proftpd to set up ftp server

```bash
sudo apt-get insatll proftpd ftp
```

Config the proftp 

```bash
cd /etc/proftpd
sudo cp proftpd.conf proftpd.conf.bak
vi proftpd.conf

--------- Change to  the file -----------
Remove leading '#' of this line line of 
#DefaultRoot                 ~
-->
DefaultRoot                 ~

Find ServerName item, change server name to "LogServer"
ServerName                    "Debian"
-->
ServerName                    "LogServer"

Do not support IPv6
 UseIPv6                               on
-->
 #UseIPv6                               on


Restart the proftpd server
sudo systemctl restart proftpd

```



## Run the Web Server

Run the uwsgi command as xrslog user on port 8000.

NOTE: This is one line command with lots of args

```bash
su - xrslog
uwsgi --wsgi-file /home/logadmin/flask-file-server/file_server.py --gevent 1000 --http-websockets --master --callable app  --http :8000  --static-map /\&=/home/xrslog/  --uid xrslog --gid xrslog

```



## Install Gitea gitea-1.4.3-linux-amd64 

Install ref https://gist.github.com/appleboy/36313a525fbef673f8aefadb9c0f8247



Download page of Gitea binary from [download page](https://dl.gitea.io/gitea) 

```
Gitea

Gitea is a painless self-hosted Git service. It is similar to GitHub, Bitbucket or Gitlab. The initial development have been done on Gogs but we have forked it and named it Gitea. If you want to read more about the reasons why we have done that please read this blog post.

Add git user
$ useradd git
$ su - git   (set password as git too)
$ cd

Download Gitea binary from download page first.

$ wget https://dl.gitea.io/gitea/1.4.3/gitea-1.4.3-linux-amd64
$ ln gitea gitea-1.4.3-linux-amd64
$ chmod +x gitea
$ ./gitea web

Run gitea command as git user. default port is 3000.



```

gitea admin:  giteaadmin * giteaadmin

Access to gitea http://10.112.14.78:3000

