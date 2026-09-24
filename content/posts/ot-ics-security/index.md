---
title: "A Beginner's Map of OT and ICS Security"
date: 2026-09-24T12:00:00-07:00
draft: true
description: "Power grids, water plants, and factories run on computers that play by different rules than office IT. Here's a map of the field for anyone curious about getting into it, from someone heading that way."
tags: ["ot-security", "ics", "scada", "cybersecurity", "careers"]
author: "Londopy"
ShowToc: true
cover:
  image: "cover.png"
  alt: "A terminal card with the post title and description"
  relative: true
---

When most people think of cybersecurity, they picture laptops, servers, and stolen passwords. But some of the most important computers in the world control physical things: dams, power grids, water treatment, pipelines, and factories.

That world is called **OT** (operational technology) and **ICS** (industrial control systems), and it's where I want to build my career. This post is the map I wish I'd had when I started learning.

## Some vocabulary

- **OT:** hardware and software that monitors or controls physical processes.
- **ICS:** the control systems themselves.
- **SCADA:** supervisory systems that monitor and control equipment spread over large areas, like a pipeline or a power grid.
- **PLC:** programmable logic controller. A rugged little computer that reads sensors and drives motors, valves, and breakers in a loop, for years at a time.
- **HMI:** human-machine interface. The screen an operator uses to watch and control the process.
- **Safety instrumented system (SIS):** an independent system whose only job is to shut things down safely when something goes dangerously wrong.

## Why OT is different from IT

**The priorities are flipped.** IT security talks about confidentiality, integrity, and availability, usually in that order. In OT, **safety** comes first, then availability. A leaked spreadsheet is bad. A chlorine pump running wild or a turbine overspeeding can hurt people.

**You can't just patch.** A PLC might run a chemical process 24/7 for 20 years. Rebooting it for an update might mean shutting down a plant. Some devices can't be updated at all.

**Old protocols, no security.** Many industrial protocols were designed when networks were assumed to be isolated and trusted. **Modbus**, one of the most common, has no authentication at all: if you can reach the device on the network, you can send it commands. Others you'll hear about: **DNP3** (common in power and water), **EtherNet/IP**, **PROFINET**, **IEC 61850** (substations), and the more modern **OPC UA**, which does support security.

**"Air-gapped" usually isn't.** Plants were supposed to be isolated from the internet. In practice, remote access, vendor connections, and business reporting have connected many of them.

## The Purdue Model

The classic way to picture an industrial network is the **Purdue Model**, which stacks it into levels:

- **Level 0:** the physical process: sensors, actuators, motors, valves
- **Level 1:** controllers (PLCs) that directly control Level 0
- **Level 2:** supervisory control: HMIs and SCADA
- **Level 3:** site operations: historians (process data databases) and plant-wide systems
- **Level 3.5:** the **DMZ** between the plant and the business network
- **Levels 4 and 5:** business IT and enterprise systems

The core idea: traffic between levels should be tightly controlled, and nothing on the internet should talk directly to Levels 0 through 2. It's a simplification, and modern plants with cloud and remote connections blur it, but it's still the shared language of the field.

## Incidents everyone in the field knows

- **Stuxnet (discovered 2010):** malware that sabotaged uranium enrichment centrifuges by manipulating PLCs while showing operators normal readings. It proved code could cause physical destruction.
- **Ukraine power grid (2015 and 2016):** attackers cut power to hundreds of thousands of people. The 2016 attack used malware (Industroyer, also called CrashOverride) that spoke grid protocols directly.
- **Triton / Trisis (2017):** malware that targeted a petrochemical plant's **safety** system, the last line of defense against disaster.
- **Colonial Pipeline (2021):** ransomware hit the company's **IT** network, and the pipeline was shut down as a precaution. OT doesn't have to be hacked directly to be affected.

## Standards and frameworks

- **ISA/IEC 62443:** the main family of standards for industrial cybersecurity.
- **NIST SP 800-82:** US guidance on securing OT.
- **NERC CIP:** mandatory security standards for the North American bulk power grid.

You don't need to memorize these, but you'll see them everywhere.

## How to start learning (legally and safely)

**Never scan or probe real industrial systems you don't own.** Touching the wrong device can disrupt a real process, and it's illegal. Build a lab instead.

- **Free training:** CISA offers free online ICS security training.
- **Simulate a plant:** OpenPLC is a free, open-source PLC you can run on a computer or a Raspberry Pi, and program in the same languages real PLCs use.
- **Real hardware:** entry-level PLCs are surprisingly affordable. [TODO: add your own lab once it exists]
- **Watch traffic:** capture Modbus or other industrial protocols with Wireshark and see how they work. Tools like Zeek and Suricata can monitor OT traffic for anomalies.
- **Community:** the ICS Village at security conferences, and SANS's free ICS resources and webcasts.

## How people get into the field

One thing surprised me: many OT security professionals come from **engineering and controls backgrounds**, not IT security. It's often easier to teach a controls engineer threat modeling than to teach a security analyst how a plant actually runs, how a turbine behaves, or why you never casually reboot a PLC.

That's my plan: start in the field on real industrial systems, then move into securing them. [TODO: expand with your own path, at whatever level of detail you're comfortable sharing publicly]

## Closing thought

OT security sits where software meets steel. It moves slower than IT, the stakes are physical, and the field needs more people who understand both sides. If any of this made you curious, start with a PLC simulator and a packet capture. You'll learn more in an afternoon than from a week of reading.
