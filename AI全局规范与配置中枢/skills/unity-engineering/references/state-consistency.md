# Gameplay state consistency

## State ownership

- Keep aggregate state focused on data. Put initialization, restoration, validation, and deterministic generation in factories/services.
- Snapshot every mutable value needed to resume identically: board, inventory, progress, RNG stream state/counters, and pending domain state. Validate on restore. Add migration only when persisted data must survive; during active development prefer one current schema unless compatibility is requested.
- Recalculate derived score from pre/post state for nonstandard mutations instead of duplicating score constants in skill handlers.

## Deterministic RNG

- Start from the authoritative match/room seed. Derive independent named streams with stable salts: `Derive(rootSeed, subSeed, fixedSalt)`.
- Do not reuse one mutable RNG stream across unrelated features; call order then changes outcomes.
- Keep a meaningful `subSeed` when it identifies generated content or a round. Remove only redundant serialized derived seeds, not the derivation boundary.
- Persist a stream counter/state only when the stream advances. Stateless re-derivation is preferable when the operation has a stable index.
- Never use process-dependent hashes such as `string.GetHashCode()` as cross-device salts.

## Progress and scoring

- Count semantic events, not UI gestures. Separate inspection from committed use: a stock-button reveal may not count, while successfully moving that card out of stock/waste into active play can count.
- Have the domain operation return facts such as `cardRevealed`, `source`, and `success`; let progression and scoring consume those facts.
- Prevent duplicate counting, but let undo restore both progress and the counted-ID set so a different post-undo reveal can count correctly.

## Undo and skills

- Make each action atomic across board state, score, progress, inventory, RNG, and external effects.
- A fully undoable action needs a complete memento/inverse. Otherwise make it an irreversible checkpoint and clear earlier undo history.
- Never leave a non-undoable mutation outside the undo stack while allowing undo to cross it; that restores an incompatible earlier board.
- Failed actions consume nothing and do not clear undo history.
- After a checkpoint, later ordinary actions may be undone only back to that checkpoint.
- Timers, coroutines, visual previews, analytics, and network effects make skill undo expensive; prefer checkpoints unless product rules explicitly require full reversal.

## UI availability

- Store canonical availability separately from temporary locks.
- Compute interaction as `interactable = domainAvailable && !animationLock && !inputLock`.
- A delay coroutine must restore the computed state, never blindly set `interactable = true`.
