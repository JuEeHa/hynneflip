#!/usr/bin/env python3
import select
import socket
import threading
from collections import namedtuple

import channel
from constants import logmessage_types, internal_submessage_types, controlmessage_types

import line_handling
import botcmd

Server = namedtuple('Server', ['host', 'port', 'nick', 'realname', 'channels'])

class LoggerThread(threading.Thread):
	def __init__(self, logging_channel, dead_notify_channel):
		self.logging_channel = logging_channel
		self.dead_notify_channel = dead_notify_channel

		threading.Thread.__init__(self)

	def run(self):
		while True:
			message_type, *message_data = self.logging_channel.recv()

			# Lines that were sent between server and client
			if message_type == logmessage_types.sent:
				assert len(message_data) == 1
				print('>' + message_data[0])

			elif message_type == logmessage_types.received:
				assert len(message_data) == 1
				print('<' + message_data[0])

			# Messages that are from internal components
			elif message_type == logmessage_types.internal:
				if message_data[0] == internal_submessage_types.quit:
					assert len(message_data) == 1
					print('--- Quit')

					# TODO: don't quit, restart
					self.dead_notify_channel.send((controlmessage_types.quit,))
					break

				elif message_data[0] == internal_submessage_types.error:
					assert len(message_data) == 2
					print('--- Error', message_data[1])

				else:
					print('--- ???', message_data)

			else:
				print('???', message_type, message_data)

# API(serverthread_object)
# Create a new API object corresponding to given ServerThread object
class API:
	def __init__(self, serverthread_object):
		# We need to access the internal functions of the ServerThread object in order to send lines etc.
		self.serverthread_object = serverthread_object

	def send_raw(self, line):
		"""Sends a raw line (will terminate it itself.
		Don't use unless you are completely sure you know wha you're doing."""
		self.serverthread_object.send_line_raw(line)

	def msg(self, recipient, message):
		"""Make sending PRIVMSGs much nicer"""
		line = b'PRIVMSG ' + recipient + b' :' + message
		self.serverthread_object.send_line_raw(line)

	def nick(self, nick):
		"""Send a NICK command and update the internal nick tracking state"""
		with self.serverthread_object.nick_lock:
			line = b'NICK ' + nick
			self.serverthread_object.send_line_raw(line)
			self.serverthread_object.nick = nick

	def get_nick(self):
		"""Returns current nick"""
		with self.serverthread_object.nick_lock:
			return self.serverthread_object.nick

	def join(self, channel):
		"""Send a JOIN command and update the internal channel tracking state"""
		with self.serverthread_object.channels_lock:
			line = b'JOIN ' + channel
			self.serverthread_object.send_line_raw(line)
			self.serverthread_object.channels.add(channel)

	def error(self, message):
		"""Log an error"""
		self.serverthread_object.logging_channel.send((constants.logmessage_types.internal, constants.internal_submessage_types.error, message))


# ServerThread(server, control_socket)
# Creates a new server main loop thread
class ServerThread(threading.Thread):
	def __init__(self, server, control_channel, logging_channel):
		self.server = server
		self.control_channel = control_channel
		self.logging_channel = logging_channel

		self.server_socket_write_lock = threading.Lock()

		self.nick = None
		self.nick_lock = threading.Lock()

		self.channels = set()
		self.channels_lock = threading.Lock()

		threading.Thread.__init__(self)

	def send_line_raw(self, line):
		# Sanitize line just in case
		line = line.replace(b'\r', b'').replace(b'\n', b'')[:510]

		with self.server_socket_write_lock:
			self.server_socket.sendall(line + b'\r\n')

		# Don't log PONGs
		if not (len(line) >= 5 and line[:5] == b'PONG '):
			self.logging_channel.send((logmessage_types.sent, line.decode(encoding = 'utf-8', errors = 'replace')))

	def handle_line(self, line):
		command, _, arguments = line.partition(b' ')
		if command.upper() == b'PING':
			self.send_line_raw(b'PONG ' + arguments)
		else:
			self.logging_channel.send((logmessage_types.received, line.decode(encoding = 'utf-8', errors = 'replace')))
			line_handling.handle_line(line, irc = self.api)

	def mainloop(self):
		# Register both the server socket and the control channel to or polling object
		poll = select.poll()
		poll.register(self.server_socket, select.POLLIN)
		poll.register(self.control_channel, select.POLLIN)

		# Keep buffer for input
		server_input_buffer = bytearray()

		# TODO: Implement timeouting
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
						error_message = 'Unknown control message: %s' % repr((command_type, *arguments))
						self.logging_channel.send((logmessage_types.internal, internal_submessage_types.error, error_message))

				else:
					assert False #unreachable

	def run(self):
		# Connect to given server
		address = (self.server.host, self.server.port)
		try:
			self.server_socket = socket.create_connection(address)
		except ConnectionRefusedError:
			# Tell controller we failed
			self.logging_channel.send((logmessage_types.internal, internal_submessage_types.error, "Can't connect to %s:%s" % address))
			self.logging_channel.send((logmessage_types.internal, internal_submessage_types.quit))
			return

		# Create an API object to give to outside line handler
		self.api = API(self)

		# Run initialization
		self.send_line_raw(b'USER HynneFlip a a :' + self.server.realname.encode('utf-8'))

		# Set up nick and channels
		self.api.nick(self.server.nick.encode('utf-8'))

		for channel in self.server.channels:
			self.api.join(channel.encode('utf-8'))

		# Run mainloop
		self.mainloop()

		# Tell the server we're quiting
		self.send_line_raw(b'QUIT :HynneFlip exiting normally')
		self.server_socket.close()

		# Tell controller we're quiting
		self.logging_channel.send((logmessage_types.internal, internal_submessage_types.quit))

# spawn_serverthread(server, logging_channel) → control_channel
# Creates a ServerThread for given server and returns the channel for controlling it
def spawn_serverthread(server, logging_channel):
	thread_control_socket, spawner_control_socket = socket.socketpair()
	control_channel = channel.Channel()
	ServerThread(server, control_channel, logging_channel).start()
	return control_channel

# spawn_loggerthread() → logging_channel, dead_notify_channel
# Spawn logger thread and returns the channel it logs and the channel it uses to notify about quiting
def spawn_loggerthread():
	logging_channel = channel.Channel()
	dead_notify_channel = channel.Channel()
	LoggerThread(logging_channel, dead_notify_channel).start()
	return logging_channel, dead_notify_channel

if __name__ == '__main__':
	server = Server(host = 'irc.freenode.net', port = 6667, nick = 'o3-base', realname = 'IRC bot based on o3-base', channels = ['##ingsoc'])

	botcmd.initialize()

	logging_channel, dead_notify_channel = spawn_loggerthread()
	control_channel = spawn_serverthread(server, logging_channel)

	while True:
		message = dead_notify_channel.recv(blocking = False)
		if message is not None:
			if message[0] == controlmessage_types.quit:
				break

		cmd = input('')
		if cmd == 'q':
			print('Keyboard quit')
			control_channel.send((controlmessage_types.quit,))
			logging_channel.send((logmessage_types.internal, internal_submessage_types.quit))
			break

		elif len(cmd) > 0 and cmd[0] == '/':
			control_channel.send((controlmessage_types.send_line, cmd[1:]))
