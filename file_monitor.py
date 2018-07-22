import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import logging
import logging.config
import shutil
import os 
import yaml
import threading
from datetime import datetime
import pathlib
import subprocess
import ctypes

TEST_MODE = False
import simpleflock

# ref https://fangpenlin.com/posts/2012/08/26/good-logging-practice-in-python/
def setup_logging(
    default_path='logging.yaml',      
    default_level=logging.INFO,
    defalut_logging_rootdir=".", #logging ouput root dir
    env_key='LOG_CFG'):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.load(f.read())
            # sub func to create log dir
            def make_log_dir(filename):
                if filename != None:                    
                    if os.path.isabs(filename):
                        dirs = os.path.dirname(filename)
                        print("Make log dir for %s" % filename)
                        if not os.path.exists(dirs):
                            os.makedirs(dirs)
                        return filename
                    else:
                        abspath = os.path.join( os.path.abspath(defalut_logging_rootdir), filename)
                        dirs = os.path.dirname(abspath)
                        print("Make log dir for %s" % abspath)
                        if not os.path.exists(dirs):
                            os.makedirs(dirs)
                        return abspath


            # create log dir if filename is defined
            try:
                filename = config['handlers']['error_file_handler']['filename']
                absfilename=make_log_dir(filename)
                config['handlers']['error_file_handler']['filename'] = absfilename
                print("get back %s" % config['handlers']['error_file_handler']['filename'] )

            except:
                logging.warn('No error file handler for logging', e)
                pass
            try:
                filename = config['handlers']['info_file_handler']['filename']
                absfilename = make_log_dir(filename)
                config['handlers']['info_file_handler']['filename'] = absfilename
            except :
                logging.warn('No error file handler for logging', e)
                pass

        print("Config logging with config file %s" % config)
        logging.config.dictConfig(config)
        logging.info("Loggin confgiuration finished configpath %s" % path)
    else:
        print('else')
        logging.basicConfig(level=default_level)

class WorkerRunnerThread():    
    def __init__(self, statpath:str, tracker, external_process:list):
        self.statpath = statpath
        self.tracker = tracker
        self.EXTERNAL_PROCESS = external_process

    def on_external_process_exit(self, args=None):
        # return inner def
        def callback(proc):        
            # external process return negtive code -1, 
            # the proc.returncode here is 255
            # we need a -1 so use cpytpe.c_int8 to convert it
            exitcode =  ctypes.c_int8(proc.returncode).value
            logging.info( "Args %s, process exitcode %s" % (proc.args, exitcode) )
            self.tracker.finish_job(self.statpath, exitcode)   
        return callback

    def popen_and_call(self, on_exit, popenArgs, **popenKWArgs):
        """
        Runs a subprocess.Popen, and then calls the function on_exit when the
        subprocess completes.

        Use it exactly the way you'd normally use subprocess.Popen, except include a
        callable to execute as the first argument. on_exit is a callable object, and
        *popenArgs and **popenKWArgs are simply passed up to subprocess.Popen.
        """
        def run_in_thread(on_exit, popenArgs, popenKWArgs):
            proc = subprocess.Popen(popenArgs, **popenKWArgs)
            proc.wait()
            on_exit(proc)
            return

        thread = threading.Thread(target=run_in_thread,
                                  args=(on_exit, popenArgs, popenKWArgs))

        # returns immediately after the thread starts    
        thread.start()

        return thread 

    def run(self):       
        ARGS = [self.statpath]
        logging.info('popen_and_call with %s' % str(self.EXTERNAL_PROCESS + ARGS)) 
        self.popen_and_call(self.on_external_process_exit(),  self.EXTERNAL_PROCESS + ARGS)

