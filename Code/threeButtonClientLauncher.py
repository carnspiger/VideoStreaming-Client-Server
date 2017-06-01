import sys
from Tkinter import Tk
from threeButtonClient import threeButtonClient

if __name__ == "__main__":
	try:
		serverAddr = sys.argv[1]
		serverPort = sys.argv[2]
		rtpPort = sys.argv[3]
		fileName = sys.argv[4]	
	except:
		print "[Usage: threeButtonClientLauncher.py Server_name Server_port RTP_port Video_file]\n"	
	
	root = Tk()
	
	# Create a new client
	app = threeButtonClient(root, serverAddr, serverPort, rtpPort, fileName)
	app.master.title("RTPClient")	
	root.mainloop()
	