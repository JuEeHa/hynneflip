# initialize()
# Called to initialize the IRC bot
# Runs before even logger is brought up, and blocks further bringup until it's done
def initialize():
	...

# handle_message(*, prefix, message, nick, channel, irc)
# Called for PRIVMSGs.
# prefix is the prefix at the start of the message, without the leading ':'
# message is the contents of the message
# nick is who sent the message
# channel is where you should send the response (note: in queries nick == channel)
# irc is the IRC API object
# All strings are bytestrings or bytearrays
def handle_message(*, prefix, message, nick, channel, irc):
	...

# handle_nonmessage(*, prefix, command, arguments, irc)
# Called for all other commands than PINGs and PRIVMSGs.
# prefix is the prefix at the start of the message, without the leading ':'
# command is the command or number code
# arguments is rest of the arguments of the command, represented as a list. ':'-arguments are handled automatically
# All strings are bytestrings or bytearrays
def handle_nonmessage(*, prefix, command, arguments, irc):
	...
