import ch
class TestBot(ch.RoomManager):
  def onConnect(self, room):
    print("Connected")
    
  def onReconnect(self, room):
    print("Reconnected")
    
  def onDisconnect(self, room):
    print("Disconnected")
  
  def onMessage(self, room, user, message):
    # Use with PsyfrBot framework? :3
    print(user.name+":"+message.body)
    if message.body.startswith("!a"):
      room.message("AAAAAAAAAAAAAA")

  
  def onFloodWarning(self, room):
    room.reconnect()
  
  def onPMMessage(self, pm, user, body):
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
