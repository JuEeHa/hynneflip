#!/usr/bin/env python3
import select
import socket
import threading
from collections import namedtuple

Server = namedtuple('Server', ['host', 'port'])

# ServerThread(server, control_socket)
# Creates a new server main loop thread
class ServerThread(threading.Thread):
	def __init__(self, server, control_socket):
		self.server = server
		self.control_socket = control_socket

		threading.Thread.__init__(self)

	def send_line_raw(self, line):
		# Sanitize line just in case
		line = line.replace(b'\r', b'').replace(b'\n', b'')[:510]

		self.server_socket.sendall(line + b'\r\n')

		# FIXME: print is not thread safe
		print('>' + line.decode(encoding = 'utf-8', errors = 'replace'))

	def handle_line(self, line):
		# TODO: implement line handling
		# FIXME: print is not thread safe
		print('<' + line.decode(encoding = 'utf-8', errors = 'replace'))

	def mainloop(self):
		# Register both the server and the control socket to our polling object
		poll = select.poll()
		poll.register(self.server_socket, select.POLLIN)
		poll.register(self.control_socket, select.POLLIN)

		# Keep buffers for input and output
		server_input_buffer = bytearray()
		server_output_buffer = bytearray()
		control_input_buffer = bytearray()

		quitting = False
		writing = False
		while not quitting:
			# Wait until we can do something
			for fd, event in poll.poll():
				# Server
				if fd == self.server_socket.fileno():
					# Ready to receive, read into buffer and handle full messages
					if event | select.POLLIN:
						data = self.server_socket.recv(1024)
						server_input_buffer.extend(data)

						# Try to see if we have a full line ending with \r\n in the buffer
						# If yes, handle it
						if b'\r\n' in server_input_buffer:
							# Newline was found, split buffer
							line, _, server_input_buffer = server_input_buffer.partition(b'\r\n')

							self.handle_line(line)

					# Ready to send, send buffered output as far as possible
					if event | select.POLLOUT:
						sent = self.server_socket.send(server_output_buffer)
						server_output_buffer = server_output_buffer[sent:]

				# Control
				elif fd == self.control_socket.fileno():
					# Read into buffer and handle full commands
					data = self.control_socket.recv(1024)
					control_input_buffer.extend(data)

					# TODO: implement command handling
					if len(control_input_buffer) > 1:
						quitting = True

				else:
					assert False #unreachable

			# See if we have to change what we're listening for
			if not writing and len(server_output_buffer) > 0:
				# Mark we're listening to socket becoming writable, and start listening
				writing = True
				poll.modify(self.server_socket, select.POLLIN | select.POLLOUT)

			elif writing and len(server_output_buffer) == 0:
				# Mark we're not listening to socket becoming writable, and stop listening
				writing = False
				poll.modify(self.server_socket, select.POLLIN)

	def run(self):
		# Connect to given server
		address = (self.server.host, self.server.port)
		try:
			self.server_socket = socket.create_connection(address)
		except ConnectionRefusedError:
			# Tell controller we failed
			self.control_socket.sendall(b'F')
			self.control_socket.close()

		# Run initialization
		# TODO: read nick/username/etc. from a config
		self.send_line_raw(b'NICK HynneFlip')
		self.send_line_raw(b'USER HynneFlip a a :HynneFlip IRC bot')

		# Run mainloop
		self.mainloop()

		# Tell the server we're quiting
		self.send_line_raw(b'QUIT :HynneFlip exiting normally')
		self.server_socket.close()

		# Tell controller we're quiting
		self.control_socket.sendall(b'Q' + b'\n')
		self.control_socket.close()

# spawn_serverthread(server) → control_socket
# Creates a ServerThread for given server and returns the socket for controlling it
def spawn_serverthread(server):
	thread_control_socket, spawner_control_socket = socket.socketpair()
	ServerThread(server, thread_control_socket).start()
	return spawner_control_socket

if __name__ == '__main__':
	control_socket = spawn_serverthread(Server('irc.freenode.net', 6667))

	while True:
		cmd = input(': ')
		if cmd == '':
			control_messages = bytearray()
			while True:
				data = control_socket.recv(1024)

				if not data:
					break

				control_messages.extend(data)

			print(control_messages.decode(encoding = 'utf-8', errors = 'replace'))

		elif cmd == 'q':
			control_socket.close()
			break

		else:
			control_socket.sendall(cmd.encode('utf-8') + b'\n')
