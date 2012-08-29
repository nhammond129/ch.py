import ch
class TestBot(ch.RoomManager):
  def onConnect(self, room):
    print("Connected")
    
  def onReconnect(self, room):
    print("Reconnected")
    
  def onDisconnect(self, room):
    print("Disconnected")
  
  def onMessage(self, room, user, message):
    print(user.name+":"+message.body)
    if message.body.startswith("!a"): # Ugh, I should write something proper. Don't do this, folks!
      room.message("AAAAAAAAAAAAAA")

  
  def onFloodWarning(self, room):
    room.reconnect()
  
  def onPMMessage(self, pm, user, body):
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
