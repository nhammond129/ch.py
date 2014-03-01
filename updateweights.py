import urllib.request
import zlib, json, re
print("Searching for latest server weights list...")
url = urllib.request.urlopen("http://st.chatango.com/js/gz/emb_perc.js")
data=zlib.decompress(url.read(),47).decode(encoding='ascii',errors='ignore')
ID=re.search("r\\d+",data).group(0)
print("Server weight list found!")
print("ID: "+ID)
print("Retrieving server weights...")
url = urllib.request.urlopen("http://st.chatango.com/h5/gz/%s/id.html"%ID)
data = url.read()
print("Found server weights.")
if url.getheader('Content-Encoding')=="gzip":
  print("Server weights encoded with gzip, decoding...")
  data = zlib.decompress(data,47)
print("Processing server weights...")
data = data.decode("utf-8","ignore").splitlines()
tags = json.loads(data[6].split(" = ")[-1])
ids = []
for a,b in tags["sm"]:
  c = tags["sw"][b]
  ids.append([a,c])
print("Writing server weights to ch.py...")
with open("ch.py","r") as penis:
  data=penis.read()
  penis.close()
data=re.sub("tsweights = .*","tsweights = %s"%str(ids),data)
F=open("ch.py","w")
F.write(data)
F.close()
print("The server weights are now updated for ch.py, enjoy!")
