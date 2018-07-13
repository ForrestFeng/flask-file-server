#/bin/sh

uwsgi --wsgi-file /home/logadmin/flask-file-server/file_server.py --gevent 1000 --http-websockets --master --callable app --http :8000 --static-map /\&=/home/xrslog/ --uid xrslog --gid xrslog


# This shell should be run as xrslog from other user's shell
# su - xrslog /home/logadmin/flask-file-server/run_file_server.sh 