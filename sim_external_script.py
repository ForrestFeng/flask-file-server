import sys
import time
import os
import shutil

print("Sleep_10.py argv", sys.argv)

thisfile = sys.argv[0]
statpath = sys.argv[1]

html='''<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>Hellow world!!</h1>
</body>
</html>
'''

rptpath = os.path.join( os.path.dirname( os.path.dirname(statpath) ),  'TraceLogReport')
# remove TraceLogReport folder
if os.path.exists(rptpath):
    shutil.rmtree(rptpath)

# Recreate TraceLogReport folder    
os.makedirs(rptpath)

for progress in [1, 30, 60, 90, 100]:
    # NOTES:
    # If we change the progress too fast (eg. remove the two lines
    # of sleep) we will end up with multiple notification with last 
    # progress value on the web server side. Because of the watchdog
    # cannot cache up the change speed of file value change.
    # In real word this is not a big issue, because the analyze process
    # usually take long time to completed.
    # Even if it change progress and completed very quickly we still be 
    # able to catch the last value. Last value win is OK for web server.

    time.sleep(1)
    with open(statpath, 'w') as f:
        f.write(str(progress))
    time.sleep(1)



    # Put a index.html file inside demo the report result
    idxpath = os.path.join(rptpath, 'index.html')
    with open(idxpath, 'w') as f:
        f.write(html)

# on success return 0
sys.exit(0)
# on fail must return -10 -> -1
#sys.exit(-1)

