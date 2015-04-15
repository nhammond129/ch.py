import urllib.request
import zlib, json, re

class updater:

  def findid(self):
    url = urllib.request.urlopen("http://st.chatango.com/cfg/nc/r.json")
    id = json.loads(url)['r']
    return id

  def findweights(self):
    url = urllib.request.urlopen("http://st.chatango.com/h5/gz/r%s/id.html"%self.ID)
    print("Found server weights.")
    if url.getheader('Content-Encoding')=="gzip":
      print("Server weights encoded with gzip, decoding...")
      data = zlib.decompress(url.read(),47)
    else:
      data=url.read()
    print("Processing server weights...")
    data = data.decode("utf-8","ignore").splitlines()
    tags = json.loads(data[7].split(" = ")[-1])
    weights = []
    for a,b in tags["sm"]:
      c = tags["sw"][b]
      weights.append([a,c])
    return weights

  def updatech(self):
    print("Writing server weights to ch.py...")
    with open("ch.py","r+") as ch:
      rdata=ch.read()
      wdata=re.sub("tsweights = .*","tsweights = %s"%str(self.weights),rdata)
      ch.seek(0)
      ch.write(wdata)
      ch.truncate()

  def run(self):
    print("Searching for latest server weights list...")
    self.ID = self.findid()
    print("Server weight ID found!")
    print("ID: r"+self.ID)
    self.weights = self.findweights()
    #print(self.weights)
    self.updatech()
    print("The server weights are now updated for ch.py, enjoy!")

main = updater()
main.run()

