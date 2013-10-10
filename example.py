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
    def Print(user,message):
      text = message.body
      while True:
        try:
          print(user.name + ': '+text)
          break
        except UnicodeEncodeError as ex:
          text = (text[0:ex.start] + '(unicode)' + text[ex.end:])
      
    Print(user,message)

    if message.body.startswith("!a"):
      room.message("AAAAAAAAAAAAAA")

  
  def onFloodBan(self, room):
    print("You are flood banned in "+room.name)
  
  def onPMMessage(self, pm, user, body):
    def Print(user, text):
      while True:
        try:
          print("PM:"+user.name + ': '+text)
          break
        except UnicodeEncodeError as ex:
          text = (text[0:ex.start] + '(unicode)' + text[ex.end:])
      
    Print(user, body)
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
