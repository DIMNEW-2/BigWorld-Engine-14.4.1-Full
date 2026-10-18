# BigWorld (TM) Open-Source Edition

This repository contains BigWorld Open-Source Edition (OSE) that is comprised of server, 
client and tools components which are used together to build massively multiplayer games 
and virtual worlds.

BigWorld OSE key features:

 - Load-Balancing
 - Scalability
 - Fault Tolerance

For more details refer to [BigWorld Technology Server Whitepaper](<docs/pdf/BigWorld Technology Server Whitepaper.pdf>)

Project status:

  - **Technology stack**: C/C++, Python, CentOS
  - **Status**:  Stable

## Dependencies

To start with this project you will need at least the following software:

 - Windows 10 with WSL2 and Hyper-V manager enabled.
 - CentOS 7
 - Microsoft Visual Studio 2019-2022
 - Vagrant
 - Docker

## Installation & Configuration

Server installation instructions are located in a separate [Server Installation Guide](<docs/pdf/Server Installation Guide.pdf>) document.
Server build instructions can be found in [Server Build Guide](<docs/pdf/Server Build Guide.pdf>).

## Experimental offline battle-server sample

An opt-in BigWorld `ServiceApp` prototype with server-authoritative lobby,
movement, firing, bots, capture and battle results is available in
[`game/res/tankarena`](game/res/tankarena/README.md). It is not a drop-in WoT
0.9.22 server or a compatible replacement for the separate LAN protocol used
by the referenced offline-battles project. Its Python 3 rule/resource tests can
be run with `python3 -m unittest discover -s tests/tankarena -v`.

## Getting help

If you have questions, concerns, bug reports, etc, please file an issue in this repository's Issue Tracker.

## Getting involved

Instructions on _how_ to contribute can be found in [CONTRIBUTING](CONTRIBUTING.md) document.
