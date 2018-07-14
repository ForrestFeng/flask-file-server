import sys
import time


print("Sleep_10.py argv", sys.argv)

thisfile = sys.argv[0]
statpath = sys.argv[1]

for progress in [2, 30, 60, 90]:
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



