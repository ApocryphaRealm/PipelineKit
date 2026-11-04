# Machine health - the design, without one person's PC

The original pipeline runs a gate before every build and every game launch, so an agent working unattended does not
pile heavy work on a machine that is already busy, hot or out of room. The script and its numbers belong to that PC and
are not in the kit. This is why it exists, what it reads and what was learned; a person who wants one can have their
agent write it for their own machine.

## Three verdicts

- **GO** - start the work.
- **WAIT** - a condition that passes with time (CPU busy, memory low, disk queue long, GPU busy, hot). Check again later.
- **STOP** - time does not fix it, or something is already running that must not run twice (out of commit, out of disk
  space, a build in flight, the game or Mod Organizer already open).

## What to read, and the traps

- **Measure before setting a threshold.** Time a real build and a real game session on the machine, and set each number
  from that. A number copied from another PC is either always refusing or never refusing.
- **CPU and memory.** The commit charge matters more than the free memory: above about 90% Windows pages hard, and near
  100% a build fails outright.
- **GPU: the busiest engine, not the sum.** Summing the engines of a GPU's counters reads over 100% and means nothing.
- **Temperature has two states, and the gate always says which.** Windows itself reports nothing usable, so a sensor
  reader has to be running. If it is not, the gate says the temperature is unknown; it never reports that as cool, and it
  never starts the reader on its own.
- **Ignore sensors that are stuck or do not throttle.** Gate on the CPU die and the GPU core. Mainboard sensors can read
  high on an idle machine, and a gate that uses "the hottest sensor" refuses forever while looking principled.
- **Two GPUs.** An integrated GPU sitting at 0 W is not the card doing the work: pick the discrete one by what it reports.
- **Removable drives** stay out of disk checks.

## What it cannot protect against

A gate only reads the moment it runs. A heavy job started after the check, or a fault in the hardware or its driver, gets
past it. If a game or a GPU driver starts failing, record what the event log says and when, and fix that separately.
