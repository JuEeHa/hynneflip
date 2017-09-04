#!/usr/bin/env python3
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

	def run(self):
		# Connect to given server
		address = (self.server.host, self.server.port)
		sock = socket.create_connection(address)

		sock.sendall(b'Testi\n')
		sock.close()

# spawn_serverthread(server) → control_socket
# Creates a ServerThread for given server and returns the socket for controlling it
def spawn_serverthread(server):
	thread_control_socket, spawner_control_socket = socket.socketpair()
	ServerThread(server, thread_control_socket).start()
	return spawner_control_socket

if __name__ == '__main__':
	spawn_serverthread(Server('localhost', 6667))
