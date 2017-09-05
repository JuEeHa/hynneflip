import select
import socket
import threading

class Channel:
	"""An asynchronic communication channel that can be used to send python object and can be poll()ed."""

	def __init__(self):
		# We use a socket to enable polling and blocking reads
		self.write_socket, self.read_socket = socket.socketpair()
		self.poll = select.poll()
		self.poll.register(self.read_socket, select.POLLIN)

		# Store messages in a list
		self.mesages = []
		self.messages_lock = threading.Lock()

	def send(self, message):
		# Add message to the list of messages and write to the write socket to signal there's data to read
		with self.messages_lock:
			self.write_socket.sendall(b'!')
			self.mesages.append(message)

	def recv(self, blocking = True):
		# Timeout of -1 will make poll wait until data is available
		# Timeout of 0 will make poll exit immediately if there's no data
		if blocking:
			timeout = -1
		else:
			timeout = 0

		# See if there is data to read / wait until there is
		results = self.poll.poll(timeout)

		# None of the sockets were ready. This can only happen if we weren't blocking
		# Return None to signal lack of data
		if len(results) == 0:
			assert not blocking
			return None

		# Remove first message from the list (FIFO principle), and read one byte from the socket
		# This keeps the number of available messages and the number of bytes readable in the socket in sync
		with self.messages_lock:
			message = self.mesages.pop(0)
			self.read_socket.recv(1)

		return message

	def fileno(self):
		# Allows for a Channel object to be passed directly to poll()
		return self.read_socket.fileno()
