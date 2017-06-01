import time,socket,random

class SimSocket:
	def __init__(self,jitter_stat,bandwidth_stat,packet_loss_stat):
		self.jitter=jitter_stat
		self.bandwidth=bandwidth_stat
		self.packet_loss=packet_loss_stat
		# if a large number of packet loss is specified, increase the chances that a packet will be dropped
		if self.packet_loss <= 100:
			self.drop_chance = 5
		else:
			self.drop_chance = 2
		self.loss_count=0
		self.totalBytes = 0
		self.firstTimer = True
		self.apply_jitter = True
		self.customSocket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	
	def send(self, data, address, port):
		# start timer
		if self.firstTimer == True:
			self.timer = time.time()
			self.firstTimer = False
		
		"""Simulate Packet Loss"""
		# depending on the desired number of packets to be lost, simulate a 50% or 20% chance that the packet will be dropped
		if self.packet_loss > 0 and self.loss_count < self.packet_loss:
			# if a random integer is equal to 2, then it's dropped (nothing sent)
			if random.randint(1,self.drop_chance)==2:
				# since the packet was dropped, increment the packet loss counter
				self.loss_count+=1
				# flip the jitter
				self.flipJitter()
			else:
				# call the send2 method
				self.send2(data,address,port)
		else:
			# call the send2 method
			self.send2(data,address,port)
			
	def send2(self, data, address, port):
		# calculate the elapsed time
		totalTime = time.time() - self.timer
		# if adding the current data to the total bytes tracker will take it over the bandwidth limit,
		# and a second hasn't yet elapsed
		if len(data) + self.totalBytes > self.bandwidth and totalTime < 1.0:
			# sleep until the full second has passed
			time.sleep(1.0 - totalTime)
			# set the timer to the current time
			self.timer = time.time()
			# reset the totalBytes tracker
			self.totalBytes = 0
		# if the time has elapsed to a second or longer, reset the timer
		if totalTime >= 1.0:
			totalTime = time.time()
		"""Simulate Jitter"""
		# apply a 50% chance that jitter will be applied
		if self.apply_jitter == True:
			time.sleep(self.jitter)
		
		# send the packet
		self.totalBytes += self.customSocket.sendto(data,(address,port))
		# flip the jitter
		self.flipJitter()

	def flipJitter(self):
		# flip-flop the jitter application
		if self.apply_jitter == True:
			self.apply_jitter = False
		else:
			self.apply_jitter = True
			
	def closeSocket(self):
		# close the socket
		self.customSocket.close()