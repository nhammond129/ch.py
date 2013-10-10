#!/usr/bin/python
import ch

class TestBot(ch.RoomManager):
  def safePrint (self, text):
      while True:
        try:
          print(text)
          break
        except UnicodeEncodeError as ex:
          text = (text[0:ex.start] + '(unicode)' + text[ex.end:])

  def onConnect(self, room):
    room.unicodeCompat = True
    print("Connected to "+room.name)
    
  def onReconnect(self, room):
    print("Reconnected to "+room.name)
    
  def onDisconnect(self, room):
    print("Disconnected from "+room.name)
  
  def onMessage(self, room, user, message):
    # Use with PsyfrBot framework? :3
    self.safePrint(user.name + ': ' + message.body)

    if message.body.startswith("!a"):
      room.message("AAAAAAAAAAAAAA")

  def onFloodBan(self, room):
    print("You are flood banned in "+room.name)
  
  def onPMMessage(self, pm, user, body):
    self.safePrint('PM: ' + user.name + ': ' + body)
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
