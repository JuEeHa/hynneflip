import enum

from collections import namedtuple

def parse_pastalie_verb(word):
	root = ''
	emotions = []

	segment = ''
	is_emotion = False
	for character in word:
		if not is_emotion and character in 'AIEUON':
			# Level 1 emotion add it directy to emotions
			# segment doesn't contain an emotion, add it to the root
			# Add '.' to root to mark where the emotion was extracted from
			# Start building a new root segment
			emotions.append(character)
			root += segment + '.'
			segment = ''

		elif not is_emotion and character in 'LY':
			# Either a level 2 or 3 emotion
			# segment doesn't contain an emotion, add it to the root and start building a new segment that does
			root += segment
			segment = character
			is_emotion = True

		elif is_emotion:
			# segment contains a start of an emotion already

			if segment == 'L':
				# A level 3 emotion, has to start with LY
				if character == 'Y':
					segment = 'LY'

				else:
					# Wasn't LY, so can't be an emotion, flip is_emotion to False, since this was a
					# root segment after all
					segment += character
					is_emotion = False

			elif segment == 'Y' or segment == 'LY':
				# Prefix of either a level 2 or level 3 emotion is complete

				if character in 'AIEUON':
					# character completes the emotion, add segment + character to emotions
					# Add '.' to root to mark where the emotion was extracted from
					# Start building a new root segment
					emotions.append(segment + character)
					root += '.'
					segment = ''
					is_emotion = False

				else:
					# Wasn't a valid level 2 or level 3 emotion word after all, flip is_emotion to
					# False
					segment += character
					is_emotion = False

		else:
			# By default, just add to the segment
			segment += character

	# At the end, add what was left of the segment to the root
	assert not is_emotion
	root += segment

	return root, emotions

SentencePart = namedtuple('SentencePart', ['is_word', 'text'])

def parse_sentence(sentence):
	parts = []

	current = ''
	is_word = True

	for character in sentence:
		if is_word and character in [' ', ',', '!', '?']:
			# One character punctuation, add non-zero part to parts and start reading new word
			# Additionally, add the punctuation to parts
			if current != '':
				parts.append(SentencePart(is_word, current))

			parts.append(SentencePart(False, character))

			current = ''
			is_word = True

		elif is_word and character == '/':
			# Start of /.
			# Add non-zero part to parts and start reading new non-word beginning with '/'
			if current != '':
				parts.append(SentencePart(is_word, current))

			current = '/'
			is_word = False

		elif not is_word and current == '/' and character == '.':
			# End of /.
			# Add it to parts and start reading new word
			parts.append(SentencePart(is_word, current + '.'))

			current = ''
			is_word = True

		elif not is_word:
			# Non-recognised multi-character symbol, we mispredicted
			# Add each part (including current char) as its own non-word and start reading new word
			for i in current:
				parts.append(SentencePart(False, i))

			parts.append(SentencePart(False, character))

			current = ''
			is_word = True

		else:
			# Append to the current word
			current += character

	# Add any leftover sentence part to the parts
	if current != '':
		parts.append(SentencePart(is_word, current))

	return parts
