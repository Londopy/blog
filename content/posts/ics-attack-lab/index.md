---
title: "I Built an ICS Attack Lab, and My IDS Lied to Me"
# Other title options:
#   "12 Alarms for an Attack I Never Sent"
#   "OpenPLC, Modbus, and a Detector That Cried Wolf"
#   "Attacking a PLC I Built, Then Catching Myself Doing It"
date: 2026-11-19T09:00:00-08:00
draft: false
description: "In my last post I said the way to learn OT security is to build a PLC simulator and watch the traffic. So I did. I stood up OpenPLC as a deliberately-attackable PLC, wrote a Modbus attacker, and put Suricata in front of it to catch me. Then my detection rules confidently reported an attack that never happened while staying silent about the one that did. Here's the build, the two traps that ate an afternoon, and why detection you can't trust is worse than none."
tags: ["ot-security", "ics", "modbus", "openplc", "suricata", "cybersecurity", "homelab"]
author: "Londopy"
ShowToc: true
cover:
  image: "cover.png"
  alt: "A terminal tailing Suricata's alert log as a Modbus write and a read request are detected"
  relative: true
---

A few weeks ago I wrote [a beginner's map of OT and ICS security](../ot-ics-security/), and it ended with a piece of advice I hadn't actually followed yet: the fastest way to learn this field is to build a little plant you can break and fix safely. Run a PLC simulator, speak its protocol, watch the traffic.

So I built one. A real PLC runtime, a real industrial protocol, and an intrusion detector standing between them to catch me attacking it. The target is a PLC I control, on a network that touches nothing real.

The build was the easy part. The part worth writing about is the moment my own detector lied to me: it fired **twelve alarms for an attack I never sent**, and stayed completely silent about the one I did. That failure turned out to be the most educational thing in the whole lab.

## The plant

The whole thing is three roles, which is exactly how a real plant security problem is shaped:

- **The target** is [OpenPLC](https://openplcproject.com/), a free, open-source PLC runtime. It runs in a small Linux VM, serves a web HMI, and exposes a **Modbus/TCP** server on port 502, behaving like a cheap industrial controller.
- **The attacker** is the lab host. No fancy tooling: `nmap` for discovery and a small script that speaks raw Modbus.
- **The defender** is [Suricata](https://suricata.io/), an open-source IDS, sniffing the wire with rules I wrote to flag industrial traffic.

Everything lives on an isolated host-only network, `192.168.57.0/24`, with no route to the internet. The attacker is `192.168.57.1`; the PLC is `192.168.57.10`. The PLC reaches out through NAT once, to download packages, and is otherwise sealed off. Rule zero of this hobby: **never point any of this at something real.** Touching the wrong device on a live industrial network can stop a physical process, and it's illegal. A VM on an isolated subnet can't hurt anyone.

```
      host-only net  192.168.57.0/24  (isolated, no internet)
 ┌─────────────────────────┐            ┌──────────────────────────────┐
 │ attacker  192.168.57.1  │   Modbus   │ OpenPLC   192.168.57.10      │
 │  - nmap                 │ ──502────▶ │  - web HMI : 8080            │
 │  - raw Modbus script    │            │  - Modbus  : 502             │
 └─────────────────────────┘            │  - Suricata watches the NIC  │
                                        └──────────────────────────────┘
```

Before any of that worked, though, I lost an afternoon to two failures that had nothing to do with security and everything to do with how real this stuff gets the moment you leave the tutorial.

## Trap one: the compile that ran out of floor

OpenPLC's installer isn't a package download. It builds a chunk of its runtime from source, including [OpenDNP3](https://github.com/dnp3/opendnp3), a C++ library for another industrial protocol. On a fresh cloud image of the OS, the install got about three-quarters of the way through that compile and died:

```text
[ 75%] Building CXX object .../IOutstationApplication.cpp.o
fatal error: closing dependency file ...: No space left on device
OpenPLC was NOT installed!
```

No space left on device. The generic cloud image I'd started from ships a **3 GB** root disk, and a from-source C++ build of an entire protocol stack fills it. The fix is boring and worth knowing: grow the virtual disk, then let the guest grow the filesystem to match. On this VM the disk resize needed the machine powered off, and the cloud image's own first-boot tooling expanded the partition automatically on the next start. Ten gigabytes of headroom later, the compile finished.

The lesson isn't "disks fill up." It's that **industrial software assumes it owns the machine.** OpenPLC wants to compile protocol stacks, drop a systemd service, and bind privileged ports. Treat it like an appliance, not an app, and give it room.

## Trap two: the clone that couldn't

With disk to spare, I re-ran the install and it failed again, differently. Every attempt to re-clone OpenPLC's source landed in a directory that was supposed to be empty but wasn't, and `git` refused.

The culprit was a single leftover folder: a Python virtual environment the *first*, failed install had created **as root**. My cleanup step deleted the source tree as my normal user, which silently skipped the root-owned folder it wasn't allowed to touch. So every re-clone found a non-empty directory and bailed, and every log I read was from a half-built tree.

```text
$ rm -rf OpenPLC_v3        # runs as me, can't remove root's files
$ git clone ... OpenPLC_v3
fatal: destination path 'OpenPLC_v3' already exists and is not an empty directory
```

One `sudo rm -rf` and the loop broke. It's a dumb bug, but it's the exact flavor of dumb bug that eats an hour, because the error (`git` complaining about a directory) points nowhere near the cause (a permissions mismatch from a crash two steps earlier). Worth internalizing: when a "clean" step runs as one user and the mess was made by another, the clean is a no-op and nothing tells you.

## Attacking the PLC

With OpenPLC installed, I logged into its web HMI, loaded a program, and hit **Start PLC**. Port 502 opened, and the lab had a live Modbus target.

Here's the thing about Modbus that makes it such a clean teaching tool: **it has no authentication.** None. If you can reach port 502, you can read and write the controller's memory. No login, no token, no handshake. The protocol was designed in 1979 for a trusted serial loop, and the TCP version just wrapped it in a header.

My attacker is a short script that builds Modbus frames by hand. First, read some coils (Modbus's name for single-bit outputs):

```text
[enumerate] reading the PLC's memory map
  coils[0..15]        -> 00 00
  holding_regs[0..7]  -> 00 00 00 00 00 00 00 00
```

Then the part that matters. One function code, `0x05`, "write single coil," and the PLC's state is mine:

```text
[write] unauthorized state change
  before: coil 0 = 0
  write coil 0 = ON   -> ack
  after:  coil 0 = 1
```

That `0 -> 1` is the whole point of OT security in one line. On a real controller, coil 0 isn't an abstraction; it's wired to something. A relay, a pump, a valve, a breaker. I didn't exploit a bug or crack a password. I asked, politely, over the network, and the PLC did it, because asking is the entire protocol. This is why the field treats the network boundary as the security boundary: the devices behind it have no other defense.

## Putting a detector in front of it

If you can't authenticate the protocol, you watch it. That's the job Suricata does here: sit on the wire, parse what goes by, and alert on things that shouldn't happen, like a write to a controller from somewhere it shouldn't come from.

My first pass at rules was the obvious one. A Modbus function code sits at a fixed spot in the packet, seven bytes in, so I wrote content rules that match that byte:

```text
alert tcp any any -> any 502 (msg:"Modbus Write Single Coil (FC05)";
    flow:to_server,established; content:"|05|"; offset:7; depth:8; sid:1000005;)
```

One rule per write function code, plus one for the connection itself. I ran the full attack, tailed the alert log, and it lit up. Writes detected, connection detected. Looked great.

It was not great.

## The lie

I counted the alerts by type, and two numbers were wrong in opposite directions.

| Alert type | What my rules reported |
|------------|------------------------|
| Modbus connection | 33 |
| Write Single Coil (FC05) | 44 |
| **Write Multiple Registers (FC16)** | **12** |
| **Read requests (recon)** | **0** |

Start with the 12. My attacker **never sends** a "write multiple registers" command. That function code, `0x10`, appears nowhere in my attack. So where did twelve alarms come from?

From a *read*. One of my attack steps is a quiet reconnaissance sweep that reads registers starting at **address 16** — and 16 is `0x10` in hex, the same byte as the write-multiple-registers function code. My crude rule matched that byte wherever it fell in the packet, so a harmless read of address 16 tripped a "someone is rewriting the controller's registers" alarm, twelve times.

Now the zero. That same recon sweep, all reads, produced **no read alerts at all**, because I hadn't written a rule for reads. An attacker mapping out my PLC's entire memory, the exact quiet step that precedes a real attack, was invisible. The only trace it left was buried under twelve false alarms about a write that never happened.

So my detector did both failure modes at once. It **cried wolf** about an attack I didn't launch, and it **slept through** the reconnaissance I did. In an office-IT setting that's an annoying tuning problem. In OT, where an operator might have seconds to decide whether a "controller rewrite" alert is real while a process runs away from them, a detector that fabricates that exact alert from a routine read is worse than no detector at all. It spends the one thing you can't buy back during an incident: trust in the alarm.

## The fix: stop poking at bytes

The problem was that I was pattern-matching raw bytes without understanding them. The byte `0x10` means "write multiple registers" **only** when it's the function code, not when it's an address, or a value, or a byte count that happens to equal sixteen. Telling those apart requires actually parsing Modbus, not grepping for a number.

Suricata can do that. It ships a real Modbus protocol parser; it just wasn't turned on. Once enabled, I could throw away the byte-poking and write rules against the *decoded* protocol:

```text
# before: match byte 7 and hope
content:"|05|"; offset:7; depth:8;

# after: match the actual, parsed function code
modbus: function 5;
```

And, finally, a rule for the thing I'd missed entirely:

```text
alert tcp any any -> any 502 (msg:"Modbus READ request (recon/monitor)";
    modbus: access read; sid:1000100;)
```

Same attack, same wire, new rules:

| Alert type | Byte rules | Protocol parser |
|------------|-----------:|----------------:|
| Connection | 33 | 33 |
| **Read requests (recon)** | **0** | **11** |
| Write Single Coil (FC05) | 44 | **21** |
| Write Single Register (FC06) | 6 | **1** |
| **Write Multiple Registers (FC16)** | **12** | **0** |

Every number got honest. The twelve phantom write alarms went to zero, because the parser knows address 16 isn't function 16. The invisible reconnaissance went from zero to eleven, because now there's a rule that understands "read." And the write counts dropped to exactly what I actually sent, one register write, twenty-one coil writes, no more double-counting a retransmitted packet as two attacks.

## What the lab actually taught me

I set out to learn how to attack and defend a PLC. I did, and the attack half was almost anticlimactic: Modbus has no authentication, so "attacking" it is just using it. The defense half was where the real lesson hid, and it wasn't the one I expected.

**Detection quality is a thing you can measure, and bad detection has two failure modes that look nothing alike.** Mine over-fired and under-fired at the same time, from the same lazy shortcut. A false positive isn't just noise; during an incident it's an active lie that competes with the real signal for an operator's attention. A false negative is a quiet hole an attacker walks through. The only fix was to make the detector actually understand the protocol it was watching instead of squinting at its bytes.

There's a caveat I'll be honest about: in my lab the IDS sniffs the PLC's own network interface, which is a convenient shortcut, not how a real plant does it. In the field the sensor sits on a tap or a span port, watching the segment from the side, so a compromised controller can't blind its own watcher. That's the next thing I want to rebuild properly.

None of this took special hardware. A VM, a free PLC runtime, a free IDS, and a hundred lines of script. If my [last post](../ot-ics-security/) made you curious about OT security, this is the afternoon I promised would teach you more than a week of reading. The protocol really does just do what you tell it. The interesting question is who's watching when you do, and whether you can believe what they tell you.
