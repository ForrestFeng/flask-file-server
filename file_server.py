from flask import Flask, make_response, request, session, render_template, send_file, Response
from flask.views import MethodView
from werkzeug import secure_filename
from datetime import datetime
import humanize
import os
import re
import stat
import json
import mimetypes
import pathlib

DEBUG = True
app = Flask(__name__, static_url_path='/assets', static_folder='assets')
root = os.path.join(os.path.expanduser('~'), 'Logs')
# Used to indentify folders that contain trace reports file.
# Such a folder a href will link to hostname/&/path/to/reprotfolder 
# which will be served by apache2 for better performance.
# Such a folder must contains index.html file for the report.
# Users can just click the report folder to see the report :)
# Folder name is in lower case to easy the judge in index.html
reportfolders = ['tracereport']
# Used to indentify folders that contains xrs trace log file. 
# Such a folder contains one or mall log files to be analyzed.
# Usaully there will be a "Analyze" button on the right of the folder row.
# User click this button to triger log analyze
# Folder name is in lower case to easy the judge in index.html
xrslogfolders = ['tracelog']
ignored = ['.bzr', '$RECYCLE.BIN', '.DAV', '.DS_Store', '.git', '.hg', '.htaccess', '.htpasswd', '.Spotlight-V100', '.svn', '__MACOSX', 'ehthumbs.db', 'robots.txt', 'Thumbs.db', 'thumbs.tps']
datatypes = {'audio': 'm4a,mp3,oga,ogg,webma,wav', 'archive': '7z,zip,rar,gz,tar', 'image': 'gif,ico,jpe,jpeg,jpg,png,svg,webp', 'pdf': 'pdf', 'quicktime': '3g2,3gp,3gp2,3gpp,mov,qt', 'source': 'atom,bat,bash,c,cmd,coffee,css,hml,js,json,java,less,markdown,md,php,pl,py,rb,rss,sass,scpt,swift,scss,sh,xml,yml,plist', 'text': 'txt', 'video': 'mp4,m4v,ogv,webm', 'website': 'htm,html,mhtm,mhtml,xhtm,xhtml'}
icontypes = {'fa-music': 'm4a,mp3,oga,ogg,webma,wav', 'fa-archive': '7z,zip,rar,gz,tar', 'fa-picture-o': 'gif,ico,jpe,jpeg,jpg,png,svg,webp', 'fa-file-text': 'pdf', 'fa-film': '3g2,3gp,3gp2,3gpp,mov,qt', 'fa-code': 'atom,plist,bat,bash,c,cmd,coffee,css,hml,js,json,java,less,markdown,md,php,pl,py,rb,rss,sass,scpt,swift,scss,sh,xml,yml', 'fa-file-text-o': 'txt', 'fa-film': 'mp4,m4v,ogv,webm', 'fa-globe': 'htm,html,mhtm,mhtml,xhtm,xhtml'}

@app.template_filter('size_fmt')
def size_fmt(size):
    return humanize.naturalsize(size)

@app.template_filter('time_fmt')
def time_desc(timestamp):
    mdate = datetime.fromtimestamp(timestamp)
    str = mdate.strftime('%Y-%m-%d %H:%M:%S')
    return str

@app.template_filter('data_fmt')
def data_fmt(filename):
    t = 'unkown'
    for type, exts in datatypes.items():
        if filename.split('.')[-1] in exts:
            t = type
    return t

@app.template_filter('icon_fmt')
def icon_fmt(filename):
    i = 'fa-file-o'
    for icon, exts in icontypes.items():
        if filename.split('.')[-1] in exts:
            i = icon
    return i

@app.template_filter('humanize')
def time_humanize(timestamp):
    mdate = datetime.utcfromtimestamp(timestamp)
    return humanize.naturaltime(mdate)

def get_type(mode):
    if stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
        type = 'dir'
    else:
        type = 'file'
    return type

def partial_response(path, start, end=None):
    file_size = os.path.getsize(path)

    if end is None:
        end = file_size - start - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    with open(path, 'rb') as fd:
        fd.seek(start)
        bytes = fd.read(length)
    assert len(bytes) == length

    response = Response(
        bytes,
        206,
        mimetype=mimetypes.guess_type(path)[0],
        direct_passthrough=True,
    )
    response.headers.add(
        'Content-Range', 'bytes {0}-{1}/{2}'.format(
            start, end, file_size,
        ),
    )
    response.headers.add(
        'Accept-Ranges', 'bytes'
    )
    return response