class JobTracker():
    MAX_JOB_PROCESS = 2
    logger = logging.getLogger(__name__)
    def __init__(self, socketio=None, rootdir=None, external_process=None):
        self.jobentry_dict = {}
        self.socketio = socketio
        self.rootdir = rootdir
        self.external_process = external_process
        self.run_schedule_thread()
        

    def set_stat(self, statpath, value:int):
        with simpleflock.SimpleFlock(statpath+'.lock', timeout = 3):        
            with open(statpath, 'w') as f:
                self.logger.info('Set stat %s to %d' % (statpath, value) )
                f.write(str(value))
    def job_entry(self, logdir:str, models=['All'], queuetime='', processtime='', finishtime='', exitcode=''):
        return dict(logdir=logdir, models=models, queuetime=queuetime, processtime=processtime, finishtime=finishtime, exitcode=exitcode)
    def job_str(self, jobentry):
        je = jobentry
        return "{'logdir':'%s', 'models':%s, 'queuetime':'%s', 'processtime':'%s', 'finishtime':'%s', 'exitcode':'%s'}" % (je['logdir'],
            je['models'], je['queuetime'], je['processtime'], je['finishtime'], je['exitcode'])   
    def finish_job(self, statpath, exitcode):
        logdir = self.as_web_logdir(statpath)  
        self.logger.info('Finish job %s' % logdir)
        # set stat exit code
        if exitcode == 0:
            self.set_stat(statpath, 101)
        else:
            self.set_stat(statpath, exitcode) 
        # removed from the jobentry_dict
        job = self.jobentry_dict.pop(logdir)
        job['finishtime'] = str(datetime.now())
        job['exitcode'] = str(exitcode)
        # save to history
        history = statpath[:-5]+'.history'
        with open(history, 'a') as f:
            f.write(self.job_str(job) + '\n')

    def as_svr_logdir(self, logdir:str):
        assert len(logdir) > 0 
        assert logdir[0] != '/'
        return os.path.join(self.rootdir, logdir)

    def as_web_logdir(self, statpath):
        # convert local abs path of stat file to web log dir path relative to root_dri
        dirpath = os.path.dirname(statpath)
        return pathlib.Path(dirpath).relative_to(self.rootdir).as_posix()

    def add(self, jobentry):
        self.jobentry_dict[jobentry['logdir']] = jobentry

    def update(self, jobentry):
        assert jobentry['logdir'] in self.jobentry_dict
        
    def on_tracelog_created_or_moved(self, src_path, dest_path=None):
        if dest_path:
            self.set_stat(os.path.join(dest_path, '.stat'), -100)
        else:
            self.set_stat(os.path.join(src_path, '.stat'), -100)
    def on_stat_modified(self, statpath): 
        svalue = None        
        with simpleflock.SimpleFlock(statpath+'.lock', timeout = 3):
            with open(statpath) as f:
                svalue = int(f.read().strip()) 
           
        logdir = self.as_web_logdir(statpath)     
        self.logger.info('*** broadcasting logdir=%s | stat=%s' % (logdir, svalue))   
        self.broadcast_stat(logdir=self.as_web_logdir(statpath), stat=svalue)
    def broadcast_stat(self, logdir, stat):
        #broadcast to all client via websocket
        broadcast = True
        self.logger.info('>>> stat_report_event logdir=%s | stat=%s' % (logdir, stat)) 
        self.socketio.emit('stat_report_event',  data={'logdir': logdir, 'stat':stat}, namespace='/NSloganalyze', broadcast=True)
    def on_request_file_created(self, requestpath):
        # only used for test
        # user click request file under TraceLog trigger this
        svr_logdir = os.path.dirname(requestpath)
        statpath = os.path.join(svr_logdir, '.stat')
        logdir = self.as_web_logdir(statpath)
        self.logger.info('User request to anylyze %s' % logdir)        
        self.set_stat(statpath, 0)        
        if not logdir in self.jobentry_dict:
            self.logger.info('Queue job %s' % logdir)
            self.jobentry_dict[logdir] = self.job_entry(logdir, queuetime=str(datetime.now()))
    def on_analyze_request(self, logdir):
        svr_logdir = self.as_svr_logdir(logdir)
        self.logger.info('User request to anylyze %s' % logdir)
        statpath = os.path.join(svr_logdir, '.stat')
        self.set_stat(statpath, 0)
        if not logdir in self.jobentry_dict:
            self.logger.info('Queue job %s' % logdir)
            self.jobentry_dict[logdir] = self.job_entry(logdir, queuetime=str(datetime.now()))
    def run_schedule_thread(self):   
        def run_in_thread(self):      
            while True:
                jobs = self.jobentry_dict.copy()
                process_jobs = [ v for v in jobs.values() if v['exitcode']=='' and v['processtime']!='']
                sorted_waiting_jobs = [ v for v in jobs.values() if v['processtime']=='' and v['queuetime']!='']
                sorted_waiting_jobs.sort(key=lambda j: j['queuetime'])
                # still has slot to run external process?
                if len(process_jobs) >= self.MAX_JOB_PROCESS:
                    time.sleep(1)
                    continue
                # pick first queued job
                if len(sorted_waiting_jobs) == 0:
                    continue                
                j = sorted_waiting_jobs[0]
                server_path = self.as_svr_logdir(j['logdir'])  

                # set stat 1
                statpath = os.path.join(server_path, '.stat')
                self.set_stat( statpath,  1)

                # append and start
                j['processtime'] = str(datetime.now())               
                self.logger.info("Process %s" % j['logdir'])
                # start runner process to processing
                t = WorkerRunnerThread(statpath, self, self.external_process) # TODO set to False for product
                t.run()

        thread = threading.Thread(target=run_in_thread, args=(self,))
        thread.start()
        self.logger.info("Job tracker schedule thread started")

        return thread # returns immediately after the thread starts 


