import sys
import time


print("Sleep_10.py argv", sys.argv)

thisfile = sys.argv[0]
statpath = sys.argv[1]

for progress in [2, 30]:
	time.sleep(2)
	with open(statpath, 'w') as f:
		f.write(str(progress))


