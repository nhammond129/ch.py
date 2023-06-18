ch.py
=====
Distributed under the terms of the GNU GPL. 

  A mostly abandoned event-based library for connecting to one or multiple Chatango rooms,
has support for several things including: messaging, message font, name color, deleting, banning,
recent history, two userlist modes, flagging, avoiding flood bans, detecting flags.

##### Planned Changes for future 1.4.* release
* Websocket Implementation of Room and PM
* IRC Implementation?
* Example of async implementation?

##### Planned Changes Before 1.4 release
###### Assuming I don't lose interest in doing the following - asl97
* Performance measuring and warning system


##### Changelog:
###### pre-1.4.0:
* Generalize handling of Room and PM into Conn like object - asl97
  - for easier to support other platform other than chatango - asl97
* Improve buffer performance by using bytearrays in place of bytes in places - asl97
  - Update the buffer in-place whenever possible
* General assumed performance improvement of miscellaneous functions  - asl97
* Close the bot when not connected to anything with no pending task or running thread via deferToThread
  - New task/room/output usually only get added due to input via select.select, existing tasks or deferToThread, they don't magically appear except when people mess with threading
    \
    Use the newly added flag as shown in example.py
    `disconnectOnEmptyConnAndTask = False`
    \
    for old behavior of pointlessly checking every 0.2 seconds by default \- asl97
* Use deterministic waiting for tasks in main loop - asl97
* No more joinThread nonsense, Fixes joinRoom to returns Room Object again
  - Seem to work fine when testing connecting to 15 rooms at once \- asl97
* Mostly cleaning up my mess and modernizing the code base - asl97
* Python 2 is no longer supported for good, it's EoL since 2020 - asl97

###### Newest available version 1.3 will be available on the v1.3 branch:
https://github.com/nhammond129/ch.py/tree/v1.3

###### Past Notice:
Recommended release for single core: [1.3.5](https://github.com/Nullspeaker/ch.py/releases/tag/v1.3.5)

WARNING: 1.3.5a and newer have some backward incompatible changes with 1.3.5 and older.

----

##### Past Readme
  I would like to note that I am not the original author, but merely the current maintainer.
The previous holder (pun unintended) unexpectedly dropped from his/her position without transferring
it and I just happened to be the one of the few who tried to pick up the pieces. ~~~~ nullspeaker

----
  Feature requests and bug reports should be directed to the issues page of the repository on Github. Please tag with the appropriate labels when doing so, as well. Contributions can be made by submitting a pull request that I or others can then merge. Link to the repository's page is at the bottom of this README. Email me (Nullspeaker) personally if you would like to request ability to merge your own commits to master without direct approval.

