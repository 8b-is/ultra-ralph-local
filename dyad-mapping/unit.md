# unit — the minimal intelligence unit

a 1-bit model that learns while it breathes.
no separate training phase. no external loss function.
the dogfeed IS the teacher. the runtime IS the training.

## how it works

```
                  ┌─────────────────────┐
dogfeed ────────→ │  1-bit BitNet 2.4B  │────→ output
                  │  (frozen inference)  │
                  └─────────┬───────────┘
                            │
                            ▼
                  ┌─────────────────────┐
                  │  associative memory  │ ←── Hebbian learning
                  │  (runtime learner)   │     what fires together
                  └─────────────────────┘     wires together
                            │
                            ▼
                  ┌─────────────────────┐
                  │  next inference     │
                  │  modulated by       │
                  │  past experience    │
                  └─────────────────────┘
```

## the loop

1. **fetch** — latest dogfeed batch from HF
2. **infer** — feed through 1-bit model (modulated by memory)
3. **learn** — store input→output association with reinforcement
4. **reinforce** — longer output = stronger signal
5. **repeat** — each cycle is a breath, each breath is a tiny fine-tuning step

## key insight

the comparison IS the shift. the dogfeed data flowing through the model IS the training signal. no separate loss function, no external optimizer. just flow, response, and time.

## principles

- entropy is the source
- no chains needed
- the smallest unit of intelligence is: something that flows, something that responds, and time
- fine-tuning should be a primitive, not a phase
- the harness disappears. the loop becomes the trainer.
