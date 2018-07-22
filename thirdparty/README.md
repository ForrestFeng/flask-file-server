## Watchdog
    Install latest verion of watchdog manually(python3 setup.py install) to fix v0.8.3 issue(installed by pip install watchdog). 
    Issue: https://github.com/gorakhargosh/watchdog/issues/117
    
    ```
      File "/home/seyz/workspace/virtenvs/foo/lib/python2.7/site-packages/watchdog/observers/api.py", line 191, in run
    self.queue_events(self.timeout)
  File "/home/seyz/workspace/virtenvs/foo/lib/python2.7/site-packages/watchdog/observers/inotify.py", line 748, in queue_events
    inotify_events = self._inotify.read_events()
  File "/home/seyz/workspace/virtenvs/foo/lib/python2.7/site-packages/watchdog/observers/inotify.py", line 538, in read_events
    wd_path = self._path_for_wd[wd]
    ```

    