"""################################################################
# File: updateweights.py
# Title: Chatango Library Weights Updater
# Original Author:
#  Nullspeaker <import codecs;codecs.encode('aunzzbaq129@tznvy.pbz','rot_13')>
# Current Maintainers and Contributors:
#  asl97 <asl97@outlook.com>
# Version: 2
# Description:
#  A python script to update the server weights within ch_weights.py
# Contact Info:
#  Any question, comment, or suggestion should be directed to the current
#  maintainers and contributors, located at:
#   https://github.com/Nullspeaker/ch.py
#
#  Where a more satisfactory response to all bug reports
#  (which can be made on he issues page) and other statements can be garnered.
#
#  For things not specific or in direct reference to this library, 'ch.py',
#  a direct response can be filed to the individual persons listed above
#  as 'Current Maintainer sand Contributors.'
################################################################"""

import urllib.request
import zlib
import json
import re


def find_url() -> str:
    """Locate the current server weights location"""
    request = urllib.request.urlopen("https://st.chatango.com/cfg/nc/r.json")
    data = request.read()
    print("Server weight list found!")
    if request.getheader('Content-Encoding') == "gzip":
        print("Server weights encoded with gzip, decoding...")
        data = zlib.decompress(data, 47)

    return f"http://st.chatango.com/h5/gz/r{json.loads(data)['r']}/id.html"


def find_weights(url: str):
    """Extract the server weights from provided url"""
    request = urllib.request.urlopen(url)
    data = request.read()
    print("Found server weights.")
    if request.getheader('Content-Encoding') == "gzip":
        print("Server weights encoded with gzip, decoding...")
        data = zlib.decompress(data, 47)

    print("Processing server weights...")
    for line in data.decode("utf-8", "ignore").splitlines():
        if '_chatangoTagserver' in line:
            tags = json.loads(line.split(" = ")[-1])
            weights: list[tuple[str, int]] = []
            for server_id, server_name in tags["sm"]:
                server_weight = tags["sw"][server_name]
                weights.append((server_id, server_weight))
            return weights


def update_ch_weights(weights: list[tuple[str, int]]):
    """Open the file ch.py and override the existing weights"""
    with open("ch_weights.py", "r+", encoding='utf-8') as ch_file:
        rdata = ch_file.read()
        var = "tsweights: list[tuple[str, int]] = "
        wdata = re.sub(var + ".*", var + str(weights), rdata)
        ch_file.seek(0)
        ch_file.write(wdata)
        ch_file.truncate()


def run():
    """Run the script to update ch.py"""
    print("Searching for latest server weights list...")
    url = find_url()
    print("URL: "+url)
    print("Retrieving server weights...")
    weights = find_weights(url)
    if weights:
        print("Writing server weights to ch_weights.py...")
        update_ch_weights(weights)
        print("The server weights are now updated for ch_weights.py, enjoy!")
    else:
        raise Exception("Unable to locate the server weights")


if __name__ == "__main__":
    run()
