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
import simpleflock
logger = None

DEBUG = False
app = Flask(__name__, static_url_path='/assets', static_folder='assets')
root = os.path.join(os.path.expanduser('~'), 'Logs')
# Used to indentify folders that contain trace reports file.
# Such a folder a href will link to hostname/&/path/to/reprotfolder 
# which will be served by apache2 for better performance.
# Such a folder must contains index.html file for the report.
# Users can just click the report folder to see the report :)
# Folder name is in lower case to easy the judge in index.html
reportfolders = ['tracereport', 'tracelogreport']
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
                # include .stat value
                statvalue = -100
                statpath = os.path.join(filepath, '.stat')
                if filename.lower() in xrslogfolders and os.path.exists(statpath):
                    with simpleflock.SimpleFlock(statpath+'.lock', timeout = 3):                    
                        with open(statpath, 'rt') as f:
                            try:
                                statvalue = int(f.read())
                            except Exception as e:
                                # reset
                                os.remove(statpath)
                info['stat'] = statvalue
                
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
def analyze(logdir):
    # Add this job if it is not in DB
    # Otherwise return the job stat in DB
    logging.info('^^^^^^ handle analyze job_tracker is None? %s' % str(job_tracker == None))
    if job_tracker != None:
        job_tracker.on_analyze_request(logdir)
    return 0

from flask_socketio import SocketIO, emit
async_mode = None
socketio = SocketIO(app, async_mode=async_mode)    
app.config['SECRET_KEY'] = 'secret!'
# Lessons learn, socketio.send or emit need do not forget the namespace kwarg
# Ref broadcast section at https://flask-socketio.readthedocs.io/en/latest/ 
namespace = '/NSloganalyze'

@socketio.on('connect', namespace=namespace)
def client_connect():
    emit('stat_report_event',  {'logdir': 'x/y/z', 'stat':0})

@socketio.on('stat_request_event', namespace=namespace)
def stat_request_event(message):
    emit('stat_report_event',
         {'logdir': 'a/b/c', 'stat':100},
         broadcast=True)

@socketio.on('analyze_request_event', namespace=namespace)
def analyze_request_event(message):
    # logic to check the requested logdir stat
    logger.info("Web server analyze_request_event  %s" % message)
    logdir = message['logdir']
    analyze(logdir)
    #emit('stat_report_event', {'logdir':logdir, 'stat':9}, broadcast=True)

@socketio.on('my_ping', namespace=namespace)
def ping_pong():
    emit('my_pong')


# To make apache2 happy
application=app

# integrate file_monitor.py
import logging
import threading
#import .file_monitor as fm 
import file_monitor as FM
job_tracker = None
#from file_monitor import setup_logging, tracker, FakeSocketio, run_file_monitor_thread
def run_fm():
    FM.TEST_MODE = False    
    threaded = True

    loggingcfg = '/home/logadmin/flask-file-server/logging.yaml' 
    external_process = ["python3", '/home/logadmin/loganalysis/lib/v5/main.py']
    if FM.TEST_MODE:
        external_process = ["python3", '/home/logadmin/flask-file-server/sim_external_script.py']        

    #!!!  defalut_logging_rootdir MUST NOT a sub folder of log_file_rootdir
    defalut_logging_rootdir='/home/xrslog'
    log_file_rootdir='/home/xrslog/Logs'
    
    if not os.path.exists(log_file_rootdir):
        os.makedirs(log_file_rootdir)

    # remove log folder if any
    # loggingdir = os.path.join(defalut_rootdir, '.log')
    # if os.path.exists(loggingdir):  
    #     shutil.rmtree(loggingdir)
    #     os.makedirs(loggingdir)

    FM.setup_logging(loggingcfg, defalut_logging_rootdir=defalut_logging_rootdir)
    global logger
    logger = logging.getLogger('Main')
    if threaded:
        logger.info("Run in threaded mode")
        tracker = FM.JobTracker(socketio=socketio,
                          rootdir=log_file_rootdir, 
                          external_process=external_process)
        global job_tracker
        job_tracker = tracker
        
        FM.run_file_monitor_thread(tracker, log_file_rootdir)


if __name__ == "__main__":
    # app.run does not support socketio 
    # see https://stackoverflow.com/questions/34735206/using-eventlet-to-manage-socketio-in-flask
    # to let socket io run properly we need run it with socketio.run(app)
    # 5000 is falsk defalut port.
    #app.run('0.0.0.0', 5000, threaded=True, debug=True) 
    run_fm()
    socketio.run(app, host='localhost', port=5000, debug=False)

    # run with uwsgi 
    # uwsgi requires gevent is installed. but when it is installed the 'socketio.run(app, host='0.0.0.0', port=5000, debug=True)'
    # has no output. The server hangs before the host and port is properly bound.
    # and you will not be able to browser the page. This is a gevent related issue, not the code issue.
    # Uninstall the gevent with sudo pip3 uninstall gevent and run this program again, it works without any error.
    # uwsgi --wsgi-file file_server.py --gevent 1000 --http-websockets --master --callable app  --http :5000  --static-map /\&=/var/www/xrslogs/  --uid xrslog --gid xrslog

