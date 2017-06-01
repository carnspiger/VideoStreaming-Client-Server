from Tkinter import *
import tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os, time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class threeButtonClient:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	packet_count = 0
	delay_counter = 0
	packet_drop_counter = 0
	total_jitter = 0
	jitter_counter = 0
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.setupMovie()
		
	def createWidgets(self):
		"""Build GUI."""
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Stop button
		self.stop = Button(self.master, width=20, padx=3, pady=3)
		self.stop["text"] = "Stop"
		self.stop["command"] = self.exitClient
		self.stop.grid(row=1, column=2, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
	
	def setupMovie(self):
		"""Setup handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
			
	def exitClient(self):
		"""Teardown handler."""
		self.sendRtspRequest(self.TEARDOWN)	
		# display the session stats
		tkMessageBox.showinfo("Server Stats", "Jitter: " + '{0:.1f}'.format((self.total_jitter / self.jitter_counter)*1000) + " ms\nBandwidth: " + '{:,.0f}'.format(self.totalBytes / self.elapsedTime) + " B/s\nPackets Lost: " + str(self.packet_drop_counter))
		self.master.destroy() # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
	
	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)
	
	def listenRtp(self):		
		"""Listen for RTP packets."""
		# mark the time when the process started
		timeStarted = time.time()
		# keep track of the total bytes sent (for bandwidth calculation)
		self.totalBytes = 0
		# keep track of the first packet (for jitter calculation)
		self.firstPacket = True
		# keep track of the time that has elapsed
		self.elapsedTime = 0
		# keep track of the last packet's delay
		self.prev_delay = 0
		# flag is true if frames were dropped
		self.frameDropped = False
		while True:
			try:
				# take note of the time before receiving from the server
				now = time.time()
				# receive data from the server
				data = self.rtpSocket.recv(20480)
				# calculate the delay (used to calculate jitter)
				delay = time.time() - now
				if data and self.state == self.PLAYING:
					"""Calculate Bandwidth"""
					if int(time.time() - timeStarted) > self.elapsedTime:
						self.elapsedTime = int(time.time() - timeStarted)
					# add the size of the received data to the total bytes tracker
					self.totalBytes += len(data)
					
					# create an RtpPacket instance
					rtpPacket = RtpPacket()
					# decode the received data
					rtpPacket.decode(data)
					
					# retrieve the frame number
					currFrameNbr = rtpPacket.seqNum()
					print "Current Seq Num: " + str(currFrameNbr)
					
					# drop any late frames
					if currFrameNbr > self.frameNbr: 
					
						"""Calculate Packet Loss"""
						# the difference between frame numbers should be 1, so if it's more than that, then packets have been dropped
						if currFrameNbr - self.frameNbr >= 2 and self.state == self.PLAYING:
							# increment the dropped packet counter
							self.packet_drop_counter += currFrameNbr - self.frameNbr - 1
							self.frameDropped = True
							
						"""Calculate Jitter"""
						# check to see if the first-packet flag is set to true
						if self.firstPacket == True and self.state == self.PLAYING:
							# store the delay
							self.prev_delay = delay
							# set the first-packet flag to false
							self.firstPacket = False
						elif self.frameDropped == False and self.state == self.PLAYING:
							# otherwise, subtract the delay from the previous delay and store it in total_jitter
							self.total_jitter += abs(delay - self.prev_delay)
							# increment the jitter counter. This represents the number of times that jitter has been successfully recorded
							self.jitter_counter += 1
							# set the previous delay for the next iteration
							self.prev_delay = delay
						else:
							# reset the dropped frame tracker
							self.frameDropped = False
							
						# update the frame number
						self.frameNbr = currFrameNbr
						# update the image
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
								
			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.playEvent.isSet(): 
					break
				
				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					
	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		
		return cachename
	
	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=288) 
		self.label.image = photo
		
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""	
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			request = "SETUP " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nTransport: RTP/UDP; client_port= " + str(self.rtpPort)
			# Keep track of the sent request.
			self.requestSent = self.SETUP
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			# Update RTSP sequence number.
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			request = "PLAY " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PLAY
		
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			# Update RTSP sequence number.
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			request = "PAUSE " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			# Update RTSP sequence number.
			self.rtspSeq = self.rtspSeq + 1
			
			# Write the RTSP request to be sent.
			request = "TEARDOWN " + str(self.fileName) + " RTSP/1.0\nCSeq: " + str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
			
			# Keep track of the sent request.
			self.requestSent = self.TEARDOWN
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		self.rtspSocket.send(request)
		
		print '\nData sent:\n' + request
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply)
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		lines = data.split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = int(lines[2].split(' ')[1])
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						# Update RTSP state.
						self.state = self.READY
						
						# Open RTP port.
						self.openRtpPort() 
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						# The play thread exits. A new thread is created on resume.
						self.playEvent.set()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1 
	
	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		
		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind(('', self.rtpPort))
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
