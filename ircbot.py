#!/usr/bin/env python3
import select
import socket
import threading
from collections import namedtuple

import channel
from constants import logmessage_types, internal_submessage_types, controlmessage_types

Server = namedtuple('Server', ['host', 'port'])

# ServerThread(server, control_socket)
# Creates a new server main loop thread
class ServerThread(threading.Thread):
	def __init__(self, server, control_channel, logging_channel):
		self.server = server
		self.control_channel = control_channel
		self.logging_channel = logging_channel

		self.server_socket_write_lock = threading.Lock()

		threading.Thread.__init__(self)

	def send_line_raw(self, line):
		# Sanitize line just in case
		line = line.replace(b'\r', b'').replace(b'\n', b'')[:510]

		with self.server_socket_write_lock:
			self.server_socket.sendall(line + b'\r\n')

		self.logging_channel.send((logmessage_types.sent, line.decode(encoding = 'utf-8', errors = 'replace')))

	def handle_line(self, line):
		# TODO: implement line handling
		self.logging_channel.send((logmessage_types.received, line.decode(encoding = 'utf-8', errors = 'replace')))

	def mainloop(self):
		# Register both the server socket and the control channel to or polling object
		poll = select.poll()
		poll.register(self.server_socket, select.POLLIN)
		poll.register(self.control_channel, select.POLLIN)

		# Keep buffer for input
		server_input_buffer = bytearray()

		quitting = False
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
						while b'\r\n' in server_input_buffer:
							# Newline was found, split buffer
							line, _, server_input_buffer = server_input_buffer.partition(b'\r\n')

							self.handle_line(line)

				# Control
				elif fd == self.control_channel.fileno():
					command_type, *arguments = self.control_channel.recv()
					if command_type == controlmessage_types.quit:
						quitting = True

					elif command_type == controlmessage_types.send_line:
						assert len(arguments) == 1
						irc_command, space, arguments = arguments[0].encode('utf-8').partition(b' ')
						line = irc_command.upper() + space + arguments
						self.send_line_raw(line)

					else:
						self.logging_channel.send((logmessage_types.internal, internal_submessage_types.error))

				else:
					assert False #unreachable

	def run(self):
		# Connect to given server
		address = (self.server.host, self.server.port)
		try:
			self.server_socket = socket.create_connection(address)
		except ConnectionRefusedError:
			# Tell controller we failed
			self.logging_channel.send((logmessage_types.internal, internal_submessage_types.error))
			self.logging_channel.send((logmessage_types.internal, internal_submessage_types.quit))
			return

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
		self.logging_channel.send((logmessage_types.internal, internal_submessage_types.quit))

# spawn_serverthread(server) → control_channel, logging_channel
# Creates a ServerThread for given server and returns the channels for controlling and monitoring it
def spawn_serverthread(server):
	thread_control_socket, spawner_control_socket = socket.socketpair()
	control_channel = channel.Channel()
	logging_channel = channel.Channel()
	ServerThread(server, control_channel, logging_channel).start()
	return (control_channel, logging_channel)

if __name__ == '__main__':
	control_channel, logging_channel = spawn_serverthread(Server('irc.freenode.net', 6667))

	while True:
		cmd = input(': ')
		if cmd == '':
			while True:
				data = logging_channel.recv(blocking = False)
				if data == None:
					break
				message_type, message_data = data
				if message_type == logmessage_types.sent:
					print('>' + message_data)
				elif message_type == logmessage_types.received:
					print('<' + message_data)
				elif message_type == logmessage_types.internal:
					if message_data == internal_submessage_types.quit:
						print('--- Quit')
					elif message_data == internal_submessage_types.error:
						print('--- Error')
					else:
						print('--- ???', message_data)
				else:
					print('???', message_type, message_data)

		elif cmd == 'q':
			control_channel.send((controlmessage_types.quit,))
			break

		elif len(cmd) > 0 and cmd[0] == '/':
			control_channel.send((controlmessage_types.send_line, cmd[1:]))
