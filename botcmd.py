import threading
import unicodedata
from collections import namedtuple

import linguistics

Entry = namedtuple('Entry', ['hymmnos', 'word_class', 'pronunciation', 'meaning_ja', 'meaning_en', 'dialect'])
hymmnos_lexicon = []
hymmnos_lexicon_by_hymmnos = {}
hymmnos_lexicon_lock = threading.Lock()

Emotion = namedtuple('Emotion', ['hymmnos', 'meaning_en'])
emotion_lexicon = {}
emotion_lexicon_lock = threading.Lock()

def initialize():
	read_hymmnos_lexicon()
	read_emotion_lexicon()

def read_hymmnos_lexicon():
	global hymmnos_lexicon, hymmnos_lexicon_by_hymmnos, hymmnos_lexicon_lock

	with hymmnos_lexicon_lock:
		# First read all entries into memory
		with open('hymmnos-lexicon.text', 'r') as f:
			for line in f:
				hymmnos, word_class, pronunciation, meaning_ja, meaning_en, dialect = line.strip('\n').split('\t')
				hymmnos_lexicon.append(Entry(hymmnos, word_class, pronunciation, meaning_ja, meaning_en, dialect))

		# Then build an index based on the Hymmnos word
		for index, entry in enumerate(hymmnos_lexicon):
			hymmnos_lexicon_by_hymmnos[normalize_casefold(entry.hymmnos)] = index

def read_emotion_lexicon():
	global emotion_lexicon, emotion_lexicon_lock

	with emotion_lexicon_lock:
		with open('emotion-lexicon.text', 'r') as f:
			for line in f:
				hymmnos, meaning_en = line.strip('\n').split('\t')
				emotion_lexicon[normalize_casefold(hymmnos)] = Emotion(hymmnos, meaning_en)

def normalize_casefold(text):
	# Let's hope this is enough to avoid all corner cases…
	return unicodedata.normalize('NFKD', text.casefold())

def case_insensitive_search(needle, haystack):
	return normalize_casefold(needle) in normalize_casefold(haystack)

def construct_word_definition(entry):
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

	return response

def handle_command(command):
	# Split the commands into the command itself and the argument. Remove additional whitespace around them
	command, _, argument = (i.strip() for i in command.partition(' '))

	if command == 'hymmnos':
		with hymmnos_lexicon_lock:
			if normalize_casefold(argument) in hymmnos_lexicon_by_hymmnos:
				entry = hymmnos_lexicon[hymmnos_lexicon_by_hymmnos[normalize_casefold(argument)]]

				return construct_word_definition(entry)

			else:
				return 'Word not found "%s"' % argument

	elif command == 'pastalie':
		root, emotions = linguistics.parse_pastalie_verb(argument)

		# Eliminate duplicated emotions but keep order (note: O(n²), replace with O(n) if this becomes a problem)
		emotions_dedupped = []
		for emotion in emotions:
			if emotion not in emotions_dedupped:
				emotions_dedupped.append(emotion)

		emotion_definitions = []
		for emotion in emotions_dedupped:
			with emotion_lexicon_lock:
				if normalize_casefold(emotion) in emotion_lexicon:
					emotion_entry = emotion_lexicon[normalize_casefold(emotion)]

					emotion_definitions.append('%s: %s' % (emotion_entry.hymmnos, emotion_entry.meaning_en))

				else:
					emotion_definitions.append('(Unknown: %s)' % emotion)

		return '%s <%s>' % (root, '; '.join(emotion_definitions))

	elif command == 'english':
		bytes_length = 0
		matches = []
		with hymmnos_lexicon_lock:
			for entry in hymmnos_lexicon:
				if case_insensitive_search(argument, entry.meaning_en):
					matches.append(entry.hymmnos)

					# Try to estimate how long the response will be, and cut off searching once we run into the limit of 350
					# (Assuming 160 bytes is enough for prefix, command, channel name, etc.)
					# Adding 2 bytes for the ', ' between the entries
					bytes_length += len(entry.hymmnos.encode('utf-8')) + 2
					if bytes_length > 350:
						# Remove the one that put us over 350 bytes
						matches.pop()

						# Have a '…' follow the matches to signal some are missing
						matches.append('…')

						# Break out of the loop

						break

		if len(matches) == 0:
			return 'No matches'

		return ', '.join(matches)

	elif command == 'help':
		if argument == 'hymmnos':
			return "hymmnos <word> – See the description of a word in Hymmnos (exact match of the 'Hymmnos' field)"
		elif argument == 'pastalie':
			return "pastalie <verb> – Give the root of a Pastalie verb and define its emotions"
		elif argument == 'english':
			return "english <text> – Look for a word in Hymmnos (substring search of the 'Meaning (E)' field)"
		elif argument == 'help':
			return "help [<command>] – See list of commands or description for a command"
		else:
			return 'Available commands: hymmnos, english, help'

	else:
		return 'Command not recognised: %s' % command

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
		response = '\u200b' + handle_command(command)

		irc.msg(channel, response_prefix + response.encode('utf-8'))

def handle_nonmessage(*, prefix, command, arguments, irc):
	...