def get_range(request):
    range = request.headers.get('Range')
    m = re.match('bytes=(?P<start>\d+)-(?P<end>\d+)?', range)
    if m:
        start = m.group('start')
        end = m.group('end')
        start = int(start)
        if end is not None:
            end = int(end)
        return start, end
    else:
        return 0, None

class PathView(MethodView):
    def get(self, p=''):
        hide_dotfile = request.args.get('hide-dotfile', request.cookies.get('hide-dotfile', 'no'))

        path = os.path.join(root, p)
        if os.path.isdir(path):
            contents = []
            total = {'size': 0, 'dir': 0, 'file': 0}
            for filename in os.listdir(path):
                if filename in ignored:
                    continue
                if hide_dotfile == 'yes' and filename[0] == '.':
                    continue
                filepath = os.path.join(path, filename)
                stat_res = os.stat(filepath)
                info = {}
                info['name'] = filename
                info['fullname'] = pathlib.Path(filepath).relative_to(root).as_posix()
                info['mtime'] = stat_res.st_mtime
                ft = get_type(stat_res.st_mode)
                info['type'] = ft
                total[ft] += 1
                sz = stat_res.st_size
                info['size'] = sz
                total['size'] += sz
                contents.append(info)
            page = render_template('index.html', path=p, contents=contents, total=total, 
                DEBUG=DEBUG,
                reportfolders=reportfolders,
                xrslogfolders=xrslogfolders,
                hide_dotfile=hide_dotfile,
                async_mode=socketio.async_mode)
            res = make_response(page, 200)
            res.set_cookie('hide-dotfile', hide_dotfile, max_age=16070400)
        elif os.path.isfile(path):
            if path.endswith('.html'):
                pass
            elif 'Range' in request.headers:
                start, end = get_range(request)
                res = partial_response(path, start, end)
            else:
                res = send_file(path)
                res.headers.add('Content-Disposition', 'attachment')
        else:
            res = make_response('Not found', 404)
        return res

    def post(self, p=''):
        path = os.path.join(root, p)
        info = {}
        if os.path.isdir(path):
            files = request.files.getlist('files[]')
            for file in files:
                try:
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(path, filename))
                except Exception as e:
                    info['status'] = 'error'
                    info['msg'] = str(e)
                else:
                    info['status'] = 'success'
                    info['msg'] = 'File Saved'
        else:
            info['status'] = 'error'
            info['msg'] = 'Invalid Operation'
        res = make_response(json.JSONEncoder().encode(info), 200)
        res.headers.add('Content-type', 'application/json')
        return res

path_view = PathView.as_view('path_view')
app.add_url_rule('/', view_func=path_view)
app.add_url_rule('/<path:p>', view_func=path_view )


# Part of DB 


# Part of socket io

# The only entry to start to analyze log file
def analyze(url):
    # Add this job if it is not in DB
    # Otherwise return the job status in DB 
    return 0


from flask_socketio import SocketIO, emit
async_mode = None
socketio = None
socketio = SocketIO(app, async_mode=async_mode)    
app.config['SECRET_KEY'] = 'secret!'
namespace = '/NSloganalyze'


@socketio.on('connect', namespace=namespace)
def client_connect():
    emit('status_report_event',  {'url': 'x/y/z', 'status':0})


@socketio.on('status_request_event', namespace=namespace)
def status_request_event(message):
    emit('status_report_event',
         {'url': 'a/b/c', 'status':100},
         broadcast=True)

@socketio.on('analyze_request_event', namespace=namespace)
def analyze_request_event(message):
    # logic to check the requested url status
    url = message['url']
    status = analyze(url)
    emit('status_report_event',
         {'url':url, 'status':status},
         broadcast=True)

@socketio.on('my_ping', namespace=namespace)
def ping_pong():
    emit('my_pong')


# To make apache2 happy
application=app

if __name__ == "__main__":
    # app.run does not support socketio 
    # see https://stackoverflow.com/questions/34735206/using-eventlet-to-manage-socketio-in-flask
    # to let socket io run properly we need run it with socketio.run(app)
    # 5000 is falsk defalut port.
    #app.run('0.0.0.0', 5000, threaded=True, debug=True) 
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

    # run with uwsgi 
    # uwsgi requires gevent is installed. but when it is installed the 'socketio.run(app, host='0.0.0.0', port=5000, debug=True)'
    # has no output. The server hangs before the host and port is properly bound.
    # and you will not be able to browser the page. This is a gevent related issue, not the code issue.
    # Uninstall the gevent with sudo pip3 uninstall gevent and run this program again, it works without any error.
    # uwsgi --wsgi-file file_server.py --gevent 1000 --http-websockets --master --callable app  --http :5000  --static-map /\&=/var/www/xrslogs/  --uid xrslog --gid xrslog

