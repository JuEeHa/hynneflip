import threading
from collections import namedtuple

Entry = namedtuple('Entry', ['hymmnos', 'word_class', 'pronunciation', 'meaning_ja', 'meaning_en', 'dialect'])
hymmnos_lexicon = []
hymmnos_lexicon_by_hymmnos = {}
hymmnos_lexicon_lock = threading.Lock()

def initialize():
	global hymmnos_lexicon, hymmnos_lexicon_by_hymmnos, hymmnos_lexicon_lock

	with hymmnos_lexicon_lock:
		# First read all entries into memory
		with open('hymmnos-lexicon.text', 'r') as f:
			for line in f:
				hymmnos, word_class, pronunciation, meaning_ja, meaning_en, dialect = line.strip('\n').split('\t')
				hymmnos_lexicon.append(Entry(hymmnos, word_class, pronunciation, meaning_ja, meaning_en, dialect))

		# Then build an index based on the Hymmnos word
		for index, entry in enumerate(hymmnos_lexicon):
			hymmnos_lexicon_by_hymmnos[entry.hymmnos] = index

def handle_command(*, command, channel, response_prefix, irc):
	# Split the commands into the command itself and the argument. Remove additional whitespace around them
	command, _, argument = (i.strip() for i in command.partition(' '))

	if command == 'hymmnos':
		with hymmnos_lexicon_lock:
			if argument in hymmnos_lexicon_by_hymmnos:
				entry = hymmnos_lexicon[hymmnos_lexicon_by_hymmnos[argument]]

				# The format is (dialect) hymmnos /pronunciation/ - word-class meaning in English
				# Dialect, pronunciation and word class can be messing, so we build the response in parts
				response = ''
				if entry.dialect:
					response += '(' + entry.dialect + ') '
				response += entry.hymmnos + ' '
				if entry.pronunciation:
					response += '/' + entry.pronunciation + '/ '
				response += '- '
				if entry.word_class:
					response += entry.word_class + ' '
				response += entry.meaning_en
			else:
				response = 'Word not found "%s"' % argument

			irc.msg(channel, response_prefix + response.encode('utf-8'))

	elif commands == 'help':
		irc.msg(channel, response_prefix + 'Available commands: hymmnos, help'.encode('utf-8'))

	else:
		irc.msg(channel, response_prefix + ('Command not recognised: %s' % command).encode('utf-8'))

def handle_message(*, prefix, message, nick, channel, irc):
	own_nick = irc.get_nick()

	# Run a command if it's prefixed with our nick we're in a query
	# In queries, nick (who sent) and channel (where to send) are the same
	if message[:len(own_nick) + 1].lower() == own_nick.lower() + b':' or nick == channel:
		if message[:len(own_nick) + 1].lower() == own_nick.lower() + b':':
			command = message[len(own_nick) + 1:].strip()
			response_prefix = nick + b': '
		else:
			command = message
			response_prefix = b''

		command = command.decode(encoding = 'utf-8', errors = 'replace')
		handle_command(command = command, channel = channel, response_prefix = response_prefix, irc = irc)

def handle_nonmessage(*, prefix, command, arguments, irc):
	...
