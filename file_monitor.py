import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import logging
import logging.config
import shutil
import os 
import yaml
import threading

# ref https://fangpenlin.com/posts/2012/08/26/good-logging-practice-in-python/
def setup_logging(
    default_path='logging.yaml',      
    default_level=logging.INFO,
    env_key='LOG_CFG'
):
    """Setup logging configuration

    """
    path = default_path
    value = os.getenv(env_key, None)
    if value:
        path = value
    logging.info("Logging config path %s" % path)
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.load(f.read())
            # sub func to create log dir
            def make_log_dir(filename):
                if filename != None:                    
                    if os.path.isabs(filename):
                        dirs = os.path.dirname(filename)
                        logging.info("Make log dir %s" % dirs)
                        os.makedirs(dirs)
                    else:
                        abspath = os.path.join( os.path.abspath(os.path.curdir), filename)
                        dirs = os.path.dirname(abspath)
                        logging.info("Make log dir %s" % dirs)
                        os.makedirs(dirs)

            # create log dir if filename is defined
            try:
                filename = config['handlers']['error_file_handler']['filename']
                make_log_dir(filename)
            except:
                pass
            try:
                filename = config['handlers']['info_file_handler']['filename']
                make_log_dir(filename)
            except:
                pass

        logging.config.dictConfig(config)
        logging.info("Loggin confgiuration finished")
    else:
        print('else')
        logging.basicConfig(level=default_level)


class Watcher:
    DIRECTORY_TO_WATCH = "/home/xrslog/5.7LogRoot"

    def __init__(self):
        self.observer = Observer()

    def run(self):
        event_handler = LogMonitorHandler()
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
    t1 = "/home/xrslog/5.7LogRoot/t1"
    def on_moved(self, event):
        super(LogMonitorHandler, self).on_moved(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Moved %s: from %s to %s", what, event.src_path,
                     event.dest_path)

    def on_created(self, event):
        super(LogMonitorHandler, self).on_created(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Created %s: %s", what, event.src_path)

        # when a directory is TraceLog we should create .status file under it
        if False or event.src_path == self.t1 and os.path.exists(self.t1):
            #time.sleep(1)
            os.rmdir(self.t1)
            logging.info("**RMDIR")


    def on_deleted(self, event):
        super(LogMonitorHandler, self).on_deleted(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Deleted %s: %s", what, event.src_path)
        if False or event.src_path == self.t1 and not os.path.exists(self.t1):
            #time.sleep(1)            
            os.mkdir(self.t1)
            logging.info("**MKDIR")


    def on_modified(self, event):
        super(LogMonitorHandler, self).on_modified(event)

        what = 'directory' if event.is_directory else 'file'
        logging.info("Modified %s: %s", what, event.src_path)


def run_file_monitor_thread(on_exit=None, args=None, **kwargs):
 
    def run_in_thread(on_exit, args, kwrgs):      
        w = Watcher()
        w.run()
        if on_exit is not None:            
            on_exit()
            logging.info("File monitor thread exit, on_exit called")


    thread = threading.Thread(target=run_in_thread,
                              args=(on_exit, args, kwargs))
    thread.start()
    logging.info("File monitor thread started")

    return thread # returns immediately after the thread starts  





if __name__ == '__main__':
    loggingcfg = '/home/logadmin/flask-file-server/logging.yaml'    
    setup_logging(loggingcfg)
    treaded = True

    if treaded:
        logging.info("Run in threaded mode")
        run_file_monitor_thread()
    else:
        w = Watcher()
        w.run()
    logging.info("Main function exit!")
