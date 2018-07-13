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


TEST = True

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
    EXTERNAL_PROCESS = ["python3", '/home/logadmin/flask-file-server/sleep_10s.py']

    def __init__(self, statpath:str, rearctor, simulate=False):
        self.statpath = statpath
        self.simulate = simulate
        self.reactor = reactor

    def set_stat(self, value:int):
        with open(self.statpath, 'w') as f:
            f.write(str(value))

    def on_external_process_exit(self, args=None):
        # return inner def
        def update_job_in_db(proc):        
            exitcode = proc.returncode
            logging.info( "Args %s, process exitcode %s" % (proc.args, exitcode) )
            if proc.returncode == 0:
                self.reactor.set_stat(self.statpath, 100)
            else:
                self.set_stat(exitcode)                
            # remove job entry from processing queue
            self.reactor.move_job_entry_from_processing_to_finished(self.statpath, exitcode)
        return update_job_in_db

    def popen_and_call(on_exit, popenArgs, **popenKWArgs):
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
        if TEST:
            # simulate analyze process 
            for i in [2,  30, 60, 90, 99]:
                time.sleep(2)
                self.reactor.set_stat(self.statpath, i)
        else:
            ARGS = [self.statpath]
            popen_and_call(self.on_external_process_exit(),  self.EXTERNAL_PROCESS + ARGS)

class FakeSocketio():
    def emit(self, *args):
        msg = str(args)
        logging.info( "FakeSocketio emit %s" % msg)

class Reactor():
    MAX_JOB_PROCESS = 2
    def __init__(self, socketio, rootdir):
        self.socketio = socketio
        self.rootdir = rootdir

    @property    
    def qfile_waiting(self):
        # return the abs file of the 
        return os.path.join(self.rootdir, '.waiting_queue')
    @property  
    def qfile_processing(self):
        # return the abs file of the 
        return os.path.join(self.rootdir, '.processing_queue')
    @property  
    def qfile_finished(self):
        # return the abs file of the 
        return os.path.join(self.rootdir, '.finished_queue')
    
    def job_entry(self, logdir:str, models=['All'], queuetime='', processtime='', finishtime='', exitcode=''):
        return dict(logdir=logdir, models=models, queuetime=queuetime, processtime=processtime, finishtime=finishtime, exitcode=exitcode)

    def as_svr_logdir(self, logdir:str):
        assert len(logdir) > 0 
        assert logdir[0] != '/'
        return os.path.join(self.rootdir, logdir)

    def as_web_logdir(self, statpath):
        # convert local abs path of stat file to web log dir path relative to root_dri
        dirpath = os.path.dirname(statpath)
        return pathlib.Path(dirpath).relative_to(self.rootdir).as_posix()

    def set_stat(self, statpath, value:int):
        with open(statpath, 'w') as f:
            logging.info('Set stat %s to %d' % (statpath, value) )
            f.write(str(value))

    def move_job_entry_from_processing_to_finished(self, statpath:str, exitcode:int):
        with open(self.qfile_processing) as f:
            wlogdir = self.as_web_logdir(statpath)
            lns = [ln.strip() for ln in f.readlines() if ln != '\n']

            for ln in lns:
                jobentry = eval(ln)
                if jobentry['logdir'] != wlogdir:
                    jobentry['finishtime'] = str(datetime.now())
                    jobentry['exitcode'] = str(returncode)
                    mewln = str(jobentry)
                    with open(self.qfile_finished, 'a') as ff:
                        ff.write('\n'.join(mewln))
                    break

    def broadcast_stat(self, logdir, stat):
        #broadcast to all client via websocket
        broadcast = True
        self.socketio.emit('status_report_event',  {'logdir': logdir, 'stat':stat}, broadcast)

    def append_to_waiting_queue(self, statpath):
        jobentry = self.job_entry(self.as_web_logdir(statpath), ["All"], str(datetime.now()) )
        with open(self.qfile_waiting, 'a') as f:
            logging.info("Append job entry to waiting queue %s" % str(jobentry))
            f.write('\n'+str(jobentry))

    def on_tracelog_created_or_moved(self, src_path, dest_path=None):
        if dest_path:
            self.set_stat(os.path.join(dest_path, '.stat'), -100)
        else:
            self.set_stat(os.path.join(src_path, '.stat'), -100)


    def on_request_file_created(self, requestpath):
        # only used for test
        # user click request file under TraceLog trigger this
        logdir = os.path.dirname(requestpath)
        logging.info('User request to anylyze %s' % logdir)
        self.set_stat(os.path.join(logdir, '.stat'), 0)


    def on_stat_modified(self, statpath): 
        svalue = None
        with open(statpath) as f:                   
            svalue = int(f.read().strip())            
        self.broadcast_stat(logdir=self.as_web_logdir(statpath), stat=svalue)
        if svalue == 0:
            self.append_to_waiting_queue(statpath)

    def num_processing_jobs(self):
        # return how many job entries in the processing queue
        num = 0
        if os.path.exists(self.qfile_processing):
            with open(self.qfile_processing) as f:
                num = len( [l.strip() for l in f.readlines() if l != '\n'] )
            logging.info("There are %d entries in processing" % num)
        return num

    def on_waiting_queue_modified(self, filepath):
        num = self.num_processing_jobs()
        logging.info('Waiting queue contains %d job entries' % num)
        if num < self.MAX_JOB_PROCESS:
            #pick the first queued job 
            lns = []
            with open(filepath) as f:            
                lns = [l.strip() for l in f.readlines() if l != '\n'] # strip end \n and other space ignore lines too short
                logging.info("Waiting queue contains %d jobs to be processed" % len(lns))
                if len(lns) > 0:
                    logging.info('Move line from waiting queue to processing queue %s' % lns[0])
                    firstlndic = eval(lns[0])
                    # set stat                    
                    logging.info("Set stat value as 1 for %s" % firstlndic['logdir'])
                    server_path = self.as_svr_logdir(firstlndic['logdir'])
                    statpath = os.path.join(server_path, '.stat')
                    self.set_stat( statpath,  1)
                    # append
                    firstlndic ['processtime'] = str(datetime.now())
                    with open(self.qfile_processing, 'a') as ff:
                        ff.write('\n'+str(firstlndic))
                        logging.info("Append job %s to processing queue" % str(firstlndic))
                        # start runner process to processing
                        t = WorkerRunnerThread(statpath, self, TEST) # TODO set to False for product
                        t.run()
            # remove           
            with open(filepath, 'w') as f:
                if len(lns) > 1:
                    f.write('\n'.join(lns[1:]))
                    logging.info("Remove job %s from waiting queue" % lns[0])

    def on_processing_queue_modified(self, filepath):
        
        pass         



