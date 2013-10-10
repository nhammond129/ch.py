#!/usr/bin/python
import ch
import sys
import codecs

class TestBot(ch.RoomManager):
  def onConnect(self, room):
    room.unicodeCompat = True
    print("Connected to "+room.name)
    
  def onReconnect(self, room):
    print("Reconnected to "+room.name)
    
  def onDisconnect(self, room):
    print("Disconnected from "+room.name)
  
  def onMessage(self, room, user, message):
    # Use with PsyfrBot framework? :3
    sys.stdout.write (user.name + ': ')
    with codecs.open ('test', 'w+', encoding='utf-8') as f:
      f.write (message.body)
    text = message.body + '\n'
    while True:
      try:
        sys.stdout.write (text)
        break
      except UnicodeEncodeError as ex:
        sys.stdout.write (text[0:ex.start] + '(unicode)')
        text = text[ex.end:]
    if message.body.startswith("!a"):
      room.message("AAAAAAAAAAAAAA")

  
  def onFloodBan(self, room):
    print("You are flood banned in "+room.name)
  
  def onPMMessage(self, pm, user, body):
    print("PM:"+user.name+": "+body)
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
