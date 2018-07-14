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


TEST_MODE = False

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
    def __init__(self, statpath:str, reactor, external_process:list):
        self.statpath = statpath
        self.reactor = reactor
        self.EXTERNAL_PROCESS = external_process

    def on_external_process_exit(self, args=None):
        # return inner def
        def update_job_in_db(proc):        
            exitcode = proc.returncode
            logging.info( "Args %s, process exitcode %s" % (proc.args, exitcode) )
            if proc.returncode == 0:
                self.reactor.set_stat(self.statpath, 100)
            else:
                sself.reactor.set_stat(self.statpath, exitcode)                
            # remove job entry from processing queue
            self.reactor.move_job_entry_from_processing_to_finished(self.statpath, exitcode)
        return update_job_in_db

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
        self.popen_and_call(self.on_external_process_exit(),  self.EXTERNAL_PROCESS + ARGS)

class FakeSocketio():
    def emit(self, *args):
        msg = str(args)
        logging.info( "FakeSocketio emit %s" % msg)

class Reactor():
    MAX_JOB_PROCESS = 2
    def __init__(self, socketio, rootdir, external_process):
        self.socketio = socketio
        self.rootdir = rootdir
        self.external_process = external_process

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
        logging.info('Move job to finished queue %s' % statpath)   
        lns = []       
        with open(self.qfile_processing) as f:
            wlogdir = self.as_web_logdir(statpath)
            lns = [ln.strip() for ln in f.readlines() if ln != '\n']

        # regenerate processing job
        plns = []
        for ln in lns:
            jobentry = eval(ln)
            if jobentry['logdir'] == wlogdir:
                jobentry['finishtime'] = str(datetime.now())
                jobentry['exitcode'] = str(exitcode)
                mewln = str(jobentry)
                if not os.path.exists(self.qfile_finished):
                    with open(self.qfile_finished, 'w') as ff:
                        ff.write(mewln+'\n')
                else:                      
                    with open(self.qfile_finished, 'a') as ff:
                        ff.write('\n'.join(mewln)+'\n')
            else:
                plns.append(ln)
        # update processing queue
        logging.debug("plns data %s; lns data %s" % (plns, lns))
        if len(plns) < len(lns):
            with open(self.qfile_processing, 'w') as f:
                f.write('\n'.join(plns))


    def broadcast_stat(self, logdir, stat):
        #broadcast to all client via websocket
        broadcast = True
        self.socketio.emit('status_report_event',  {'logdir': logdir, 'stat':stat}, broadcast)

    def append_to_waiting_queue(self, statpath):
        logdir = self.as_web_logdir(statpath)
        jobentry = self.job_entry(logdir, ["All"], str(datetime.now()) )        
        if not os.path.exists(self.qfile_waiting): 
            # append directly if no file exist
            with open(self.qfile_waiting, 'w') as f:
                logging.info("Append job entry to waiting queue %s" % str(jobentry))
                f.write(str(jobentry)+'\n')
        else: 
            # ignore the job that is already in queue 
            with open(self.qfile_waiting) as f:
                lns = [l.strip() for l in f.readlines() if l != '\n'] # strip end \n and other space ignore lines too short
                logdir_lst = [eval(l)['logdir'] for l in lns]
                if not logdir in logdir_lst:
                    with open(self.qfile_waiting, 'a') as f:
                        logging.info("Append job entry to waiting queue %s" % str(jobentry))
                        f.write(str(jobentry)+'\n')

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
        return num

    def on_waiting_queue_modified(self, filepath):
        num = self.num_processing_jobs()
        logging.info('%d jobs in processing queue' % num)
        if num < self.MAX_JOB_PROCESS:
            #pick the first queued job 
            lns = []
            with open(filepath) as f:            
                lns = [l.strip() for l in f.readlines() if l != '\n'] # strip end \n and other space ignore lines too short
                logging.info("%d jobs in waiting queue " % len(lns))
                if len(lns) > 0:
                    firstlndic = eval(lns[0])
                    server_path = self.as_svr_logdir(firstlndic['logdir'])
                    # remove first         
                    with open(filepath, 'w') as f:
                        if len(lns) > 1:
                            logging.info("Remove job %s from waiting queue" % server_path)
                            f.write('\n'.join(lns[1:])+'\n')

                    firstlndic = eval(lns[0])
                    # set stat 
                    statpath = os.path.join(server_path, '.stat')
                    self.set_stat( statpath,  1)
                    # append and start
                    firstlndic ['processtime'] = str(datetime.now())
                    with open(self.qfile_processing, 'a') as ff:
                        ff.write(str(firstlndic)+'\n')
                        logging.info("Append job %s to processing queue" % server_path)
                        # start runner process to processing
                        t = WorkerRunnerThread(statpath, self, self.external_process) # TODO set to False for product
                        t.run()


    def on_processing_queue_modified(self, filepath):
        # do nothing now
        pass         



class Watcher:
    def __init__(self, reactor, dir_to_watch):
        self.observer = Observer()
        self.dir_to_watch = dir_to_watch
        self.reactor = reactor

    def run(self):
        event_handler = LogMonitorHandler(self.reactor)
        self.observer.schedule(event_handler, self.dir_to_watch, recursive=True)
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

        # TraceLog
        if event.is_directory and os.path.basename(event.src_path) in ["TraceLog"]:
            self.reactor.on_tracelog_created_or_moved(event.src_path)

        # request file
        if TEST_MODE and not event.is_directory and os.path.basename(event.src_path) in ['request']:
            self.reactor.on_request_file_created(event.src_path)


    def on_deleted(self, event):
        super(LogMonitorHandler, self).on_deleted(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Deleted %s: %s", what, event.src_path)
 
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



def run_file_monitor_thread(reactor, dir_to_watch):   

    def run_in_thread(reactor, dir_to_watch):      
        w = Watcher(reactor, dir_to_watch)
        w.run()
        logging.info("File monitor thread is running...")


    thread = threading.Thread(target=run_in_thread, args=(reactor,dir_to_watch))
    thread.start()
    logging.info("File monitor thread started")

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
        reactor = Reactor(socketio=FakeSocketio(), 
                          rootdir=log_file_rootdir, 
                          external_process=external_process)
        if TEST_MODE:
            if os.path.exists(reactor.qfile_waiting): os.remove(reactor.qfile_waiting)
            if os.path.exists(reactor.qfile_processing): os.remove(reactor.qfile_processing)
            if os.path.exists(reactor.qfile_finished): os.remove(reactor.qfile_finished)
        run_file_monitor_thread(reactor, log_file_rootdir)
    else:
        w = Watcher()
        w.run()
    logging.info("Main function last line!")
