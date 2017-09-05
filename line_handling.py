import threading

import constants

import botcmd

class LineParsingError(Exception): None

# parse_line(line) → prefix, command, arguments
# Split the line into its component parts
def parse_line(line):
	def read_byte():
		# Read one byte and advance the index
		nonlocal line, index

		if eol():
			raise LineParsingError

		byte = line[index]
		index += 1

		return byte

	def peek_byte():
		# Look at current byte, don't advance index
		nonlocal line, index
		
		if eol():
			raise LineParsingError

		return line[index]

	def eol():
		# Test if we've reached the end of the line
		nonlocal line, index
		return index >= len(line)

	def skip_space():
		# Skip until we run into a non-space character or eol.
		while not eol() and peek_byte() == ord(' '):
			read_byte()

	def read_until_space():
		nonlocal line, index

		if eol():
			raise LineParsingError

		# Try to find a space
		until = line[index:].find(b' ')

		if until == -1:
			# Space not found, read until end of line
			until = len(line)
		else:
			# Space found, add current index to it to get right index
			until += index

		# Slice line upto the point of next space / end and update index
		data = line[index:until]
		index = until

		return data

	def read_until_end():
		nonlocal line, index

		if eol():
			raise LineParsingError
		
		# Read all of the data, and make index point to eol
		data = line[index:]
		index = len(line)

		return data

	index = 0

	prefix = None
	command = None
	arguments = []

	if peek_byte() == ord(':'):
		read_byte()
		prefix = read_until_space()

	skip_space()

	command = read_until_space()

	skip_space()

	while not eol():
		if peek_byte() == ord(':'):
			read_byte()
			argument = read_until_end()
		else:
			argument = read_until_space()

		arguments.append(argument)

		skip_space()

	return prefix, command, arguments

class LineHandlerThread(threading.Thread):
	def __init__(self, line, *, irc):
		self.line = line
		self.irc = irc

		threading.Thread.__init__(self)

	def run(self):
		try:
			prefix, command, arguments = parse_line(self.line)
		except LineParsingError:
			irc.error("Cannot parse line" + self.line.decode(encoding = 'utf-8', errors = 'replace'))

		if command.upper() == b'PRIVMSG':
			# PRIVMSG should have two parameters: recipient and the message
			assert len(arguments) == 2
			recipients, message = arguments

			# Prefix contains the nick of the sender, delimited from user and host by '!'
			nick = prefix.split(b'!')[0]

			# Recipients are in a comma-separate list
			for recipient in recipients.split(b','):
				# 'channel' is bit of a misnomer. This is where we'll send the response to
				# Usually it's the channel, but in queries it's not
				channel = recipient if recipient[0] == ord('#') else nick

				# Delegate rest to botcmd.handle_message
				botcmd.handle_message(prefix = prefix, message = message, nick = nick, channel = channel, irc = self.irc)

		else:
			# Delegate to botcmd.handle_nonmessage
			botcmd.handle_nonmessage(prefix = prefix, command = command, arguments = arguments, irc = self.irc)

def handle_line(line, *, irc):
	# Spawn a thread to handle the line
	LineHandlerThread(line, irc = irc).start()