class Watcher:
    DIRECTORY_TO_WATCH = "/home/xrslog/5.7LogRoot"

    def __init__(self, reactor):
        self.observer = Observer()

    def run(self):
        event_handler = LogMonitorHandler(reactor)
        self.observer.schedule(event_handler, self.DIRECTORY_TO_WATCH, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(5)
        except:
            self.observer.stop()
            print("Error")

        self.observer.join()


class LogMonitorHandler(FileSystemEventHandler):
    def __init__(self, reactor):
        self.reactor = reactor

    t1 = "/home/xrslog/5.7LogRoot/t1"
    def on_moved(self, event):
        super(LogMonitorHandler, self).on_moved(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Moved %s: from %s to %s", what, event.src_path,
                     event.dest_path)
        # TraceLog
        if event.is_directory and os.path.basename(event.dest_path) in ["TraceLog"]:
            self.reactor.on_tracelog_created_or_moved(None, event.dest_path)

    def on_created(self, event):
        super(LogMonitorHandler, self).on_created(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Created %s: %s", what, event.src_path)

        # when a directory is TraceLog we should create .status file under it
        if False or event.src_path == self.t1 and os.path.exists(self.t1):
            #time.sleep(1)
            #os.rmdir(self.t1)
            logging.info("**RMDIR")

        # TraceLog
        if event.is_directory and os.path.basename(event.src_path) in ["TraceLog"]:
            self.reactor.on_tracelog_created_or_moved(event.src_path)

        # request file
        if TEST and not event.is_directory and os.path.basename(event.src_path) in ['request']:
            self.reactor.on_request_file_created(event.src_path)


    def on_deleted(self, event):
        super(LogMonitorHandler, self).on_deleted(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Deleted %s: %s", what, event.src_path)
        if False or event.src_path == self.t1 and not os.path.exists(self.t1):
            #time.sleep(1)            
            #os.mkdir(self.t1)
            logging.info("**MKDIR")


    def on_modified(self, event):
        super(LogMonitorHandler, self).on_modified(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Modified %s: %s", what, event.src_path)

        # Watiting queue
        if not event.is_directory:
            if event.src_path == self.reactor.qfile_waiting:
                self.reactor.on_waiting_queue_modified(event.src_path)
            if os.path.basename(event.src_path) == '.stat':
                self.reactor.on_stat_modified(event.src_path)



def run_file_monitor_thread(reactor):   

    def run_in_thread(reactor):      
        w = Watcher(reactor)
        w.run()
        logging.info("File monitor thread is running...")


    thread = threading.Thread(target=run_in_thread, args=(reactor,))
    thread.start()
    logging.info("File monitor thread started")

    return thread # returns immediately after the thread starts  



if __name__ == '__main__':
    loggingcfg = '/home/logadmin/flask-file-server/logging.yaml'  
    #!!!  defalut_logging_rootdir MUST NOT a sub folder of xrslog_file_rootdir
    defalut_logging_rootdir='/home/xrslog'
    xrslog_file_rootdir='/home/xrslog/5.7LogRoot'

    # remove log folder if any
    # loggingdir = os.path.join(defalut_rootdir, '.log')
    # if os.path.exists(loggingdir):  
    #     shutil.rmtree(loggingdir)
    #     os.makedirs(loggingdir)

    setup_logging(loggingcfg, defalut_logging_rootdir=defalut_logging_rootdir)

    

    treaded = True

    if treaded:
        logging.info("Run in threaded mode")
        reactor = Reactor(socketio=FakeSocketio(), rootdir=xrslog_file_rootdir)
        run_file_monitor_thread(reactor)
    else:
        w = Watcher()
        w.run()
    logging.info("Main function exit!")
