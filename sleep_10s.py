import sys
import time

logging.info(sys.argv)

thisfile = sys.argv[0]
statpath = sys.argv[1]

for progress in [2, 30, 60, 90 99]:
	time.sleep(10)
	with open(statpath, 'w') as f:
		f.write(str(progress))


