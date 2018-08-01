#/bin/sh

#uwsgi --wsgi-file /home/logadmin/flask-file-server/file_server.py --gevent 1000 --http-websockets --master --callable app --http :8000 --static-map /a=/home/xrslog/ --uid xrslog --gid xrslog
# uwsgi running file server, socketio does not beable to send message to we client.
#uwsgi --wsgi-file /home/logadmin/flask-file-server/file_server.py --http-websockets --master --callable app --http :6000 --static-map /\&=/home/xrslog/Logs --uid xrslog --gid xrslog


# For now let's run it with the flask webserver
python3 /home/logadmin/flask-file-server/file_server.py

