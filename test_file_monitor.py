import os
import shutil

# Steps to run this test
# Start python3 file_monitor.py as xrslog
# In another shell start python3 test_file_monitory.py as xrslog too.
# See console output of file_monitor.py

def test_by_create_TraceLog_and_create_request_file_under_it():
    # our logs should goes to this folder
    log_file_rootdir='/home/xrslog/DirectViewLogs'
    assert os.path.exists(log_file_rootdir)
    os.chdir(log_file_rootdir)
    if os.path.exists('5.7Evo'): 
        shutil.rmtree('5.7Evo')
    # simulate TraceLog file uploaded
    os.makedirs('5.7Evo/TraceLog')
    # simulator user request to start analyze TraceLog
    open('5.7Evo/TraceLog/request','w').write('')


    ### Another upload
    os.makedirs('5.7Evo/SiteIssue2/TraceLog')
    # simulator user request to start analyze TraceLog
    open('5.7Evo/SiteIssue2/TraceLog/request','w').write('')

if __name__ == '__main__':
    test_by_create_TraceLog_and_create_request_file_under_it()