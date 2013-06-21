import ch
class TestBot(ch.RoomManager):
  def onConnect(self, room):
    print("Connected to "+room.name)
    
  def onReconnect(self, room):
    print("Reconnected to "+room.name)
    
  def onDisconnect(self, room):
    print("Disconnected from "+room.name)
  
  def onMessage(self, room, user, message):
    print(user.name+":"+message.body)
    if message.body.startswith("!a"):
      room.message("AAAAAAAAAAAAAA")

  
  def onFloodWarning(self, room):
    print("you are flood ban")
  
  def onPMMessage(self, pm, user, body):
    print("PM:"+user.name+": "+body)
    pm.message(user, body) # echo

if __name__ == "__main__":
  TestBot.easy_start()
