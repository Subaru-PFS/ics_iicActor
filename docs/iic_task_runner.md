# IIC Task Runner
 
This document addresses IIC basic command flow mechanism.

IIC is *always* listening for incoming commands and is responsible to translate them into Tasks

What's a Task ?

a Task is a sequence/script which requires known PFS resources (dcb, sps, fps, ...etc).

* Any given resource can only be allocated to a single task.
* Tasks are concurrent and independent from each other.
* Tasks are running in their own Thread.

In practise, when an user/sequencer/gen2 send a command :

IIC translates this command in a Task with associated required resources.

* If the resources are available :
   * IIC allocates those ressources.
   * Task is accepted and shall be processed.
  
* If the resources are *not* available :
   * Task is rejected.

In both cases, command must returns immediately to prevent main thread to be blocked.

IIC replies to status with a list of individual Task status that reflect their completion.

Associated mhs keywords will be generated and displayed later on in a dedicated GUI/pannel

## Notes and questions

* Tasks should all be abortable ?
* Does a single command could lead to creation of several Tasks ?