class FakeSocketio():
    def emit(self, msg, data={}, broadcast=False):
        items = []
        for k in sorted(data.keys()):
            items.append('%s:%s' % (k, data[k]) )
        sdata = '{%s}' % (','.join(items))
        logging.info( "FakeSocketio emit %s %s" % (msg, sdata) )

class Watcher:
    logger = logging.getLogger(__name__)
    def __init__(self, tracker, dir_to_watch):
        self.observer = Observer()
        self.dir_to_watch = dir_to_watch
        self.tracker = tracker
        
    def run(self):
        event_handler = LogMonitorHandler(self.tracker)
        self.observer.schedule(event_handler, self.dir_to_watch, recursive=True)
        self.observer.start()
        self.logger.info("Watch dog observer started")
        try:
            while True:
                time.sleep(1)
        except:
            self.observer.stop()
            self.logger.error("Watcher dog error", exc_info=True)

        self.observer.join()


class LogMonitorHandler(FileSystemEventHandler):
    logger = logging.getLogger(__name__)
    def __init__(self, tracker):
        self.tracker = tracker

    def on_moved(self, event):
        super(LogMonitorHandler, self).on_moved(event)

        what = 'directory' if event.is_directory else 'file'
        self.logger.info("Moved %s: from %s to %s", what, event.src_path,
                     event.dest_path)
        # TraceLog created
        if event.is_directory and os.path.basename(event.dest_path) in ["TraceLog"]:
            self.tracker.on_tracelog_created_or_moved(None, event.dest_path)

    def on_created(self, event):
        super(LogMonitorHandler, self).on_created(event)

        what = 'directory' if event.is_directory else 'file'
        self.logger.info("Created %s: %s", what, event.src_path)

        # TraceLog
        if event.is_directory and os.path.basename(event.src_path) in ["TraceLog"]:
            self.tracker.on_tracelog_created_or_moved(event.src_path)

        # request file
        if TEST_MODE and not event.is_directory and os.path.basename(event.src_path) in ['request']:
            self.tracker.on_request_file_created(event.src_path)


    def on_deleted(self, event):
        super(LogMonitorHandler, self).on_deleted(event)

        what = 'directory' if event.is_directory else 'file'
        self.logger.info("Deleted %s: %s", what, event.src_path)
 
    def on_modified(self, event):
        super(LogMonitorHandler, self).on_modified(event)

        what = 'directory' if event.is_directory else 'file'
        self.logger.info("Modified %s: %s", what, event.src_path)

        # stat
        if not event.is_directory:
            if os.path.basename(event.src_path) == '.stat':
                self.tracker.on_stat_modified(event.src_path)

def run_file_monitor_thread(tracker, dir_to_watch):   
    logger = logging.getLogger(__name__)
    def run_in_thread(tracker, dir_to_watch):      
        w = Watcher(tracker, dir_to_watch)
        w.run()
        logger.info("File monitor thread is running...")


    thread = threading.Thread(target=run_in_thread, args=(tracker, dir_to_watch))
    thread.start()
    logger.info("File monitor thread started")

    return thread # returns immediately after the thread starts  



if __name__ == '__main__':
    TEST_MODE = True
    treaded = True

    loggingcfg = '/home/logadmin/flask-file-server/logging.yaml' 
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

    setup_logging(loggingcfg, defalut_logging_rootdir=defalut_logging_rootdir)
    if treaded:
        logging.info("Run in threaded mode")
        tracker = JobTracker(socketio=FakeSocketio(), 
                          rootdir=log_file_rootdir, 
                          external_process=external_process)
        if TEST_MODE:
            if os.path.exists(tracker.qfile_waiting): os.remove(tracker.qfile_waiting)
            if os.path.exists(tracker.qfile_processing): os.remove(tracker.qfile_processing)
            if os.path.exists(tracker.qfile_finished): os.remove(tracker.qfile_finished)
        run_file_monitor_thread(tracker, log_file_rootdir)
    else:
        w = Watcher()
        w.run()
    logging.info("Main function last line!")
